# 每日热梗采集工具 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每天自动抓取中文互联网热搜,经规则粗筛 → GLM 分类 → B站二创验证 → GLM 释义,产出当日梗日报并入库累积。

**Architecture:** Python 单一仓库,8 个职责单一的模块组成 pipeline。GitHub Actions 每天定时跑,SQLite 持久化,Markdown 日报 commit 回仓库供人阅读。

**Tech Stack:** Python 3.11+ / httpx / PyYAML / pytest / SQLite3 (stdlib) / GitHub Actions / 智谱 GLM (glm-4.5-air, glm-4.6) / 自部署 DailyHotApi

**Spec:** [`docs/specs/2026-07-05-daily-meme-tracker-design.md`](../specs/2026-07-05-daily-meme-tracker-design.md)

---

## File Structure

| 文件 | 职责 |
|:---|:---|
| `pyproject.toml` | 依赖、工具配置 |
| `src/geng/config.py` | 所有阈值、模型名、路径常量 |
| `src/geng/models.py` | dataclass: HotItem / Candidate / ClassifiedMeme / FinalMeme |
| `src/geng/discover.py` | 调 DailyHotApi,返回 list[HotItem] |
| `src/geng/filter.py` | 规则粗筛 |
| `src/geng/classify.py` | GLM-4.5-Air 分类 |
| `src/geng/verify.py` | B站搜索结果数验证 |
| `src/geng/explain.py` | GLM-4.6 释义 |
| `src/geng/store.py` | SQLite 读写 |
| `src/geng/report.py` | Markdown 日报生成 |
| `src/geng/pipeline.py` | 串联 1-6 + 降级 + 重试 |
| `src/geng/__main__.py` | CLI 入口 |
| `data/exclude/stars.txt` | 明星排除清单(种子) |
| `data/exclude/places.txt` | 地名排除清单(种子) |
| `data/exclude/shows.txt` | 节目/影视排除清单(种子) |
| `tests/` | 单元测试,fixture 数据 |
| `.github/workflows/daily.yml` | 定时任务 |

**约定:**
- 所有外部 IO(HTTP/LLM/文件/DB)集中在模块边界函数内,核心逻辑纯函数化
- 每个 pipeline 步骤函数签名为 `(input_list, *, client=None) -> output_list`,client 可注入便于 mock
- `FinalMeme` 是最终入库结构,各步骤函数逐步给 dataclass 字段填值

---

## Task 1: 项目骨架与依赖

**Files:**
- Create: `pyproject.toml`
- Create: `src/geng/__init__.py` (空)
- Create: `src/geng/config.py`
- Create: `README.md` (最简)
- Create: `.gitignore`

- [ ] **Step 1: 写 pyproject.toml**

```toml
[project]
name = "geng"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "tenacity>=8.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[project.scripts]
geng = "geng.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/geng"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: 写 config.py**

```python
"""集中配置: 阈值、模型名、路径常量。所有模块从这里读。"""
import os
from pathlib import Path

# 数据源
PLATFORMS = ["weibo", "bilibili", "douyin"]
DAILYHOT_API_BASE = os.environ.get("DAILYHOT_API_BASE", "https://api-hot.imsyy.top")

# 粗筛规则
EXCLUDE_LISTS_DIR = Path("data/exclude")
MEME_LENGTH_RANGE = (3, 14)          # 梗标题长度区间(字符数,含)
MIN_PLATFORMS_CROSS = 2              # 跨平台共振阈值

# LLM
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
CLASSIFY_MODEL = "glm-4.5-air"
EXPLAIN_MODEL = "glm-4.6"
LLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
LLM_MAX_RETRY = 2
LLM_TIMEOUT = 30

# B站验证
BILI_VERIFY_THRESHOLD = 20           # 二创视频数阈值
BILI_SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
HTTP_TIMEOUT = 20

# 存储
DB_PATH = Path("data/memes.db")
DAILY_REPORT_DIR = Path("daily")

# pipeline
TODAY = None  # 测试时注入,生产为 None 表示用 date.today()
```

- [ ] **Step 3: 写 .gitignore**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
.coverage
htmlcov/
*.egg-info/
build/
dist/
```

注意: `data/memes.db` 和 `daily/*.md` **不** gitignore——它们要 commit 回仓库。

- [ ] **Step 4: 写最简 README.md**

```markdown
# geng — 每日热梗采集工具

每天自动抓取中文互联网热搜,经规则粗筛 → GLM 分类 → B站二创验证 → GLM 释义,产出当日梗日报并入库累积。

详见 [设计文档](docs/specs/2026-07-05-daily-meme-tracker-design.md)。

## 使用

需要设置环境变量:
- `ZHIPU_API_KEY` — 智谱开放平台 API Key
- `DAILYHOT_API_BASE` — 自部署 DailyHotApi 地址(可选,默认用公共实例)

运行:
```bash
pip install -e .
geng
```
```

- [ ] **Step 5: 安装并验证**

Run: `pip install -e ".[dev]"`
Expected: 成功安装,geng 包可 import

Run: `python -c "import geng.config; print(geng.config.PLATFORMS)"`
Expected: 输出 `['weibo', 'bilibili', 'douyin']`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/geng/__init__.py src/geng/config.py README.md .gitignore
git commit -m "feat: project skeleton with config"
```

---

## Task 2: 数据模型 dataclass

**Files:**
- Create: `src/geng/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_models.py
from geng.models import HotItem, Candidate, ClassifiedMeme, FinalMeme

def test_hotitem_creation():
    item = HotItem(id="weibo-1", platform="weibo", title="测试标题", hot=1000, url="http://x", fetched_at="2026-07-05")
    assert item.title == "测试标题"
    assert item.platform == "weibo"

def test_classifiedmeme_defaults():
    m = ClassifiedMeme(title="YYDS", date="2026-07-05", platforms=["weibo"], hot_scores={"weibo": 100})
    assert m.is_meme is None
    assert m.confidence == 0.0
    assert m.classify_reason == ""

