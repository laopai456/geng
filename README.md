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
