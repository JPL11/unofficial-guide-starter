# Acceptance criteria — The Unofficial Guide

Five criteria that say what "working" means for this system, written in unit 1
**before** any results existed.

Corpus: `city_guides` — fourteen long, sectioned travel guides for nine
fictional towns. Test questions are in `questions.py`.

---

## 1. Retrieved chunks contain the answer

For at least 4 of my 5 test questions, the retrieved chunks include one that
contains the answer.

**Why this target:** Four of my five questions have their answer inside a
single labelled section of a single guide (a drive time, a car-park time, a
ticket price, a town name), so I expect retrieval to find those. The fifth
("best time to visit Halden Bay") is spread over two guides and two sections,
so that is the one I expect to be hard, and 4 of 5 leaves room for exactly one
miss. 5 of 5 would be claiming the hard one works before I have seen it; 3 of 5
would let two of the easy ones fail without me noticing.

---

## 2. Every answer names a source

Every answer the system produces names at least one source document.

**Why this target:** All five and not four, because the prompt hands the model
each chunk with a `[from filename]` tag and the system instruction tells it to
name the file. Nothing about the corpus makes that hard: every chunk has a
filename attached. If this fails it means the model ignored the instruction,
and even one miss would be a real bug in the prompt, not bad luck.

---

## 3. The relevance gate stops out-of-corpus questions

When I ask a question my documents clearly don't cover, the relevance gate
stops it and the system returns "I don't have enough information about that" —
in at least 4 of 5 tries.

The five questions are the ones in `OUT_OF_SCOPE` at the bottom of
`questions.py` (Mongolia, diesel engines, the 1994 World Cup, ibuprofen, Rust).

**Why this target:** The guides are about travel in one small region, and the
five out-of-scope questions are about different subjects entirely, so I expect
a clear gap between the two groups of distances. I am leaving one miss allowed
because "How do I change the oil in a diesel engine?" and "capital of Mongolia"
share travel-ish vocabulary (driving, cities) with the guides, and the
embedding model may pull one of them under the cutoff. I will set the cutoff in
Milestone 4 from the measured gap, not from the 0.6 default.

---

## 4. Chunks are one section each, and none is a fragment

Every chunk produced by `split_documents` is between 120 and 900 characters
long, and no chunk contains more than one `##` section heading.

**Why this target:** When I read the guides in Milestone 1, every one of them
is a title paragraph followed by labelled `##` sections ("Getting there",
"Eat and drink", "When to go"), and each section is one paragraph of roughly
170 to 710 characters. That means "one section = one chunk" is the natural unit:
a chunk with two headings in it answers two topics badly, and a chunk under
120 characters can only be a bare title line with no content under it. The
starter's fixed 800-character windows produced a 24-character chunk on this
corpus and routinely put the end of one section and the start of the next in
the same chunk, which is exactly what this criterion rules out. 900 is the
upper bound because the longest section in the corpus is 711 characters plus a
short title prefix, so anything longer means the chunker glued two sections
together.

---

## 5. The named source is the right one

For all 5 test questions, the document the answer names is the document
that actually contains the `expects` phrase for that question.

**Why this target:** Criterion 2 only checks that *a* source is named. I care
that it is the *correct* one, because a travel guide that cites the Marchwood
guide for a Kestrelford fact is worse than useless: a reader would go to the
wrong file to check. This corpus makes wrong attribution a real risk, since the
"Practical notes" section is copied almost word for word into every town guide
and the cross-cutting guides (transport, seasons, accessibility) repeat facts
from the town guides. 5 of 5 rather than 4 of 5 because I check this by hand
for only five questions, and if one is wrong I want that to count as a miss and
get diagnosed rather than be absorbed by a margin.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 2 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         > **Revised in unit 2:** ...
         >
         > **Why revised:** ...

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point. A number you missed stays where it is, gets diagnosed, and
     gets a fix attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
