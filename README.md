# The Unofficial Guide

Jacky Li — corpus: `city_guides`

---

# Unit 1

## What This Does

This is a small retrieval-augmented question-answering system over the
`city_guides` corpus: fourteen travel guides for nine fictional towns in one
region, nine of them per-town guides and five cross-cutting ones (eating,
walking, transport, seasons, accessibility). Each guide is split into its
labelled sections, embedded locally with all-MiniLM-L6-v2, and stored in
Chroma. When you ask a question, the five closest sections are retrieved; if
the best one is further than 0.65 away the system says it doesn't have enough
information, otherwise Gemini writes a short answer from those sections only
and names the file it used. It answers practical, factual travel questions —
how long a drive takes, when a car park fills, what a tower costs to climb,
which town is easiest with limited mobility, when to visit.

Ask it from the command line:

```
python app.py ask "How long does it take to drive from Brightwater to Kestrelford?"
```

## Chunking Strategy

**Chunk size:** one labelled section per chunk, whatever length that section
is. In this corpus that comes out at 171 to 757 characters, 317 on average
(94 chunks from 14 documents). Sections under 120 characters are merged into
the section after them; sections over 900 would be split at a paragraph break,
but none is.

**Overlap:** none (0 characters).

Every guide in `city_guides` has the same shape: a `# Town` title, one intro
paragraph, then six or seven `## ` sections with the same labels in the same
order ("Getting there", "Getting around", "Eat and drink", "What to see",
"Where to stay", "When to go", "Practical notes"). The cross-cutting guides
are the same idea with different labels ("Straightforward" / "Mixed" /
"Difficult", or one section per season). Each section is a single paragraph,
and the paragraph is the unit of meaning: a question about parking in Halden
Bay is answered entirely inside "Halden Bay — Getting there", and nothing in
"Eat and drink" helps. So the heading is where to cut.

The starter's fixed 800-character windows made 51 chunks from these 14 files,
with a shortest chunk of 24 characters (a tail fragment) and most chunks
straddling two headings: the end of "Getting around" and the start of "Eat
and drink" in the same chunk. That chunk matches a transport question a bit
and a food question a bit and neither well.

Two decisions I made on top of "cut at headings":

- **Prefix every chunk with `Town — Section`.** Once a section is on its own,
  "Everything closes by 9pm" doesn't say *where*. The embedding can't match
  "Halden Bay" in the question to a chunk that never mentions Halden Bay,
  and the model can't cite the right town. The prefix fixes both.
- **No overlap.** Overlap exists so a sentence doesn't get cut in half.
  Cutting at a heading never cuts a sentence, so overlap here would only copy
  the last line of one section into the next and blur which section is about
  what.

I measured section lengths before writing the code: 98 sections, median
285 characters, longest 711. Four of the 98 were bare title lines of 23 to 27
characters on the cross-cutting guides (they have no intro paragraph), which is
what the 120-character merge rule exists for. Without it those four would have
become chunks that say "When to visit the region" and nothing else.

## Sample Chunks

Printed by `python app.py chunks --indices 51,48,78,60,21`. All five are
produced by `chunker.py::split_documents`.

**Chunk 1** — source: `guide_kestrelford.md#1` — produced by: `chunker.py::split_documents`

```
Kestrelford — Getting there
No railway station; the line was closed in 1963 and the trackbed is now a walking route. Buses run from Brightwater roughly hourly on weekdays, every two hours on Saturdays, and not at all on Sundays. Driving takes 55 minutes and the last eight are on a single-track road with passing places.
```

Stands alone: answers "how do I get to Kestrelford", "is there a train",
"what's the drive like", "do buses run on Sunday".

**Chunk 2** — source: `guide_halden_bay.md#6` — produced by: `chunker.py::split_documents`

```
Halden Bay — When to go
June and September are the sweet spot. July and August are busy enough that the parking problem becomes the defining feature of the visit. Winter is dramatic and largely closed. The coastal path is genuinely dangerous in high wind and gets shut.
```

