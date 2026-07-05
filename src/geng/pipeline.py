# src/geng/pipeline.py
"""串联 discover → extract → filter → classify → verify → explain → store + report。

新流程: 抓 B站热门视频评论 → jieba 提取候选梗 → 排除清单过滤 → LLM 分类 → B站验证 → LLM 释义 → 入库。
"""
from __future__ import annotations
import logging
from pathlib import Path
from . import discover, extract, filter as filter_mod, classify, verify, explain, store, report

log = logging.getLogger(__name__)

def run_daily(
    date: str | None = None,
    db_path: Path | None = None,
    report_dir: Path | None = None,
) -> int:
    """跑完整 pipeline,返回入库条数。"""
    import datetime
    date = date or datetime.date.today().isoformat()

    # [1] 发现: 抓视频 + 评论。无登录态每视频只~3条热评,故多抓视频
    videos, comments = discover.collect_corpus(videos_limit=30, pages_per_video=5)
    log.info("[1] discover: %d 视频, %d 条评论", len(videos), len(comments))
    total_raw = len(comments)

    # [1.5] 提取: 评论 → 候选短语
    phrases = extract.extract_candidates(comments)
    phrase_counts = _count_phrases(comments, phrases)
    log.info("[1.5] extract: %d 个候选短语, 样例: %s", len(phrases), phrases[:8])

    # [2] 粗筛: 排除清单
    candidates = filter_mod.coarse_filter(phrases, date=date, phrase_counts=phrase_counts)
    log.info("[2] filter: %d 条通过排除清单", len(candidates))

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


def _count_phrases(comments, phrases) -> dict[str, int]:
    """统计每个候选短语在多少条评论里出现。用于热度。"""
    result = {p: 0 for p in phrases}
    phrase_set = set(phrases)
    for c in comments:
        # 简单 substring 匹配
        msg = c.message
        for p in phrase_set:
            if p in msg:
                result[p] += 1
    return result
