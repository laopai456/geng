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

# 存储
DB_PATH = Path("data/memes.db")
DAILY_REPORT_DIR = Path("daily")

# pipeline
TODAY = None