Stands alone for "when should I visit Halden Bay". It mentions "the parking
problem" without saying what it is, so a parking question needs the "Getting
there" chunk too; that's why top-k stays at 5.

**Chunk 3** — source: `guide_seasons.md#0` — produced by: `chunker.py::split_documents`

```
When to visit the region — Spring, March to May
Days lengthen quickly and businesses that closed for winter reopen through
March and April. By May everything is open and the weather is reliable enough
to plan around. Late May is arguably the best week of the year in Brightwater —
long days, everything running, and the students gone.

The Kestrelford Saturday market builds back to full size through April.
```

This is the merge rule at work: `guide_seasons.md` opens with a bare
`# When to visit the region` line and no intro, so the title was folded into
the first season instead of becoming a 26-character chunk.

**Chunk 4** — source: `guide_marchwood.md#2` — produced by: `chunker.py::split_documents`

```
Marchwood — Getting around
A tram network of four lines, running every 8 minutes on weekdays and every 15 at weekends, until midnight. A day ticket costs less than two single fares and nobody tells you this at the machine. The centre is walkable but the interesting districts are not adjacent to each other.
```

Stands alone: tram frequency, ticket advice, walkability, all for one town.

**Chunk 5** — source: `guide_eating.md#0` — produced by: `chunker.py::split_documents`

```
Eating across the region — The pattern worth knowing
Almost everywhere in this region, the good cooking is one street back from
wherever the visitors are. Brightwater's riverside strip is priced for people
who walked there from the hotels; Corry Lane, two streets inland, serves
comparable food for about a third less. Halden Bay's harbour front is roughly
double Fell Street, one level up. Pellew Sands's seafront is chips and ice
cream, and Marine Terrace behind it is where the actual restaurants are.

Marchwood is the exception, in that the good district — Northgate — is a tram
ride away rather than a street away, and the station area is uniformly poor.
```

The longest kind of chunk in the corpus (660 characters) and the one that
comes closest to "too big": it names four towns, so it matches any
where-to-eat question a little. It is still one thought (the pattern), which
is why I kept sections whole rather than splitting long ones by sentence.

## Sample Answer

**Question:** How long does it take to drive from Brightwater to Kestrelford?

**Answer:**

Output of `python app.py ask "How long does it take to drive from Brightwater to Kestrelford?"`:

```
  (best distance 0.268, cutoff 0.65)

Driving from Brightwater to Kestrelford takes 55 minutes, with the last eight minutes on a single-track road that has passing places.

Source: guide_kestrelford.md

Sources retrieved: guide_brightwater.md, guide_kestrelford.md, guide_thornby_wells.md

1 model calls this session, 659 tokens (619 in, 40 out)
```

The answer names one file, and it is the file that holds the "55 minutes"
sentence, even though three files were retrieved. An off-topic question stops
at the gate before any model call:

```
$ python app.py ask "Who won the 1994 World Cup?"
  (best distance 0.982, cutoff 0.65)

I don't have enough information about that.

0 model calls this session
```

**My relevance cutoff:** 0.65 (`THRESHOLD` in `config.py`).

I ran the five test questions and the five `OUT_OF_SCOPE` questions through
`python app.py retrieve` with the section chunker and top-k 5, and wrote down
the best distance for each:

| Question | In corpus? | Best distance |
|---|---|---|
| How long does it take to drive from Brightwater to Kestrelford? | yes | 0.268 |
| By what time do the Halden Bay car parks fill up on summer weekends? | yes | 0.289 |
| How much does it cost to climb the parish church tower in Kestrelford? | yes | 0.402 |
| Which town in the region is the easiest to get around with limited mobility? | yes | 0.465 |
| When is the best time of year to visit Halden Bay? | yes | 0.192 |
| What is the capital of Mongolia? | no | 0.808 |
| How do I change the oil in a diesel engine? | no | 0.881 |
| Who won the 1994 World Cup? | no | 0.982 |
| What is the recommended dosage of ibuprofen for a headache? | no | 0.835 |
| How do I write a for loop in Rust? | no | 0.859 |

