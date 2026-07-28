import argparse
import asyncio
import csv
import json
import re
import time
from dataclasses import dataclass

from openai import AsyncOpenAI

LENGTH_BUCKETS = {
    "short": (0, 250),
    "medium": (150, 600),
    "long": (400, 2048),
}

JUDGE_SYSTEM_PROMPT = """You are an expert technical evaluator. You will be given a question, \
guidance on what a correct answer should cover, and a candidate's actual response. \
Score the response on two dimensions, each from 1 (poor) to 5 (excellent):

ACCURACY: is the technical content correct?
COMPLETENESS: does it cover the key points from the guidance without missing anything important?

Respond with ONLY valid JSON, no other text, no markdown fences:
{"accuracy": <int 1-5>, "completeness": <int 1-5>, "reasoning": "<one sentence>"}"""


def load_golden_dataset(path):
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def has_repeated_block(text, block_words=20, min_repeats=2):
    words = text.split()
    if len(words) < block_words * min_repeats:
        return False
    seen = {}
    for i in range(len(words) - block_words + 1):
        chunk = " ".join(words[i:i + block_words])
        seen[chunk] = seen.get(chunk, 0) + 1
        if seen[chunk] >= min_repeats:
            return True
    return False


def avg_words_per_sentence(text):
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return 0
    total_words = sum(len(s.split()) for s in sentences)
    return total_words / len(sentences)


def length_bucket_match(bucket, token_count):
    lo, hi = LENGTH_BUCKETS.get(bucket, (0, 999999))
    return lo <= token_count <= hi


def concept_coverage_recall(text, required_concepts):
    if not required_concepts:
        return None
    text_lower = text.lower()
    hits = sum(1 for c in required_concepts if c.lower() in text_lower)
    return round(hits / len(required_concepts), 2)


def _parse_judge_json(raw):
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        parsed = json.loads(cleaned)
        return parsed.get("accuracy"), parsed.get("completeness"), parsed.get("reasoning", "")
    except (json.JSONDecodeError, AttributeError):
        return None, None, f"PARSE_FAILURE: {raw[:200]}"


async def llm_judge(client, judge_model, question, rubric_notes, response_text):
    user_prompt = (
        f"QUESTION:\n{question}\n\n"
        f"GUIDANCE ON A CORRECT ANSWER:\n{rubric_notes}\n\n"
        f"CANDIDATE RESPONSE:\n{response_text}"
    )
    try:
        response = await client.chat.completions.create(
            model=judge_model,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=200,
        )
        raw = response.choices[0].message.content or ""
    except Exception as e:
        return None, None, f"JUDGE_CALL_FAILED: {e}"
    return _parse_judge_json(raw)


@dataclass
class EvalRow:
    id: str
    category: str
    context: str
    user_input: str
    response_text: str
    token_count: int
    stopped: bool
    expected_length_bucket: str
    length_bucket_ok: bool
    possible_double_answer: bool
    avg_words_per_sentence: float
    concept_coverage_recall: float
    known_risk: str
    rubric_notes: str
    latency_s: float
    llm_judge_accuracy: object = None
    llm_judge_completeness: object = None
    llm_judge_reasoning: str = ""


