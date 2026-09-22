"""Normalise extracted text before it is chunked.

Deterministic, and it never rewrites wording: it only removes invisible artefacts of
PDF extraction and tidies whitespace. Punctuation, Unicode, ₹ and – are all kept.
"""
import re
import unicodedata

# Single characters some PDFs use for letter pairs. They look right, but the model
# would see "ﬁnd" and "find" as different text.
_LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"})
# Invisible characters: soft hyphen, zero-width space, word joiner, byte-order mark.
_INVISIBLE = re.compile("[­​⁠﻿]")
# Non-breaking and other unusual spaces, plus tab / form feed / vertical tab.
_ODD_SPACES = re.compile("[\t\f\v   -   　]")
# Remaining control characters (NUL included). Newlines are handled separately.
_CONTROL = re.compile("[\x00-\x08\x0e-\x1f\x7f]")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)  # one spelling per character, e.g. é
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(_LIGATURES)
    text = _INVISIBLE.sub("", text)
    text = _ODD_SPACES.sub(" ", text)
    text = _CONTROL.sub("", text)
    text = re.sub(r" {2,}", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)  # at most one blank line in a row
    return text.strip()