The two groups don't overlap: in-corpus tops out at 0.465, out-of-scope
bottoms out at 0.808, a gap of about 0.34. The starter's 0.6 would have worked.
I put the cutoff at 0.65 rather than the midpoint (0.64) or 0.6 because the
risk on each side isn't symmetric: the accessibility question was already at
0.465 with a fairly direct wording, and a real user asking "which of these
places is OK for a wheelchair" could plausibly land at 0.55 to 0.6 and deserve
an answer, whereas nothing off-topic came within 0.15 of 0.65. What I give up
at 0.65 versus 0.6: a question that's *near* the corpus (say, about a town
that isn't in it) is a little more likely to get through to the model, and
then the grounding instruction has to catch it.

Two things I noticed while reading the retrieved chunks:

- For the car-park question the closest chunk (0.289) was "Halden Bay — When
  to go", which mentions the parking problem but not the 10am time. The chunk
  with the actual answer was second at 0.326, and two more chunks that repeat
  the fact (the seasons guide and the regional transport guide) were also in
  the top five. Retrieval is reading "summer weekends" harder than "car park".
- For the accessibility question the answer chunk ("Straightforward", naming
  Thornby Wells) was fourth at 0.548, behind the guide's intro and its
  "Difficult" section. With top-k 3 it would not have been retrieved at all.
  That is why top-k stays at 5.

## How I Used AI

**1.** I used Claude Code for the chunker. I asked it to cut the guides at
their headings, and before writing code it measured every section in the
corpus: 98 sections, median 285 characters, longest 711, and four "sections"
of 23 to 27 characters that turned out to be bare `# Title` lines on the
cross-cutting guides. Cutting purely at headings would have turned those four
into content-free chunks, so the merge rule (fold anything under 120
characters into the next section) went in on the strength of that
measurement. I also asked for the `Town — Section` prefix on every chunk after
seeing that the retrieved "When to go" section for Halden Bay wouldn't say
which town it was about if the prefix weren't there.

**3. (unit 2)** I asked Claude Code to build `tools/criteria_table.py` to turn
the per-question results file into the per-criterion run log. Its first
version reported criterion 2 as 1/5 and criterion 5 as 0/5, which I knew
was wrong because I had just read fifteen answers with source lines. The
regex that pulled answers out of the run file used the dot-all flag and
swallowed every answer after the first into one match. Worth recording
because a scorer that silently under-counts is the kind of bug that turns
into a false MISSED in a run log, and the only reason it was caught is
that I read the raw answers first.

**4. (unit 2)** Before building hybrid search I asked it to run BM25 alone
over the 94 chunks for the two weak questions, which is where the evidence
in Diagnoses comes from. I did not ask it whether BM25 might hurt the other
three; the drive-time regression was found by the after run, not predicted.
The brief's suggested question ("tell me why that might not work") would
have surfaced the missing stemming: "driving takes" versus "drive" and
"take" is the kind of thing a model spots immediately when asked and never
mentions when not.

**2.** I asked Claude Code to run the five in-corpus and five out-of-scope
questions through retrieval and lay the distances side by side. It proposed
0.65 for the cutoff. I kept it, but the reasoning I wrote above is the part I
checked: it pointed out that the accessibility answer chunk came back at rank
4, and I confirmed that means top-k 3 would silently lose it, which is a
stronger reason to keep top-k at 5 than "start at 4 or 5" from the brief. It
also drafted the "Source:" line in the grounding instruction; I added the
"if two excerpts disagree, name both" rule after seeing that the same fact
(Halden Bay parking) appears in three different files, and I wanted the
citation to be the file the answer actually came from (criterion 5).

---

# Unit 2

<!-- These sections get ADDED to what's already above. Don't delete or rewrite
     unit 1 — the point is that someone can see what you said before you knew
     how it went. -->

