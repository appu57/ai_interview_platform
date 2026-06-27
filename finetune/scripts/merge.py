import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from datasets import load_dataset

MODEL_NAME = "unsloth/Qwen3-4B-Instruct-2507"
ADAPTER_PATH = os.path.join("finetune", "adapter", "adapter_final_v2")
MERGED_OUT = os.path.join("finetune", "merged_model_v2")
MERGED_PATH = os.path.join("finetune","merged","merged_model_v2")
EVAL_PATH = os.path.join("finetune", "dataset", "eval.jsonl")

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
    print(f"Loading base model on CPU...")
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.bfloat16,
        device_map="cpu",
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"Loading adapter from {ADAPTER_PATH}...")
    if not os.path.isfile(os.path.join(ADAPTER_PATH, "adapter_config.json")):
        raise FileNotFoundError(
            f"adapter_config.json not found in {ADAPTER_PATH}. "
            f"Check the path is correct."
        )
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)

    print("Merging adapter into base model weights...")
    merged_model = model.merge_and_unload()

    print(f"Saving merged model to: {MERGED_OUT}")
    os.makedirs(MERGED_OUT, exist_ok=True)
    merged_model.save_pretrained(MERGED_OUT, safe_serialization=True)
    tokenizer.save_pretrained(MERGED_OUT)

    print("Merge complete.")

    FIREWALL_QUESTION = ("A client's firewall frequently drops long-lived HTTP connections. "
                          "How do you ensure a robust streaming experience for a 2,000-token "
                          "response without losing data?")

    if not os.path.isdir(MERGED_PATH):
        raise FileNotFoundError(f"{MERGED_PATH} not found - run merge.py first.")

    model = AutoModelForCausalLM.from_pretrained(MERGED_PATH, torch_dtype=torch.bfloat16, device_map="cpu")
    tokenizer = AutoTokenizer.from_pretrained(MERGED_PATH)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    eval_dataset_raw = load_dataset("json", data_files=EVAL_PATH, split="train")
    sample_questions = [get_first_user_message(eval_dataset_raw[i]["conversations"]) for i in [0, 1, 2]]

    answer, n_tok = generate(model, tokenizer, FIREWALL_QUESTION, max_new_tokens=200, greedy=True)
    print(answer)

    is_likely_english = all(ord(c) < 0x400 for c in answer[:200] if c.isalpha())

    for i, q in enumerate(sample_questions):
        ans, n_tok2 = generate(model, tokenizer, q, max_new_tokens=150, greedy=True)
        print(f"\nQ{i} ({n_tok2} tokens): {q[:100]}...")
        print(f"A: {ans[:300]}")


if __name__ == "__main__":
    main()