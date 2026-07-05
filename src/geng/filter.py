"""[2] 规则粗筛: 对候选短语应用排除清单(明星/地名/节目)。"""
from __future__ import annotations
import re
from .models import Candidate
from . import config

_PURE_NUMBER = re.compile(r"^[\d.,]+$")
_PURE_DATE = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")

def is_pure_number(text: str) -> bool:
    return bool(_PURE_NUMBER.match(text.strip()))

def is_pure_date(text: str) -> bool:
    return bool(_PURE_DATE.search(text))

def _load_exclude_list(name: str) -> list[str]:
    path = config.EXCLUDE_LISTS_DIR / name
    if not path.exists():
        return []
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line)
    return words

def _matches_exclude(title: str, exclude_words: list[str]) -> bool:
    return any(w in title for w in exclude_words)

def coarse_filter(
    phrases: list[str],
    date: str,
    phrase_counts: dict[str, int] | None = None,
) -> list[Candidate]:
    """对候选短语应用排除清单(明星/地名/节目)。

    phrases: 来自 extract 的候选短语
    date: ISO date
    phrase_counts: 可选,{phrase: 出现次数},填入 Candidate.hot_scores["bilibili"]
    """
    lo, hi = config.MEME_LENGTH_RANGE
    stars = _load_exclude_list("stars.txt")
    places = _load_exclude_list("places.txt")
    shows = _load_exclude_list("shows.txt")
    exclude_words = stars + places + shows
    phrase_counts = phrase_counts or {}

    candidates: list[Candidate] = []
    seen: set[str] = set()
    for phrase in phrases:
        if not phrase:
            continue
        if phrase in seen:
            continue
        if not (lo <= len(phrase) <= hi):
            continue
        # extract 已经过滤纯数字/纯日期,这里保留作为防御
        if is_pure_number(phrase) or is_pure_date(phrase):
            continue
        if _matches_exclude(phrase, exclude_words):
            continue
        seen.add(phrase)
        candidates.append(Candidate(
            title=phrase,
            date=date,
            platforms=["bilibili"],
            hot_scores={"bilibili": phrase_counts.get(phrase, 0)},
        ))
    return candidates
