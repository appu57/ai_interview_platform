# os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
# import gc
# import shutil
# import torch
# import os
# from unsloth import FastLanguageModel
# from trl import SFTTrainer, SFTConfig
# from transformers import (
#     DataCollatorForSeq2Seq,
#     EarlyStoppingCallback,
# )
# from datasets import load_dataset
# from finetune.scripts.logging_utils import get_logger

# print(torch.__version__, torch.version.cuda, torch.cuda.is_available())
# print(torch.cuda.get_device_name(0))

# log = get_logger("mockai.pipeline.train")

# # Training was executed on Kaggle. If you are using a smaller GPU, consider reducing the batch size or using gradient accumulation and max_seq_length. You can also use a smaller model variant (e.g., Qwen-3B) for training.
# cache_dir = "/kaggle/working/unsloth_compiled_cache"
# if os.path.isdir(cache_dir):
#     shutil.rmtree(cache_dir)
#     print("Cleared stale Unsloth compiled cache.")

# MAX_SEQ_LENGTH = 2048
# MODEL_NAME = "unsloth/Qwen3-4B-Instruct-2507"

# TRAIN_PATH = "/kaggle/input/datasets/username/dsa-sys-dataset/train.jsonl"
# EVAL_PATH = "/kaggle/input/datasets/username/dsa-sys-dataset/eval.jsonl"

# ADAPTER_OUT = "/kaggle/working/adapter"
# CHECKPOINT_DIR = "/kaggle/working/checkpoints"


# print("Loading model...")
# model, tokenizer = FastLanguageModel.from_pretrained(
#     model_name=MODEL_NAME,
#     max_seq_length=MAX_SEQ_LENGTH,
#     dtype=None,
#     load_in_4bit=False,
# )
# print(f"VRAM after load: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

# model = FastLanguageModel.get_peft_model(
#     model,
#     r=16,
#     target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
#                     "gate_proj", "up_proj", "down_proj"],
#     lora_alpha=32,
#     lora_dropout=0,
#     bias="none",
#     use_gradient_checkpointing=True,
#     random_state=42,
# )
# gc.collect()
# torch.cuda.empty_cache()
# torch.cuda.reset_peak_memory_stats()
# print(f"VRAM after peft + cache clear: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

# trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
# total = sum(p.numel() for p in model.parameters())
# print(f"Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.3f}%)")

# if tokenizer.pad_token is None:
#     tokenizer.pad_token = tokenizer.eos_token
# tokenizer.padding_side = "right"

# print("Loading dataset...")
# log.info(f"Loading dataset from {TRAIN_PATH} / {EVAL_PATH}...")
# if not os.path.isfile(TRAIN_PATH):
#     raise FileNotFoundError(f"MOCKAI_TRAIN_PATH does not exist: {TRAIN_PATH}")
# if not os.path.isfile(EVAL_PATH):
#     raise FileNotFoundError(f"MOCKAI_EVAL_PATH does not exist: {EVAL_PATH}")

# train_dataset = load_dataset("json", data_files=TRAIN_PATH, split="train")
# eval_dataset = load_dataset("json", data_files=EVAL_PATH, split="train")

# if len(train_dataset) == 0:
#     raise ValueError(f"Train dataset at {TRAIN_PATH} is empty.")
# if len(eval_dataset) == 0:
#     raise ValueError(f"Eval dataset at {EVAL_PATH} is empty.")

# MAX_UNMATCHED_TURN_FRACTION = 0.05  # 5% of assistant turns failing prompt-mask alignment is considered too high
# def tokenize_with_prompt_masking(examples, tokenizer):
#     all_input_ids = []
#     all_labels = []

#     im_end_ids = tokenizer("<|im_end|>", add_special_tokens=False)["input_ids"]
#     total_assistant_turns = 0
#     unmatched_turns = 0

#     for conv in examples["conversations"]:
#         full_text = tokenizer.apply_chat_template(
#             conv, tokenize=False, add_generation_prompt=False,
#         )
#         full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]

