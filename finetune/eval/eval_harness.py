import argparse
import asyncio
import re
import sys
import time
from dataclasses import dataclass

from openai import AsyncOpenAI

VALIDATOR_SYSTEM_PROMPT = """You are the MockAI system design tutor. You are given the original
interview question and a JSON transcription of the candidate's
whiteboard diagram. Evaluate whether the diagram reasonably addresses
the question.

Respond in this exact format, nothing else:

SCORE: <integer 0-10>
FEEDBACK: <2-4 sentences, spoken tone, as if you're talking to the
candidate out loud. Name one thing they got right and one gap or risk
in their design. Do not use markdown, bullet points, or headers -- this
gets read aloud via text-to-speech.>"""

TEST_CASES = [
    {
        "name": "url_shortener_basic_design",
        "question": "Design a URL shortener handling 10k writes/sec and 100k reads/sec.",
        "diagram": '{"components": [{"id": "c1", "label": "API", "shape": "rect", "role": "service"}, {"id": "c2", "label": "Cache", "shape": "hexagon", "role": "cache"}], "connections": [{"from": "c1", "to": "c2", "label": null}]}',
    },
    {
        "name": "payment_gateway_empty_board",
        "question": "Design a payment gateway for a company processing 5k transactions/sec at peak.",
        "diagram": '{"components": [], "connections": [], "notes": "board was empty"}',
    },
    {
        "name": "chat_app_full_design",
        "question": "Design a chat application supporting 1M concurrent connections.",
        "diagram": '{"components": [{"id": "c1", "label": "LB", "shape": "diamond", "role": "load balancer"}, {"id": "c2", "label": "WebSocket Service", "shape": "rect", "role": "service"}, {"id": "c3", "label": "Redis PubSub", "shape": "cylinder", "role": "database"}], "connections": [{"from": "c1", "to": "c2"}, {"from": "c2", "to": "c3"}]}',
    },
]

FORMAT_RE = re.compile(r"SCORE:\s*\d+\s*\n?FEEDBACK:\s*.+", re.IGNORECASE | re.DOTALL)


@dataclass
class CaseResult:
    name: str
    stopped_naturally: bool
    hit_cap: bool
    format_ok: bool
    repeated_block: bool
    raw_output: str
    latency_s: float

    @property
    def passed(self) -> bool:
        return self.stopped_naturally and self.format_ok and not self.repeated_block


def _has_repeated_block(text: str, block_words: int = 15, min_repeats: int = 3) -> bool:
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


async def run_case(client: AsyncOpenAI, model: str, case: dict, num_predict: int) -> CaseResult:
    user_prompt = f"QUESTION:\n{case['question']}\n\nCANDIDATE'S DIAGRAM (JSON):\n{case['diagram']}"

    start = time.monotonic()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VALIDATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=num_predict,
    )
    latency = time.monotonic() - start

    choice = response.choices[0]
    text = choice.message.content or ""
    finish_reason = choice.finish_reason  # "stop" vs "length" is the key signal

    return CaseResult(
        name=case["name"],
        stopped_naturally=(finish_reason == "stop"),
        hit_cap=(finish_reason == "length"),
        format_ok=bool(FORMAT_RE.search(text.strip())),
        repeated_block=_has_repeated_block(text),
        raw_output=text,
        latency_s=latency,
    )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mockai-tutor-new:latest")
    parser.add_argument("--host", default="http://localhost:11434/v1")
    parser.add_argument("--num-predict", type=int, default=700,
                         help="Token cap per response. Should match/exceed your Modelfile's num_predict. "
                              "700 default -- real answers in this dataset can run long; too tight a cap "
                              "creates a false 'didn't stop' reading, same trap as the earlier stop-check gate.")
    args = parser.parse_args()

    client = AsyncOpenAI(base_url=args.host, api_key="ollama")

    results = await asyncio.gather(*[
        run_case(client, args.model, case, args.num_predict) for case in TEST_CASES
    ])

    print(f"\n{'='*70}\nEVAL HARNESS RESULTS -- model={args.model}\n{'='*70}")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"\n[{status}] {r.name}")
        print(f"  stopped_naturally={r.stopped_naturally}  hit_cap={r.hit_cap}  "
              f"format_ok={r.format_ok}  repeated_block={r.repeated_block}  "
              f"latency={r.latency_s:.2f}s")
        if not r.passed:
            print(f"  --- output (first 500 chars) ---\n  {r.raw_output[:500]}")

    all_passed = all(r.passed for r in results)
    print(f"\n{'='*70}")
    if all_passed:
        print(f"ALL {len(results)} CASES PASSED. Safe to set "
              f"FINE_TUNED_MODEL_NAME={args.model} in design_validator_node.py.")
    else:
        failed = [r.name for r in results if not r.passed]
        print(f"FAILED: {failed}. Do not deploy this model -- see output above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())