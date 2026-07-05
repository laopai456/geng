import json
from pathlib import Path
from geng.store import init_db, save_to_db, query_by_date
from geng.models import FinalMeme

def _meme(title="YYDS", date="2026-07-05"):
    return FinalMeme(
        title=title, date=date, platforms=["weibo", "bilibili"],
        hot_scores={"weibo": 100}, confidence=0.9, classify_reason="缩写",
        verified=True, bili_video_count=234, definition="永远的神",
        origin="电竞圈", usage="赞美", examples=["科比YYDS"],
    )

def test_save_and_query(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    n = save_to_db([_meme()], date="2026-07-05", db_path=db)
    assert n == 1
    rows = query_by_date("2026-07-05", db_path=db)
    assert len(rows) == 1
    assert rows[0]["title"] == "YYDS"
    assert json.loads(rows[0]["platforms"]) == ["weibo", "bilibili"]
    assert rows[0]["verified"] == 1
    assert json.loads(rows[0]["examples"]) == ["科比YYDS"]

def test_dedup_same_title_same_date(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    save_to_db([_meme("YYDS", "2026-07-05")], date="2026-07-05", db_path=db)
    # 同一天同标题不重复
    save_to_db([_meme("YYDS", "2026-07-05")], date="2026-07-05", db_path=db)
    rows = query_by_date("2026-07-05", db_path=db)
    assert len(rows) == 1

def test_different_date_keeps_both(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    save_to_db([_meme("YYDS", "2026-07-05")], date="2026-07-05", db_path=db)
    save_to_db([_meme("YYDS", "2026-07-06")], date="2026-07-06", db_path=db)
    assert len(query_by_date("2026-07-05", db_path=db)) == 1
    assert len(query_by_date("2026-07-06", db_path=db)) == 1
