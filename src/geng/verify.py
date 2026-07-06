"""[4] 查 B站搜索结果数,验证是否有足够二创。"""
from __future__ import annotations
import logging
from typing import Protocol
import httpx
from .models import ClassifiedMeme
from . import config

log = logging.getLogger(__name__)

class BiliSearchClient(Protocol):
    def search_count(self, keyword: str) -> int | None: ...

class HttpxBiliClient:
    """生产实现: 调 B站搜索 API。"""
    def search_count(self, keyword: str) -> int | None:
        params = {"search_type": "video", "keyword": keyword, "page_size": 1}
        headers = {"User-Agent": "Mozilla/5.0"}
        # trust_env=False: 绕开系统代理(见 discover.py 注释)
        with httpx.Client(timeout=config.HTTP_TIMEOUT, trust_env=False) as client:
            resp = client.get(config.BILI_SEARCH_URL, params=params, headers=headers)
            resp.raise_for_status()
            return parse_bili_count(resp.json())

def parse_bili_count(raw: dict) -> int | None:
    try:
        return raw["data"]["numResults"]
    except (KeyError, TypeError):
        return None

def verify_bilibili(
    memes: list[ClassifiedMeme],
    client: BiliSearchClient | None = None,
    threshold: int | None = None,
) -> list[ClassifiedMeme]:
    """对每条梗查 B站搜索数,填入 verified 与 bili_video_count。失败标 None。"""
    client = client or HttpxBiliClient()
    threshold = config.BILI_VERIFY_THRESHOLD if threshold is None else threshold
    for m in memes:
        try:
            count = client.search_count(m.title)
        except Exception as e:
            log.warning("verify: B站查询失败 (%s): %s", m.title, e)
            m.verified = None
            m.bili_video_count = None
            continue
        if count is None:
            m.verified = None
            m.bili_video_count = None
        else:
            m.verified = count >= threshold
            m.bili_video_count = count
    return memes