## Run Log — Before

Produced by `python run_eval.py --label before` (file:
`results/run_2026-09-16_1716_before.md`, function `run_eval.py::main`), with
`scorer.py::judge` marking each answer, and aggregated one row per criterion by
`tools/criteria_table.py`. Same corpus, chunker, cutoff (0.65) and top-k (5) as
submitted in unit 1. Cache off, three real model calls per question.

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 2. Every answer names a source | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 4. Every chunk 120–900 chars, at most one heading | 94 of 94 | 94/94 | 94/94 | 94/94 | MET |
| 5. Named source contains the answer | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |

Criteria 1, 3 and 4 are the same in all three columns because retrieval,
the gate and the chunker are deterministic; one pass is the whole
measurement. Criteria 2 and 5 depend on the generated answer and were
checked against each of the three answers.

How each row was counted:

- **1.** `store.search` re-run per question; pass if any of the 5 returned
  chunks contains the `expects` phrase (case and whitespace ignored).
- **2.** The answer contains a `Source:` line naming at least one corpus file,
  and is not the refusal string.
- **3.** From the run file's gate table: 5 of 5 `OUT_OF_SCOPE` questions
  refused, best distances 0.808 to 0.982.
- **4.** `chunker.split_documents` re-run; every chunk checked for length and
  heading count. 94 chunks, zero violations.
- **5.** Every file the `Source:` line names contains the `expects` phrase.

Real output, one run per criterion:

**Criterion 1** — retrieval for the accessibility question, run 1
(`store.py::search`). The answer chunk came back, but fourth:

```
#   distance   source
1   0.4649     guide_accessibility.md#0   (intro: "An honest assessment rather than...")
2   0.5024     guide_accessibility.md#3   (Difficult)
3   0.5350     guide_corry_vale.md#2
4   0.5484     guide_accessibility.md#1   (Straightforward: "Thornby Wells is the easiest town...")
5   0.5514     guide_corry_vale.md#0
```

**Criterion 2 and 5** — the tower question, run 2 (`generate.py::answer_from_chunks`):

```
It costs £2 to climb the parish church tower in Kestrelford.

Source: guide_kestrelford.md
```

`guide_kestrelford.md` is the only file containing "£2".

**Criterion 3** — the gate table from the run file (`run_eval.py::check_out_of_scope`):

```
| Out-of-scope question | Best distance | Gate |
| What is the capital of Mongolia? | 0.808 | refused |
| How do I change the oil in a diesel engine? | 0.881 | refused |
| Who won the 1994 World Cup? | 0.982 | refused |
| What is the recommended dosage of ibuprofen for a headache? | 0.835 | refused |
| How do I write a for loop in Rust? | 0.859 | refused |
```

**Criterion 4** — `python app.py index` summary line (`chunker.py::describe`):

```
chunked  94 chunks, 317 characters on average (shortest 171, longest 757), produced by chunker.py::split_documents
```

**Criterion 2 and 5, the run that moved** — the car-park question across three
runs. The wording changed each time, the source line did not:

```
run 1: The Halden Bay car parks fill up by 10am on summer weekends.
run 2: On summer weekends, the parking lots in Halden Bay fill by 10am.
run 3: The parking lots in Halden Bay fill up by 10 am on summer weekends.
       Source: guide_halden_bay.md, guide_seasons.md, guide_regional_transport.md
```

Run 3 wrote "10 am" with a space against an `expects` of "10am". That is
why `scorer.py` compares with whitespace removed; a reader would not call
that answer wrong.

## Verdicts

Against the targets in `criteria.md` as written in unit 1. No criterion was
revised.

