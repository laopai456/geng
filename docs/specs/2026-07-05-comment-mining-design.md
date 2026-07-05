# 评论流新词发现 — 设计补充文档

- **状态**: 设计待确认
- **日期**: 2026-07-05
- **基于**: 对 [`2026-07-05-daily-meme-tracker-design.md`](./2026-07-05-daily-meme-tracker-design.md) 的 discover 阶段重构
- **背景**: 实测发现热搜榜(视频标题/话题词)形态偏离"梗",热梗真正栖息地是评论区

## 1. 为什么要重构 discover

### 实测结论(2026-07-05)

跑了一版基于 B站热搜榜的 pipeline,产出 5 条结果,3 条不是梗:
- "超市后门抽卡歪了的二人" → 视频标题
- "地摊提拉米苏为何总在翻车" → 视频标题
- "为何下沉音乐还在霸屏" → 讨论话题

**根因**: 热搜榜的单元是"话题/标题",而梗是"被反复使用的短语"。两者形态不同。用户的洞察是对的——**热梗在评论区**。

### 探针实验(2026-07-05)

对单个热门视频抓 300 条评论做 n-gram 统计,发现:
- ✅ 算法能捞出"打call""星星眼""保卫萝卜""大哭"等真实网络用语
- ❌ 纯字符 n-gram 产生 `doge/oge/cal/YYY` 等子串碎片
- ❌ 单视频评论高度同质,被该视频话题淹没(全是"父与子")

### 必须解决的两个坑

1. **碎片问题**: 需要 jieba 分词后再做 n-gram,而不是按字符切
2. **同质问题**: 需要跨多个不同视频汇总评论,让"全网通用梗"在统计上浮出

## 2. 新架构(替换原 discover 阶段)

```
[1] discover
    ├─ fetch_top_videos()       拿 B站排行榜 top 10 视频 (bvid + aid + 标题)
    └─ fetch_comments()         每个视频抓 top 评论(按热度,~300条/视频)
                                汇总成"今日语料库" (~3000 条评论)
        ↓
[1.5] extract (新阶段)          评论语料 → 候选梗短语
    ├─ tokenize (jieba)         分词
    ├─ ngram_stats              词级 1-3 gram 频次统计
    ├─ baseline_filter          用通用词频表过滤虚词/常用词
    ├─ cross_video_filter       只保留在 ≥2 个不同视频里出现的短语
    └─ top_k                    按频次取 top 30 作为候选
        ↓ (~30 条候选)
[2] filter (保留)               排除清单(明星/地名)过滤
        ↓
[3] classify (保留)             DeepSeek 判断"是不是真梗"
        ↓
[4] verify (保留)               B站搜索结果数验证
        ↓
[5] explain (保留)              DeepSeek 释义
        ↓
[6] store + report (保留)       入库 + 日报
```

**保留的部分**: filter/classify/verify/explain/store/report/pipeline 全部不动。**只重构 discover,新增 extract。**

## 3. 模块划分

```
src/geng/
├── discover.py          # 重构: fetch_top_videos + fetch_comments (返回原始评论)
├── extract.py           # 新增: 评论语料 → 候选梗 (分词+ngram+过滤)
├── filter.py            # 保留,微调: 输入从 HotItem 改为 str (短语)
├── ...其他模块保留...
```

### discover.py 重构

```python
# 旧: fetch_trending() -> list[HotItem]  (抓热搜榜)
# 新: 抓视频 + 评论

@dataclass
class VideoInfo:
    bvid: str
    aid: int
    title: str

@dataclass
class Comment:
    video_bvid: str          # 来源视频,用于跨视频去重统计
    message: str             # 评论原文
    likes: int               # 点赞数(用于排序)

def fetch_top_videos(limit: int = 10) -> list[VideoInfo]:
    """B站排行榜 top N 视频。"""

def fetch_comments(video: VideoInfo, limit: int = 300) -> list[Comment]:
    """单个视频的 top 评论(按热度排序)。"""

def collect_corpus(videos_limit: int = 10, comments_per_video: int = 300) -> list[Comment]:
    """抓多个视频的评论,汇成语料库。某视频失败不阻塞。"""
```

### extract.py 新增

