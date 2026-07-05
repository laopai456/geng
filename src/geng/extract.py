"""[1.5] 从评论语料提取候选梗短语。

jieba 分词 → 词级 1-3 gram → 基线词表过滤 → 跨视频过滤 → top_k。
"""
from __future__ import annotations
import logging
import re
from collections import defaultdict
from pathlib import Path
import jieba
from .models import Comment
from . import config

log = logging.getLogger(__name__)

# 复用同一个 jieba 实例(避免重复初始化)
_tokenize = jieba.lcut

# 纯标点/符号/纯数字检测
_PURE_PUNCT = re.compile(r"^[\s\d\W]+$")
_PURE_DIGIT = re.compile(r"^\d+$")


def _load_baseline(path: Path | None = None) -> set[str]:
    """加载基线词表。"""
    path = path or config.BASELINE_WORDS_FILE
    if not path.exists():
        return set()
    words = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.add(line)
    return words


def _tokenize_comment(message: str) -> list[str]:
    """jieba 分词,去空白 token。"""
    return [t for t in _tokenize(message) if t.strip()]


def _phrase_ngrams(tokens: list[str], ns: tuple[int, ...] = (1, 2, 3)) -> list[str]:
    """词级 n-gram。把 n 个连续 token 直接拼接(中文短语不需要空格分隔)。"""
    out: list[str] = []
    for n in ns:
        for i in range(len(tokens) - n + 1):
            phrase = "".join(tokens[i : i + n])
            out.append(phrase)
    return out


def _is_valid_phrase(phrase: str, baseline: set[str], len_range: tuple[int, int]) -> bool:
    """短语是否值得作为候选。"""
    if not phrase:
        return False
    lo, hi = len_range
    if not (lo <= len(phrase) <= hi):
        return False
    if _PURE_DIGIT.match(phrase):
        return False
    if _PURE_PUNCT.match(phrase):
        return False
    # 整体在基线词表里 → 直接过滤
    if phrase in baseline:
        return False
    return True


def extract_candidates(
    comments: list[Comment],
    top_k: int | None = None,
    min_videos: int | None = None,
    ns: tuple[int, ...] = (1, 2, 3),
) -> list[str]:
    """从评论语料提取候选梗短语。

    Returns: 候选短语列表,按出现频次降序,长度 ≤ top_k。
    """
    top_k = top_k if top_k is not None else config.EXTRACT_TOP_K
    min_videos = min_videos if min_videos is not None else config.EXTRACT_MIN_VIDEOS
    baseline = _load_baseline()
    len_range = config.EXTRACT_PHRASE_LEN_RANGE

    # phrase -> {"count": int, "videos": set[str]}
    stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "videos": set()})

    for c in comments:
        tokens = _tokenize_comment(c.message)
        # 同一条评论内去重(一条评论重复说同一个词只算一次)
        phrases_in_comment = set(_phrase_ngrams(tokens, ns))
        for phrase in phrases_in_comment:
            if not _is_valid_phrase(phrase, baseline, len_range):
                continue
            stats[phrase]["count"] += 1
            stats[phrase]["videos"].add(c.video_bvid)

    # 跨视频过滤 + 排序
    candidates = [
        (phrase, s["count"], len(s["videos"]))
        for phrase, s in stats.items()
        if len(s["videos"]) >= min_videos
    ]
    # 主排序: count 降序;次排序: 跨视频数降序
    candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)

    result = [phrase for phrase, _, _ in candidates[:top_k]]
    log.info(
        "extract: %d 个短语通过过滤,取 top %d (跨视频≥%d)",
        len(candidates), len(result), min_videos,
    )
    return result
