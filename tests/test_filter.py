# tests/test_filter.py
from geng.filter import coarse_filter, is_pure_number, is_pure_date

def test_pure_number_excluded():
    assert is_pure_number("12345") is True
    assert is_pure_number("YYDS") is False

def test_pure_date_excluded():
    assert is_pure_date("2026年7月5日") is True
    assert is_pure_date("YYDS") is False

def test_length_filter():
    # 太短 (<3) 和太长 (>14) 都被过滤
    out = coarse_filter(["哦", "这是一个非常非常非常非常非常长的标题超过十四字"], date="2026-07-05")
    assert out == []

def test_star_excluded():
    out = coarse_filter(["迪丽热巴现身机场"], date="2026-07-05")
    assert out == []

def test_normal_phrase_passes():
    out = coarse_filter(["YYDS"], date="2026-07-05")
    assert len(out) == 1
    assert out[0].title == "YYDS"
    assert out[0].platforms == ["bilibili"]

def test_phrase_counts_populate_hot_scores():
    out = coarse_filter(["YYDS"], date="2026-07-05", phrase_counts={"YYDS": 42})
    assert out[0].hot_scores == {"bilibili": 42}

def test_dedup_repeated_phrases():
    out = coarse_filter(["YYDS", "YYDS", "YYDS"], date="2026-07-05")
    assert len(out) == 1
