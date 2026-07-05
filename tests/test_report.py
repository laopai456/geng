# tests/test_report.py
from geng.report import render_daily_report
from geng.models import FinalMeme


def _meme(title, verified=True, definition="某释义"):
    return FinalMeme(
        title=title, date="2026-07-05", platforms=["weibo", "bilibili"],
        hot_scores={"weibo": 1000}, confidence=0.9, classify_reason="",
        verified=verified, bili_video_count=234 if verified else 5,
        definition=definition, origin="某事件", usage="赞美", examples=["例句"],
    )


def test_report_has_header_and_stats(tmp_path):
    path = render_daily_report([_meme("YYDS", True), _meme("待观察", False)], date="2026-07-05", total_raw=87, out_dir=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "2026-07-05 热梗日报" in text
    assert "87" in text              # 原始数量
    assert "2" in text               # 入库数量


def test_report_separates_verified_and_observing(tmp_path):
    path = render_daily_report([_meme("YYDS", True), _meme("待观察", False)], date="2026-07-05", total_raw=10, out_dir=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "已验证" in text
    assert "待观察" in text
    assert text.index("YYDS") < text.index("待观察")


def test_report_contains_explanation_fields(tmp_path):
    path = render_daily_report([_meme("YYDS", True)], date="2026-07-05", total_raw=10, out_dir=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "释义" in text
    assert "出处" in text
    assert "用法" in text
    assert "例句" in text
    assert "某释义" in text


def test_report_filename(tmp_path):
    path = render_daily_report([_meme("YYDS", True)], date="2026-07-05", total_raw=10, out_dir=tmp_path)
    assert path.name == "2026-07-05.md"
