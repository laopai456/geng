# src/geng/explain.py
"""[5] 调 GLM-4.6 为每条梗生成释义、出处、用法、例句。"""
from __future__ import annotations
import json
import logging
from .models import ClassifiedMeme, FinalMeme
from .llm import LLMClient, GLMClient
from . import config

log = logging.getLogger(__name__)

def build_explain_prompt(m: ClassifiedMeme) -> str:
    return (
        f"请解释中文网络梗「{m.title}」。输出包含释义、出处、用法、例句的 JSON,字段:\n"
        '- "definition": 这是什么梗(1-2句)\n'
        '- "origin": 出处(来自哪个事件/人物/作品)\n'
        '- "usage": 怎么在句子里用\n'
        '- "examples": 例句数组(1-2个)\n'
        "只输出 JSON,不要多余文字。如果不确定是不是真梗,definition 留空字符串。"
    )

def parse_explain_response(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            return {}
        try:
            data = json.loads(raw[start:end+1])
        except json.JSONDecodeError:
            return {}
    data.setdefault("examples", [])
    if not isinstance(data["examples"], list):
        data["examples"] = []
    return data

def explain_meme(
    memes: list[ClassifiedMeme],
    client: LLMClient | None = None,
) -> list[FinalMeme]:
    """逐条调 GLM-4.6 释义,失败时仍返回 FinalMeme(释义字段留空)。"""
    client = client or GLMClient()
    out: list[FinalMeme] = []
    for m in memes:
        f = FinalMeme.from_classified(m)
        try:
            raw = client.chat(config.EXPLAIN_MODEL, [
                {"role": "user", "content": build_explain_prompt(m)},
            ])
            d = parse_explain_response(raw)
            f.definition = d.get("definition") or None
            f.origin = d.get("origin") or None
            f.usage = d.get("usage") or None
            f.examples = d.get("examples", [])
        except Exception as e:
            log.warning("explain: 释义失败 (%s): %s", m.title, e)
            f.definition = None
        out.append(f)
    return out
