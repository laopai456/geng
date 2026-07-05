"""[6] 生成当日 Markdown 日报。"""
from __future__ import annotations

from pathlib import Path

from . import config
from .models import FinalMeme


def render_daily_report(
    memes: list[FinalMeme],
    date: str,
    total_raw: int,
    out_dir: Path | None = None,
) -> Path:
    out_dir = out_dir or config.DAILY_REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    verified = [m for m in memes if m.verified is True]
    observing = [m for m in memes if m.verified is not True]

    lines: list[str] = []
    lines.append(f"# {date} 热梗日报")
    lines.append("")
    lines.append(
        f"> 共采集 {total_raw} 条热搜,经筛选入库 {len(memes)} 条"
        f"(其中 {len(verified)} 条已验证)"
    )
    lines.append("")

    lines.append("## ✅ 已验证梗")
    lines.append("")
    for i, m in enumerate(verified, 1):
        lines.extend(_render_meme(i, m))
        lines.append("")

    if observing:
        lines.append("## 🔍 待观察(未通过二创验证)")
        lines.append("")
        for i, m in enumerate(observing, 1):
            lines.extend(_render_meme(i, m))
            lines.append("")

    lines.append("---")
    lines.append("*数据源: 微博 / B站 / 抖音  •  释义由 GLM-4.6 生成*")
    lines.append("")

    path = out_dir / f"{date}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_meme(idx: int, m: FinalMeme) -> list[str]:
    platforms_str = " / ".join(f"{p}🔥" for p in m.platforms)
    bili_str = (
        f"约 {m.bili_video_count} 个视频"
        if m.bili_video_count is not None
        else "未验证"
    )
    return [
        f"### {idx}. {m.title}",
        f"- **释义**: {m.definition or '(无)'}",
        f"- **出处**: {m.origin or '(无)'}",
        f"- **用法**: {m.usage or '(无)'}",
        f"- **例句**: {'; '.join(m.examples) if m.examples else '(无)'}",
        f"- **B站二创**: {bili_str}",
        f"- **来源**: {platforms_str}",
        "",
    ]
