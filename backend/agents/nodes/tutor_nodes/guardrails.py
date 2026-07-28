import re
from typing import Tuple

MAX_USER_TEXT_CHARS = 4000 

_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"ignore (all )?(previous|prior|above) instructions",
        r"disregard (all )?(previous|prior|above)",
        r"you are now\b",
        r"system prompt",
        r"reveal your (instructions|prompt|system message)",
    ]
]

_LEAK_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"GROUNDING:",
        r"CONFIDENCE:\s*(HIGH|LOW)",
        r"STATUS:\s*(OK|INSUFFICIENT)",
        r"<<<END_.*?>>>",
    ]
]


def check_input(text: str) -> Tuple[bool, str]:
    """(ok, reason). Fail closed -- cheap regex check, no reason to spend a 100s local-model call on obviously bad input."""
    if not text:
        return True, ""
    if len(text) > MAX_USER_TEXT_CHARS:
        return False, "input too long"
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return False, f"possible prompt injection ({pat.pattern})"
    return True, ""


def check_output(text: str) -> Tuple[bool, str]:
    """(ok, reason). Only hard-flags empty output or leaked internal markers -- content correctness is the judge's job, not this."""
    if not text or not text.strip():
        return False, "empty output"
    for pat in _LEAK_PATTERNS:
        if pat.search(text):
            return False, f"leaked internal marker ({pat.pattern})"
    return True, ""