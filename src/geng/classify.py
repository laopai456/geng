# src/geng/classify.py
"""[3] 调 DeepSeek (deepseek-chat) 判断每条候选是否为真梗。"""
from __future__ import annotations
import json
import logging
from .models import Candidate, ClassifiedMeme
from .llm import LLMClient, DeepSeekClient
from . import config

log = logging.getLogger(__name__)

_SYSTEM = (
    "你是中文网络流行语专家。判断每个标题是否属于'网络梗'(可被网友移植使用的"
    "名场面/金句/新造词/二创源泉),而不是单纯的明星八卦、社会新闻、节目名、"
    "民生话题。严格按 JSON 输出,不要多余文字。"
)

def build_classify_prompt(candidates: list[Candidate]) -> str:
    lines = ["请判断以下标题是否为'网络梗',输出 JSON:", "{"]
    lines.append('  "items": [')
    for i, c in enumerate(candidates):
        comma = "," if i < len(candidates) - 1 else ""
        lines.append(f'    {{"title": "{c.title}"}}{comma}')
    lines.append("  ]")
    lines.append("}")
    lines.append(
        "请只输出形如 {\"items\": [{\"title\":\"...\",\"is_meme\":true/false,"
        "\"confidence\":0.0-1.0,\"reason\":\"一句话\"}]} 的 JSON,is_meme 是 bool。"
    )
    return "\n".join(lines)

def parse_classify_response(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            return []
        try:
            data = json.loads(raw[start:end+1])
        except json.JSONDecodeError:
            return []
    return data.get("items", [])

def classify_memes(
    candidates: list[Candidate],
    client: LLMClient | None = None,
    batch_size: int = 20,
) -> list[ClassifiedMeme]:
    """分批调用 LLM,返回判定为梗的 ClassifiedMeme。"""
    # 无候选直接返回,避免在空跑时强制要求 LLM 凭据
    if not candidates:
        return []
    # 客户端构造可能失败(如缺 API key),失败则整体降级
    if client is None:
        try:
            client = DeepSeekClient()
        except Exception as e:
            log.warning("classify: LLM 客户端构造失败,降级保留全部候选: %s", e)
            return [
                ClassifiedMeme(
                    title=c.title, date=c.date, platforms=c.platforms,
                    hot_scores=c.hot_scores, is_meme=None, confidence=0.0,
                    classify_reason="LLM分类失败,降级保留",
                )
                for c in candidates
            ]
    out: list[ClassifiedMeme] = []
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i+batch_size]
        if not batch:
            continue
        try:
            raw = client.chat(config.CLASSIFY_MODEL, [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": build_classify_prompt(batch)},
            ])
            parsed = parse_classify_response(raw)
        except Exception as e:
            log.warning("classify: LLM 调用失败,降级保留全部候选: %s", e)
            for c in batch:
                out.append(ClassifiedMeme(
                    title=c.title, date=c.date, platforms=c.platforms,
                    hot_scores=c.hot_scores, is_meme=None, confidence=0.0,
                    classify_reason="LLM分类失败,降级保留",
                ))
            continue
        by_title = {p["title"]: p for p in parsed if "title" in p}
        for c in batch:
            p = by_title.get(c.title, {})
            is_meme = bool(p.get("is_meme", False))
            if not is_meme:
                continue
            out.append(ClassifiedMeme(
                title=c.title, date=c.date, platforms=c.platforms,
                hot_scores=c.hot_scores, is_meme=True,
                confidence=float(p.get("confidence", 0.5)),
                classify_reason=str(p.get("reason", "")),
            ))
    return out