| # | Criterion | Verdict | How I decided |
|---|---|---|---|
| 1 | Retrieved chunks contain the answer, 4 of 5 | **MET** | 5 of 5 in every run, and retrieval is deterministic so the three columns can't differ. The honest caveat: two of the five only pass because top-k is 5. The accessibility answer was rank 4 and the car-park answer rank 2. At the "top 3" version of this criterion it would be 4 of 5, still met, but with no margin. |
| 2 | Every answer names a source, 5 of 5 | **MET** | All 15 answers ended with a `Source:` line naming a real corpus file, and none was the refusal string. Checked by regex in `tools/criteria_table.py`, then read by eye. |
| 3 | Gate stops out-of-corpus questions, 4 of 5 | **MET** | 5 of 5 refused, and the closest out-of-scope distance (0.808) is 0.16 above the cutoff. This was never close. |
| 4 | Every chunk 120–900 chars, at most one heading, all 94 | **MET** | Recomputed from `split_documents`: zero violations. The shortest chunk is 171 and the longest 757, so both bounds have room. |
| 5 | Named source contains the answer, 5 of 5 | **MET** | This was the one I expected to be close. The car-park answer named three files every run, and I counted it as a pass only because all three genuinely contain "10am" (the fact is repeated in the town guide, the seasons guide and the transport guide). Had it named a file that merely mentions Halden Bay parking without the time, it would have been a miss. |

The one I argued with myself over is criterion 5 on the car-park question.
Naming three sources for a one-number fact is not wrong, but it is less useful
than naming one, and the criterion as written can't tell the difference. That
is a measurement gap, not a miss; it goes in What I'd Do Differently rather
than as a revision, because the original still measures something real
(no wrong file was ever cited).

## Diagnoses

**No criterion was missed.** So the honest question is whether the targets
were safe. Partly, yes:

- Criterion 3 (gate, 4 of 5) was never in danger. The gap between the two
  groups of distances is 0.34 wide. "5 of 5" would have been the right target
  for this corpus, and I'd tighten it to that.
- Criterion 4 (chunk bounds) is a property of a deterministic function over a
  fixed corpus. Once it passed on the day I wrote the chunker it could not
  fail again without a code change. It measures something real, but three
  runs of it are theatre.
- Criterion 1 (4 of 5, top-k 5) is the one I'd tighten, and the run log
  shows exactly where it is weak. Retrieval got the answer chunk into the top
  5 for all five questions, but at these ranks:

| Question | Rank of the first chunk containing the answer |
|---|---|
| Drive time to Kestrelford | 1 |
| Halden Bay car parks | 2 |
| Kestrelford tower price | 1 |
| Easiest town with limited mobility | **4** |
| Best time for Halden Bay | 1 |

That is 4 of 5 at top-3 and 3 of 5 at top-1. Two of five answers are being
found by the margin top-k gives, not by retrieval ranking them where they
belong. That is a near miss, and it has a mechanism, so I'm diagnosing it as
if it were one.

**Stage: retrieval (embedding similarity).** Mechanism, two cases with the same
shape:

- *Halden Bay car parks.* The closest chunk (0.289) is "Halden Bay — When to
  go", which talks about "the parking problem" in July and August. It's about
  the right topic, but it never says 10am. The chunk with the answer,
  "Halden Bay — Getting there", is at 0.326. The embedding is matching the
  question's "summer weekends" to the seasonal chunk harder than it matches
  "car parks fill" to the chunk that literally says "fill by 10am". Semantic
  similarity is doing what it does: rewarding topical overlap, not the exact
  term.
- *Easiest town with limited mobility.* The top chunk (0.465) is the
  accessibility guide's intro, which says "some of these places are difficult"
  and nothing else. Second is its "Difficult" section. The "Straightforward"
  section, which opens with "Thornby Wells is the easiest town in the region",
  is fourth at 0.548. Same mechanism: every section of that guide is about
  mobility, so they all score similarly on meaning, and the one that contains
  the exact word "easiest" gets no credit for it.

