# 每日热梗采集工具 (geng) — 设计文档

- **状态**: 设计待确认
- **日期**: 2026-07-05
- **仓库**: https://github.com/laopai456/geng

## 1. 目标

每天自动采集中文互联网当天**真正成为"梗"**的内容(名场面 / 金句 / 新造词 / 二创源泉),并为每条梗生成释义、出处、用法、例句。长期累积成一个可查询的本地梗库。

### 显式不做 (YAGNI)

- 不做"热搜聚合浏览"——已有 DailyHot 等成熟项目
- 不做梗释义的人工精修百科——小鸡词典那种死掉的能力,工具补不回来,只做 AI 释义
- 不做实时推送 / Web 应用——本期只做"采集 + 入库 + 日报",推送和网站留到后续

### 已知质量天花板 (诚实陈述)

- 每日热搜约 100 条,其中真正能成"梗"的约 10-15 条,工具通过三层漏斗尽量降噪
- AI 释义是事后解读,不是词典级权威释义
- 当天刚爆的梗,萌娘百科 / 百度百科可能尚未收录,释义完全依赖 AI

## 2. 架构与数据流

```
GitHub Actions  (cron: 每天 UTC 15:00 = 北京时间 23:00)
        ↓
[1] 发现   调自部署 DailyHotApi → 微博 + B站 + 抖音 当日热搜
                                                    (~100 条原始)
        ↓
[2] 粗筛    规则过滤明显非梗:
            • 排除明星库 / 地名 / 节目名 (硬排除清单)
            • 文本长度 3-14 字
            • 跨平台出现 ≥2 次
            • 排除纯数字 / 纯日期 / 纯 URL
                                                    (~30-40 条候选)
        ↓
[3] LLM 分类    GLM-4.5-Air 批量判断
            每条返回: is_meme(bool) + confidence(0-1) + 一句话理由
                                                    (~10-15 条真梗)
        ↓
[4] B站二创验证  对每条真梗查 B站搜索结果数
            • 二创/鬼畜类视频数 ≥ 阈值(初始 20) → verified=true
            • < 阈值 → verified=false (仍入库,标记为"待观察")
                                                    (~5-10 条 verified)
        ↓
[5] LLM 释义   GLM-4.6 对 verified=true 的逐条生成:
            • 释义 (这是什么梗)
            • 出处 (来自哪个事件/人物/作品)
            • 用法 (怎么在句子里用)
            • 例句 (1-2 个)
        ↓
[6] 入库 + 日报  写入 SQLite,生成当日 Markdown 日报,commit 回仓库
```

### 降级策略 (任一外部依赖失败都不阻塞)

| 失败点 | 降级行为 |
|:---|:---|
| DailyHotApi 某平台接口失败 | 跳过该平台,继续处理其他平台,日志记录 |
| GLM 分类失败 | 降级为纯规则结果 (粗筛输出直接进入下一步,标 `classified=false`) |
| B站验证失败 | 跳过验证,所有候选 `verified=null`,释义照常做 |
| GLM 释义失败 | 该条释义字段留空,梗本身仍入库 |
| 整体流程异常 | Actions 标记失败,发 issue 提示,但不破坏已有数据 |

## 3. 模块划分

```
geng/
├── src/geng/
│   ├── discover.py      # [1] 调 DailyHotApi,返回统一格式的热搜列表
│   ├── filter.py        # [2] 规则粗筛
│   ├── classify.py      # [3] GLM-4.5-Air 分类
│   ├── verify.py        # [4] B站二创验证
│   ├── explain.py       # [5] GLM-4.6 释义
│   ├── store.py         # [6] SQLite 读写
│   ├── report.py        # [6] 生成 Markdown 日报
│   ├── pipeline.py      # 串联 1-6,处理降级与重试
│   └── config.py        # 阈值、平台列表、模型名、超时等
├── data/
│   ├── exclude/         # 排除清单: stars.txt, places.txt, shows.txt
│   └── memes.db         # SQLite (commit 回仓库)
├── daily/               # 每日 Markdown 日报 YYYY-MM-DD.md
├── .github/workflows/daily.yml
├── pyproject.toml
└── README.md
```

每个模块对外只暴露一个纯函数,接收上一步的输出,返回本步的输出。所有 IO(HTTP / 文件 / DB)集中在模块边界,核心逻辑可单元测试。

### 各模块接口

```python
# discover.py
def fetch_trending(platforms: list[str], date: str) -> list[HotItem]:
    """返回统一格式: {id, platform, title, hot, url, fetched_at}"""

# filter.py
def coarse_filter(items: list[HotItem]) -> list[Candidate]:
    """应用排除清单与启发式规则,返回 Candidate"""

# classify.py
def classify_memes(candidates: list[Candidate]) -> list[ClassifiedMeme]:
    """调用 GLM-4.5-Air,返回 is_meme + confidence + reason"""

# verify.py
def verify_bilibili(memes: list[ClassifiedMeme]) -> list[ClassifiedMeme]:
    """查 B站搜索结果数,填入 verified + bili_video_count"""

# explain.py
def generate_explanations(memes: list[ClassifiedMeme]) -> list[FinalMeme]:
    """调用 GLM-4.6,填入 definition/origin/usage/examples"""

# store.py
def save_to_db(memes: list[FinalMeme], date: str) -> int: ...
def query(...): ...   # 留接口,供后续查询脚本/网站使用

# report.py
def render_daily_report(memes: list[FinalMeme], date: str) -> Path: ...
```

