"""
build_calibration_data.py - Extract plain text from your training data to
use as imatrix calibration data, instead of llama.cpp's generic default
calibration text. Using domain-specific calibration data (your own DSA/
system-design Q&A) means the quantizer prioritizes precision for the
token patterns that actually matter for your use case.

"""
import json

TRAIN_PATH = "finetune/dataset/train.jsonl"
OUTPUT_PATH = "llama.cpp/calibration_data.txt"


def main():
    lines_written = 0
    with open(TRAIN_PATH, "r", encoding="utf-8") as infile, \
         open(OUTPUT_PATH, "w", encoding="utf-8") as outfile:
        for line in infile:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            for turn in obj.get("conversations", []):
                content = turn.get("content", "").strip()
                if content:
                    outfile.write(content + "\n\n")
                    lines_written += 1

    print(f"Wrote {lines_written} text segments to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()