"""discover 模块测试。

新架构(2026-07): 函数接收 httpx.Client 作为首参,collect_corpus 经 _make_session
内部管理会话。这里用 FakeClient 直接注入(方式 A):单元测试直接构造 FakeClient
传入;collect_corpus 测试 monkeypatch _make_session 返回 FakeClient。
"""
import logging

import httpx

from geng import discover
from geng.discover import fetch_top_videos, fetch_comments, collect_corpus
from geng.models import VideoInfo, Comment


# ---------------------------------------------------------------------------
# 通用 fake httpx.Client 工具
# ---------------------------------------------------------------------------
class FakeResp:
    """假 httpx.Response。可配置 json 数据与 raise_for_status 抛出的异常。"""

    def __init__(self, json_data, *, raise_exc=None):
        self._data = json_data
        self._raise = raise_exc

    def raise_for_status(self):
        if self._raise is not None:
            raise self._raise

    def json(self):
        return self._data


class FakeClient:
    """假 httpx.Client。

    responses 可为:
    - dict: {url_substring: FakeResp} —— 按 URL 子串匹配。
    - list: [FakeResp, ...] —— 按调用顺序消费。

    对 B站首页(非 api)请求统一返回空 OK,模拟 _make_session 拿 cookie 的过程。
    """

    def __init__(self, responses=None):
        self._responses = responses if responses is not None else {}
        self._call_idx = 0
        # 模拟 httpx.Client.cookies.keys()
        self.cookies = type("C", (), {"keys": lambda self: ["buvid3"]})()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None, headers=None):
        # bilibili 首页调用(_make_session 拿 buvid3): 返回空 OK
        if "bilibili.com/" in url and "api" not in url:
            return FakeResp({"code": 0})
        # 按子串匹配
        if isinstance(self._responses, dict):
            for key, resp in self._responses.items():
                if key in url:
                    return resp
            return FakeResp({"code": -1, "message": "no mock for " + url})
        # 按顺序消费
        if self._call_idx < len(self._responses):
            r = self._responses[self._call_idx]
            self._call_idx += 1
            return r
        return FakeResp({"code": -1, "message": "exhausted"})

    def close(self):
        pass


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


def _replies_json(messages_likes, next_cursor=0):
    """messages_likes: list[(message, like)] -> reply 列表。

    next_cursor: 响应里 cursor.next 的值(0/ falsy 表示无下一页)。
    """
    replies = [
        {"content": {"message": msg}, "like": like}
        for msg, like in messages_likes
    ]
    return {
        "code": 0,
        "data": {"replies": replies, "cursor": {"next": next_cursor}},
    }


# ===========================================================================
# 1. fetch_top_videos
# ===========================================================================
def test_fetch_top_videos_parses_ranking():
    """排行榜 3 个视频 -> 3 个 VideoInfo,字段正确。"""
    client = FakeClient({"ranking": FakeResp(_ranking_json(3))})
    videos = fetch_top_videos(client, limit=10)
    assert len(videos) == 3
    v0 = videos[0]
    assert isinstance(v0, VideoInfo)
    assert v0.aid == 1000
    assert v0.bvid == "BV000000000"
    assert v0.title == "视频标题0"
    assert [v.aid for v in videos] == [1000, 1001, 1002]


def test_fetch_top_videos_empty_list_returns_empty():
    """data.list 为空/缺失 -> 返回 [] (不崩)。"""
    client = FakeClient({"ranking": FakeResp({"data": {}})})
    assert fetch_top_videos(client) == []

    client2 = FakeClient({"ranking": FakeResp({"data": {"list": []}})})
    assert fetch_top_videos(client2) == []


def test_fetch_top_videos_respects_limit():
    """limit 截断返回数量。"""
    client = FakeClient({"ranking": FakeResp(_ranking_json(5))})
    videos = fetch_top_videos(client, limit=2)
    assert len(videos) == 2


# ===========================================================================
# 2. fetch_comments: 解析 + 空页停止
# ===========================================================================
def test_fetch_comments_parses_replies():
    """page1 返回 3 条评论, cursor.next=0 停止 -> 拿到 3 条。"""
    page1 = _replies_json(
        [("梗A", 100), ("梗B", 50), ("梗C", 10)],
        next_cursor=0,  # 触发停止
    )
    client = FakeClient({"reply/main": FakeResp(page1)})
    video = VideoInfo(bvid="BV001", aid=999, title="t")
    comments = fetch_comments(client, video, pages=5, page_size=30)

    assert len(comments) == 3
    c0 = comments[0]
    assert isinstance(c0, Comment)
    assert c0.message == "梗A"
    assert c0.likes == 100
    assert c0.video_bvid == "BV001"
    assert [c.message for c in comments] == ["梗A", "梗B", "梗C"]


