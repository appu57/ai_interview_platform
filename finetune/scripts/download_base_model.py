#  python finetune/scripts/download_base_model.py --variant 4bit   # for training
#  python finetune/scripts/download_base_model.py --variant full   # for merging
#  python finetune/scripts/download_base_model.py --variant both   # both (default)

import os
import argparse
from huggingface_hub import snapshot_download

from finetune.scripts.retry_utils import retry

variants = {
    "4bit":{
        "hub_name":"unsloth/Qwen3-4B-Instruct-2507-bnb-4bit",
        "local_dir":os.path.join("base_model","Qwen3-4B-Instruct-2507-4bit"),
        "purpose": "Need quantized model for SFT Trainer"
    },
    "full":{
        "hub_name":"Qwen/Qwen3-4B-Instruct-2507",
        "local_dir":os.path.join("base_model", "Qwen3-4B-Instruct-2507-full"),
        "purpose":"To merge lora adaptors back in the base model"
    }
}


@retry(times=4, base_delay=10.0)
def _download(repo_id: str, local_dir: str) -> str:
    return snapshot_download(repo_id=repo_id, local_dir=local_dir)

def download_variant(key:str):
    config = variants[key]
    os.makedirs(config["local_dir"], exist_ok=True)
    local_path = _download(config["hub_name"], config["local_dir"])

    # local_path = snapshot_download(
    #     repo_id= config["hub_name"],
    #     local_dir=config["local_dir"],
    #     local_dir_use_symlinks=False  // local_dir_use_symlinks deprecated in latest huggingface_hub, so using retry decorator instead
    # )

    total_size_mb = 0
    for f in sorted(os.listdir(local_path)):
        full_path = os.path.join(local_path, f)
        if os.path.isfile(full_path):
            total_size_mb += os.path.getsize(full_path) / (1024 * 1024)
    print(f"Total size in mb: {total_size_mb:8.1f} MB") #8.1f for formatting to 8 characters wide, 1 decimal place

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["4bit", "full", "both"], default="both")
    args = parser.parse_args()
 
    if args.variant == "both":
        download_variant("4bit")
        download_variant("full")
    else:
        download_variant(args.variant) 
 
if __name__ == "__main__":
    main()