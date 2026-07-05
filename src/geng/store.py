"""[6] SQLite 读写。JSON 字段以文本存。"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from .models import FinalMeme
from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    date             TEXT NOT NULL,
    platforms        TEXT NOT NULL,
    hot_scores       TEXT,
    confidence       REAL,
    classify_reason  TEXT,
    verified         INTEGER,
    bili_video_count INTEGER,
    definition       TEXT,
    origin           TEXT,
    usage            TEXT,
    examples         TEXT,
    created_at       TEXT NOT NULL,
    UNIQUE(title, date)
);
CREATE INDEX IF NOT EXISTS idx_date ON memes(date);
CREATE INDEX IF NOT EXISTS idx_verified ON memes(verified);
"""

def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)

def _bool_to_int(v) -> int | None:
    if v is None:
        return None
    return 1 if v else 0

def save_to_db(memes: list[FinalMeme], date: str, db_path: Path | None = None) -> int:
    import datetime
    now = datetime.datetime.now().isoformat()
    n = 0
    with _connect(db_path) as conn:
        for m in memes:
            cur = conn.execute(
                """INSERT OR IGNORE INTO memes
                (title, date, platforms, hot_scores, confidence, classify_reason,
                 verified, bili_video_count, definition, origin, usage, examples, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    m.title, m.date, json.dumps(m.platforms, ensure_ascii=False),
                    json.dumps(m.hot_scores, ensure_ascii=False),
                    m.confidence, m.classify_reason,
                    _bool_to_int(m.verified), m.bili_video_count,
                    m.definition, m.origin, m.usage,
                    json.dumps(m.examples, ensure_ascii=False), now,
                ),
            )
            n += cur.rowcount
        conn.commit()
    return n

def query_by_date(date: str, db_path: Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM memes WHERE date = ? ORDER BY id", (date,)
        ).fetchall()
    return [dict(r) for r in rows]