def test_fetch_comments_stops_on_null_replies():
    """data.replies 为 null/空 -> 视为空页停止,不再翻页。"""
    calls = {"n": 0}

    class CountingClient(FakeClient):
        def get(self, url, params=None, headers=None):
            if "bilibili.com/" in url and "api" not in url:
                return FakeResp({"code": 0})
            calls["n"] += 1
            return FakeResp({"code": 0, "data": {"replies": None}})

    client = CountingClient({})
    video = VideoInfo(bvid="BV002", aid=1, title="t")
    assert fetch_comments(client, video, pages=5) == []
    # 只被调用一次(replies 空即 break,不翻页)
    assert calls["n"] == 1


def test_fetch_comments_stops_on_nonzero_code(monkeypatch, caplog):
    """code=-352(风控) -> 停止翻页,记 warning,返回 []。"""
    client = FakeClient({
        "reply/main": FakeResp({"code": -352, "message": "风控"}),
    })
    video = VideoInfo(bvid="BV003", aid=1, title="t")
    with caplog.at_level(logging.WARNING, logger="geng.discover"):
        comments = fetch_comments(client, video, pages=5)
    assert comments == []
    assert any("BV003" in r.getMessage() and "code" in r.getMessage()
               for r in caplog.records)


# ===========================================================================
# 3. fetch_comments: 网络错误保留已抓评论
# ===========================================================================
def test_fetch_comments_network_failure_returns_partial(monkeypatch):
    """page1 成功 3 条(next=5), page2 抛 HTTPError -> 保留 page1 的 3 条后 break。"""
    page1 = FakeResp(_replies_json(
        [("x", 1), ("y", 2), ("z", 3)],
        next_cursor=5,  # 触发翻第二页
    ))
    page2 = FakeResp({}, raise_exc=httpx.HTTPError("simulated 500"))
    queue = [page1, page2]

    class SeqClient(FakeClient):
        def get(self, url, params=None, headers=None):
            if "bilibili.com/" in url and "api" not in url:
                return FakeResp({"code": 0})
            if "reply/main" in url and queue:
                return queue.pop(0)
            return FakeResp({"code": -1, "message": "exhausted"})

    client = SeqClient({})
    video = VideoInfo(bvid="BV004", aid=1, title="t")
    comments = fetch_comments(client, video, pages=10)

    assert len(comments) == 3
    assert {c.message for c in comments} == {"x", "y", "z"}


# ===========================================================================
# 4. collect_corpus: 聚合 + 跳过失败视频
# ===========================================================================
def test_collect_corpus_aggregates_and_skips_failed(monkeypatch, caplog):
    """BV1 抓到 3 评论, BV2 评论接口抛错 -> 总共 3 条, BV2 记 warning, 视频全返回。"""
    videos = [
        VideoInfo(bvid="BV1", aid=1, title="v1"),
        VideoInfo(bvid="BV2", aid=2, title="v2"),
    ]

    # FakeClient: ranking 返回 2 视频; reply/main 对 BV1 返 3 评论,
    # 对 BV2 抛 HTTPError(通过带 raise_exc 的 FakeResp)
    bv1_replies = _replies_json(
        [("梗1", 1), ("梗2", 2), ("梗3", 3)], next_cursor=0,
    )

    class RoutingClient(FakeClient):
        """按 oid 区分 BV1/BV2 评论响应的定向 client。"""

        def __init__(self):
            super().__init__({})
            self._bv2_called = False

        def get(self, url, params=None, headers=None):
            if "bilibili.com/" in url and "api" not in url:
                return FakeResp({"code": 0})
            if "ranking" in url:
                return FakeResp({
                    "data": {"list": [
                        {"aid": 1, "bvid": "BV1", "title": "v1"},
                        {"aid": 2, "bvid": "BV2", "title": "v2"},
                    ]}
                })
            if "reply/main" in url:
                oid = (params or {}).get("oid")
                if oid == 1:
                    return FakeResp(bv1_replies)
                if oid == 2:
                    return FakeResp({}, raise_exc=httpx.HTTPError("BV2 挂了"))
            return FakeResp({"code": -1, "message": "no mock for " + url})

    monkeypatch.setattr(discover, "_make_session", lambda: RoutingClient())

    with caplog.at_level(logging.WARNING, logger="geng.discover"):
        out_videos, out_comments = collect_corpus(
            videos_limit=10, pages_per_video=5,
        )

    assert out_videos == videos
    assert len(out_comments) == 3
    assert {c.video_bvid for c in out_comments} == {"BV1"}
    assert any("BV2" in r.getMessage() for r in caplog.records)
