"""pipeline 各阶段流转的数据结构。字段随 pipeline 推进逐步填充。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HotItem:
    """[1] discover 阶段输出: 一条原始热搜。(旧热搜榜流程,已弃用但保留兼容)"""

    id: str
    platform: str
    title: str
    hot: int
    url: str
    fetched_at: str  # ISO date


@dataclass
class VideoInfo:
    """[1] discover 阶段输出: B站排行榜上的一个视频。"""

    bvid: str
    aid: int
    title: str


@dataclass
class Comment:
    """[1] discover 阶段输出: 一条评论。video_bvid 用于跨视频统计。"""

    video_bvid: str
    message: str
    likes: int


@dataclass
class Candidate:
    """[2] filter 阶段输出: 通过粗筛的候选梗。"""

    title: str
    date: str
    platforms: list[str]  # 出现在哪些平台
    hot_scores: dict[str, int]  # {platform: hot}


@dataclass
class ClassifiedMeme:
    """[3] classify 阶段输出: 带 LLM 判断的候选。"""

    title: str
    date: str
    platforms: list[str]
    hot_scores: dict[str, int]
    is_meme: bool | None = None
    confidence: float = 0.0
    classify_reason: str = ""
    # [4] verify 阶段填充
    verified: bool | None = None
    bili_video_count: int | None = None


@dataclass
class FinalMeme:
    """[5] explain 阶段输出: 最终入库结构。"""

    title: str
    date: str
    platforms: list[str]
    hot_scores: dict[str, int]
    confidence: float
    classify_reason: str
    verified: bool | None = None
    bili_video_count: int | None = None
    definition: str | None = None
    origin: str | None = None
    usage: str | None = None
    examples: list[str] = field(default_factory=list)

    @classmethod
    def from_classified(cls, m: ClassifiedMeme) -> "FinalMeme":
        """verify → explain 桥接: 复用 classified/verify 阶段已填字段。"""
        return cls(
            title=m.title,
            date=m.date,
            platforms=m.platforms,
            hot_scores=m.hot_scores,
            confidence=m.confidence,
            classify_reason=m.classify_reason,
            verified=m.verified,
            bili_video_count=m.bili_video_count,
        )
