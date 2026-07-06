"""集中配置: 阈值、模型名、路径常量。所有模块从这里读。"""
import os
from pathlib import Path

# 数据源 (直接抓取,不依赖 DailyHotApi)
PLATFORMS = ["weibo", "bilibili"]
DAILYHOT_API_BASE = os.environ.get("DAILYHOT_API_BASE", "")  # 已弃用,保留兼容

# 粗筛规则
EXCLUDE_LISTS_DIR = Path("data/exclude")
MEME_LENGTH_RANGE = (3, 14)
MIN_PLATFORMS_CROSS = 1   # 单平台也算(只有 2 个源,且很多梗只单平台爆发)

# extract 阶段配置
BASELINE_WORDS_FILE = Path("data/baseline/common_words.txt")
EXTRACT_MIN_VIDEOS = 1          # 候选至少在 N 个不同视频出现。无登录态每视频只~3条热评,跨视频概率低,放宽到 1
EXTRACT_PHRASE_LEN_RANGE = (2, 8)  # 候选短语字符长度范围
EXTRACT_TOP_K = 30              # 最终候选数量
EXTRACT_NGRAM_NS = (1, 2, 3)    # 1-3 token 组合。单 token 靠基线词表 + 常用词过滤

# LLM (DeepSeek, OpenAI 兼容接口)
LLM_API_KEY = os.environ.get("LLM_API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
CLASSIFY_MODEL = "deepseek-chat"          # 便宜,做分类
EXPLAIN_MODEL = "deepseek-chat"           # 同一模型,释义条目少够用
LLM_BASE_URL = "https://api.deepseek.com/v1"
LLM_MAX_RETRY = 2
LLM_TIMEOUT = 30

# B站验证
BILI_VERIFY_THRESHOLD = 20
BILI_SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
HTTP_TIMEOUT = 20

# B站 discover: 热门视频 + 评论接口(2026-07 改版,直接抓评论区挖梗)
# 用 popular(热门流)而非 ranking(排行榜):ranking 在多数环境被 -352 风控,
# popular 更稳定且评论区更活跃。
BILI_POPULAR_URL = "https://api.bilibili.com/x/web-interface/popular"
BILI_REPLY_URL = "https://api.bilibili.com/x/v2/reply/main"

# 存储
DB_PATH = Path("data/memes.db")
DAILY_REPORT_DIR = Path("daily")

# pipeline
TODAY = None
