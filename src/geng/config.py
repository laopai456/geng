"""集中配置: 阈值、模型名、路径常量。所有模块从这里读。"""
import os
from pathlib import Path

# 数据源
PLATFORMS = ["weibo", "bilibili", "douyin"]
DAILYHOT_API_BASE = os.environ.get("DAILYHOT_API_BASE", "https://api-hot.imsyy.top")

# 粗筛规则
EXCLUDE_LISTS_DIR = Path("data/exclude")
MEME_LENGTH_RANGE = (3, 14)
MIN_PLATFORMS_CROSS = 2

# LLM
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
CLASSIFY_MODEL = "glm-4.5-air"
EXPLAIN_MODEL = "glm-4.6"
LLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
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
