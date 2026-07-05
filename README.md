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
