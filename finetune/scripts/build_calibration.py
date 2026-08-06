import json
from finetune.scripts.logging_utils import get_logger

log = get_logger("mockai.pipeline.calibration")

CALIBRATION_TRAIN_PATH = "finetune/dataset/train.jsonl"
CALIBRATION_OUTPUT_PATH = "llama.cpp/calibration_data.txt"


def main():
    lines_written = 0
    with open(CALIBRATION_TRAIN_PATH, "r", encoding="utf-8") as infile, \
         open(CALIBRATION_OUTPUT_PATH, "w", encoding="utf-8") as outfile:
        for line in infile:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                log.warning(f"Skipping malformed JSON at {CALIBRATION_TRAIN_PATH}:{line_no}: {e}")
                skipped_lines += 1
                continue
            for turn in obj.get("conversations", []):
                content = turn.get("content", "").strip()
                if content:
                    outfile.write(content + "\n\n")
                    lines_written += 1

    print(f"Wrote {lines_written} text segments to {CALIBRATION_OUTPUT_PATH}")


if __name__ == "__main__":
    main()