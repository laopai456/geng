"""discover 模块测试。

新架构(2026-07): 改挖评论区而非热搜榜。
通过 monkeypatch httpx.Client 注入 FakeClient,避免真实 HTTP。
"""
import logging

import httpx

from geng.discover import (
    fetch_top_videos,
    fetch_comments,
    collect_corpus,
)
from geng.models import VideoInfo, Comment


# ---------------------------------------------------------------------------
# 通用 fake httpx.Client 工具
# ---------------------------------------------------------------------------
class FakeResp:
    def __init__(self, json_data):
        self._data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class FakeClient:
    """可注入"按请求选响应"回调的假 client。"""

    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None):
        return self._responder(url, params)


def _install_client(monkeypatch, responder):
    """注入一个 FakeClient,其 get 调用 responder(url, params)。

    responder 返回 FakeResp 或 dict,也可抛异常(模拟网络错误)。
    """
    def factory(*a, **kw):
        c = FakeClient()
        c._responder = staticmethod(responder)
        return c

    monkeypatch.setattr("geng.discover.httpx.Client", factory)
    return factory


# ---------------------------------------------------------------------------
# fixtures: 样本 JSON
# ---------------------------------------------------------------------------
def _ranking_json(n=3):
    return {
        "data": {
            "list": [
                {
                    "aid": 1000 + i,
                    "bvid": f"BV{i:09d}",
                    "title": f"视频标题{i}",
                }
                for i in range(n)
            ]
        }
    }


def _replies_json(messages_likes):
    """messages_likes: list[(message, like)] -> reply 列表。"""
    replies = []
    for msg, like in messages_likes:
        replies.append({"content": {"message": msg}, "like": like})
    return {"data": {"replies": replies}}


def _resp(payload):
    """dict -> FakeResp 的便捷封装。"""
    if isinstance(payload, FakeResp):
        return payload
    return FakeResp(payload)


# ===========================================================================
# 1. fetch_top_videos
# ===========================================================================
def test_fetch_top_videos_parses_ranking(monkeypatch):
    """排行榜 3 个视频 -> 3 个 VideoInfo,字段正确。"""
    _install_client(monkeypatch, lambda url, params: _resp(_ranking_json(3)))
    videos = fetch_top_videos(limit=10)
    assert len(videos) == 3
    v0 = videos[0]
    assert isinstance(v0, VideoInfo)
    assert v0.aid == 1000
    assert v0.bvid == "BV000000000"
    assert v0.title == "视频标题0"
    assert [v.aid for v in videos] == [1000, 1001, 1002]


def test_fetch_top_videos_empty_list_returns_empty(monkeypatch):
    """data.list 为空/缺失 -> 返回 [] (不崩)。"""
    _install_client(monkeypatch, lambda url, params: _resp({"data": {}}))
    assert fetch_top_videos() == []

    _install_client(monkeypatch, lambda url, params: _resp({"data": {"list": []}}))
    assert fetch_top_videos() == []


def test_fetch_top_videos_respects_limit(monkeypatch):
    """limit 截断返回数量。"""
    _install_client(monkeypatch, lambda url, params: _resp(_ranking_json(5)))
    videos = fetch_top_videos(limit=2)
    assert len(videos) == 2


# ===========================================================================
# 2. fetch_comments: 解析 + 空页停止
# ===========================================================================
def test_fetch_comments_parses_and_stops_on_empty(monkeypatch):
    """page1 返回 3 条评论,page2 空 -> 只拿到 3 条,不再翻页。"""
    page1 = _replies_json([("梗A", 100), ("梗B", 50), ("梗C", 10)])
    page2 = {"data": {"replies": []}}

    def responder(url, params):
        return _resp(page1 if params["next"] == 1 else page2)

    _install_client(monkeypatch, responder)
    video = VideoInfo(bvid="BV001", aid=999, title="t")
    comments = fetch_comments(video, pages=10, page_size=30)

    assert len(comments) == 3
    c0 = comments[0]
    assert isinstance(c0, Comment)
    assert c0.message == "梗A"
    assert c0.likes == 100
    assert c0.video_bvid == "BV001"