def test_finalmeme_carries_classified_fields():
    f = FinalMeme(title="YYDS", date="2026-07-05", platforms=["weibo"], hot_scores={"weibo": 100},
                  confidence=0.9, classify_reason="网络缩写")
    assert f.definition is None
    assert f.origin is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_models.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'geng.models'`

- [ ] **Step 3: 写 models.py**

```python
# src/geng/models.py
"""pipeline 各阶段流转的数据结构。字段随 pipeline 推进逐步填充。"""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class HotItem:
    """[1] discover 阶段输出: 一条原始热搜。"""
    id: str
    platform: str
    title: str
    hot: int
    url: str
    fetched_at: str            # ISO date

@dataclass
class Candidate:
    """[2] filter 阶段输出: 通过粗筛的候选梗。"""
    title: str
    date: str
    platforms: list[str]                # 出现在哪些平台
    hot_scores: dict[str, int]          # {platform: hot}

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
        return cls(
            title=m.title, date=m.date, platforms=m.platforms, hot_scores=m.hot_scores,
            confidence=m.confidence, classify_reason=m.classify_reason,
            verified=m.verified, bili_video_count=m.bili_video_count,
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/geng/models.py tests/test_models.py
git commit -m "feat: data models for pipeline stages"
```

---

## Task 3: discover 模块(抓热搜)

**Files:**
- Create: `src/geng/discover.py`
- Create: `tests/fixtures/weibo_sample.json`
- Test: `tests/test_discover.py`

- [ ] **Step 1: 准备 fixture**

```json
# tests/fixtures/weibo_sample.json
{
  "code": 200,
  "message": "success",
  "data": [
    {"id": "1", "title": "某明星离婚", "hot": "5000000", "url": "http://weibo.com/1", "mobileUrl": "http://m.weibo.cn/1"},
    {"id": "2", "title": "如何呢又能怎", "hot": "1200000", "url": "http://weibo.com/2", "mobileUrl": "http://m.weibo.cn/2"},
    {"id": "3", "title": "2026年7月5日", "hot": "300", "url": "http://weibo.com/3", "mobileUrl": "http://m.weibo.cn/3"}
  ]
}
```

- [ ] **Step 2: 写失败测试**

```python
# tests/test_discover.py
import json
from pathlib import Path
from geng.discover import fetch_trending, parse_platform_response
from geng.models import HotItem

FIXTURE = Path(__file__).parent / "fixtures" / "weibo_sample.json"

def test_parse_platform_response():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    items = parse_platform_response(raw, platform="weibo", date="2026-07-05")
    assert len(items) == 3
    assert isinstance(items[0], HotItem)
    assert items[0].platform == "weibo"
    assert items[0].hot == 5000000
    assert items[1].id == "weibo-2"

def test_fetch_trending_with_mock_client(monkeypatch):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    class FakeClient:
        def get_json(self, platform): return raw
    items = fetch_trending(["weibo"], date="2026-07-05", client=FakeClient())
    assert len(items) == 3
    assert all(i.platform == "weibo" for i in items)

def test_fetch_trending_skips_failed_platform(monkeypatch, caplog):
    class FlakyClient:
        def get_json(self, platform):
            if platform == "bilibili":
                raise RuntimeError("503")
            return json.loads(FIXTURE.read_text(encoding="utf-8"))
    items = fetch_trending(["weibo", "bilibili"], date="2026-07-05", client=FlakyClient())
    assert len(items) == 3  # bilibili 挂了,weibo 仍返回
    assert any("bilibili" in r.getMessage() for r in caplog.records)
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_discover.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 4: 写 discover.py**

```python
# src/geng/discover.py
"""[1] 调 DailyHotApi 抓各平台当日热搜。"""
from __future__ import annotations
import logging
from typing import Protocol
import httpx
from .models import HotItem
from . import config

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
        items.append(HotItem(
            id=f"{platform}-{entry.get('id') or entry.get('title')}",
            platform=platform,
            title=str(entry.get("title", "")).strip(),
            hot=hot,
            url=str(entry.get("url", "")).strip(),
            fetched_at=date,
        ))
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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_discover.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/geng/discover.py tests/test_discover.py tests/fixtures/weibo_sample.json
git commit -m "feat: discover module with graceful platform failure"
```

---

## Task 4: filter 模块(规则粗筛)

**Files:**
- Create: `data/exclude/stars.txt`, `data/exclude/places.txt`, `data/exclude/shows.txt` (种子清单)
- Create: `src/geng/filter.py`
- Test: `tests/test_filter.py`

- [ ] **Step 1: 写排除清单种子(每行一个词)**

```text
# data/exclude/stars.txt
# 明星/公众人物,包含即剔除
迪丽热巴
杨超越
易烊千玺
王一博
蔡徐坤
```

```text
# data/exclude/places.txt
# 地名,完全匹配或包含即剔除
北京
上海
广州
深圳
成都
```

```text
# data/exclude/shows.txt
# 综艺/影视/节目名
奔跑吧
向往的生活
乘风破浪
中国好声音
```

- [ ] **Step 2: 写失败测试**

```python
# tests/test_filter.py
from geng.filter import coarse_filter, is_pure_number, is_pure_date
from geng.models import HotItem

def _item(title, platform="weibo", hot=1000):
    return HotItem(id=f"{platform}-1", platform=platform, title=title, hot=hot, url="", fetched_at="2026-07-05")

def test_pure_number_excluded():
    assert is_pure_number("12345") is True
    assert is_pure_number("YYDS") is False

def test_pure_date_excluded():
    assert is_pure_date("2026年7月5日") is True
    assert is_pure_date("如何呢又能怎") is False

def test_length_filter():
    items = [_item("哦"), _item("这是一个非常非常非常非常非常长的标题超过十四字")]
    out = coarse_filter(items, date="2026-07-05")
    assert out == []

def test_star_excluded():
    out = coarse_filter([_item("迪丽热巴现身机场")], date="2026-07-05")
    assert out == []

def test_cross_platform_required():
    # 同标题只在一个平台,不过 MIN_PLATFORMS_CROSS=2
    items = [_item("如何呢又能怎", platform="weibo")]
    out = coarse_filter(items, date="2026-07-05")
    assert out == []

def test_cross_platform_passes():
    items = [
        _item("如何呢又能怎", platform="weibo", hot=1000),
        _item("如何呢又能怎", platform="bilibili", hot=2000),
    ]
    out = coarse_filter(items, date="2026-07-05")
    assert len(out) == 1
    assert out[0].title == "如何呢又能怎"
    assert set(out[0].platforms) == {"weibo", "bilibili"}
    assert out[0].hot_scores["bilibili"] == 2000
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_filter.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 4: 写 filter.py**

```python
# src/geng/filter.py
"""[2] 规则粗筛: 排除明显非梗,合并跨平台共振。"""
from __future__ import annotations
import re
from collections import defaultdict
from pathlib import Path
from .models import HotItem, Candidate
from . import config

_PURE_NUMBER = re.compile(r"^[\d.,]+$")
_PURE_DATE = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")

def is_pure_number(text: str) -> bool:
    return bool(_PURE_NUMBER.match(text.strip()))

def is_pure_date(text: str) -> bool:
    return bool(_PURE_DATE.search(text))

def _load_exclude_list(name: str) -> list[str]:
    path = config.EXCLUDE_LISTS_DIR / name
    if not path.exists():
        return []
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line)
    return words

