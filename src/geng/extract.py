"""[1.5] 从评论语料提取候选梗短语。

预处理(去表情/标点/URL) → jieba 分词 → 词级 2-3 gram → 基线词表过滤 → 跨视频过滤 → top_k。
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

# B站文字表情: [doge] [笑哭] [OK] 等,方括号包裹的英文/中文
_BILI_EMOTE = re.compile(r"\[[^\[\]]{1,10}\]")
# URL
_URL = re.compile(r"https?://\S+|www\.\S+")
# @ 用户
_MENTION = re.compile(r"@\S+")
# 任何标点符号(中英文) — 用 Unicode 类别更稳: 所有非字母/非数字/非 CJK 字符
_PUNCT = re.compile(r"[^\w\u4e00-\u9fff]")
# 连续空白
_WS = re.compile(r"\s+")

# 短语内任何位置出现标点/数字 → 无效
# \W 在 re 默认 (re.UNICODE) 下匹配非 [a-zA-Z0-9_] 与非所有 Unicode 字母;
# 但我们要保留中日韩文,所以用反向: 含数字或 ASCII 标点 → 无效
_DIGIT_OR_ASCII_PUNCT = re.compile(r"[\d!-/:-@\[-`{-~]")


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


def _clean_message(message: str) -> str:
    """预处理: 去表情/URL/@用户/标点。只保留中英文字符(连成块)。"""
    s = _BILI_EMOTE.sub(" ", message)
    s = _URL.sub(" ", s)
    s = _MENTION.sub(" ", s)
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


def _tokenize_comment(message: str) -> list[str]:
    """预处理 + jieba 分词。返回 token 列表(已去标点/空白)。"""
    cleaned = _clean_message(message)
    if not cleaned:
        return []
    return [t for t in _tokenize(cleaned) if t.strip() and _is_meaningful_token(t)]


def _is_meaningful_token(tok: str) -> bool:
    """token 至少含一个中文字符或 2+ 连续英文字符。过滤纯数字/单字母碎片。"""
    if not tok:
        return False
    # 含中文
    if re.search(r"[一-鿿]", tok):
        return True
    # 2+ 连续英文(如 YYDS, call, doge)
    if re.search(r"[A-Za-z]{2,}", tok):
        return True
    return False


def _phrase_ngrams(tokens: list[str], ns: tuple[int, ...] = (1, 2, 3)) -> list[str]:
    """词级 n-gram。拼接 n 个连续 token。默认 1-3 gram(单 token 也算,靠 _is_valid_phrase 过滤)。"""
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
    # 含任何标点/数字 → 无效
    if _DIGIT_OR_ASCII_PUNCT.search(phrase):
        return False
    # 整体在基线词表里 → 直接过滤
    if phrase in baseline:
        return False
    return True


def extract_candidates(
    comments: list[Comment],
    top_k: int | None = None,
    min_videos: int | None = None,
    ns: tuple[int, ...] | None = None,
) -> list[str]:
    top_k = top_k if top_k is not None else config.EXTRACT_TOP_K
    min_videos = min_videos if min_videos is not None else config.EXTRACT_MIN_VIDEOS
    ns = ns if ns is not None else config.EXTRACT_NGRAM_NS
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
        if not tokens:
            continue
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
