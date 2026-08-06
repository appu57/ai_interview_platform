import json, sys, time, os
from groq import Groq, APIStatusError
from dotenv import load_dotenv
import random
import re
from finetune.scripts.logging_utils import get_logger

random.seed(42)
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
log = get_logger("mockai.pipeline.build_dataset")


TUTOR_SYSTEM_PROMPT = (
    "You are a patient DSA and System Design tutor speaking aloud to a student "
    "in a voice conversation. Explain step-by-step in clear, natural spoken "
    "language. Do NOT use markdown, bullet points, numbered lists, or code-block "
    "formatting in your spoken explanation — describe code logic in words."
)

INPUT_PATH = "finetune/dataset/dsa_cp_questions.jsonl"
TRAIN_PATH = "finetune/dataset/train.jsonl"
EVAL_PATH = "finetune/dataset/eval.jsonl"
MAX_WORDS_PER_EXAMPLE = 1300  

def strip_code_blocks(text: str) -> str:
    """Remove ```python ... ``` blocks — speech shouldn't read code verbatim."""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()


def extract_section(output: str, header: str, next_headers: list[str] = None) -> str:

    start_match = re.search(re.escape(header), output)
    if not start_match:
        return ""
    start_idx = start_match.end()

    next_header_match = re.search(r"\n\s*\d{1,2}\.\s", output[start_idx:])
    if next_header_match:
        end_idx = start_idx + next_header_match.start()
        return output[start_idx:end_idx].strip()
    return output[start_idx:].strip()


def strip_section_numbering(text: str) -> str:
    return re.sub(r"^\s*\d{1,2}\.\s*([A-Z][A-Z\s\-()]*)\n", r"\1.\n", text, flags=re.MULTILINE)


def build_full_explanation(entry: dict) -> str:
    output = entry["output"]
    cleaned = strip_section_numbering(output)
    return cleaned.strip()


def build_pattern_hint(entry: dict) -> str:
    hidden = entry.get("hidden_patterns", [])
    if isinstance(hidden, str):
        patterns = hidden 
    else:
        patterns = ", ".join(hidden)
    technique = entry.get("technique", "")
    if not patterns and not technique:
        return ""
    if not patterns:
        return technique.strip()
    return f"This problem relates to the {patterns} pattern. {technique}".strip()


def build_mistake_note(entry: dict) -> str:
    output = entry["output"]
    mistakes = extract_section(output, "10. COMMON MISTAKES", ["11.", "12."])
    return strip_code_blocks(mistakes)


def build_complexity_note(entry: dict) -> str:
    output = entry["output"]
    complexity = extract_section(output, "9. FORMAL COMPLEXITY ANALYSIS", ["10.", "11."])
    return strip_code_blocks(complexity) or entry.get("time-complexity", "")


