#!/usr/bin/env python3
"""
Turn one results/run_*.md file into the per-criterion run log the README wants.

    python tools/criteria_table.py results/run_2026-09-16_1200_before.md

run_eval.py writes one row per QUESTION. criteria.md is one row per CRITERION.
This script does the aggregation, recomputing anything that doesn't need a
model call (retrieval, chunk sizes, the gate) so the numbers are reproducible
from the committed run file plus the committed code.

Per criterion, per run:
  1. Retrieved chunk contains the answer   — search() each question again
     (retrieval is deterministic) and check whether any returned chunk contains
     the expects phrase.
  2. Every answer names a source           — the answer text contains a
     'Source:' line naming at least one file from the corpus.
  3. Gate stops out-of-corpus questions    — read from the run file's gate
     table (one deterministic pass, same number in all three columns).
  4. Chunks are one section each           — every chunk from
     chunker.split_documents is 120..900 chars and has at most one '## '
     heading (deterministic; same number in all three columns).
  5. The named source is the right one     — every file the Source: line names
     contains the expects phrase for that question.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import questions as qs  # noqa: E402
from chunker import split_documents  # noqa: E402
from gate import REFUSAL  # noqa: E402
from ingest import load_documents  # noqa: E402
from scorer import contains_expected  # noqa: E402
from store import search  # noqa: E402

FILE_RE = re.compile(r"[\w\-]+\.(?:md|txt)")


def parse_run_file(path: Path):
    """Pull (question, run, answer) triples and the gate table out of a run file."""
    text = path.read_text(encoding="utf-8")
    answers = {}
    for m in re.finditer(
        r"^### ([^\n]+?) — run (\d+)\n\n(?:- [^\n]*\n)+\n```\n(.*?)\n```", text, re.M | re.S
    ):
        answers[(m.group(1), int(m.group(2)))] = m.group(3)
    gate = {}
    for m in re.finditer(r"^\| (.+?) \| ([\d.]+) \| (refused|\*\*let through\*\*) \|$", text, re.M):
        gate[m.group(1)] = m.group(3) == "refused"
    m = re.search(r"top-k: (\d+) · relevance cutoff: ([\d.]+)", text)
    top_k, threshold = int(m.group(1)), float(m.group(2))
    return answers, gate, top_k, threshold


def named_sources(answer: str) -> list[str]:
    m = re.search(r"^Source:\s*(.+)$", answer, re.M)
    if not m:
        return []
    return FILE_RE.findall(m.group(1))


def main(path: Path):
    answers, gate, top_k, threshold = parse_run_file(path)
    items = qs.answered()
    runs = sorted({r for _, r in answers})
    docs = {d.source: d.text for d in load_documents()}

    # Criterion 1 — deterministic retrieval, computed once.
    retrieved_ok = {}
    first_rank = {}
    for q in items:
        rs = search(q["question"], top_k=top_k)
        hits = [i for i, r in enumerate(rs, 1) if contains_expected(q["expects"], r.text)]
        retrieved_ok[q["question"]] = bool(hits)
        first_rank[q["question"]] = hits[0] if hits else None
    c1 = sum(retrieved_ok.values())

    # Criterion 3 — from the run file.
    c3 = sum(gate.values())

    # Criterion 4 — deterministic chunking.
    chunks = split_documents(load_documents())
    bad = [c for c in chunks if not (120 <= len(c.text) <= 900) or c.text.count("\n## ") > 0]
    c4_ok = not bad

    table = []
    for run in runs:
        c2 = c5 = 0
        for q in items:
            a = answers.get((q["question"], run), "")
            names = named_sources(a)
            if a.strip() != REFUSAL and names:
                c2 += 1
            if names and all(
                contains_expected(q["expects"], docs.get(n, "")) for n in names
            ):
                c5 += 1
        table.append((c2, c5))

    n = len(items)
    print(f"Source file: {path.relative_to(ROOT)}  (top-k {top_k}, cutoff {threshold})\n")
    print("| Criterion | Target | " + " | ".join(f"Run {r}" for r in runs) + " | Verdict |")
    print("|---|---|" + "---|" * len(runs) + "---|")
    rows = [
        ("1. Retrieved chunk contains the answer", "4 of 5", [f"{c1}/{n}"] * len(runs), c1 >= 4),
        ("2. Every answer names a source", "5 of 5", [f"{c2}/{n}" for c2, _ in table], all(c2 == n for c2, _ in table)),
        ("3. Gate stops out-of-corpus questions", "4 of 5", [f"{c3}/{len(gate)}"] * len(runs), c3 >= 4),
        ("4. Every chunk 120–900 chars, one heading", "all 94", [("94/94" if c4_ok else f"{94-len(bad)}/94")] * len(runs), c4_ok),
        ("5. Named source contains the answer", "5 of 5", [f"{c5}/{n}" for _, c5 in table], all(c5 == n for _, c5 in table)),
    ]
    for name, target, cells, met in rows:
        print(f"| {name} | {target} | " + " | ".join(cells) + f" | {'MET' if met else 'MISSED'} |")

    print("\nCriterion 1 detail — rank of the first retrieved chunk containing the expects phrase:")
    for q in items:
        print(f"  rank {first_rank[q['question']] or '-'}  {q['question']}")
    print(f"\nCriterion 4 detail — {len(chunks)} chunks, violations: {[(c.label, len(c.text)) for c in bad] or 'none'}")
    print("\nPer-answer scorer.judge (expects phrase present):")
    for q in items:
        marks = ["pass" if contains_expected(q["expects"], answers.get((q["question"], r), "")) else "FAIL" for r in runs]
        print(f"  {' '.join(marks):15} {q['question']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]).resolve())
