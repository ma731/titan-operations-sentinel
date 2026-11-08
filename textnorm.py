"""
Normalise action text before a keyword rule reads it.

The safety gate and the tier rules match words. Found by the red team (F-11): a model that
has been manipulated, or text copied from a poisoned document, can carry the same words in a
form a plain `in` check does not see: a zero-width space inside "bypass", Cyrillic letters
that look Latin, full-width characters, s p a c e d letters, or "byp4ss". The meaning is
unchanged for a person reading the plan, so the rules must not be fooled by it either.

Callers match the raw text AND the normalised text, so this can only add matches.
"""
from __future__ import annotations

import re
import unicodedata

_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­᠎"), None)
# Letters from other scripts that render like Latin ones (the common confusables).
_CONFUSABLE = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "к": "k", "м": "m", "т": "t", "в": "b", "н": "h", "ԁ": "d", "ɡ": "g", "ӏ": "l",
    "α": "a", "ε": "e", "ο": "o", "ρ": "p", "τ": "t", "ι": "i", "κ": "k", "ν": "v", "υ": "u", "χ": "x",
})
_LEET = str.maketrans({"4": "a", "@": "a", "3": "e", "1": "i", "!": "i", "0": "o", "5": "s", "$": "s", "7": "t"})
_SPACED = re.compile(r"\b(?:[a-z0-9@$!][ .\-_]){2,}[a-z0-9@$!]\b")
_MIXED = re.compile(r"(?=[\w@$!]*[a-z])(?=[\w@$!]*[0-9@$!])[\w@$!]+")


def normalize(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "").translate(_INVISIBLE).lower().translate(_CONFUSABLE)
    s = _SPACED.sub(lambda m: re.sub(r"[ .\-_]", "", m.group(0)), s)   # "b y p a s s" -> "bypass"
    return _MIXED.sub(lambda m: m.group(0).translate(_LEET), s)        # "byp4ss" -> "bypass"


def variants(text: str) -> tuple[str, str]:
    """The lower-cased raw text and its normalised form: match either."""
    return (text or "").lower(), normalize(text)