def truncate(text: str, max_words: int = MAX_WORDS_PER_EXAMPLE) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def variant_full_walkthrough(entry: dict) -> dict:
    human = entry["question"]
    gpt = build_full_explanation(entry)  # full content, no truncation
    return {"conversations": [
        {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": human},
        {"role": "assistant", "content": gpt},
    ]}


def variant_quick_doubt(entry: dict) -> dict:
    human = f"Wait, I'm stuck on this one — {entry['question']} What's the trick here?"
    hint = build_pattern_hint(entry)
    if not hint:
        hint = truncate(build_full_explanation(entry), max_words=120)
    gpt = truncate(hint, max_words=150)
    if not gpt.strip():
        return None
    return {"conversations": [
        {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": human},
        {"role": "assistant", "content": gpt},
    ]}


def variant_complexity_followup(entry: dict) -> dict:
    human = (
        f"For this problem — {entry['question']} — what's the time and space "
        f"complexity of the approach, and why?"
    )
    gpt = truncate(build_complexity_note(entry), max_words=200)
    if not gpt.strip():
        return None
    return {"conversations": [
        {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": human},
        {"role": "assistant", "content": gpt},
    ]}


def variant_mistake_check(entry: dict) -> dict:
    mistakes = build_mistake_note(entry)
    if not mistakes.strip():
        return None
    human = f"What do people usually mess up when solving: {entry['question']}"
    gpt = truncate(mistakes, max_words=200)
    return {"conversations": [
        {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": human},
        {"role": "assistant", "content": gpt},
    ]}


def variant_wrong_approach_correction(entry: dict) -> dict:
    hint = build_pattern_hint(entry)
    if not hint:
        return None

    human = (
        f"For this problem — {entry['question']} — I was thinking of just checking "
        f"every possible option with brute force. Would that work?"
    )
    gpt = truncate(
        f"That would technically give the right answer, but it won't be efficient enough "
        f"for larger inputs. {hint}",
        max_words=250,
    )
    return {"conversations": [
        {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": human},
        {"role": "assistant", "content": gpt},
    ]}


VARIANT_FNS = [
    variant_full_walkthrough,
    variant_quick_doubt,
    variant_complexity_followup,
    variant_mistake_check,
    variant_wrong_approach_correction,
]

def is_valid(example: dict) -> bool:
    if example is None:
        return False
    gpt_turn = next(t for t in example["conversations"] if t["role"] == "assistant")
    word_count = len(gpt_turn["content"].split())
    if word_count < 15:
        return False  # too short, likely an empty extracted section / parsing failure
    return True


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)

def repair_raw_newlines_in_strings(content: str) -> str:
    result = []
    in_string = False
    escape_next = False

    for ch in content:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue

        if ch == "\\":
            result.append(ch)
            escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue

        if in_string and ch == "\n":
            result.append("\\n")
            continue
        if in_string and ch == "\r":
            continue  # drop carriage returns inside strings
        if in_string and ord(ch) < 0x20:
            continue  # drop other raw control characters inside strings

        result.append(ch)

    return "".join(result)


def load_raw_entries(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    content = repair_raw_newlines_in_strings(content)

    if content.startswith("["):
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass  # fall through to other strategies

    entries = []
    all_lines_parsed = True
    for line in content.splitlines():
        line = line.strip().rstrip(",") 
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            all_lines_parsed = False
            break

    if all_lines_parsed and entries:
        return entries


    entries = []
    decoder = json.JSONDecoder()
    text = content
    idx = 0
    text_len = len(text)
    while idx < text_len:
        while idx < text_len and text[idx] in " \t\n\r,[]":
            idx += 1
        if idx >= text_len:
            break
        try:
            obj, end_idx = decoder.raw_decode(text, idx)
            entries.append(obj)
            idx = end_idx
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Could not parse JSON starting at character {idx}. "
                f"File may be malformed near: ...{text[max(0,idx-50):idx+50]}..."
            ) from e

    return entries


def detect_topic(entry: dict) -> str:
    hidden = entry.get("hidden_patterns", "")
    has_dsa_patterns = bool(hidden) and (isinstance(hidden, list) or isinstance(hidden, str) and hidden.strip())

    sysdesign_keywords = [
        "kv cache", "pagedattention", "vllm", "batching", "speculative decoding",
        "load balanc", "sharding", "replication", "microservice", "latency",
        "throughput", "scalability", "distributed", "cache invalidation",
        "consistent hashing", "message queue", "fde", "inference optim",
        "gpu memory", "quantiz",
    ]
    question_and_output = (entry.get("question", "") + " " + entry.get("output", "")).lower()
    has_sysdesign_keyword = any(kw in question_and_output for kw in sysdesign_keywords)

    if has_sysdesign_keyword and not has_dsa_patterns:
        return "system_design"
    if has_dsa_patterns:
        return "dsa"
    return "system_design"  # default for ambiguous/conceptual entries without patterns


def validate_entries(raw_entries: list[dict]) -> tuple[list[dict], list[dict]]:
    valid = []
    skipped = []
    for i, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            skipped.append({"index": i, "reason": f"not a dict (got {type(entry).__name__})", "entry": entry})
            continue
        missing = [k for k in ("question", "output") if k not in entry or not entry[k]]
        if missing:
            skipped.append({
                "index": i,
                "reason": f"missing/empty required field(s): {missing}",
                "entry_id": entry.get("id", "unknown"),
                "entry_preview": str(entry)[:200],
            })
            continue
        valid.append(entry)
    return valid, skipped


def main():
    raw_entries = load_raw_entries(INPUT_PATH)
    log.warning(f"Loaded {len(raw_entries)} raw entries")

    raw_entries, skipped = validate_entries(raw_entries)
    if skipped:
        log.warning(f"\n Skipped {len(skipped)} malformed entries:")
        for s in skipped:
            log.warning(f"  - index {s['index']} (id={s.get('entry_id', '?')}): {s['reason']}")
            log.warning(f"    preview: {s['entry_preview']}")
        log.warning()
    log.warning(f"Proceeding with {len(raw_entries)} valid entries\n")

    topic_counts = {"dsa": 0, "system_design": 0}
    for entry in raw_entries:
        topic_counts[detect_topic(entry)] += 1
    total = len(raw_entries)
    log.warning(f"Topic split in raw data: "
          f"DSA={topic_counts['dsa']} ({topic_counts['dsa']/total:.0%}), "
          f"System Design/Infra={topic_counts['system_design']} ({topic_counts['system_design']/total:.0%})")

    all_examples = []
    for entry in raw_entries:
        topic = detect_topic(entry)

        ex = variant_full_walkthrough(entry)
        ex["topic"] = topic
        all_examples.append(ex)

        other_variants = random.sample(VARIANT_FNS[1:], k=2)
        for variant_fn in other_variants:
            ex = variant_fn(entry)
            if ex is not None:
                ex["topic"] = topic
                all_examples.append(ex)

    all_examples = [ex for ex in all_examples if is_valid(ex)]
    log.warning(f"After diversification + filtering: {len(all_examples)} examples")

    oversized = []
    for ex in all_examples:
        gpt_turn = next(t for t in ex["conversations"] if t["role"] == "assistant")
        tok_est = estimate_tokens(gpt_turn["content"])
        if tok_est > 1500:
            human_turn = next(t for t in ex["conversations"] if t["role"] == "user")
            oversized.append({"question": human_turn["content"][:80], "estimated_tokens": tok_est})

    if oversized:
        log.warning(f"\n  {len(oversized)} examples estimate OVER ~1500 tokens "
              f"(content kept fully intact here, but Stage 3's max_seq_length=2048 "
              f"WILL truncate the tail of these during actual training unless raised):")
        for o in oversized[:10]:
            log.warning(f"  - ~{o['estimated_tokens']} tok: {o['question']}...")
        if len(oversized) > 10:
            log.warning(f"  ... and {len(oversized) - 10} more")

    final_topic_counts = {"dsa": 0, "system_design": 0}
    for ex in all_examples:
        final_topic_counts[ex["topic"]] += 1
    total_final = len(all_examples)
    log.warning(f"Topic split in final dataset: "
          f"DSA={final_topic_counts['dsa']} ({final_topic_counts['dsa']/total_final:.0%}), "
          f"System Design/Infra={final_topic_counts['system_design']} ({final_topic_counts['system_design']/total_final:.0%})")

    # Shuffle and split 85/15
    random.shuffle(all_examples)
    split_idx = int(len(all_examples) * 0.85)
    train, val = all_examples[:split_idx], all_examples[split_idx:]

    with open(TRAIN_PATH, "w") as f:
        for ex in train:
            f.write(json.dumps(ex) + "\n")

    with open(EVAL_PATH, "w") as f:
        for ex in val:
            f.write(json.dumps(ex) + "\n")

    log.warning(f"Wrote {len(train)} train examples -> {TRAIN_PATH}")
    log.warning(f"Wrote {len(val)} eval examples -> {EVAL_PATH}")


if __name__ == "__main__":
    main()