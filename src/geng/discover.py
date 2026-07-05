"""[1] 抓 B站排行榜热门视频 + 每个视频的 top 评论。

替代旧的"抓热搜榜"逻辑——热梗真正栖息在评论区。
某视频失败不阻塞其余。

关键: B站评论接口对无 cookie 请求返回 code=-352 (风控)。
必须用持久 Client 先访问首页拿 buvid3 cookie,再用旧 /x/v2/reply 接口(pn 翻页)。
"""
from __future__ import annotations

import logging
import time

import httpx

from . import config
from .models import VideoInfo, Comment

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def _make_session() -> httpx.Client:
    """创建带 cookie 的会话: 先访问 B站首页拿 buvid3,否则评论接口 -352 风控。"""
    client = httpx.Client(timeout=config.HTTP_TIMEOUT, headers=_HEADERS, follow_redirects=True)
    try:
        client.get("https://www.bilibili.com/")
        log.info("discover: 会话已建立, cookies=%s", list(client.cookies.keys()))
    except Exception as e:
        log.warning("discover: 访问首页失败(评论可能被风控): %s", e)
    return client


def fetch_top_videos(client: httpx.Client, limit: int = 10) -> list[VideoInfo]:
    """B站全站排行榜 top N 视频。接口空时返回 []。"""
    resp = client.get(config.BILI_RANKING_URL, params={"rid": 0, "type": "all"})
    resp.raise_for_status()
    raw = resp.json()
    entries = raw.get("data", {}).get("list") or []
    videos: list[VideoInfo] = []
    for e in entries[:limit]:
        try:
            videos.append(
                VideoInfo(
                    bvid=str(e.get("bvid", "")),
                    aid=int(e.get("aid", 0)),
                    title=str(e.get("title", "")).strip(),
                )
            )
        except (TypeError, ValueError):
            continue
    return videos


def fetch_comments(
    client: httpx.Client,
    video: VideoInfo,
    pages: int = 5,
    page_size: int = 20,
) -> list[Comment]:
    """单个视频的 top 评论。用 reply/main 接口,cursor 游标翻页。

    无登录态下 B站通常只给少量热评(~3条),翻页很快见底。
    cursor.next 是下一页游标(非页码),从响应里读取。
    """
    comments: list[Comment] = []
    per_headers = {"Referer": f"https://www.bilibili.com/video/{video.bvid}"}
    nxt = 0  # 首页游标
    for page in range(1, pages + 1):
        try:
            resp = client.get(
                config.BILI_REPLY_URL,
                params={
                    "type": 1,
                    "oid": video.aid,
                    "next": nxt,
                    "ps": page_size,
                    "mode": 3,  # 按热度
                },
                headers=per_headers,
            )
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            log.warning(
                "discover: 视频 %s 第 %d 页评论失败: %s",
                video.bvid, page, e,
            )
            break
        if raw.get("code") != 0:
            log.warning(
                "discover: 视频 %s 评论 code=%s msg=%s,停止",
                video.bvid, raw.get("code"), raw.get("message", ""),
            )
            break
        replies = raw.get("data", {}).get("replies") or []
        if not replies:
            break
        for rep in replies:
            msg = (rep.get("content") or {}).get("message", "")
            if not msg:
                continue
            try:
                likes = int(rep.get("like") or 0)
            except (TypeError, ValueError):
                likes = 0
            comments.append(
                Comment(
                    video_bvid=video.bvid,
                    message=msg,
                    likes=likes,
                )
            )
        # 用返回的 cursor.next 翻页(不是固定 +1)
        cursor = raw.get("data", {}).get("cursor") or {}
        nxt = cursor.get("next", 0)
        if not nxt:
            break  # 无下一页游标
        time.sleep(0.3)
    return comments


def collect_corpus(
    videos_limit: int = 10,
    pages_per_video: int = 8,
) -> tuple[list[VideoInfo], list[Comment]]:
    """抓多个视频的评论,汇成语料库。某视频失败不阻塞其余。

    用单个持久会话(带 cookie),所有视频共享。
    返回 (videos, comments) 元组。
    """
    client = _make_session()
    try:
        videos = fetch_top_videos(client, limit=videos_limit)
        log.info("discover: 抓到 %d 个热门视频", len(videos))
        all_comments: list[Comment] = []
        for v in videos:
            try:
                cmts = fetch_comments(client, v, pages=pages_per_video)
                log.info("discover: 视频 %s 抓到 %d 条评论", v.bvid, len(cmts))
                all_comments.extend(cmts)
            except Exception as e:
                log.warning("discover: 视频 %s 评论抓取失败: %s", v.bvid, e)
        return videos, all_comments
    finally:
        client.close()