def _matches_exclude(title: str, exclude_words: list[str]) -> bool:
    return any(w in title for w in exclude_words)

def coarse_filter(items: list[HotItem], date: str) -> list[Candidate]:
    """应用粗筛规则,按标题分组合并跨平台。"""
    lo, hi = config.MEME_LENGTH_RANGE
    stars = _load_exclude_list("stars.txt")
    places = _load_exclude_list("places.txt")
    shows = _load_exclude_list("shows.txt")
    exclude_words = stars + places + shows

    # 先按单条规则过滤
    survived: list[HotItem] = []
    for it in items:
        t = it.title
        if not t:
            continue
        if not (lo <= len(t) <= hi):
            continue
        if is_pure_number(t) or is_pure_date(t):
            continue
        if _matches_exclude(t, exclude_words):
            continue
        survived.append(it)

    # 按标题分组,统计跨平台
    groups: dict[str, list[HotItem]] = defaultdict(list)
    for it in survived:
        groups[it.title].append(it)

    candidates: list[Candidate] = []
    for title, group in groups.items():
        platforms = sorted({g.platform for g in group})
        if len(platforms) < config.MIN_PLATFORMS_CROSS:
            continue
        hot_scores: dict[str, int] = {}
        for g in group:
            hot_scores[g.platform] = max(hot_scores.get(g.platform, 0), g.hot)
        candidates.append(Candidate(
            title=title, date=date, platforms=platforms, hot_scores=hot_scores
        ))
    return candidates
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_filter.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add src/geng/filter.py tests/test_filter.py data/exclude/
git commit -m "feat: coarse filter with exclude lists and cross-platform grouping"
```

---

## Task 5: classify 模块(GLM 分类)

**Files:**
- Create: `src/geng/llm.py` (LLM 客户端封装)
- Create: `src/geng/classify.py`
- Test: `tests/test_classify.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_classify.py
import json
from geng.classify import classify_memes, build_classify_prompt, parse_classify_response
from geng.models import Candidate

def _candidate(title):
    return Candidate(title=title, date="2026-07-05", platforms=["weibo", "bilibili"], hot_scores={"weibo": 100})

def test_build_classify_prompt_contains_all_titles():
    prompt = build_classify_prompt([_candidate("YYDS"), _candidate("某明星离婚")])
    assert "YYDS" in prompt
    assert "某明星离婚" in prompt
    assert "JSON" in prompt

def test_parse_classify_response_valid():
    raw = '{"items": [{"title": "YYDS", "is_meme": true, "confidence": 0.95, "reason": "网络缩写"}]}'
    parsed = parse_classify_response(raw)
    assert len(parsed) == 1
    assert parsed[0]["is_meme"] is True
    assert parsed[0]["confidence"] == 0.95

def test_parse_classify_response_handles_garbage():
    parsed = parse_classify_response("这不是JSON")
    assert parsed == []

def test_classify_memes_with_mock_client():
    class MockLLM:
        def chat(self, model, messages):
            return '{"items": [{"title": "YYDS", "is_meme": true, "confidence": 0.9, "reason": "缩写梗"}]}'
    out = classify_memes([_candidate("YYDS")], client=MockLLM())
    assert len(out) == 1
    assert out[0].is_meme is True
    assert out[0].confidence == 0.9

def test_classify_memes_filters_non_meme():
    class MockLLM:
        def chat(self, model, messages):
            return '{"items": [{"title": "YYDS", "is_meme": true, "confidence": 0.9, "reason": ""}, {"title": "新闻", "is_meme": false, "confidence": 0.1, "reason": "新闻"}]}'
    out = classify_memes([_candidate("YYDS"), _candidate("新闻")], client=MockLLM())
    assert len(out) == 1
    assert out[0].title == "YYDS"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_classify.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: 写 llm.py**

```python
# src/geng/llm.py
"""智谱 GLM 客户端封装,带重试。接口设计为可 mock。"""
from __future__ import annotations
from typing import Protocol
import json
import logging
import httpx
from tenacity import retry, stop_after_attempt
from . import config

log = logging.getLogger(__name__)

class LLMClient(Protocol):
    def chat(self, model: str, messages: list[dict]) -> str: ...

class GLMClient:
    """生产实现: 调智谱 GLM。"""
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.ZHIPU_API_KEY
        if not self.api_key:
            raise RuntimeError("ZHIPU_API_KEY 未设置")

    @retry(stop=stop_after_attempt(config.LLM_MAX_RETRY + 1), reraise=True)
    def chat(self, model: str, messages: list[dict]) -> str:
        url = f"{config.LLM_BASE_URL}/chat/completions"
        with httpx.Client(timeout=config.LLM_TIMEOUT) as client:
            resp = client.post(
                url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages, "temperature": 0.3},
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]
```

- [ ] **Step 4: 写 classify.py**

