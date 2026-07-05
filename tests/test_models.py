from geng.models import HotItem, Candidate, ClassifiedMeme, FinalMeme


def test_hotitem_creation():
    item = HotItem(id="weibo-1", platform="weibo", title="测试标题", hot=1000, url="http://x", fetched_at="2026-07-05")
    assert item.title == "测试标题"
    assert item.platform == "weibo"


def test_classifiedmeme_defaults():
    m = ClassifiedMeme(title="YYDS", date="2026-07-05", platforms=["weibo"], hot_scores={"weibo": 100})
    assert m.is_meme is None
    assert m.confidence == 0.0
    assert m.classify_reason == ""


def test_finalmeme_carries_classified_fields():
    f = FinalMeme(title="YYDS", date="2026-07-05", platforms=["weibo"], hot_scores={"weibo": 100},
                  confidence=0.9, classify_reason="网络缩写")
    assert f.definition is None
    assert f.origin is None


def test_finalmeme_from_classified_maps_all_fields():
    m = ClassifiedMeme(
        title="YYDS", date="2026-07-05", platforms=["weibo", "zhihu"],
        hot_scores={"weibo": 100, "zhihu": 50},
        is_meme=True, confidence=0.88, classify_reason="网络缩写",
        verified=True, bili_video_count=42,
    )
    f = FinalMeme.from_classified(m)
    assert f.title == m.title
    assert f.date == m.date
    assert f.platforms == m.platforms
    assert f.hot_scores == m.hot_scores
    assert f.confidence == m.confidence
    assert f.classify_reason == m.classify_reason
    assert f.verified == m.verified
    assert f.bili_video_count == m.bili_video_count
    # explain-stage fields start empty
    assert f.definition is None
    assert f.examples == []


def test_candidate_minimal():
    c = Candidate(title="梗", date="2026-07-05", platforms=["weibo"], hot_scores={"weibo": 1})
    assert c.platforms == ["weibo"]
