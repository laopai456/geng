"""[1] 调 DailyHotApi 抓各平台当日热搜。"""
from __future__ import annotations

import logging
from typing import Protocol

import httpx

from . import config
from .models import HotItem

log = logging.getLogger(__name__)


class DailyHotClient(Protocol):
    def get_json(self, platform: str) -> dict: ...


class HttpxDailyHotClient:
    """生产实现: 调 DailyHotApi。"""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or config.DAILYHOT_API_BASE).rstrip("/")

    def get_json(self, platform: str) -> dict:
        url = f"{self.base_url}/{platform}"
        resp = httpx.get(url, timeout=config.HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json()


def parse_platform_response(raw: dict, platform: str, date: str) -> list[HotItem]:
    """把 DailyHotApi 返回解析为 HotItem 列表。"""
    items: list[HotItem] = []
    for entry in raw.get("data", []) or []:
        try:
            hot = int(entry.get("hot") or 0)
        except (TypeError, ValueError):
            hot = 0
        items.append(
            HotItem(
                id=f"{platform}-{entry.get('id') or entry.get('title')}",
                platform=platform,
                title=str(entry.get("title", "")).strip(),
                hot=hot,
                url=str(entry.get("url", "")).strip(),
                fetched_at=date,
            )
        )
    return items


def fetch_trending(
    platforms: list[str] | None = None,
    date: str | None = None,
    client: DailyHotClient | None = None,
) -> list[HotItem]:
    """抓多个平台热搜,某平台失败不阻塞其余。"""
    platforms = platforms or config.PLATFORMS
    client = client or HttpxDailyHotClient()
    all_items: list[HotItem] = []
    for p in platforms:
        try:
            raw = client.get_json(p)
            all_items.extend(parse_platform_response(raw, p, date or _today()))
        except Exception as e:
            log.warning("discover: 平台 %s 抓取失败: %s", p, e)
    return all_items


def _today() -> str:
    import datetime

    return datetime.date.today().isoformat()
