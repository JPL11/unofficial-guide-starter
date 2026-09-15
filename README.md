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

<!-- Your five criteria, three runs each. `python run_eval.py --label before`
     runs the questions, puts the OUT_OF_SCOPE ones through the gate, and
     writes it all into results/ for you. Targets come from criteria.md; the
     verdict column is your call.

     Criterion 3 is measured in one deterministic pass rather than three, so
     the same number goes in all three run columns. That's correct, not lazy.

     Milestone 1. -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 |  |  |  |  |
| 2. Every answer names a source | 5 of 5 |  |  |  |  |
| 3. Gate stops out-of-corpus questions | 4 of 5 |  |  |  |  |
| 4. | | | | | |
| 5. | | | | | |

<!-- Underneath, paste the REAL output for each criterion from one of your
     runs — the actual text your system produced, not a description of it.
     Name the file and function that produced it. -->

## Verdicts

<!-- MET or MISSED for each of the five, against the target you wrote last
     unit — not a new one. Plus a sentence on how you decided. That sentence
     matters most where it was close.

     If your target said 4 of 5 and your runs came out 4, 3, 4, that's a MISS.
     The target has to hold, not show up occasionally.

     Milestone 2. -->

| # | Criterion | Verdict | How I decided |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |
| 4 |  |  |  |
| 5 |  |  |  |

## Diagnoses

<!-- For each miss: which stage caused it, and how. The stage alone isn't
     enough — you need the mechanism.

     Not a diagnosis: "Question 3 didn't work."
     A diagnosis:     "Question 3 asks about laundry costs. The answer is in
                       one sentence that got split across two chunks, so
                       neither chunk on its own contains it."

     The five stages: loading → chunking → embedding → retrieval → generation.

     Look for a pattern. If three misses all ask about numbers, that's one
     problem, not three.

     Missed nothing? Say so, then say honestly whether your targets were set
     low, and which one you'd tighten and to what.

     Milestone 3. -->

## The Improvement

**What I changed:**

**Why I picked it:**

<!-- Connect it to a specific diagnosis above in one sentence. If you can't,
     you picked a fix because it sounded impressive. -->

### Run Log — After

<!-- Same format, same five criteria, three runs each.
     `python run_eval.py --label after` -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 |  |  |  |  |
| 2. Every answer names a source | 5 of 5 |  |  |  |  |
| 3. Gate stops out-of-corpus questions | 4 of 5 |  |  |  |  |
| 4. | | | | | |
| 5. | | | | | |

**Did it help?**

<!-- Say plainly whether it did, and how you know. If it made things worse,
     say that — a change that backfired, honestly reported, earns full credit
     and is more interesting than one that worked. What matters is that you can
     tell.

     Milestone 4. -->

## What's Still Broken

<!-- For each criterion still missed after your fix: what you'd do about it,
     and why you stopped where you did.

     "I ran out of time" is fine if it's true. Pretending nothing is left is
     not.

     Milestone 5. -->

## What I'd Do Differently

<!-- Knowing what you know now — which of your five criteria would you write
     differently, and why?

     Milestone 5. -->