def test_fetch_comments_stops_on_null_replies(monkeypatch):
    """data.replies 为 null -> 视为空页停止。"""
    _install_client(monkeypatch, lambda url, params: _resp({"data": {"replies": None}}))
    video = VideoInfo(bvid="BV002", aid=1, title="t")
    assert fetch_comments(video, pages=5) == []


# ===========================================================================
# 3. fetch_comments: 容错坏条目
# ===========================================================================
def test_fetch_comments_handles_malformed_entries(monkeypatch):
    """缺 content / 缺 like 的条目不崩,空 message 跳过,like 缺失置 0。"""
    page1 = {
        "data": {
            "replies": [
                {"content": {"message": "正常的"}, "like": 7},
                {"like": 5},                              # 缺 content -> 跳过
                {"content": {"message": ""}, "like": 5},  # 空 msg -> 跳过
                {"content": {"message": "无赞"}},         # 缺 like -> likes=0
                {"content": {"message": "坏赞"}, "like": "abc"},  # 坏 like -> likes=0
            ]
        }
    }

    def responder(url, params):
        return _resp(page1 if params["next"] == 1 else {"data": {"replies": []}})

    _install_client(monkeypatch, responder)
    video = VideoInfo(bvid="BV003", aid=1, title="t")
    comments = fetch_comments(video, pages=5)

    msgs = [c.message for c in comments]
    assert msgs == ["正常的", "无赞", "坏赞"]
    assert comments[1].likes == 0
    assert comments[2].likes == 0


# ===========================================================================
# 4. fetch_comments: 网络错误停止翻页
# ===========================================================================
def test_fetch_comments_network_failure_stops_pagination(monkeypatch):
    """page1 成功 3 条,page2 抛 HTTPError -> 保留 page1 的 3 条后 break。"""
    page1 = _replies_json([("x", 1), ("y", 2), ("z", 3)])

    def responder(url, params):
        if params["next"] == 1:
            return _resp(page1)
        raise httpx.HTTPError("simulated 500")

    _install_client(monkeypatch, responder)
    video = VideoInfo(bvid="BV004", aid=1, title="t")
    comments = fetch_comments(video, pages=10)

    assert len(comments) == 3
    assert {c.message for c in comments} == {"x", "y", "z"}


# ===========================================================================
# 5. collect_corpus: 聚合 + 跳过失败视频
# ===========================================================================
def test_collect_corpus_aggregates_and_skips_failed(monkeypatch, caplog):
    """video1 成功 3 评论,video2 失败 -> 总共 3 条,video2 记 warning。"""
    videos = [
        VideoInfo(bvid="BV1", aid=1, title="v1"),
        VideoInfo(bvid="BV2", aid=2, title="v2"),
    ]

    def fake_fetch_top_videos(limit=10):
        return videos

    def fake_fetch_comments(video, pages=10, page_size=30):
        if video.bvid == "BV1":
            return [
                Comment(video_bvid="BV1", message="梗1", likes=1),
                Comment(video_bvid="BV1", message="梗2", likes=2),
                Comment(video_bvid="BV1", message="梗3", likes=3),
            ]
        raise RuntimeError("video2 挂了")

    monkeypatch.setattr("geng.discover.fetch_top_videos", fake_fetch_top_videos)
    monkeypatch.setattr("geng.discover.fetch_comments", fake_fetch_comments)

    with caplog.at_level(logging.WARNING, logger="geng.discover"):
        out_videos, out_comments = collect_corpus(videos_limit=10, pages_per_video=10)

    assert out_videos == videos
    assert len(out_comments) == 3
    assert {c.video_bvid for c in out_comments} == {"BV1"}
    assert any("BV2" in r.getMessage() for r in caplog.records)
