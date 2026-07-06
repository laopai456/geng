"""[1.5] extract 模块测试: jieba 分词 + 词级 n-gram + 跨视频过滤。"""
from geng.extract import (
    _is_valid_phrase,
    _phrase_ngrams,
    extract_candidates,
)
from geng.models import Comment


# ---------------------------------------------------------------------------
# 1. ngram 生成
# ---------------------------------------------------------------------------
def test_phrase_ngrams_basic():
    # 默认 ns=(1,2,3)
    out = _phrase_ngrams(["打", "call"])
    assert "打" in out
    assert "call" in out
    assert "打call" in out


def test_phrase_ngrams_multichar_with_ns_2_3():
    out = _phrase_ngrams(["永远", "的", "神"], ns=(2, 3))
    assert "永远的" in out
    assert "的神" in out
    assert "永远的神" in out


# ---------------------------------------------------------------------------
# 2. 短语有效性过滤
# ---------------------------------------------------------------------------
def test_is_valid_phrase_rejects_short_long_digit_punct_baseline():
    baseline = {"的", "今天"}
    len_range = (2, 8)

    assert _is_valid_phrase("a", baseline, len_range) is False          # 太短
    assert _is_valid_phrase("这是一个超过八个字的短语测试", baseline, len_range) is False  # 太长 >8
    assert _is_valid_phrase("12345", baseline, len_range) is False      # 纯数字
    assert _is_valid_phrase("...", baseline, len_range) is False        # 纯标点
    assert _is_valid_phrase("的", baseline, len_range) is False         # 基线词
    assert _is_valid_phrase("YYDS", baseline, len_range) is True        # 有效


def test_is_valid_phrase_stopword_rule_filters_function_word_fragments():
    """双保险: 短词(≤3字)全由单字虚词组成 → 过滤,即便不在 baseline 里。
    长短语(如「破防了」)含虚词也保留。
    """
    baseline = {"的", "是", "就", "不", "还", "了"}   # 含单字虚词
    len_range = (2, 8)
    stopwords = {"的", "是", "就", "不", "还", "了"}

    # 虚词碎片 → 过滤
    assert _is_valid_phrase("就是", baseline, len_range, stopwords) is False
    assert _is_valid_phrase("不是", baseline, len_range, stopwords) is False
    assert _is_valid_phrase("还是", baseline, len_range, stopwords) is False
    assert _is_valid_phrase("了是", baseline, len_range, stopwords) is False

    # 真梗含虚词 → 保留(长度 >3 或含非虚词字)
    assert _is_valid_phrase("破防了", baseline, len_range, stopwords) is True
    assert _is_valid_phrase("爷青回", baseline, len_range, stopwords) is True
    assert _is_valid_phrase("YYDS", baseline, len_range, stopwords) is True


def test_is_valid_phrase_stopword_none_falls_back_to_baseline_only():
    """不传 stopwords(旧调用方式)→ 只走 baseline 整体匹配,兼容。"""
    baseline = {"的"}
    assert _is_valid_phrase("就是", baseline, (2, 8)) is True   # 不在 baseline,通过
    assert _is_valid_phrase("的", baseline, (2, 8)) is False


# ---------------------------------------------------------------------------
# 3. 跨视频命中
# ---------------------------------------------------------------------------
def test_extract_finds_repeated_phrase_across_videos(monkeypatch):
    """YYDS 在 3 个视频 5 条评论里出现,应能被提取。"""
    monkeypatch.setattr("geng.extract._load_baseline", lambda path=None: {"的", "今天"})

    comments = [
        Comment(video_bvid="BV1", message="YYDS 真是太好看了", likes=10),
        Comment(video_bvid="BV1", message="YYDS 永远的神", likes=5),
        Comment(video_bvid="BV2", message="YYDS 没谁了", likes=8),
        Comment(video_bvid="BV2", message="就是 YYDS 啊", likes=3),
        Comment(video_bvid="BV3", message="YYDS", likes=1),
        # 噪声
        Comment(video_bvid="BV1", message="的", likes=0),
        Comment(video_bvid="BV2", message="今天天气不错", likes=2),
    ]

    result = extract_candidates(comments, min_videos=2, top_k=30)
    assert "YYDS" in result


# ---------------------------------------------------------------------------
# 4. 单视频同质化过滤
# ---------------------------------------------------------------------------
def test_extract_filters_single_video_phrases(monkeypatch):
    """父与子 只在 BV1 反复出现 → 单视频,应被滤掉。"""
    monkeypatch.setattr("geng.extract._load_baseline", lambda path=None: set())

    comments = [
        Comment(video_bvid="BV1", message="父与子", likes=10),
    ] * 10  # 同一视频 10 条
    # 加一些来自其他视频但不含"父与子"的噪声,凑齐多视频场景
    comments += [
        Comment(video_bvid="BV2", message="其他评论内容", likes=1),
        Comment(video_bvid="BV3", message="无关评论", likes=1),
    ]

    result = extract_candidates(comments, min_videos=2, top_k=30)
    assert "父与子" not in result


# ---------------------------------------------------------------------------
# 5. 基线词过滤
# ---------------------------------------------------------------------------
def test_extract_filters_baseline_words(monkeypatch):
    """今天 跨 3 个视频,但在基线词表里 → 滤掉。"""
    monkeypatch.setattr("geng.extract._load_baseline", lambda path=None: {"今天"})

    comments = [
        Comment(video_bvid="BV1", message="今天真不错", likes=1),
        Comment(video_bvid="BV2", message="今天天气很好", likes=1),
        Comment(video_bvid="BV3", message="今天去玩了", likes=1),
    ]

    result = extract_candidates(comments, min_videos=2, top_k=30)
    assert "今天" not in result


# ---------------------------------------------------------------------------
# 6. top_k 上限
# ---------------------------------------------------------------------------
def test_extract_top_k_limits_output(monkeypatch):
    """构造多个跨视频命中短语,top_k=3 → 结果 ≤ 3。"""
    monkeypatch.setattr("geng.extract._load_baseline", lambda path=None: set())

    phrases = ["YYDS", "绝绝子", "破防了", "笑死我了", "真的会谢"]
    comments = []
    for p in phrases:
        for bv in ("BV1", "BV2"):
            comments.append(Comment(video_bvid=bv, message=p, likes=1))

    result = extract_candidates(comments, min_videos=2, top_k=3)
    assert len(result) <= 3


# ---------------------------------------------------------------------------
# 7. 空输入
# ---------------------------------------------------------------------------
def test_extract_empty_comments(monkeypatch):
    monkeypatch.setattr("geng.extract._load_baseline", lambda path=None: set())
    assert extract_candidates([], min_videos=2, top_k=30) == []


# ---------------------------------------------------------------------------
# 8. 按 count 降序
# ---------------------------------------------------------------------------
def test_extract_returns_sorted_by_count(monkeypatch):
    monkeypatch.setattr("geng.extract._load_baseline", lambda path=None: set())

    comments = []
    # 词组 A 出现 10 次,跨 2 视频
    for _ in range(5):
        comments.append(Comment(video_bvid="BV1", message="YYDS", likes=1))
        comments.append(Comment(video_bvid="BV2", message="YYDS", likes=1))
    # 词组 B 出现 5 次,跨 2 视频
    for _ in range(3):
        comments.append(Comment(video_bvid="BV1", message="绝绝子", likes=1))
        comments.append(Comment(video_bvid="BV2", message="绝绝子", likes=1))

    result = extract_candidates(comments, min_videos=2, top_k=30)
    assert "YYDS" in result
    assert "绝绝子" in result
    assert result.index("YYDS") < result.index("绝绝子")