**The pattern:** both weak questions contain an exact term ("fill", "easiest")
that appears in the answer chunk and not in its competitors, and the
competitors win on general topic. That is the textbook case for adding
keyword matching alongside the embedding. As a check before building
anything, I ran BM25 alone over the 94 chunks for these two questions
(`rank_bm25`, the package already in `requirements.txt`):

```
Halden Bay car parks:         BM25 rank 1 = guide_regional_transport.md#2 (contains "10am")
                              BM25 rank 2 = guide_halden_bay.md#1        (contains "10am")
Easiest with limited mobility: BM25 rank 1 = guide_accessibility.md#1     (the answer chunk)
```

Keyword search puts the answer at rank 1 or 2 for both questions where the
embedding had it at 2 and 4. That is what the improvement below is built on.

Not a diagnosis, but worth recording: the only non-determinism in the whole
system is the generated wording (three different phrasings of "fill by 10am",
one with a space). Nothing upstream of generation moved between runs.

## The Improvement

**What I changed:** hybrid search. `store.py::search` now retrieves the top 20
chunks by embedding distance, ranks all 94 chunks by BM25 keyword score
(`rank_bm25`, already in `requirements.txt`), fuses the two lists with
reciprocal rank fusion (score = Σ 1/(60 + rank)), and returns the fused top 5.
Every returned chunk keeps its real cosine distance, and the chunk the
embedding ranked first is always kept, so the relevance gate sees exactly the
same best distance as before and criterion 3 cannot move. `HYBRID_SEARCH = True`
in `config.py` is the switch; `False` gives back the unit 1 system exactly.
This is the only change to the pipeline in this unit. Chunker, cutoff, top-k,
prompt and model are as submitted.

**Why I picked it:** the diagnosis above found that for two of five questions
the answer chunk lost to neighbours that share the topic but not the exact
term ("fill", "easiest"), and that BM25 alone ranked those chunks first or
second. Keyword matching is the missing signal, so I added it.

### Run Log — After

Produced by `python run_eval.py --label after`
(`results/run_2026-09-16_1720_after.md`, `run_eval.py::main`), aggregated by
`tools/criteria_table.py`. Same five questions, same three runs, cache off.

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 2. Every answer names a source | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 4. Every chunk 120–900 chars, at most one heading | 94 of 94 | 94/94 | 94/94 | 94/94 | MET |
| 5. Named source contains the answer | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |

Side by side, the table is identical to Before. The criteria as written
cannot see this change, which is itself a finding (see What I'd Do
Differently). The number the diagnosis was actually about is the rank of the
answer chunk, and that did move:

| Question | Rank before (embedding only) | Rank after (hybrid) |
|---|---|---|
| Drive time to Kestrelford | 1 | **5** |
| Halden Bay car parks | 2 | **1** |
| Kestrelford tower price | 1 | 1 |
| Easiest town with limited mobility | 4 | **2** |
| Best time for Halden Bay | 1 | 1 |
| *Answer in top 3* | 4 of 5 | 4 of 5 |
| *Answer at rank 1* | 3 of 5 | 3 of 5 |

Real output after the change, accessibility question, run 1
(`generate.py::answer_from_chunks`):

```
According to the provided document, Thornby Wells is the easiest town in the region to get around with limited mobility because it is flat, compact, and everything is close together.

Source: guide_accessibility.md
```

**Did it help?** Partly, and it also broke something, and I can tell which
is which.

- It fixed the two cases the diagnosis named. The car-park answer chunk went
  from rank 2 to 1 and the accessibility chunk from rank 4 to 2. The
  mechanism worked as predicted: BM25 credited "fill" and "easiest".
- It hurt the drive-time question, which went from rank 1 to rank 5, and it
  is at 5 only because of the rule that always keeps the embedding's
  top chunk. Without that safeguard the answer would have dropped out of the
  top 5 entirely and criterion 1 would have gone to 4 of 5. The mechanism:
  BM25 has no stemming and no stop-word list, so "how long does it take to
  drive from Brightwater to Kestrelford" scores chunks on "long", "take",
  "from", "Brightwater", "Kestrelford". The answer chunk says "Driving takes
  55 minutes", and neither "driving" nor "takes" matches. BM25's top chunk
  for that question was "Walking in the region — Seasonal notes", which
  mentions both town names and the word "take", and the fusion let four such
  chunks outrank the real answer.