```python
# src/geng/classify.py
"""[3] 调 GLM-4.5-Air 判断每条候选是否为真梗。"""
from __future__ import annotations
import json
import logging
from .models import Candidate, ClassifiedMeme
from .llm import LLMClient, GLMClient
from . import config

log = logging.getLogger(__name__)

_SYSTEM = (
    "你是中文网络流行语专家。判断每个标题是否属于'网络梗'(可被网友移植使用的"
    "名场面/金句/新造词/二创源泉),而不是单纯的明星八卦、社会新闻、节目名、"
    "民生话题。严格按 JSON 输出,不要多余文字。"
)

def build_classify_prompt(candidates: list[Candidate]) -> str:
    lines = ["请判断以下标题是否为'网络梗',输出 JSON:", "{"]
    lines.append('  "items": [')
    for i, c in enumerate(candidates):
        comma = "," if i < len(candidates) - 1 else ""
        lines.append(f'    {{"title": "{c.title}"}}{comma}')
    lines.append("  ]")
    lines.append("}")
    lines.append(
        "请只输出形如 {\"items\": [{\"title\":\"...\",\"is_meme\":true/false,"
        "\"confidence\":0.0-1.0,\"reason\":\"一句话\"}]} 的 JSON,is_meme 是 bool。"
    )
    return "\n".join(lines)

def parse_classify_response(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 容错: 截取第一个 JSON 对象
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            return []
        try:
            data = json.loads(raw[start:end+1])
        except json.JSONDecodeError:
            return []
    return data.get("items", [])

def classify_memes(
    candidates: list[Candidate],
    client: LLMClient | None = None,
    batch_size: int = 20,
) -> list[ClassifiedMeme]:
    """分批调用 LLM,返回判定为梗的 ClassifiedMeme。"""
    client = client or GLMClient()
    out: list[ClassifiedMeme] = []
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i+batch_size]
        if not batch:
            continue
        try:
            raw = client.chat(config.CLASSIFY_MODEL, [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": build_classify_prompt(batch)},
            ])
            parsed = parse_classify_response(raw)
        except Exception as e:
            log.warning("classify: LLM 调用失败,降级保留全部候选: %s", e)
            for c in batch:
                out.append(ClassifiedMeme(
                    title=c.title, date=c.date, platforms=c.platforms,
                    hot_scores=c.hot_scores, is_meme=None, confidence=0.0,
                    classify_reason="LLM分类失败,降级保留",
                ))
            continue
        # 建立 title → 解析结果 映射
        by_title = {p["title"]: p for p in parsed if "title" in p}
        for c in batch:
            p = by_title.get(c.title, {})
            is_meme = bool(p.get("is_meme", False))
            if not is_meme:
                continue
            out.append(ClassifiedMeme(
                title=c.title, date=c.date, platforms=c.platforms,
                hot_scores=c.hot_scores, is_meme=True,
                confidence=float(p.get("confidence", 0.5)),
                classify_reason=str(p.get("reason", "")),
            ))
    return out
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_classify.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/geng/llm.py src/geng/classify.py tests/test_classify.py
git commit -m "feat: classify module with GLM client and degradation"
```

---

## Task 6: verify 模块(B站二创验证)

**Files:**
- Create: `src/geng/verify.py`
- Test: `tests/test_verify.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_verify.py
from geng.verify import verify_bilibili, parse_bili_count, BiliSearchClient
from geng.models import ClassifiedMeme

def _meme(title, is_meme=True):
    return ClassifiedMeme(
        title=title, date="2026-07-05", platforms=["weibo", "bilibili"],
        hot_scores={"weibo": 100}, is_meme=is_meme, confidence=0.9,
    )

def test_parse_bili_count_handles_response():
    raw = {"data": {"numResults": 234}}
    assert parse_bili_count(raw) == 234

def test_parse_bili_count_handles_missing():
    assert parse_bili_count({}) is None
    assert parse_bili_count({"data": {}}) is None

def test_verify_marks_above_threshold():
    class MockClient:
        def search_count(self, keyword): return 100
    out = verify_bilibili([_meme("YYDS")], client=MockClient())
    assert out[0].verified is True
    assert out[0].bili_video_count == 100

def test_verify_marks_below_threshold():
    class MockClient:
        def search_count(self, keyword): return 5
    out = verify_bilibili([_meme("冷门")], client=MockClient())
    assert out[0].verified is False
    assert out[0].bili_video_count == 5

def test_verify_handles_failure():
    class MockClient:
        def search_count(self, keyword): raise RuntimeError("503")
    out = verify_bilibili([_meme("YYDS")], client=MockClient())
    assert out[0].verified is None
    assert out[0].bili_video_count is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_verify.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: 写 verify.py**

```python
# src/geng/verify.py
"""[4] 查 B站搜索结果数,验证是否有足够二创。"""
from __future__ import annotations
import logging
from typing import Protocol
import httpx
from .models import ClassifiedMeme
from . import config

log = logging.getLogger(__name__)

class BiliSearchClient(Protocol):
    def search_count(self, keyword: str) -> int | None: ...

class HttpxBiliClient:
    """生产实现: 调 B站搜索 API。"""
    def search_count(self, keyword: str) -> int | None:
        params = {"search_type": "video", "keyword": keyword, "page_size": 1}
        headers = {"User-Agent": "Mozilla/5.0"}
        with httpx.Client(timeout=config.HTTP_TIMEOUT) as client:
            resp = client.get(config.BILI_SEARCH_URL, params=params, headers=headers)
            resp.raise_for_status()
            return parse_bili_count(resp.json())

def parse_bili_count(raw: dict) -> int | None:
    try:
        return raw["data"]["numResults"]
    except (KeyError, TypeError):
        return None

def verify_bilibili(
    memes: list[ClassifiedMeme],
    client: BiliSearchClient | None = None,
    threshold: int | None = None,
) -> list[ClassifiedMeme]:
    """对每条梗查 B站搜索数,填入 verified 与 bili_video_count。失败标 None。"""
    client = client or HttpxBiliClient()
    threshold = config.BILI_VERIFY_THRESHOLD if threshold is None else threshold
    for m in memes:
        try:
            count = client.search_count(m.title)
        except Exception as e:
            log.warning("verify: B站查询失败 (%s): %s", m.title, e)
            m.verified = None
            m.bili_video_count = None
            continue
        if count is None:
            m.verified = None
            m.bili_video_count = None
        else:
            m.verified = count >= threshold
            m.bili_video_count = count
    return memes
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_verify.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/geng/verify.py tests/test_verify.py
git commit -m "feat: bilibili verification module"
```

---

## Task 7: explain 模块(GLM 释义)

**Files:**
- Create: `src/geng/explain.py`
- Test: `tests/test_explain.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_explain.py
import json
from geng.explain import explain_meme, build_explain_prompt, parse_explain_response
from geng.models import ClassifiedMeme, FinalMeme

