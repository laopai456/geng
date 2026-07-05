from geng.filter import coarse_filter, is_pure_number, is_pure_date
from geng.models import HotItem

def _item(title, platform="weibo", hot=1000):
    return HotItem(id=f"{platform}-1", platform=platform, title=title, hot=hot, url="", fetched_at="2026-07-05")

def test_pure_number_excluded():
    assert is_pure_number("12345") is True
    assert is_pure_number("YYDS") is False

def test_pure_date_excluded():
    assert is_pure_date("2026年7月5日") is True
    assert is_pure_date("如何呢又能怎") is False

def test_length_filter():
    items = [_item("哦"), _item("这是一个非常非常非常非常非常长的标题超过十四字")]
    out = coarse_filter(items, date="2026-07-05")
    assert out == []

def test_star_excluded():
    out = coarse_filter([_item("迪丽热巴现身机场")], date="2026-07-05")
    assert out == []

def test_cross_platform_required():
    # 同标题只在一个平台,不过 MIN_PLATFORMS_CROSS=2
    items = [_item("如何呢又能怎", platform="weibo")]
    out = coarse_filter(items, date="2026-07-05")
    assert out == []

def test_cross_platform_passes():
    items = [
        _item("如何呢又能怎", platform="weibo", hot=1000),
        _item("如何呢又能怎", platform="bilibili", hot=2000),
    ]
    out = coarse_filter(items, date="2026-07-05")
    assert len(out) == 1
    assert out[0].title == "如何呢又能怎"
    assert set(out[0].platforms) == {"weibo", "bilibili"}
    assert out[0].hot_scores["bilibili"] == 2000
