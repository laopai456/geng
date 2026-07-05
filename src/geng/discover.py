"""[1] 抓 B站排行榜热门视频 + 每个视频的 top 评论。

替代旧的"抓热搜榜"逻辑——热梗真正栖息在评论区。
某视频失败不阻塞其余。
"""
from __future__ import annotations

import logging
import time

import httpx

from . import config
from .models import VideoInfo, Comment

log = logging.getLogger(__name__)

# 通用请求头: 模拟浏览器,Referer 提高 B站评论接口可靠性
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


def fetch_top_videos(limit: int = 10) -> list[VideoInfo]:
    """B站全站排行榜 top N 视频。接口空时返回 []。"""
    url = f"{config.BILI_RANKING_URL}"
    with httpx.Client(timeout=config.HTTP_TIMEOUT, headers=_HEADERS) as client:
        resp = client.get(url, params={"rid": 0, "type": "all"})
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
    video: VideoInfo,
    pages: int = 10,
    page_size: int = 30,
) -> list[Comment]:
    """单个视频的 top 评论(按热度)。翻 pages 页。空页时停止。"""
    comments: list[Comment] = []
    with httpx.Client(timeout=config.HTTP_TIMEOUT, headers=_HEADERS) as client:
        for page in range(1, pages + 1):
            try:
                resp = client.get(
                    config.BILI_REPLY_URL,
                    params={
                        "type": 1,
                        "oid": video.aid,
                        "next": page,
                        "ps": page_size,
                        "mode": 3,
                    },
                )
                resp.raise_for_status()
                raw = resp.json()
            except Exception as e:
                log.warning(
                    "discover: 视频 %s 第 %d 页评论失败: %s",
                    video.bvid, page, e,
                )
                break
            replies = raw.get("data", {}).get("replies") or []
            if not replies:
                break  # 空页 = 没更多评论
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
            time.sleep(0.3)  # 礼貌限速
    return comments


def collect_corpus(
    videos_limit: int = 10,
    pages_per_video: int = 10,
) -> tuple[list[VideoInfo], list[Comment]]:
    """抓多个视频的评论,汇成语料库。某视频失败不阻塞其余。

    返回 (videos, comments) 元组。
    """
    videos = fetch_top_videos(limit=videos_limit)
    log.info("discover: 抓到 %d 个热门视频", len(videos))
    all_comments: list[Comment] = []
    for v in videos:
        try:
            cmts = fetch_comments(v, pages=pages_per_video)
            log.info("discover: 视频 %s 抓到 %d 条评论", v.bvid, len(cmts))
            all_comments.extend(cmts)
        except Exception as e:
            log.warning("discover: 视频 %s 评论抓取失败: %s", v.bvid, e)
    return videos, all_comments
