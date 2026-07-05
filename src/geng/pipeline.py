# src/geng/pipeline.py
"""串联 discover → filter → classify → verify → explain → store + report。
每个外部依赖都用模块级引用,便于测试 monkeypatch。失败降级不阻塞。"""
from __future__ import annotations
import logging
from pathlib import Path
from . import discover, filter as filter_mod, classify, verify, explain, store, report

log = logging.getLogger(__name__)

def run_daily(
    date: str | None = None,
    db_path: Path | None = None,
    report_dir: Path | None = None,
) -> int:
    """跑完整 pipeline,返回入库条数。"""
    import datetime
    date = date or datetime.date.today().isoformat()

    # [1] 发现
    items = discover.fetch_trending(date=date)
    total_raw = len(items)
    log.info("[1] discover: %d 条原始热搜", total_raw)

    # [2] 粗筛
    candidates = filter_mod.coarse_filter(items, date=date)
    log.info("[2] filter: %d 条候选", len(candidates))

    # [3] LLM 分类 (内部已降级)
    classified = classify.classify_memes(candidates)
    log.info("[3] classify: %d 条判定为梗", len(classified))

    # [4] B站验证
    verified = verify.verify_bilibili(classified)
    log.info("[4] verify: %d 条已验证", sum(1 for m in verified if m.verified))

    # [5] LLM 释义 (内部已降级)
    finals = explain.explain_meme(verified)
    log.info("[5] explain: %d 条释义完成", sum(1 for f in finals if f.definition))

    # [6] 入库 + 日报
    store.init_db(db_path)
    n = store.save_to_db(finals, date=date, db_path=db_path)
    report.render_daily_report(finals, date=date, total_raw=total_raw, out_dir=report_dir)
    log.info("[6] store: 入库 %d 条, 日报已生成", n)
    return n
