# tests/test_pipeline.py
from geng.pipeline import run_daily
from geng.store import init_db, query_by_date

def test_run_daily_end_to_end(tmp_path, monkeypatch):
    db_path = tmp_path / "memes.db"
    report_dir = tmp_path / "daily"
    init_db(db_path)

    # mock discover
    from geng.models import HotItem
    fake_items = [
        HotItem(id="w1", platform="weibo", title="YYDS", hot=1000, url="", fetched_at="2026-07-05"),
        HotItem(id="b1", platform="bilibili", title="YYDS", hot=2000, url="", fetched_at="2026-07-05"),
        HotItem(id="w2", platform="weibo", title="某明星离婚", hot=5000, url="", fetched_at="2026-07-05"),
        HotItem(id="b2", platform="bilibili", title="某明星离婚", hot=3000, url="", fetched_at="2026-07-05"),
    ]
    monkeypatch.setattr("geng.pipeline.discover.fetch_trending", lambda **kw: fake_items)

    # mock classify / explain —— 用 messages 长度区分:
    # classify 发 system+user(2条),explain 只发 user(1条)
    class FakeLLM:
        def chat(self, model, messages):
            if len(messages) >= 2:
                return '{"items":[{"title":"YYDS","is_meme":true,"confidence":0.9,"reason":"缩写"},{"title":"某明星离婚","is_meme":false,"confidence":0.1,"reason":"八卦"}]}'
            return '{"definition":"永远的神","origin":"电竞","usage":"赞美","examples":["科比YYDS"]}'
    monkeypatch.setattr("geng.pipeline.classify.DeepSeekClient", lambda *a, **kw: FakeLLM())
    monkeypatch.setattr("geng.pipeline.explain.DeepSeekClient", lambda *a, **kw: FakeLLM())

    # mock bili
    class FakeBili:
        def search_count(self, kw): return 234
    monkeypatch.setattr("geng.pipeline.verify.HttpxBiliClient", lambda *a, **kw: FakeBili())

    n = run_daily(date="2026-07-05", db_path=db_path, report_dir=report_dir)
    assert n == 1   # 只有 YYDS
    rows = query_by_date("2026-07-05", db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["title"] == "YYDS"
    assert (report_dir / "2026-07-05.md").exists()

def test_run_daily_degrades_when_llm_fails(tmp_path, monkeypatch):
    """LLM 分类挂掉时,粗筛候选仍入库(标记为降级)。"""
    db_path = tmp_path / "memes.db"
    report_dir = tmp_path / "daily"
    init_db(db_path)

    from geng.models import HotItem
    fake_items = [
        HotItem(id="w1", platform="weibo", title="YYDS", hot=1000, url="", fetched_at="2026-07-05"),
        HotItem(id="b1", platform="bilibili", title="YYDS", hot=2000, url="", fetched_at="2026-07-05"),
    ]
    monkeypatch.setattr("geng.pipeline.discover.fetch_trending", lambda **kw: fake_items)

    class FailingLLM:
        def chat(self, model, messages): raise RuntimeError("500")
    monkeypatch.setattr("geng.pipeline.classify.DeepSeekClient", lambda *a, **kw: FailingLLM())
    monkeypatch.setattr("geng.pipeline.explain.DeepSeekClient", lambda *a, **kw: FailingLLM())
    class FakeBili:
        def search_count(self, kw): return 234
    monkeypatch.setattr("geng.pipeline.verify.HttpxBiliClient", lambda *a, **kw: FakeBili())

    n = run_daily(date="2026-07-05", db_path=db_path, report_dir=report_dir)
    # 分类失败降级,粗筛候选(YYDS)仍入库
    assert n == 1
    rows = query_by_date("2026-07-05", db_path=db_path)
    assert "降级" in rows[0]["classify_reason"]
