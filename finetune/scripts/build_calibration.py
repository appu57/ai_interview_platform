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