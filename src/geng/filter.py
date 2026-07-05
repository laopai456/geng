"""[2] 规则粗筛: 排除明显非梗,合并跨平台共振。"""
from __future__ import annotations
import re
from collections import defaultdict
from .models import HotItem, Candidate
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

def coarse_filter(items: list[HotItem], date: str) -> list[Candidate]:
    """应用粗筛规则,按标题分组合并跨平台。"""
    lo, hi = config.MEME_LENGTH_RANGE
    stars = _load_exclude_list("stars.txt")
    places = _load_exclude_list("places.txt")
    shows = _load_exclude_list("shows.txt")
    exclude_words = stars + places + shows

    survived: list[HotItem] = []
    for it in items:
        t = it.title
        if not t:
            continue
        if not (lo <= len(t) <= hi):
            continue
        if is_pure_number(t) or is_pure_date(t):
            continue
        if _matches_exclude(t, exclude_words):
            continue
        survived.append(it)

    groups: dict[str, list[HotItem]] = defaultdict(list)
    for it in survived:
        groups[it.title].append(it)

    candidates: list[Candidate] = []
    for title, group in groups.items():
        platforms = sorted({g.platform for g in group})
        if len(platforms) < config.MIN_PLATFORMS_CROSS:
            continue
        hot_scores: dict[str, int] = {}
        for g in group:
            hot_scores[g.platform] = max(hot_scores.get(g.platform, 0), g.hot)
        candidates.append(Candidate(
            title=title, date=date, platforms=platforms, hot_scores=hot_scores
        ))
    return candidates
