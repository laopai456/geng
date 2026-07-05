# src/geng/llm.py
"""DeepSeek 客户端封装(OpenAI 兼容接口),带重试。接口设计为可 mock。"""
from __future__ import annotations
from typing import Protocol
import json
import logging
import httpx
from tenacity import retry, stop_after_attempt
from . import config

log = logging.getLogger(__name__)

class LLMClient(Protocol):
    def chat(self, model: str, messages: list[dict]) -> str: ...

class DeepSeekClient:
    """生产实现: 调 DeepSeek (OpenAI 兼容接口)。"""
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.LLM_API_KEY
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY (或 DEEPSEEK_API_KEY) 未设置")

    @retry(stop=stop_after_attempt(config.LLM_MAX_RETRY + 1), reraise=True)
    def chat(self, model: str, messages: list[dict]) -> str:
        url = f"{config.LLM_BASE_URL}/chat/completions"
        with httpx.Client(timeout=config.LLM_TIMEOUT) as client:
            resp = client.post(
                url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages, "temperature": 0.3},
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]
