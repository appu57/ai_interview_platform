import os
import math
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from datasets import load_dataset

MODEL_NAME = "unsloth/Qwen3-4B-Instruct-2507"
ADAPTER_PATH = os.path.join("finetune", "adapter", "adapter_final_v2")
EVAL_PATH = os.path.join("finetune", "dataset", "eval.jsonl")
MAX_SEQ_LENGTH = 2048


def get_first_user_message(conversations):
    for turn in conversations:
        if turn["role"] == "user":
            return turn["content"]
    raise ValueError("No user turn found")


def get_input_ids(tokenizer, question, device):
    encoded = tokenizer.apply_chat_template(
        [{"role": "user", "content": question}],
        tokenize=True, add_generation_prompt=True, return_tensors="pt"
    )
    ids = encoded["input_ids"] if (isinstance(encoded, dict) or hasattr(encoded, "keys")) else encoded
    return ids.to(device)


def compute_eval_loss(model, tokenizer, eval_dataset_raw, device):
    model.eval()
    total_loss = 0.0
    total_tokens = 0
    with torch.no_grad():
        for ex in eval_dataset_raw:
            conv = ex["conversations"]
            text = tokenizer.apply_chat_template(conv, tokenize=False, add_generation_prompt=False)
            ids = tokenizer(text, truncation=True, max_length=MAX_SEQ_LENGTH, return_tensors="pt")["input_ids"].to(device)
            outputs = model(input_ids=ids, labels=ids)
            n_tokens = ids.shape[1]
            total_loss += outputs.loss.item() * n_tokens
            total_tokens += n_tokens
    avg_loss = total_loss / total_tokens
    return avg_loss, math.exp(avg_loss)


def generate(model, tokenizer, question, max_new_tokens=200, greedy=True):
    input_ids = get_input_ids(tokenizer, question, model.device)
    with torch.no_grad():
        output = model.generate(
            input_ids=input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=not greedy,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    new_tokens = output[0][input_ids.shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True), len(new_tokens)


def main():
    FIREWALL_QUESTION = ("A client's firewall frequently drops long-lived HTTP connections. "
                          "How do you ensure a robust streaming experience for a 2,000-token "
                          "response without losing data?")

    print("Loading eval dataset...")
    eval_dataset_raw = load_dataset("json", data_files=EVAL_PATH, split="train")
    sample_questions = [get_first_user_message(eval_dataset_raw[i]["conversations"]) for i in [0, 1, 2]]


    base_model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.bfloat16, device_map="cpu")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    raw_loss, raw_ppl = compute_eval_loss(base_model, tokenizer, eval_dataset_raw, base_model.device)
    print(f"RAW MODEL eval loss: {raw_loss:.4f} | perplexity: {raw_ppl:.4f}")

    raw_firewall_answer, raw_firewall_tokens = generate(base_model, tokenizer, FIREWALL_QUESTION)
    print(f"\nRAW - Firewall question ({raw_firewall_tokens} tokens):\n{raw_firewall_answer[:400]}")

    del base_model
    import gc
    gc.collect()


    base_model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.bfloat16, device_map="cpu")
    if not os.path.isfile(os.path.join(ADAPTER_PATH, "adapter_config.json")):
        raise FileNotFoundError(f"adapter_config.json not found in {ADAPTER_PATH} - check the path.")
    adapter_model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)

    ft_loss, ft_ppl = compute_eval_loss(adapter_model, tokenizer, eval_dataset_raw, adapter_model.device)
    print(f"ADAPTER-ON-BASE eval loss: {ft_loss:.4f} | perplexity: {ft_ppl:.4f}")

    ft_firewall_answer, ft_firewall_tokens = generate(adapter_model, tokenizer, FIREWALL_QUESTION)
    print(f"\nADAPTER - Firewall question ({ft_firewall_tokens} tokens):\n{ft_firewall_answer[:400]}")

    for i, q in enumerate(sample_questions):
        answer, n_tok = generate(adapter_model, tokenizer, q, max_new_tokens=150)
        print(f"\nQ{i} ({n_tok} tokens): {q[:100]}...")
        print(f"A: {answer[:300]}")


    print(f"Raw model eval loss:       {raw_loss:.4f}")
    print(f"Adapter-on-base eval loss: {ft_loss:.4f}")
    print(f"\nIf adapter loss is lower and answers look good, proceed to merge.py.")


if __name__ == "__main__":
    main()