def _meme():
    return ClassifiedMeme(
        title="YYDS", date="2026-07-05", platforms=["weibo", "bilibili"],
        hot_scores={"weibo": 100}, is_meme=True, confidence=0.9,
        verified=True, bili_video_count=234,
    )

def test_build_explain_prompt_includes_title():
    p = build_explain_prompt(_meme())
    assert "YYDS" in p
    assert "释义" in p
    assert "JSON" in p

def test_parse_explain_response_valid():
    raw = '{"definition":"永远的神","origin":"电竞圈","usage":"赞美","examples":["科比YYDS"]}'
    d = parse_explain_response(raw)
    assert d["definition"] == "永远的神"
    assert d["examples"] == ["科比YYDS"]

def test_parse_explain_response_partial():
    raw = '{"definition":"某梗"}'
    d = parse_explain_response(raw)
    assert d["definition"] == "某梗"
    assert d["examples"] == []

def test_parse_explain_response_garbage():
    d = parse_explain_response("nope")
    assert d == {}

def test_explain_meme_with_mock():
    class MockLLM:
        def chat(self, model, messages):
            return '{"definition":"永远的神","origin":"电竞圈","usage":"赞美某人/某物","examples":["科比YYDS","这游戏YYDS"]}'
    out = explain_meme([_meme()], client=MockLLM())
    assert len(out) == 1
    f = out[0]
    assert isinstance(f, FinalMeme)
    assert f.definition == "永远的神"
    assert f.origin == "电竞圈"
    assert f.examples == ["科比YYDS", "这游戏YYDS"]
    assert f.verified is True

def test_explain_meme_failure_keeps_record():
    class MockLLM:
        def chat(self, model, messages): raise RuntimeError("500")
    out = explain_meme([_meme()], client=MockLLM())
    assert len(out) == 1
    assert out[0].definition is None   # 释义留空但记录仍在
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_explain.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: 写 explain.py**

```python
# src/geng/explain.py
"""[5] 调 GLM-4.6 为每条梗生成释义、出处、用法、例句。"""
from __future__ import annotations
import json
import logging
from .models import ClassifiedMeme, FinalMeme
from .llm import LLMClient, GLMClient
from . import config

log = logging.getLogger(__name__)

def build_explain_prompt(m: ClassifiedMeme) -> str:
    return (
        f"请解释中文网络梗「{m.title}」。严格输出 JSON,字段:\n"
        '- "definition": 这是什么梗(1-2句)\n'
        '- "origin": 出处(来自哪个事件/人物/作品)\n'
        '- "usage": 怎么在句子里用\n'
        '- "examples": 例句数组(1-2个)\n'
        "只输出 JSON,不要多余文字。如果不确定是不是真梗,definition 留空字符串。"
    )

def parse_explain_response(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            return {}
        try:
            data = json.loads(raw[start:end+1])
        except json.JSONDecodeError:
            return {}
    data.setdefault("examples", [])
    if not isinstance(data["examples"], list):
        data["examples"] = []
    return data

def explain_meme(
    memes: list[ClassifiedMeme],
    client: LLMClient | None = None,
) -> list[FinalMeme]:
    """逐条调 GLM-4.6 释义,失败时仍返回 FinalMeme(释义字段留空)。"""
    client = client or GLMClient()
    out: list[FinalMeme] = []
    for m in memes:
        f = FinalMeme.from_classified(m)
        try:
            raw = client.chat(config.EXPLAIN_MODEL, [
                {"role": "user", "content": build_explain_prompt(m)},
            ])
            d = parse_explain_response(raw)
            f.definition = d.get("definition") or None
            f.origin = d.get("origin") or None
            f.usage = d.get("usage") or None
            f.examples = d.get("examples", [])
        except Exception as e:
            log.warning("explain: 释义失败 (%s): %s", m.title, e)
            f.definition = None
        out.append(f)
    return out
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_explain.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/geng/explain.py tests/test_explain.py
git commit -m "feat: explain module with GLM-4.6 and graceful failure"
```

---

## Task 8: store 模块(SQLite)

**Files:**
- Create: `src/geng/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_store.py
import json
from pathlib import Path
from geng.store import init_db, save_to_db, query_by_date
from geng.models import FinalMeme

def _meme(title="YYDS", date="2026-07-05"):
    return FinalMeme(
        title=title, date=date, platforms=["weibo", "bilibili"],
        hot_scores={"weibo": 100}, confidence=0.9, classify_reason="缩写",
        verified=True, bili_video_count=234, definition="永远的神",
        origin="电竞圈", usage="赞美", examples=["科比YYDS"],
    )

def test_save_and_query(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    n = save_to_db([_meme()], date="2026-07-05", db_path=db)
    assert n == 1
    rows = query_by_date("2026-07-05", db_path=db)
    assert len(rows) == 1
    assert rows[0]["title"] == "YYDS"
    assert json.loads(rows[0]["platforms"]) == ["weibo", "bilibili"]
    assert rows[0]["verified"] == 1
    assert json.loads(rows[0]["examples"]) == ["科比YYDS"]

def test_dedup_same_title_same_date(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    save_to_db([_meme("YYDS", "2026-07-05")], date="2026-07-05", db_path=db)
    # 同一天同标题不重复
    save_to_db([_meme("YYDS", "2026-07-05")], date="2026-07-05", db_path=db)
    rows = query_by_date("2026-07-05", db_path=db)
    assert len(rows) == 1

def test_different_date_keeps_both(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    save_to_db([_meme("YYDS", "2026-07-05")], date="2026-07-05", db_path=db)
    save_to_db([_meme("YYDS", "2026-07-06")], date="2026-07-06", db_path=db)
    assert len(query_by_date("2026-07-05", db_path=db)) == 1
    assert len(query_by_date("2026-07-06", db_path=db)) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_store.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: 写 store.py**

```python
# src/geng/store.py
"""[6] SQLite 读写。JSON 字段以文本存。"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from .models import FinalMeme
from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    date             TEXT NOT NULL,
    platforms        TEXT NOT NULL,
    hot_scores       TEXT,
    confidence       REAL,
    classify_reason  TEXT,
    verified         INTEGER,
    bili_video_count INTEGER,
    definition       TEXT,
    origin           TEXT,
    usage            TEXT,
    examples         TEXT,
    created_at       TEXT NOT NULL,
    UNIQUE(title, date)
);
CREATE INDEX IF NOT EXISTS idx_date ON memes(date);
CREATE INDEX IF NOT EXISTS idx_verified ON memes(verified);
"""