```python
def extract_candidates(
    comments: list[Comment],
    top_k: int = 30,
    min_videos: int = 2,        # 至少在 N 个不同视频出现
) -> list[str]:
    """从评论语料提取候选梗短语。"""
    # 1. jieba 分词所有评论
    # 2. 词级 1-3 gram 统计
    # 3. 用基线词频表过滤虚词/常用词/纯英文碎片
    # 4. 跨视频过滤: 只保留出现在 ≥ min_videos 个视频的短语
    # 5. 取 top_k
```

## 4. 关键技术决策

### 4.1 分词:jieba

新增依赖 `jieba`。理由:
- 解决字符 n-gram 的碎片问题(`打call` 不会被切歪)
- 词级 n-gram 更符合"短语"语义
- 成熟稳定,中文 NLP 标配

### 4.2 基线词频:B2 方案(通用词频表)

不积累历史基线(那是 B1 方案,要等一周)。用**静态通用高频词表**:
- 内置 `data/baseline/common_words.txt`(种子,包含"的/了/是/这个/那个/今天/真的"等)
- 短语若整体在基线表里,直接过滤
- 优点:今天就能跑
- 缺点:精度比 B1 差,可能漏掉"突然爆发的常用词"——但靠 LLM 分类兜底

### 4.3 跨视频过滤(min_videos ≥ 2)

探针实验的核心教训:单视频评论同质。**要求候选短语至少在 2 个不同视频的评论里出现**,才能浮出来。这过滤掉"某个视频专属话题",保留"跨视频通用"的梗。

### 4.4 数据规模:轻量(top 10)

- 抓 top 10 视频的评论,每视频 ~300 条
- 总语料 ~3000 条评论
- GitHub Actions 耗时约 2-3 分钟
- 跨视频过滤阈值 min_videos=2(10 个视频里至少 2 个出现)

## 5. filter.py 微调

旧 filter 接收 `list[HotItem]`(热搜项)。新流程候选是"短语字符串"。

```python
# 旧
def coarse_filter(items: list[HotItem], date: str) -> list[Candidate]:

# 新
def coarse_filter(phrases: list[str], date: str) -> list[Candidate]:
    """对候选短语应用排除清单(明星/地名)。长度过滤保留。"""
```

`Candidate` dataclass 不变,只是构造方式从 HotItem 改为 str。

## 6. 测试策略

- **discover**: mock B站排行榜/评论 API,断言能拿到 VideoInfo 和 Comment 列表
- **extract**: 用构造的评论语料(含已知梗 + 已知噪音),断言能捞出梗、过滤噪音
  - 例: 评论文本里塞 "YYDS" 5 次(跨3视频)、"的" 100 次、"父与子" 50 次(单视频),断言 YYDS 被选中,其余被过滤
- **跨视频过滤**: 单元测试 "只在1个视频出现" 的短语被剔除
- **基线过滤**: 单元测试 "的/了/是" 被剔除
- **pipeline 集成**: mock 全部外部依赖,验证 评论 → 梗 的完整链路

## 7. 已知局限(诚实陈述)

1. **轻量数据源**: top 10 视频仍可能偏 B站主流话题(游戏/动画)。如果视频多样性不够,跨视频过滤后候选可能很少(甚至 < 10)
2. **基线词表需要养**: 种子版只有几十个虚词,初期会漏掉"今天突然爆发的常用词"。靠 LLM 分类兜底
3. **jieba 切词不完美**: 网络新词 jieba 可能不认识(比如最新的谐音梗),会被切成碎片。可后续加自定义词典
4. **依赖 B站单源**: 抖音/微博评论未接入(反爬/接口问题)。如果 B站当天热门视频话题集中,效果会打折

## 8. 验收标准

1. 跑一次,top 10 视频的评论被成功抓取(~3000 条)
2. extract 产出 20-30 个候选短语,虚词/常用词被过滤
3. 跨视频过滤后,候选短语确实在 ≥2 个视频评论中出现
4. 最终入库的梗(经 LLM + B站验证),人工抽查 3 条,至少 2 条是"真实的、可被使用的网络梗"
5. 单次 pipeline 耗时 < 5 分钟

## 9. 不做的事(YAGNI)

- 不做历史词频积累(B1 方案)——本期用静态基线
- 不接入抖音/微博评论——反爬成本不值
- 不做新词发现的复杂统计检验(互信息/边界熵)——n-gram + 过滤够用,先看效果
- 不做实时评论流——每天定时跑一次