#         labels = [-100] * len(full_ids)

#         for turn in conv:
#             if turn["role"] != "assistant":
#                 continue
#             total_assistant_turns += 1
#             content_ids = tokenizer(turn["content"], add_special_tokens=False)["input_ids"] + im_end_ids
#             if not content_ids:
#                 continue
#             n = len(content_ids)
#             for start in range(len(full_ids) - n + 1):
#                 if full_ids[start:start + n] == content_ids:
#                     for j in range(start, start + n):
#                         labels[j] = full_ids[j]
#                     break
#                 else:
#                     unmatched_turns += 1

#         all_input_ids.append(full_ids[:MAX_SEQ_LENGTH])
#         all_labels.append(labels[:MAX_SEQ_LENGTH])
#         if unmatched_turns:
#             fraction = unmatched_turns / max(total_assistant_turns, 1)
#             log.warning(
#                 f"{unmatched_turns}/{total_assistant_turns} assistant turn(s) in this batch "
#                 f"({fraction:.1%}) could not be located inside their conversation's token ids "
#                 f"and were left fully masked (no training signal)."
#             )
#             if fraction > MAX_UNMATCHED_TURN_FRACTION:
#                 raise RuntimeError(
#                     f"{fraction:.1%} of assistant turns in this batch failed prompt-mask "
#                     f"alignment, above the MOCKAI_MAX_UNMATCHED_TURN_FRACTION threshold "
#                     f"({MAX_UNMATCHED_TURN_FRACTION:.1%}). Aborting rather than training on "
#                     f"a batch that's lost most of its signal -- check tokenizer/encoding "
#                     f"consistency in the dataset."
#                 )


#     return {"input_ids": all_input_ids, "labels": all_labels}


# train_dataset = train_dataset.map(
#     lambda ex: tokenize_with_prompt_masking(ex, tokenizer),
#     batched=True, remove_columns=["conversations", "topic"],
# )
# eval_dataset = eval_dataset.map(
#     lambda ex: tokenize_with_prompt_masking(ex, tokenizer),
#     batched=True, remove_columns=["conversations", "topic"],
# )

# log.info(f"Train: {len(train_dataset)} | Eval: {len(eval_dataset)}")

# sample_labels = train_dataset[0]["labels"]
# masked_count = sum(1 for l in sample_labels if l == -100)
# real_count = len(sample_labels) - masked_count
# log.info(f"Sanity check: {masked_count} masked tokens, {real_count} real label tokens "
#       f"in first example.")


# im_end_id = tokenizer("<|im_end|>", add_special_tokens=False)["input_ids"][0]
# real_labels_first_example = [l for l in sample_labels if l != -100]

# truncated = sum(1 for ex in train_dataset if len(ex["input_ids"]) >= MAX_SEQ_LENGTH)
# if truncated:
#     log.warning(f"WARNING: {truncated}/{len(train_dataset)} train examples hit "
#           f"MAX_SEQ_LENGTH={MAX_SEQ_LENGTH} and were truncated.")

# data_collator = DataCollatorForSeq2Seq(tokenizer, model=model, padding=True, pad_to_multiple_of=8)

# trainer = SFTTrainer(
#     model=model,
#     tokenizer=tokenizer,
#     train_dataset=train_dataset,
#     eval_dataset=eval_dataset,
#     data_collator=data_collator,
#     max_seq_length=MAX_SEQ_LENGTH,
#     callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
#     args=SFTConfig(
#         per_device_train_batch_size=1,
#         gradient_accumulation_steps=16,
#         per_device_eval_batch_size=1,
#         warmup_steps=20,
#         num_train_epochs=5,
#         learning_rate=2e-4,
#         fp16=not torch.cuda.is_bf16_supported(),
#         bf16=torch.cuda.is_bf16_supported(),
#         optim="adamw_8bit",
#         logging_steps=10,
#         eval_strategy="steps",
#         eval_steps=50,
#         save_strategy="steps",
#         save_steps=50,
#         save_total_limit=2,
#         load_best_model_at_end=True,
#         metric_for_best_model="eval_loss",
#         greater_is_better=False,
#         output_dir=CHECKPOINT_DIR,
#         report_to="none",
#         remove_unused_columns=False,
#         gradient_checkpointing=True,
#         gradient_checkpointing_kwargs={"use_reentrant": False},
#         average_tokens_across_devices=False,
#     ),
# )

