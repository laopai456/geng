from geng.verify import verify_bilibili, parse_bili_count, BiliSearchClient
from geng.models import ClassifiedMeme

def _meme(title, is_meme=True):
    return ClassifiedMeme(
        title=title, date="2026-07-05", platforms=["weibo", "bilibili"],
        hot_scores={"weibo": 100}, is_meme=is_meme, confidence=0.9,
    )

def test_parse_bili_count_handles_response():
    raw = {"data": {"numResults": 234}}
    assert parse_bili_count(raw) == 234

def test_parse_bili_count_handles_missing():
    assert parse_bili_count({}) is None
    assert parse_bili_count({"data": {}}) is None

def test_verify_marks_above_threshold():
    class MockClient:
        def search_count(self, keyword): return 100
    out = verify_bilibili([_meme("YYDS")], client=MockClient())
    assert out[0].verified is True
    assert out[0].bili_video_count == 100

def test_verify_marks_below_threshold():
    class MockClient:
        def search_count(self, keyword): return 5
    out = verify_bilibili([_meme("冷门")], client=MockClient())
    assert out[0].verified is False
    assert out[0].bili_video_count == 5

def test_verify_handles_failure():
    class MockClient:
        def search_count(self, keyword): raise RuntimeError("503")
    out = verify_bilibili([_meme("YYDS")], client=MockClient())
    assert out[0].verified is None
    assert out[0].bili_video_count is None
