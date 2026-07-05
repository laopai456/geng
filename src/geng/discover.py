"""[1] 直接抓各平台热搜(微博 / B站)。

设计: 每个平台一个独立的 fetcher 函数,签名统一返回 list[HotItem]。
任一平台失败不阻塞其余。返回原始 HotItem,后续 filter 阶段做去重/合并。
"""
from __future__ import annotations

import logging
import datetime
from typing import Callable

import httpx

from . import config
from .models import HotItem

log = logging.getLogger(__name__)

# 通用请求头: 模拟浏览器,绕过最基础的 UA 校验
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

Fetcher = Callable[[str], list[HotItem]]


def fetch_weibo(date: str) -> list[HotItem]:
    """微博热搜榜。接口: https://weibo.com/ajax/side/hotSearch

    返回结构: data.realtime = [{word, num, category, ...}]
    """
    url = "https://weibo.com/ajax/side/hotSearch"
    with httpx.Client(timeout=config.HTTP_TIMEOUT, headers=_HEADERS) as client:
        resp = client.get(url)
        resp.raise_for_status()
        raw = resp.json()

    items: list[HotItem] = []
    for entry in raw.get("data", {}).get("realtime", []) or []:
        title = str(entry.get("word", "")).strip()
        if not title:
            continue
        try:
            hot = int(entry.get("num") or 0)
        except (TypeError, ValueError):
            hot = 0
        # 去掉微博热搜常见的 # 标记
        title = title.strip("#")
        if not title:
            continue
        items.append(
            HotItem(
                id=f"weibo-{entry.get('word')}",
                platform="weibo",
                title=title,
                hot=hot,
                url=f"https://s.weibo.com/weibo?q=%23{title}%23",
                fetched_at=date,
            )
        )
    return items


def fetch_bilibili(date: str) -> list[HotItem]:
    """B站热搜榜。接口: https://app.bilibili.com/x/v2/search/trending/ranking

    返回结构: data.list = [{keyword, show_name, ...}]
    """
    url = "https://app.bilibili.com/x/v2/search/trending/ranking"
    params = {"limit": 50, "main_ver": "v3"}
    with httpx.Client(timeout=config.HTTP_TIMEOUT, headers=_HEADERS) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        raw = resp.json()

    items: list[HotItem] = []
    # 不同版本接口字段略有差异,做容错
    entries = (
        raw.get("data", {}).get("list")
        or raw.get("data", {}).get("trending", {}).get("list")
        or []
    )
    for entry in entries:
        title = str(entry.get("show_name") or entry.get("keyword") or "").strip()
        if not title:
            continue
        try:
            hot = int(entry.get("hot_id") or entry.get("goto") or 0)
        except (TypeError, ValueError):
            hot = 0
        items.append(
            HotItem(
                id=f"bilibili-{title}",
                platform="bilibili",
                title=title,
                hot=hot,
                url=str(entry.get("uri") or entry.get("url") or ""),
                fetched_at=date,
            )
        )
    return items


# 平台 → fetcher 映射。新增平台只需在此注册。
FETCHERS: dict[str, Fetcher] = {
    "weibo": fetch_weibo,
    "bilibili": fetch_bilibili,
    # 抖音接口需要 cookie/鉴权,反爬严,暂不直接抓。
    # 若要恢复,可在这里注册 fetch_douyin。
}


def fetch_trending(
    platforms: list[str] | None = None,
    date: str | None = None,
    client=None,  # 保留参数兼容旧签名(忽略),直接抓取不需要外部 client
) -> list[HotItem]:
    """抓多个平台热搜,某平台失败不阻塞其余。

    参数 client 仅用于向后兼容测试调用,实际直接抓取忽略它。
    """
    platforms = platforms or config.PLATFORMS
    date = date or datetime.date.today().isoformat()
    all_items: list[HotItem] = []
    for p in platforms:
        fetcher = FETCHERS.get(p)
        if fetcher is None:
            log.warning("discover: 未知平台 %s (跳过)", p)
            continue
        try:
            items = fetcher(date)
            log.info("discover: %s 抓到 %d 条", p, len(items))
            all_items.extend(items)
        except Exception as e:
            log.warning("discover: 平台 %s 抓取失败: %s", p, e)
    return all_items
