"""
Stage 2 of the pipeline: splitting documents into chunks.

⚠️ THIS IS THE FILE YOU CHANGE IN MILESTONE 3.

`split_documents` below is deliberately plain. It cuts every document into
fixed-size pieces with a fixed overlap and pays no attention to where sentences
or paragraphs end. It works, and it is not good.

On a corpus of short posts it may not cut anything at all: `campus_life` comes
out as 88 documents and 88 chunks, because almost nothing in it reaches 800
characters. That is the baseline, not a bug — Milestone 3 is where you decide
whether one post should stay one chunk.

Your job in Milestone 3 is to replace the *body* of `split_documents` with a
strategy that fits the documents you actually read in Milestone 1. Keep the
name and the shape of what it returns — the rest of the pipeline calls it, and
your README has to name the function that produced your chunks.

If you get stuck for 30 minutes, `fallback_split` is the original. Switch back
to it, write down what you saw, and move on. That's a real observation about
your pipeline, not giving up.
"""

import re
from dataclasses import dataclass

import config
from ingest import Document


@dataclass
class Chunk:
    """One piece of one document."""

    text: str
    source: str        # which file it came from
    index: int         # which chunk within that file, starting at 0
    produced_by: str   # the function that made it — cite this in your README

    @property
    def label(self) -> str:
        return f"{self.source}#{self.index}"


def fallback_split(
    documents: list[Document],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """
    The starter's original chunker. Fixed-size character windows with overlap.

    Keep this function. Milestone 3's stop rule points back at it, and having
    something to compare your own strategy against is useful in unit 2.
    """
    chunk_size = chunk_size or config.CHUNK_SIZE
    overlap = overlap or config.CHUNK_OVERLAP

    if overlap >= chunk_size:
        raise ValueError("overlap has to be smaller than chunk_size")

    chunks: list[Chunk] = []
    for doc in documents:
        start = 0
        index = 0
        while start < len(doc.text):
            piece = doc.text[start : start + chunk_size].strip()
            if piece:
                chunks.append(
                    Chunk(
                        text=piece,
                        source=doc.source,
                        index=index,
                        produced_by="chunker.py::fallback_split",
                    )
                )
                index += 1
            start += chunk_size - overlap

    return chunks


# Sections shorter than this are merged into the section that follows them.
# In city_guides the only things this catches are the bare "# Title" lines on
# the four cross-cutting guides, which have no paragraph under them.
MIN_SECTION_CHARS = 120

# Sections longer than this get split again at a paragraph break. Nothing in
# city_guides reaches it (longest section is 711 characters), so it is a
# guard against a bigger corpus, not something that fires today.
MAX_SECTION_CHARS = 900


def _sections(text: str) -> list[tuple[str, str]]:
    """
    Split one markdown document into (heading, body) pairs at each '#' or
    '##' heading line. Text before the first heading gets an empty heading.
    """
    sections: list[tuple[str, str]] = []
    heading = ""
    body: list[str] = []
    for line in text.split("\n"):
        if re.match(r"^#{1,2} ", line):
            if body or heading:
                sections.append((heading, "\n".join(body).strip()))
            heading = line.lstrip("#").strip()
            body = []
        else:
            body.append(line)
    if body or heading:
        sections.append((heading, "\n".join(body).strip()))
    return sections


def _split_long(body: str, limit: int) -> list[str]:
    """Split an over-long body at paragraph breaks, keeping paragraphs whole."""
    pieces: list[str] = []
    current = ""
    for para in re.split(r"\n\s*\n", body):
        para = para.strip()
        if not para:
            continue
        candidate = f"{current}\n\n{para}" if current else para
        if current and len(candidate) > limit:
            pieces.append(current)
            current = para
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def split_documents(documents: list[Document]) -> list[Chunk]:
    """
    One labelled section = one chunk.

    Every city_guides document is a "# Town" title, an intro paragraph, and
    then a run of "## Getting there", "## Eat and drink", "## When to go" ...
    sections, each one a single paragraph of roughly 170 to 710 characters.
    The information a question wants is organised by heading, so the heading
    is the right place to cut. Concretely:

      - Cut at every '#' / '##' heading line.
      - Prefix each chunk with "Town — Section" so a chunk still says which
        town it is about after it has been pulled away from its document.
        Without that, "Everything closes by 9pm" is true of some town and
        useless on its own.
      - Fold sections under MIN_SECTION_CHARS into the next section. That is
        how the bare title line of guide_seasons.md ends up attached to its
        first season instead of becoming a 26-character chunk.
      - Re-split anything over MAX_SECTION_CHARS at a paragraph break.
      - No character overlap. Sections do not share sentences, so overlap
        would only copy the end of "Getting there" into "Getting around".
    """
    chunks: list[Chunk] = []
    for doc in documents:
        sections = _sections(doc.text)
        title = sections[0][0] if sections and sections[0][0] else doc.source

        # Merge fragments into the section that follows them.
        merged: list[tuple[str, str]] = []
        pending_heading, pending_body = "", ""
        for heading, body in sections:
            if pending_body:
                body = f"{pending_body}\n\n{body}".strip()
                heading = heading or pending_heading
                pending_heading, pending_body = "", ""
            if len(body) < MIN_SECTION_CHARS:
                pending_heading, pending_body = heading, body
                continue
            merged.append((heading, body))
        if pending_body:
            if merged:
                h, b = merged[-1]
                merged[-1] = (h, f"{b}\n\n{pending_body}".strip())
            else:
                merged.append((pending_heading, pending_body))

        index = 0
        for heading, body in merged:
            for piece in _split_long(body, MAX_SECTION_CHARS):
                if heading and heading != title:
                    text = f"{title} — {heading}\n{piece}"
                else:
                    text = f"{title}\n{piece}"
                chunks.append(
                    Chunk(
                        text=text,
                        source=doc.source,
                        index=index,
                        produced_by="chunker.py::split_documents",
                    )
                )
                index += 1
    return chunks


def describe(chunks: list[Chunk]) -> str:
    """A one-line summary, printed after indexing."""
    if not chunks:
        return "0 chunks"
    lengths = [len(c.text) for c in chunks]
    return (
        f"{len(chunks)} chunks, "
        f"{sum(lengths) // len(lengths)} characters on average "
        f"(shortest {min(lengths)}, longest {max(lengths)}), "
        f"produced by {chunks[0].produced_by}"
    )


if __name__ == "__main__":
    from ingest import load_documents

    chunks = split_documents(load_documents())
    print(describe(chunks))