- Net on the measure I set out to move (answer in top 3): 4 of 5 before, 4
  of 5 after. Different question missing each time. So by my own metric it
  did not help, even though it fixed exactly what it was aimed at.

Criterion 3 is unchanged at 5 of 5 with identical distances (0.808 to 0.982),
as designed. Criteria 2 and 5 held at 5 of 5 on all three runs; the model
still cited the right file in every answer.

## What's Still Broken

No criterion is missed after the fix, so this section is about the thing the
criteria don't measure and the fix made visible.

**The drive-time regression.** The answer chunk for "How long does it take to
drive from Brightwater to Kestrelford?" is at rank 5 with hybrid search, held
there only by the keep-the-embedding's-best rule. What I'd do: two small
things to BM25, in this order, measuring after each. First, drop stop words
from the query before scoring ("how", "does", "it", "take", "to", "from" are
doing most of the damage). Second, weight the fusion toward the embedding,
for example 2/(60+rank) for the embedding list and 1/(60+rank) for BM25, so a
keyword-only hit needs to be strong to displace a semantic one. I expect the
first alone to move that question back to rank 1 or 2 without undoing the
gains on the other two. I stopped because the unit allows one change and
this would be a second tuning pass on it; the honest result of the first
pass is more useful to record than a tuned one would be.

**Multi-file citations.** The car-park answer names three files in every run.
All three contain the fact, so it passes criterion 5, but the reader gets
three places to look for one number. What I'd do: change the grounding
instruction from "name the file(s) you used" to "name the single file that
states the fact; name a second only if it adds something the first does
not." That's a prompt change, which is generation-stage, and not what my
diagnosis pointed at, so it waits.

**Everything else is not broken, it is untested.** Five questions is a small
test. Every question has an answer that sits inside one section, with one
exception that spans two. Nothing tests a question whose answer requires
two sections from two different towns ("which is cheaper to stay in, Halden
Bay or Kestrelford, in August?"), and nothing tests a question about a town
that sounds plausible but isn't in the corpus. I'd add both kinds before
trusting these numbers.

## What I'd Do Differently

Three of the five criteria I'd rewrite for the next unit.

**Criterion 1** is the big one. "The retrieved chunks include one that
contains the answer, 4 of 5" was met before and after a change that moved
the answer chunk from rank 1 to rank 5 on one question and from rank 4 to
rank 2 on another. A criterion that cannot see either of those movements is
not measuring retrieval quality, it is measuring whether top-k is big
enough. I'd write: *"For at least 4 of 5 questions, the chunk containing the
answer is in the top 3; for at least 3 of 5 it is rank 1."* Both numbers
were 4 of 5 and 3 of 5 in this unit, so those targets are set at where the
system actually is, and a change that helps or hurts would show.

**Criterion 3** was safe. 4 of 5 with a 0.34 gap between the groups was never
going to miss. I'd set it to 5 of 5 and add five *near-scope* questions to
`OUT_OF_SCOPE` (a town that isn't in the corpus, a train that doesn't exist)
with their own 4 of 5 target, because that is where a gate actually earns
its keep and I have no evidence about it.

**Criterion 4** is deterministic. It can only fail if the code changes, so
three runs of it are one run. I'd keep it as a check but I wouldn't count it
as one of the five; in its place I'd put something about the chunk prefix:
*"For all 5 questions, the top chunk names the town the question asks
about."* That would have caught the drive-time regression, where the top
fused chunk was about walking, not about getting to Kestrelford.

**Criterion 5** I'd keep, but tighten the wording so a three-file citation
for a one-file fact counts as a partial miss: *"names exactly the file(s)
that contain the fact, and no more than two."*

