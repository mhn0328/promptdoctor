"""Rough offline token estimation.

promptlint deliberately ships no tokenizer and makes no network calls: the
numbers below are good enough to spot a 4x bigger prompt, not to predict an
invoice. Most modern BPE vocabularies land around 1.3 tokens per English word
and roughly 0.7 tokens per CJK character, which is what we approximate here.
"""

from __future__ import annotations

import re

_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]")
_WORD = re.compile(r"[A-Za-z0-9_]+")
_PUNCT = re.compile(r"[^\sA-Za-z0-9_\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]")

ENGLISH_TOKENS_PER_WORD = 1.3
CJK_TOKENS_PER_CHAR = 0.7
PUNCT_TOKENS_PER_CHAR = 0.9


def estimate_tokens(text: str) -> int:
    """Return an approximate token count for ``text``.

    The estimate mixes three signals: CJK characters (roughly one token each),
    latin words and leftover punctuation. Expect it to be within ~20% of a real
    tokenizer for prose, and to be conservative for code.
    """
    if not text:
        return 0

    cjk_chars = len(_CJK.findall(text))
    without_cjk = _CJK.sub(" ", text)
    word_tokens = ENGLISH_TOKENS_PER_WORD * len(_WORD.findall(without_cjk))
    punct_tokens = PUNCT_TOKENS_PER_CHAR * len(_PUNCT.findall(without_cjk))

    return max(1, round(cjk_chars * CJK_TOKENS_PER_CHAR + word_tokens + punct_tokens))
