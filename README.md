# geng — 每日热梗采集工具

每天自动抓取中文互联网热搜,经**规则粗筛 → DeepSeek 分类 → B站二创验证 → DeepSeek 释义**四层漏斗,产出当日"真梗"日报并入库累积。

## 工作原理

```
100 条热搜 → 粗筛 30 条候选 → DeepSeek 分类 10 条真梗 → B站验证 5 条 → DeepSeek 释义 → 入库 + 日报
```

详见 [设计文档](docs/specs/2026-07-05-daily-meme-tracker-design.md)。

## 查看方式

- **当日梗**: 打开 [daily/](daily/) 目录,点当天日期的 `.md` 文件
- **历史/统计**: 用 [DB Browser for SQLite](https://sqlitebrowser.org/) 打开 `data/memes.db`

## 部署

### 1. 准备 API Key

- **DeepSeek**: 去 https://platform.deepseek.com 注册,创建 API Key

### 2. 配置 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 添加:
- `LLM_API_KEY` — DeepSeek API Key

> 数据源(微博/B站热搜)由本工具直接抓取,**无需**部署 DailyHotApi。

### 3. 启用 Actions

默认每天北京时间 23:00 自动跑。也可在 Actions 页手动触发。

## 本地运行

```bash
pip install -e ".[dev]"
export LLM_API_KEY=xxx
geng                  # 跑当天
geng 2026-07-05       # 跑指定日期
pytest                # 跑测试
```

## 成本

- GitHub Actions: 公开仓库免费
- Vercel DailyHotApi: 免费额度足够
- DeepSeek: deepseek-chat 约 ¥1/百万 token,日均 < ¥0.1,约 ¥3/月

## 已知局限

- AI 释义不是词典级权威,偶有不准确
- 抽查发现误判时,可往 `data/exclude/stars.txt` 等清单加词
- 初期排除清单薄,误判会偏多,需要养几周
- **数据源**:微博接口需 cookie(常 403),主要依赖 B站热搜(50条/天)。单平台也足够产出候选
- 抖音接口需鉴权,暂未接入
