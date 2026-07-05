import json
import logging
from pathlib import Path
from geng.discover import fetch_trending, parse_platform_response
from geng.models import HotItem

FIXTURE = Path(__file__).parent / "fixtures" / "weibo_sample.json"


def test_parse_platform_response():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    items = parse_platform_response(raw, platform="weibo", date="2026-07-05")
    assert len(items) == 3
    assert isinstance(items[0], HotItem)
    assert items[0].platform == "weibo"
    assert items[0].hot == 5000000
    assert items[1].id == "weibo-2"


def test_fetch_trending_with_mock_client(monkeypatch):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    class FakeClient:
        def get_json(self, platform):
            return raw

    items = fetch_trending(["weibo"], date="2026-07-05", client=FakeClient())
    assert len(items) == 3
    assert all(i.platform == "weibo" for i in items)


def test_fetch_trending_skips_failed_platform(monkeypatch, caplog):
    class FlakyClient:
        def get_json(self, platform):
            if platform == "bilibili":
                raise RuntimeError("503")
            return json.loads(FIXTURE.read_text(encoding="utf-8"))

    with caplog.at_level(logging.WARNING):
        items = fetch_trending(["weibo", "bilibili"], date="2026-07-05", client=FlakyClient())
    assert len(items) == 3  # bilibili 挂了,weibo 仍返回
    assert any("bilibili" in r.getMessage() for r in caplog.records)
