"""Differential fuzz: leptris vs lxml on random (document, path) pairs.

Run:  LEPTRIS_LIB_PATH=... python scripts/differential_fuzz.py [trials]

Compares findall across random small trees and representative paths.
Divergence handling mirrors the documented contract: leptris's find*
accepts full XPath 1.0 — a SUPERSET of lxml's ElementPath — so
"lxml rejects, leptris succeeds" is parity, not divergence; both
erroring (any classes) is parity. Anything else is a finding.

Requires lxml (pip install .[bench]).

Currently: 0 divergences (libleptris 1.9.18, #630 fixed). Rerun per
adoption as a standing regression gate.
"""

from __future__ import annotations

import random
import sys

import lxml.etree as LET

from leptris import fromstring

TAGS = ["a", "b", "c", "ns:x", "ns:y"]
ATTRS = ["id", "k", "ns:p", "p"]
NS = {"ns": "urn:ns"}
PATHS = [
    "a", "b", "a/b", "a//b", ".//a", "./b/c", "*", "*/*", "a[1]",
    "a[last()]", "a[@id]", "a[@id='5']", "a[@id > 3]",
    "b[position() > 1]", "//b", "//a[@k]", "count(//a)",
    "count(//b[@id])", "//a | //b", ".//*", "ns:x", "ns:y//a",
    "a/ns:x", "string(.//a)", "boolean(//b[@id='7'])",
    "name(.//a[1])", "a[text()='t']", "b[not(@id)]", "a[b]",
    "a[not(b)]", ".//ns:x", "count(//ns:*)",
]


def make_element(depth: int, rng: random.Random):
    tag = rng.choice(TAGS)
    attrs = {
        a: str(rng.randint(0, 20))
        for a in rng.sample(ATTRS, rng.randint(0, 2))
    }
    text = rng.choice(["", "t", "hello world", "5"])
    kids = [
        make_element(depth + 1, rng)
        for _ in range(rng.randint(0, 3) if depth < 3 else 0)
    ]
    return tag, attrs, text, kids


def render(node) -> str:
    tag, attrs, text, kids = node
    a = "".join(f" {k}='{v}'" for k, v in attrs.items())
    if not kids and not text:
        return f"<{tag}{a}/>"
    return f"<{tag}{a}>{text}{''.join(render(k) for k in kids)}</{tag}>"


def outcome(fn, path):
    """('error',) | list of result tags/strings (scalars wrapped)."""
    try:
        results = fn(path, NS)
    except Exception:
        return ("error",)
    if isinstance(results, (str, float, bool)):
        return [results]
    return [r if isinstance(r, str) else r.tag for r in results]


def main() -> int:
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    rng = random.Random(20260829)
    divergences = 0
    for _ in range(trials):
        xml = f"<root xmlns:ns='urn:ns'>{render(make_element(0, rng))}</root>"
        path = rng.choice(PATHS)
        pr = outcome(fromstring(xml.encode()).findall, path)
        lr = outcome(LET.fromstring(xml.encode()).findall, path)
        if pr == lr:
            continue
        # leptris superset: lxml rejects where leptris succeeds -> parity
        if lr == ("error",):
            continue
        divergences += 1
        print(f"DIVERGENCE path={path!r}")
        print(f"  leptris: {pr[:6]}")
        print(f"  lxml   : {lr[:6]}")
        print(f"  xml: {xml[:140]}")
    print(f"{trials} trials, {divergences} divergences")
    return 1 if divergences else 0


if __name__ == "__main__":
    sys.exit(main())
