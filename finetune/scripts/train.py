import os

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import gc
import shutil
import torch
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from transformers import (
    DataCollatorForSeq2Seq,
    EarlyStoppingCallback,
)
from datasets import load_dataset

print(torch.__version__, torch.version.cuda, torch.cuda.is_available())
print(torch.cuda.get_device_name(0))

cache_dir = "/kaggle/working/unsloth_compiled_cache"
if os.path.isdir(cache_dir):
    shutil.rmtree(cache_dir)
    print("Cleared stale Unsloth compiled cache.")

MAX_SEQ_LENGTH = 2048
MODEL_NAME = "unsloth/Qwen3-4B-Instruct-2507"

TRAIN_PATH = "/kaggle/input/datasets/username/dsa-sys-dataset/train.jsonl"
EVAL_PATH = "/kaggle/input/datasets/username/dsa-sys-dataset/eval.jsonl"

ADAPTER_OUT = "/kaggle/working/adapter"
CHECKPOINT_DIR = "/kaggle/working/checkpoints"


print("Loading model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=False,
)
print(f"VRAM after load: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing=True,
    random_state=42,
)
gc.collect()
torch.cuda.empty_cache()
torch.cuda.reset_peak_memory_stats()
print(f"VRAM after peft + cache clear: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
print(f"Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.3f}%)")

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

print("Loading dataset...")
train_dataset = load_dataset("json", data_files=TRAIN_PATH, split="train")
eval_dataset = load_dataset("json", data_files=EVAL_PATH, split="train")


def tokenize_with_prompt_masking(examples, tokenizer):
    all_input_ids = []
    all_labels = []

    im_end_ids = tokenizer("<|im_end|>", add_special_tokens=False)["input_ids"]

    for conv in examples["conversations"]:
        # Tokenize the WHOLE conversation once.
        full_text = tokenizer.apply_chat_template(
            conv, tokenize=False, add_generation_prompt=False,
        )
        full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]

        labels = [-100] * len(full_ids)

        for turn in conv:
            if turn["role"] != "assistant":
                continue
            content_ids = tokenizer(turn["content"], add_special_tokens=False)["input_ids"] + im_end_ids
            if not content_ids:
                continue
            n = len(content_ids)
            for start in range(len(full_ids) - n + 1):
                if full_ids[start:start + n] == content_ids:
                    for j in range(start, start + n):
                        labels[j] = full_ids[j]
                    break

        all_input_ids.append(full_ids[:MAX_SEQ_LENGTH])
        all_labels.append(labels[:MAX_SEQ_LENGTH])

    return {"input_ids": all_input_ids, "labels": all_labels}


train_dataset = train_dataset.map(
    lambda ex: tokenize_with_prompt_masking(ex, tokenizer),
    batched=True, remove_columns=["conversations", "topic"],
)
eval_dataset = eval_dataset.map(
    lambda ex: tokenize_with_prompt_masking(ex, tokenizer),
    batched=True, remove_columns=["conversations", "topic"],
)

print(f"Train: {len(train_dataset)} | Eval: {len(eval_dataset)}")

sample_labels = train_dataset[0]["labels"]
masked_count = sum(1 for l in sample_labels if l == -100)
real_count = len(sample_labels) - masked_count
print(f"Sanity check: {masked_count} masked tokens, {real_count} real label tokens "
      f"in first example.")


im_end_id = tokenizer("<|im_end|>", add_special_tokens=False)["input_ids"][0]
real_labels_first_example = [l for l in sample_labels if l != -100]

truncated = sum(1 for ex in train_dataset if len(ex["input_ids"]) >= MAX_SEQ_LENGTH)
if truncated:
    print(f"WARNING: {truncated}/{len(train_dataset)} train examples hit "
          f"MAX_SEQ_LENGTH={MAX_SEQ_LENGTH} and were truncated.")

data_collator = DataCollatorForSeq2Seq(tokenizer, model=model, padding=True, pad_to_multiple_of=8)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    data_collator=data_collator,
    max_seq_length=MAX_SEQ_LENGTH,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    args=SFTConfig(
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        per_device_eval_batch_size=1,
        warmup_steps=20,
        num_train_epochs=5,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        optim="adamw_8bit",
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=50,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        output_dir=CHECKPOINT_DIR,
        report_to="none",
        remove_unused_columns=False,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        average_tokens_across_devices=False,
    ),
)

print("Starting training...")
trainer.train()

print(f"Saving final LoRA adapter to {ADAPTER_OUT}")
model.save_pretrained(ADAPTER_OUT)
tokenizer.save_pretrained(ADAPTER_OUT)
print("Training done. Best checkpoint was loaded automatically (load_best_model_at_end=True).")