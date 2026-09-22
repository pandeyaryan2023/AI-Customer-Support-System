"""Split text into overlapping chunks of whole sentences.

Pure and deterministic: no database, no Ollama. The same text and settings always
give the same chunks.

    chunk 0: sentences 1-12   (up to max_words words)
    chunk 1: sentences 11-23  (starts by repeating the last ~overlap_words words)
    ...

Each chunk is an exact slice of the input, so wording, ₹, – and line breaks are untouched.
"""
import re
from dataclasses import dataclass
from typing import NamedTuple

# A sentence ends at . ! or ? (optionally followed by a closing quote or bracket) and
# then whitespace; a blank line also ends one. Single line breaks do NOT: in PDF text
# they are just where the printed line wrapped, often in the middle of a sentence.
_SENTENCE_END = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"'”’)\]]))\s+|\n\s*\n")


@dataclass(frozen=True)
class Chunk:
    index: int  # position in the document: 0, 1, 2, ...
    text: str
    word_count: int


class _Span(NamedTuple):
    """A piece of the text, by position: text[start:end] holds `words` words."""

    start: int
    end: int
    words: int


def chunk_text(text: str, max_words: int, overlap_words: int) -> list[Chunk]:
    if max_words < 1 or not 0 <= overlap_words < max_words:
        raise ValueError("need max_words >= 1 and 0 <= overlap_words < max_words")
    units = _units(text, max_words)
    chunks: list[Chunk] = []
    first = 0
    while first < len(units):
        # Take whole units while they fit in the word budget.
        last, words = first, 0
        while last < len(units) and words + units[last].words <= max_words:
            words += units[last].words
            last += 1
        chunks.append(Chunk(len(chunks), text[units[first].start:units[last - 1].end], words))
        if last == len(units):
            break
        first = _overlap_start(units, first, last, overlap_words, max_words)
    return chunks


def _units(text: str, max_words: int) -> list[_Span]:
    """Sentences, except that a "sentence" longer than a whole chunk (text with no
    punctuation, say) is broken into single words so it can still be split."""
    units = []
    for start, end in _sentence_spans(text):
        words = len(text[start:end].split())
        if words <= max_words:
            units.append(_Span(start, end, words))
        else:
            units.extend(_Span(start + m.start(), start + m.end(), 1)
                         for m in re.finditer(r"\S+", text[start:end]))
    return units


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for boundary in _SENTENCE_END.finditer(text):
        if text[start:boundary.start()].strip():
            spans.append((start, boundary.start()))
        start = boundary.end()
    if text[start:].strip():
        spans.append((start, len(text.rstrip())))
    return spans


def _overlap_start(units: list[_Span], first: int, last: int, overlap_words: int, max_words: int) -> int:
    """Where the next chunk starts: step back over whole units at the end of the chunk
    just made, up to overlap_words words. Always leaves room for at least one new unit,
    and always moves forward, so the loop cannot repeat or run forever."""
    room = min(overlap_words, max_words - units[last].words)
    start, words = last, 0
    while start - 1 > first and words + units[start - 1].words <= room:
        start -= 1
        words += units[start].words
    return start
