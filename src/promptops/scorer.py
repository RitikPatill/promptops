from __future__ import annotations

import re

from promptops.models import ExpectedSpec


def score_deterministic(output: str, expected: ExpectedSpec) -> tuple[bool, str]:
    """
    Returns (pass, reason).
    - expected.root is None  → always passes, reason = "no check"
    - expected.root is str   → re.search(pattern, output) must match
    - expected.root is list  → every substring must appear (case-sensitive)
    """
    spec = expected.root

    if spec is None:
        return True, "no check"

    if isinstance(spec, str):
        if re.search(spec, output):
            return True, f"regex matched: '{spec}'"
        return False, f"regex not matched: '{spec}'"

    # list of substrings — all must be present
    for substring in spec:
        if substring not in output:
            return False, f"missing: '{substring}'"
    return True, "all substrings found"
