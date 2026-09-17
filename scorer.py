"""
Decides whether one answer counts as correct. Built for unit 2.

`run_eval.py` imports this automatically and fills its Run columns with
pass / fail instead of leaving them blank.

What "correct" means here, and why:

  An answer passes when it contains the question's `expects` phrase from
  questions.py, compared with case and whitespace ignored. The whitespace rule
  exists because the model wrote "10 am" for a question whose expects phrase
  is "10am", and a person reading that answer would not call it wrong. Nothing
  fuzzier than that: "roughly an hour" does not match "55 minutes", because
  a reader checking the guide would notice the difference.

  A refusal never passes an in-corpus question, even when the expects phrase
  is missing for a good reason — a refusal is the system saying it couldn't
  answer, and for these five questions it can.

The other four criteria are not one-bool-per-answer, so they live in
`tools/criteria_table.py`, which reads a results/ file and recomputes them.
"""

import re

from gate import REFUSAL


def _squash(text: str) -> str:
    """Lower-case and strip every whitespace character."""
    return re.sub(r"\s+", "", text.lower())


def contains_expected(expects: str, text: str) -> bool:
    return bool(expects) and _squash(expects) in _squash(text)


def judge(question: str, expects: str, answer: str, results) -> bool:
    """The hook run_eval.py looks for. True means the answer passes."""
    if answer.strip() == REFUSAL:
        return False
    return contains_expected(expects, answer)
