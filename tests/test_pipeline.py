# tests/test_pipeline.py
from geng.pipeline import run_daily
from geng.store import init_db, query_by_date
from geng.models import Comment


def _cmt(bvid, msg):
    return Comment(video_bvid=bvid, message=msg, likes=10)


def test_run_daily_end_to_end(tmp_path, monkeypatch):
    db_path = tmp_path / "memes.db"
    report_dir = tmp_path / "daily"
    init_db(db_path)

    # mock discover: 返回 (videos, comments)。评论里多次出现真梗 "YYDS" 跨多个视频
    fake_comments = [
        _cmt("BV1", "这游戏YYDS"),
        _cmt("BV1", "YYDS 永远的神"),
        _cmt("BV2", "科比YYDS"),
        _cmt("BV2", "YYDS没毛病"),
        _cmt("BV3", "YYDS"),
        # 噪音
        _cmt("BV1", "的"),
        _cmt("BV2", "今天天气不错"),
    ]
    monkeypatch.setattr("geng.pipeline.discover.collect_corpus",
                        lambda **kw: (["BV1", "BV2", "BV3"], fake_comments))

    # mock extract: 直接返回候选(绕过 jieba)
    monkeypatch.setattr("geng.pipeline.extract.extract_candidates",
                        lambda comments, **kw: ["YYDS"])

    # mock classify: YYDS 是梗
    class FakeLLM:
        def chat(self, model, messages):
            if len(messages) >= 2:  # classify 发 system+user
                return '{"items":[{"title":"YYDS","is_meme":true,"confidence":0.95,"reason":"缩写"}]}'
            return '{"definition":"永远的神","origin":"电竞","usage":"赞美","examples":["科比YYDS"]}'
    monkeypatch.setattr("geng.pipeline.classify.DeepSeekClient", lambda *a, **kw: FakeLLM())
    monkeypatch.setattr("geng.pipeline.explain.DeepSeekClient", lambda *a, **kw: FakeLLM())

    # mock bili verify
    class FakeBili:
        def search_count(self, kw): return 5000
    monkeypatch.setattr("geng.pipeline.verify.HttpxBiliClient", lambda *a, **kw: FakeBili())

    n = run_daily(date="2026-07-05", db_path=db_path, report_dir=report_dir)
    assert n == 1
    rows = query_by_date("2026-07-05", db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["title"] == "YYDS"
    assert (report_dir / "2026-07-05.md").exists()


def test_run_daily_degrades_when_llm_fails(tmp_path, monkeypatch):
    """LLM 分类挂掉,候选仍入库(降级标记)。"""
    db_path = tmp_path / "memes.db"
    report_dir = tmp_path / "daily"
    init_db(db_path)

    fake_comments = [_cmt("BV1", "YYDS"), _cmt("BV2", "YYDS"), _cmt("BV3", "YYDS")]
    monkeypatch.setattr("geng.pipeline.discover.collect_corpus",
                        lambda **kw: (["BV1", "BV2", "BV3"], fake_comments))
    monkeypatch.setattr("geng.pipeline.extract.extract_candidates",
                        lambda comments, **kw: ["YYDS"])

    class FailingLLM:
        def chat(self, model, messages): raise RuntimeError("500")
    monkeypatch.setattr("geng.pipeline.classify.DeepSeekClient", lambda *a, **kw: FailingLLM())
    monkeypatch.setattr("geng.pipeline.explain.DeepSeekClient", lambda *a, **kw: FailingLLM())
    class FakeBili:
        def search_count(self, kw): return 5000
    monkeypatch.setattr("geng.pipeline.verify.HttpxBiliClient", lambda *a, **kw: FakeBili())

    n = run_daily(date="2026-07-05", db_path=db_path, report_dir=report_dir)
    assert n == 1
    rows = query_by_date("2026-07-05", db_path=db_path)
    assert "降级" in rows[0]["classify_reason"]