# print("Starting training...")
# trainer.train()

# print(f"Saving final LoRA adapter to {ADAPTER_OUT}")
# model.save_pretrained(ADAPTER_OUT)
# tokenizer.save_pretrained(ADAPTER_OUT)
# print("Training done. Best checkpoint was loaded automatically (load_best_model_at_end=True).")


import os
import gc
import torch
import shutil

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

from datasets import load_dataset
from unsloth import FastLanguageModel, is_bfloat16_supported
from unsloth.chat_templates import get_chat_template, train_on_responses_only
from trl import SFTTrainer, SFTConfig
from transformers import DataCollatorForSeq2Seq
from finetune.scripts.logging_utils import get_logger

log = get_logger("mockai.pipeline.train")

print(f"PyTorch Version: {torch.__version__} | CUDA Version: {torch.version.cuda} | CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Device: {torch.cuda.get_device_name(0)}")

# Clear stale caches
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

# Configure ChatML Template for Qwen
tokenizer = get_chat_template(
    tokenizer,
    chat_template="qwen-2.5", # Works seamlessly with Qwen3-Instruct models
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_alpha=32,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing=True,
    random_state=42,
)

gc.collect()
torch.cuda.empty_cache()
torch.cuda.reset_peak_memory_stats()
print(f"VRAM after PEFT setup: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
print(f"Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.3f}%)")

print("Loading dataset...")
log.info(f"Loading dataset from {TRAIN_PATH} / {EVAL_PATH}...")
if not os.path.isfile(TRAIN_PATH):
    raise FileNotFoundError(f"TRAIN_PATH does not exist: {TRAIN_PATH}")
if not os.path.isfile(EVAL_PATH):
    raise FileNotFoundError(f"EVAL_PATH does not exist: {EVAL_PATH}")

train_dataset = load_dataset("json", data_files=TRAIN_PATH, split="train")
eval_dataset = load_dataset("json", data_files=EVAL_PATH, split="train")

def format_prompts(examples):
    texts = [
        tokenizer.apply_chat_template(
            conv, 
            tokenize=False, 
            add_generation_prompt=False
        ) for conv in examples["conversations"]
    ]
    return {"text": texts}

train_dataset = train_dataset.map(format_prompts, batched=True)
eval_dataset = eval_dataset.map(format_prompts, batched=True)

log.info(f"Train samples: {len(train_dataset)} | Eval samples: {len(eval_dataset)}")

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=2,
    packing=False, # Set to False when performing strict response-only loss masking
    args=SFTConfig(
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        per_device_eval_batch_size=1,
        warmup_steps=20,
        num_train_epochs=5,
        learning_rate=2e-4,
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
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
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    ),
)

# Apply Loss Masking specifically on assistant outputs
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|im_start|>user\n",
    response_part="<|im_start|>assistant\n",
)

# Quick Sanity Check to confirm prompt masking is working
sample_labels = trainer.train_dataset[0]["labels"]
masked_count = sum(1 for l in sample_labels if l == -100)
real_count = len(sample_labels) - masked_count
log.info(f"Sanity Check -> Masked Tokens: {masked_count} | Real Labels (-100 ignored): {real_count}")

print("Starting training...")
trainer.train()

print(f"Saving final LoRA adapter to {ADAPTER_OUT}")
model.save_pretrained(ADAPTER_OUT)
tokenizer.save_pretrained(ADAPTER_OUT)
print("Training complete. Best model checkpoint loaded automatically.")