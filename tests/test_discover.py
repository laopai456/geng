"""discover 模块测试。

新架构: 每个平台一个独立 fetcher 函数(返回 list[HotItem]),
通过 monkeypatch FETCHERS 字典注入 mock,避免真实 HTTP。
"""
import logging
from geng.discover import fetch_trending, fetch_weibo, fetch_bilibili, FETCHERS
from geng.models import HotItem


def _fake_weibo(date):
    return [
        HotItem(id="weibo-1", platform="weibo", title="某明星离婚", hot=5000000, url="http://x", fetched_at=date),
        HotItem(id="weibo-2", platform="weibo", title="如何呢又能怎", hot=1200000, url="http://x", fetched_at=date),
    ]


def _fake_bili(date):
    return [
        HotItem(id="bilibili-1", platform="bilibili", title="YYDS", hot=2000, url="", fetched_at=date),
    ]


def test_fetch_weibo_returns_hotitems(monkeypatch):
    """fetch_weibo 单元测试: mock httpx 返回微博格式 JSON。"""
    fake_json = {
        "data": {
            "realtime": [
                {"word": "YYDS", "num": "1000"},
                {"word": "#测试#", "num": "500"},
                {"word": "", "num": "0"},  # 空标题被过滤
            ]
        }
    }

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return fake_json

    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): return FakeResp()

    monkeypatch.setattr("geng.discover.httpx.Client", FakeClient)
    items = fetch_weibo("2026-07-05")
    assert len(items) == 2          # 空标题被过滤
    assert items[0].title == "YYDS"
    assert items[0].hot == 1000     # 字符串转 int
    assert items[0].platform == "weibo"
    # 微博 # 标记被去掉
    assert items[1].title == "测试"


def test_fetch_bilibili_returns_hotitems(monkeypatch):
    """fetch_bilibili: 容错多种字段名(show_name / keyword)。"""
    fake_json = {
        "data": {
            "list": [
                {"show_name": "热门梗A", "hot_id": "999"},
                {"keyword": "无show_name", "hot_id": "100"},
            ]
        }
    }

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return fake_json

    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, params=None): return FakeResp()

    monkeypatch.setattr("geng.discover.httpx.Client", FakeClient)
    items = fetch_bilibili("2026-07-05")
    assert len(items) == 2
    assert items[0].title == "热门梗A"  # 优先 show_name
    assert items[1].title == "无show_name"  # 回退到 keyword


def test_fetch_trending_dispatches_to_fetchers(monkeypatch):
    """fetch_trending 应调用 FETCHERS 中注册的 fetcher。"""
    monkeypatch.setitem(FETCHERS, "weibo", _fake_weibo)
    monkeypatch.setitem(FETCHERS, "bilibili", _fake_bili)
    items = fetch_trending(["weibo", "bilibili"], date="2026-07-05")
    assert len(items) == 3
    platforms = {i.platform for i in items}
    assert platforms == {"weibo", "bilibili"}


def test_fetch_trending_skips_failed_platform(monkeypatch, caplog):
    """某 fetcher 抛异常时不阻塞其余,记 warning。"""
    def _failing(date):
        raise RuntimeError("503")

    monkeypatch.setitem(FETCHERS, "weibo", _fake_weibo)
    monkeypatch.setitem(FETCHERS, "bilibili", _failing)
    with caplog.at_level(logging.WARNING):
        items = fetch_trending(["weibo", "bilibili"], date="2026-07-05")
    assert len(items) == 2  # bilibili 挂了,weibo 仍返回
    assert any("bilibili" in r.getMessage() for r in caplog.records)


def test_fetch_trending_unknown_platform_skipped(monkeypatch, caplog):
    """未注册的平台被跳过并记 warning。"""
    monkeypatch.setitem(FETCHERS, "weibo", _fake_weibo)
    with caplog.at_level(logging.WARNING):
        items = fetch_trending(["weibo", "tiktok"], date="2026-07-05")
    assert len(items) == 2  # 只有 weibo
    assert any("tiktok" in r.getMessage() for r in caplog.records)