## 4. 数据模型

### SQLite schema

```sql
CREATE TABLE memes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,           -- 梗的标题(取自热搜)
    date            TEXT NOT NULL,           -- 采集日期 YYYY-MM-DD
    platforms       TEXT NOT NULL,           -- JSON array,出现的平台
    hot_scores      TEXT,                    -- JSON,各平台热度
    confidence      REAL,                    -- LLM 分类置信度 0-1
    classify_reason TEXT,                    -- LLM 给的分类理由
    verified        BOOLEAN,                 -- B站二创验证
    bili_video_count INTEGER,                -- B站相关视频数
    definition      TEXT,                    -- 释义
    origin          TEXT,                    -- 出处
    usage           TEXT,                    -- 用法
    examples        TEXT,                    -- JSON array,例句
    created_at      TEXT NOT NULL,
    UNIQUE(title, date)                      -- 同一天同标题不重复入库
);
CREATE INDEX idx_date ON memes(date);
CREATE INDEX idx_verified ON memes(verified);
```

### Markdown 日报格式

```markdown
# 2026-07-05 热梗日报

> 共采集 87 条热搜,经筛选入库 7 条 (其中 5 条已验证)

## ✅ 已验证梗

### 1. <梗标题>
- **释义**: ...
- **出处**: ...
- **用法**: ...
- **例句**: ...
- **B站二创**: 约 234 个视频
- **来源**: 微博🔥 / 抖音🔥

---

## 🔍 待观察 (未通过二创验证)

### <梗标题>
... (同上格式)

---
*数据源: 微博 / B站 / 抖音  •  释义由 GLM-4.6 生成*
```

## 5. 关键技术选择

| 组件 | 选择 | 理由 |
|:---|:---|:---|
| 语言 | Python 3.11+ | 抓取/LLM 生态成熟,Actions 镜像现成 |
| 热搜数据源 | 自部署 DailyHotApi (Vercel) | 公共实例易挂,自己部署一次长期稳定 |
| LLM 分类 | 智谱 GLM-4.5-Air | 便宜,中文网络语境理解强 |
| LLM 释义 | 智谱 GLM-4.6 | 质量更好,释义条目少成本可接受 |
| 存储 | SQLite (`.db` commit 到仓库) | 零运维,可累积,后续可被任何应用读 |
| 人读视图 | Markdown 日报 (commit 到 `daily/`) | GitHub 网页直接渲染,手机可读 |
| 定时 | GitHub Actions cron | 免费、不依赖本地开机 |
| 历史/统计 | DB Browser for SQLite (桌面 GUI) | 零开发 |

### 成本估算

- GitHub Actions: 公开仓库免费分钟数足够(每天约 2 分钟)
- Vercel DailyHotApi: 免费额度足够
- 智谱 GLM: 每天约 100 条分类 + 10 条释义,估算 < ¥0.1/天,< ¥3/月

## 6. 外部依赖与配置

### 需要用户准备

1. **GitHub Secrets**:
   - `ZHIPU_API_KEY` — 智谱 API Key,从 https://open.bigmodel.cn 申请
   - `DAILYHOT_API_BASE` — 自部署的 DailyHotApi 地址(如 `https://xxx.vercel.app`)

2. **自部署 DailyHotApi** (一次性,5 分钟):
   - Fork `imsyy/DailyHotApi`
   - 一键部署到 Vercel
   - 拿到域名填入 Secret

### 仓库内配置 (config.py)

```python
PLATFORMS = ["weibo", "bilibili", "douyin"]
EXCLUDE_LISTS_DIR = "data/exclude"
MEME_LENGTH_RANGE = (3, 14)
MIN_PLATFORMS_CROSS = 2          # 跨平台共振阈值
CLASSIFY_MODEL = "glm-4.5-air"
EXPLAIN_MODEL = "glm-4.6"
BILI_VERIFY_THRESHOLD = 20       # B站二创视频数阈值
HTTP_TIMEOUT = 20
LLM_MAX_RETRY = 2
DB_PATH = "data/memes.db"
DAILY_REPORT_DIR = "daily"
```

## 7. 测试策略

- **discover/filter**: 用录制的真实热搜 JSON 做 fixture(脱敏),断言粗筛能剔除明显的明星/新闻
- **classify/explain**: 不在 CI 调真实 GLM(API Key 不能进 CI),改用 mock client,断言 prompt 构造与字段填充正确
- **verify**: mock B站搜索响应,断言阈值判断逻辑
- **store/report**: 临时 SQLite,断言唯一约束、日报生成
- **pipeline**: 集成测试,mock 所有外部依赖,验证降级路径(故意让某层抛错,确认不阻塞)

## 8. 验收标准

工具上线后需满足:

1. GitHub Actions 连续 7 天成功跑通,无人工干预
2. 某个平台接口临时失败的那天,流程仍产出当日梗(降级生效)
3. 每日 Markdown 日报在 GitHub 网页能正常渲染
4. SQLite 数据库可被 DB Browser 打开,数据连续无缺失日期
5. 抽查任意一天的 verified 梗,释义读起来合理(允许偶有不准确,不允许明显胡编)

## 9. 后续演进 (本期不做,留接口)

- 推送: pipeline 末尾加 `notify.py`,接 Telegram / 企业微信
- 网站: 基于 SQLite 写 Flask/Next.js 前端
- 搜索: 复用 `store.query()` 接口
- 多源扩充: filter 支持加入知乎/贴吧热搜