async def run_one(client, model, entry, judge_client, judge_model):
    start = time.monotonic()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": entry["system_prompt"]},
            {"role": "user", "content": entry["user_input"]},
        ],
        temperature=0.0,
        max_tokens=2048, 
    )
    latency = time.monotonic() - start
    choice = response.choices[0]
    text = choice.message.content or ""
    token_count = response.usage.completion_tokens

    judge_accuracy, judge_completeness, judge_reasoning = None, None, ""
    if judge_model:
        judge_accuracy, judge_completeness, judge_reasoning = await llm_judge(
            judge_client, judge_model, entry["user_input"], entry.get("rubric_notes", ""), text
        )

    return EvalRow(
        id=entry["id"],
        category=entry["category"],
        context=entry["context"],
        user_input=entry["user_input"][:100],
        response_text=text,
        token_count=token_count,
        stopped=(choice.finish_reason == "stop"),
        expected_length_bucket=entry["expected_length_bucket"],
        length_bucket_ok=length_bucket_match(entry["expected_length_bucket"], token_count),
        possible_double_answer=has_repeated_block(text),
        avg_words_per_sentence=round(avg_words_per_sentence(text), 1),
        concept_coverage_recall=concept_coverage_recall(text, entry.get("required_concepts")),
        known_risk=entry.get("known_risk") or "",
        rubric_notes=entry.get("rubric_notes", ""),
        latency_s=round(latency, 1),
        llm_judge_accuracy=judge_accuracy,
        llm_judge_completeness=judge_completeness,
        llm_judge_reasoning=judge_reasoning,
    )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Ollama model name, e.g. mockai-tutor-new")
    parser.add_argument("--host", default="http://localhost:11434/v1")
    parser.add_argument("--dataset", default="golden_dataset.jsonl")
    parser.add_argument("--out", default=None, help="Output CSV path (default: golden_eval_<model>.csv)")
    parser.add_argument("--judge-model", default=None,
                         help="Optional: a DIFFERENT Ollama model to use as an LLM judge for "
                              "accuracy/completeness. Omit to skip judge scoring entirely.")
    args = parser.parse_args()
    out_path = args.out or f"golden_eval_{args.model}.csv"

    if args.judge_model and args.judge_model == args.model:
        print("WARNING: --judge-model is the same as --model. A model judging its own output "
              "is a known bias risk (it tends to rate its own answers favorably) -- consider "
              "using a different model as the judge.")

    entries = load_golden_dataset(args.dataset)
    client = AsyncOpenAI(base_url=args.host, api_key="ollama")
    judge_client = client  # same connection, just a different model name per-call

    print(f"Running {len(entries)} golden entries through {args.model}"
          f"{f' (judged by {args.judge_model})' if args.judge_model else ''}...")
    rows = []
    for entry in entries:
        row = await run_one(client, args.model, entry, judge_client, args.judge_model)
        flag = []
        if not row.stopped:
            flag.append("DID NOT STOP")
        if not row.length_bucket_ok:
            flag.append(f"LENGTH OUTSIDE '{row.expected_length_bucket}' BUCKET")
        if row.possible_double_answer:
            flag.append("POSSIBLE DOUBLE-ANSWER")
        if row.avg_words_per_sentence > 35:
            flag.append("LONG SENTENCES -- CHECK SPOKEN STYLE")
        if row.concept_coverage_recall is not None and row.concept_coverage_recall < 0.5:
            flag.append(f"LOW CONCEPT COVERAGE ({row.concept_coverage_recall})")
        flag_str = ", ".join(flag) if flag else "no automated flags"
        judge_str = (f"  judge: acc={row.llm_judge_accuracy} comp={row.llm_judge_completeness}"
                     if args.judge_model else "")
        print(f"  [{row.id}] {row.token_count} tokens -- {flag_str}{judge_str}")
        rows.append(row)


    fieldnames = [
        "id", "category", "context", "user_input", "expected_length_bucket",
        "token_count", "stopped", "length_bucket_ok", "possible_double_answer",
        "avg_words_per_sentence", "concept_coverage_recall",
        "llm_judge_accuracy", "llm_judge_completeness", "llm_judge_reasoning",
        "known_risk", "rubric_notes",
        "accuracy_score_1to5", "completeness_score_1to5", "spoken_style_score_1to5",
        "human_notes",
        "response_text", "latency_s",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            record = {
                "id": row.id, "category": row.category, "context": row.context,
                "user_input": row.user_input, "expected_length_bucket": row.expected_length_bucket,
                "token_count": row.token_count, "stopped": row.stopped,
                "length_bucket_ok": row.length_bucket_ok,
                "possible_double_answer": row.possible_double_answer,
                "avg_words_per_sentence": row.avg_words_per_sentence,
                "concept_coverage_recall": row.concept_coverage_recall,
                "llm_judge_accuracy": row.llm_judge_accuracy,
                "llm_judge_completeness": row.llm_judge_completeness,
                "llm_judge_reasoning": row.llm_judge_reasoning,
                "known_risk": row.known_risk, "rubric_notes": row.rubric_notes,
                "accuracy_score_1to5": "", "completeness_score_1to5": "",
                "spoken_style_score_1to5": "", "human_notes": "",
                "response_text": row.response_text, "latency_s": row.latency_s,
            }
            writer.writerow(record)

    print(f"\nSaved to {out_path}. Open it, read/listen to each response_text, "
          f"and fill in the three *_score_1to5 columns plus human_notes before "
          f"comparing against another model version.")


if __name__ == "__main__":
    asyncio.run(main())