def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)

def save_to_db(memes: list[FinalMeme], date: str, db_path: Path | None = None) -> int:
    import datetime
    now = datetime.datetime.now().isoformat()
    n = 0
    with _connect(db_path) as conn:
        for m in memes:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO memes
                    (title, date, platforms, hot_scores, confidence, classify_reason,
                     verified, bili_video_count, definition, origin, usage, examples, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        m.title, m.date, json.dumps(m.platforms, ensure_ascii=False),
                        json.dumps(m.hot_scores, ensure_ascii=False),
                        m.confidence, m.classify_reason,
                        _bool_to_int(m.verified), m.bili_video_count,
                        m.definition, m.origin, m.usage,
                        json.dumps(m.examples, ensure_ascii=False), now,
                    ),
                )
                n += conn.total_changes and 1 or 0
            except sqlite3.IntegrityError:
                continue
        conn.commit()
    return n

def _bool_to_int(v) -> int | None:
    if v is None: return None
    return 1 if v else 0

def query_by_date(date: str, db_path: Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM memes WHERE date = ? ORDER BY id", (date,)).fetchall()
    return [dict(r) for r in rows]
```

注:`save_to_db` 返回值用 cursor rowcount 更准确——见 Step 4 调整,这里先让测试通过。

- [ ] **Step 4: 运行测试,修正计数 bug**

Run: `pytest tests/test_store.py -v`
Expected: `test_save_and_query` 可能因计数逻辑失败。

修正 `save_to_db` 用 cursor.rowcount:

```python
# 替换 save_to_db 函数体
def save_to_db(memes: list[FinalMeme], date: str, db_path: Path | None = None) -> int:
    import datetime
    now = datetime.datetime.now().isoformat()
    n = 0
    with _connect(db_path) as conn:
        for m in memes:
            cur = conn.execute(
                """INSERT OR IGNORE INTO memes
                (title, date, platforms, hot_scores, confidence, classify_reason,
                 verified, bili_video_count, definition, origin, usage, examples, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    m.title, m.date, json.dumps(m.platforms, ensure_ascii=False),
                    json.dumps(m.hot_scores, ensure_ascii=False),
                    m.confidence, m.classify_reason,
                    _bool_to_int(m.verified), m.bili_video_count,
                    m.definition, m.origin, m.usage,
                    json.dumps(m.examples, ensure_ascii=False), now,
                ),
            )
            n += cur.rowcount
        conn.commit()
    return n
```

Run: `pytest tests/test_store.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/geng/store.py tests/test_store.py
git commit -m "feat: sqlite store with dedup and query"
```

---

## Task 9: report 模块(Markdown 日报)

**Files:**
- Create: `src/geng/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_report.py
import json
from pathlib import Path
from geng.report import render_daily_report
from geng.models import FinalMeme

def _meme(title, verified=True, definition="某释义"):
    return FinalMeme(
        title=title, date="2026-07-05", platforms=["weibo", "bilibili"],
        hot_scores={"weibo": 1000}, confidence=0.9, classify_reason="",
        verified=verified, bili_video_count=234 if verified else 5,
        definition=definition, origin="某事件", usage="赞美", examples=["例句"],
    )

def test_report_has_header_and_stats(tmp_path):
    path = render_daily_report([_meme("YYDS", True), _meme("待观察", False)], date="2026-07-05", total_raw=87, out_dir=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "2026-07-05 热梗日报" in text
    assert "87" in text              # 原始数量
    assert "2" in text               # 入库数量

def test_report_separates_verified_and_observing(tmp_path):
    path = render_daily_report([_meme("YYDS", True), _meme("待观察", False)], date="2026-07-05", total_raw=10, out_dir=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "已验证" in text
    assert "待观察" in text
    assert text.index("YYDS") < text.index("待观察")

def test_report_contains_explanation_fields(tmp_path):
    path = render_daily_report([_meme("YYDS", True)], date="2026-07-05", total_raw=10, out_dir=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "释义" in text
    assert "出处" in text
    assert "用法" in text
    assert "例句" in text
    assert "某释义" in text

def test_report_filename(tmp_path):
    path = render_daily_report([_meme("YYDS", True)], date="2026-07-05", total_raw=10, out_dir=tmp_path)
    assert path.name == "2026-07-05.md"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_report.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: 写 report.py**

```python
# src/geng/report.py
"""[6] 生成当日 Markdown 日报。"""
from __future__ import annotations
from pathlib import Path
from .models import FinalMeme
from . import config

def render_daily_report(
    memes: list[FinalMeme],
    date: str,
    total_raw: int,
    out_dir: Path | None = None,
) -> Path:
    out_dir = out_dir or config.DAILY_REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    verified = [m for m in memes if m.verified is True]
    observing = [m for m in memes if m.verified is not True]

    lines: list[str] = []
    lines.append(f"# {date} 热梗日报")
    lines.append("")
    lines.append(f"> 共采集 {total_raw} 条热搜,经筛选入库 {len(memes)} 条(其中 {len(verified)} 条已验证)")
    lines.append("")

    lines.append("## ✅ 已验证梗")
    lines.append("")
    for i, m in enumerate(verified, 1):
        lines.extend(_render_meme(i, m))
        lines.append("")

    if observing:
        lines.append("## 🔍 待观察(未通过二创验证)")
        lines.append("")
        for i, m in enumerate(observing, 1):
            lines.extend(_render_meme(i, m))
            lines.append("")

    lines.append("---")
    lines.append("*数据源: 微博 / B站 / 抖音  •  释义由 GLM-4.6 生成*")
    lines.append("")

    path = out_dir / f"{date}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

def _render_meme(idx: int, m: FinalMeme) -> list[str]:
    platforms_str = " / ".join(f"{p}🔥" for p in m.platforms)
    bili_str = f"约 {m.bili_video_count} 个视频" if m.bili_video_count is not None else "未验证"
    out = [
        f"### {idx}. {m.title}",
        f"- **释义**: {m.definition or '(无)'}",
        f"- **出处**: {m.origin or '(无)'}",
        f"- **用法**: {m.usage or '(无)'}",
        f"- **例句**: {'; '.join(m.examples) if m.examples else '(无)'}",
        f"- **B站二创**: {bili_str}",
        f"- **来源**: {platforms_str}",
        "",
    ]
    return out
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_report.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/geng/report.py tests/test_report.py
git commit -m "feat: markdown daily report generator"
```

---

## Task 10: pipeline 串联 + 降级

**Files:**
- Create: `src/geng/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: 写失败测试(集成,mock 所有外部依赖)**

```python
# tests/test_pipeline.py
from geng.pipeline import run_daily
from geng.store import init_db, query_by_date

def test_run_daily_end_to_end(tmp_path, monkeypatch):
    db_path = tmp_path / "memes.db"
    report_dir = tmp_path / "daily"
    init_db(db_path)

    # mock discover
    from geng.models import HotItem
    fake_items = [
        HotItem(id="w1", platform="weibo", title="YYDS", hot=1000, url="", fetched_at="2026-07-05"),
        HotItem(id="b1", platform="bilibili", title="YYDS", hot=2000, url="", fetched_at="2026-07-05"),
        HotItem(id="w2", platform="weibo", title="某明星离婚", hot=5000, url="", fetched_at="2026-07-05"),
        HotItem(id="b2", platform="bilibili", title="某明星离婚", hot=3000, url="", fetched_at="2026-07-05"),
    ]
    monkeypatch.setattr("geng.pipeline.discover.fetch_trending", lambda **kw: fake_items)

    # mock classify
    class FakeLLM:
        def chat(self, model, messages):
            if "classify" in model or "air" in model:
                return '{"items":[{"title":"YYDS","is_meme":true,"confidence":0.9,"reason":"缩写"},{"title":"某明星离婚","is_meme":false,"confidence":0.1,"reason":"八卦"}]}'
            return '{"definition":"永远的神","origin":"电竞","usage":"赞美","examples":["科比YYDS"]}'
    monkeypatch.setattr("geng.pipeline.classify.GLMClient", lambda *a, **kw: FakeLLM())
    monkeypatch.setattr("geng.pipeline.explain.GLMClient", lambda *a, **kw: FakeLLM())

    # mock bili
    class FakeBili:
        def search_count(self, kw): return 234
    monkeypatch.setattr("geng.pipeline.verify.HttpxBiliClient", lambda *a, **kw: FakeBili())

    n = run_daily(date="2026-07-05", db_path=db_path, report_dir=report_dir)
    assert n == 1   # 只有 YYDS
    rows = query_by_date("2026-07-05", db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["title"] == "YYDS"
    assert (report_dir / "2026-07-05.md").exists()

def test_run_daily_degrades_when_llm_fails(tmp_path, monkeypatch):
    """LLM 分类挂掉时,粗筛候选仍入库(标记为降级)。"""
    db_path = tmp_path / "memes.db"
    report_dir = tmp_path / "daily"
    init_db(db_path)

    from geng.models import HotItem
    fake_items = [
        HotItem(id="w1", platform="weibo", title="YYDS", hot=1000, url="", fetched_at="2026-07-05"),
        HotItem(id="b1", platform="bilibili", title="YYDS", hot=2000, url="", fetched_at="2026-07-05"),
    ]
    monkeypatch.setattr("geng.pipeline.discover.fetch_trending", lambda **kw: fake_items)

    class FailingLLM:
        def chat(self, model, messages): raise RuntimeError("500")
    monkeypatch.setattr("geng.pipeline.classify.GLMClient", lambda *a, **kw: FailingLLM())
    monkeypatch.setattr("geng.pipeline.explain.GLMClient", lambda *a, **kw: FailingLLM())
    class FakeBili:
        def search_count(self, kw): return 234
    monkeypatch.setattr("geng.pipeline.verify.HttpxBiliClient", lambda *a, **kw: FakeBili())

    n = run_daily(date="2026-07-05", db_path=db_path, report_dir=report_dir)
    # 分类失败降级,粗筛候选(YYDS)仍入库
    assert n == 1
    rows = query_by_date("2026-07-05", db_path=db_path)
    assert "降级" in rows[0]["classify_reason"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: 写 pipeline.py**

```python
# src/geng/pipeline.py
"""串联 discover → filter → classify → verify → explain → store + report。
每个外部依赖都用模块级引用,便于测试 monkeypatch。失败降级不阻塞。"""
from __future__ import annotations
import logging
from pathlib import Path
from . import discover, filter as filter_mod, classify, verify, explain, store, report

log = logging.getLogger(__name__)

def run_daily(
    date: str | None = None,
    db_path: Path | None = None,
    report_dir: Path | None = None,
) -> int:
    """跑完整 pipeline,返回入库条数。"""
    import datetime
    date = date or datetime.date.today().isoformat()

    # [1] 发现
    items = discover.fetch_trending(date=date)
    total_raw = len(items)
    log.info("[1] discover: %d 条原始热搜", total_raw)

    # [2] 粗筛
    candidates = filter_mod.coarse_filter(items, date=date)
    log.info("[2] filter: %d 条候选", len(candidates))

    # [3] LLM 分类 (内部已降级)
    classified = classify.classify_memes(candidates)
    log.info("[3] classify: %d 条判定为梗", len(classified))

    # [4] B站验证
    verified = verify.verify_bilibili(classified)
    log.info("[4] verify: %d 条已验证", sum(1 for m in verified if m.verified))

    # [5] LLM 释义 (内部已降级)
    finals = explain.explain_meme(verified)
    log.info("[5] explain: %d 条释义完成", sum(1 for f in finals if f.definition))

    # [6] 入库 + 日报
    store.init_db(db_path)
    n = store.save_to_db(finals, date=date, db_path=db_path)
    report.render_daily_report(finals, date=date, total_raw=total_raw, out_dir=report_dir)
    log.info("[6] store: 入库 %d 条, 日报已生成", n)
    return n
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_pipeline.py -v`
Expected: 2 passed

- [ ] **Step 5: 跑全部测试确认无回归**

Run: `pytest -v`
Expected: 所有测试通过

- [ ] **Step 6: Commit**

```bash
git add src/geng/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline orchestration with degradation"
```

---

## Task 11: CLI 入口

**Files:**
- Create: `src/geng/__main__.py`
- Test: 手动验证

- [ ] **Step 1: 写 __main__.py**

```python
# src/geng/__main__.py
"""CLI 入口: geng [date]"""
import sys
import logging
from .pipeline import run_daily

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    date = sys.argv[1] if len(sys.argv) > 1 else None
    n = run_daily(date=date)
    print(f"完成: 入库 {n} 条")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 手动验证(无 API Key 时应优雅降级)**

Run: `geng 2026-07-05`
Expected: 日志显示各阶段进度,discover 可能因无网络失败但流程不崩,最终打印"完成: 入库 0 条"

- [ ] **Step 3: Commit**

```bash
git add src/geng/__main__.py
git commit -m "feat: CLI entrypoint"
```

---

## Task 12: GitHub Actions 工作流

**Files:**
- Create: `.github/workflows/daily.yml`

- [ ] **Step 1: 写工作流**

```yaml
# .github/workflows/daily.yml
name: Daily Meme Collection

on:
  schedule:
    # UTC 15:00 = 北京时间 23:00
    - cron: "0 15 * * *"
  workflow_dispatch:    # 支持手动触发

permissions:
  contents: write       # 允许 commit 回仓库

concurrency:
  group: daily-meme
  cancel-in-progress: false    # 不允许并发跑(保护 SQLite)

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install
        run: pip install -e .

      - name: Run pipeline
        env:
          ZHIPU_API_KEY: ${{ secrets.ZHIPU_API_KEY }}
          DAILYHOT_API_BASE: ${{ secrets.DAILYHOT_API_BASE }}
        run: geng

      - name: Commit results
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/memes.db daily/ || true
          if git diff --staged --quiet; then
            echo "无新增数据"
          else
            git commit -m "data: $(date -u +%Y-%m-%d) daily memes"
            git push
          fi
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/daily.yml
git commit -m "ci: daily GitHub Actions workflow"
git push origin main
```

- [ ] **Step 3: 在 GitHub 仓库手动触发验证**

去仓库 Actions 页 → "Daily Meme Collection" → Run workflow → 确认跑通(注意:此时需已配好 Secrets,否则会降级返回 0 条)

---

## Task 13: README 完善与文档

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 重写 README**

```markdown
# geng — 每日热梗采集工具

每天自动抓取中文互联网热搜,经**规则粗筛 → GLM 分类 → B站二创验证 → GLM 释义**四层漏斗,产出当日"真梗"日报并入库累积。

## 工作原理

```
100 条热搜 → 粗筛 30 条候选 → GLM 分类 10 条真梗 → B站验证 5 条 → GLM 释义 → 入库 + 日报
```

详见 [设计文档](docs/specs/2026-07-05-daily-meme-tracker-design.md)。

## 查看方式

- **当日梗**: 打开 [daily/](daily/) 目录,点当天日期的 `.md` 文件
- **历史/统计**: 用 [DB Browser for SQLite](https://sqlitebrowser.org/) 打开 `data/memes.db`

## 部署

### 1. 准备 API Key

- **智谱 GLM**: 去 https://open.bigmodel.cn 注册,创建 API Key
- **DailyHotApi**: Fork [imsyy/DailyHotApi](https://github.com/imsyy/DailyHotApi),部署到 Vercel

### 2. 配置 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 添加:
- `ZHIPU_API_KEY` — 智谱 API Key
- `DAILYHOT_API_BASE` — 你部署的 DailyHotApi 地址(如 `https://xxx.vercel.app`)

### 3. 启用 Actions

默认每天北京时间 23:00 自动跑。也可在 Actions 页手动触发。

## 本地运行

```bash
pip install -e ".[dev]"
export ZHIPU_API_KEY=xxx
geng                  # 跑当天
geng 2026-07-05       # 跑指定日期
pytest                # 跑测试
```

## 成本

- GitHub Actions: 公开仓库免费
- Vercel DailyHotApi: 免费额度足够
- 智谱 GLM: < ¥0.1/天,约 ¥3/月

## 已知局限

- AI 释义不是词典级权威,偶有不准确
- 抽查发现误判时,可往 `data/exclude/stars.txt` 等清单加词
- 初期排除清单薄,误判会偏多,需要养几周
```

- [ ] **Step 2: Commit & push**

```bash
git add README.md
git commit -m "docs: comprehensive README"
git push origin main
```

---

## Self-Review 结果

**Spec 覆盖检查:**
- [x] 发现 → Task 3
- [x] 粗筛规则(长度/排除清单/跨平台/纯数字日期)→ Task 4
- [x] GLM 分类(批量 + JSON 解析 + 降级)→ Task 5
- [x] B站验证(阈值 + 失败处理)→ Task 6
- [x] GLM 释义(逐条 + 失败保留)→ Task 7
- [x] SQLite(去重 + 索引 + 查询)→ Task 8
- [x] Markdown 日报(已验证/待观察分区)→ Task 9
- [x] pipeline 串联 + 降级 → Task 10
- [x] GitHub Actions + commit 回仓库 → Task 12
- [x] CLI → Task 11

**Placeholder 扫描:** 无 TODO/TBD,所有代码块完整。

**类型一致性:** `HotItem → Candidate → ClassifiedMeme → FinalMeme` 字段链路已对齐,`FinalMeme.from_classified` 桥接 verify→explain。

**已知简化(诚实):**
- B站搜索 API 无 key 可能有限流,生产中可能需要 cookie。Task 6 的 HttpxBiliClient 可后续加 cookie
- DailyHotApi 各平台返回字段略有差异,Task 3 的 parse 用 `entry.get` 容错
- 排除清单是种子,真实使用需要扩充
