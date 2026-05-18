# style-lab

[English](./README.md) | 简体中文

一个 Claude Code 技能：把产品描述变成 3–5 个**风格迥异**、各自独立的单页 HTML 设计稿，再加一个对比页，几秒钟就能逐版翻看。

产出是**可直接运行的 HTML**——不是截图，不是 React，无需构建。任意浏览器打开即可，几秒钟*感受*到设计。

## 安装

本仓库是一个 Claude Code 插件：

```
/plugin install koko-t7i/style-lab
```

`.claude-plugin/{plugin,marketplace}.json` 已为 `/plugin marketplace` 配置好。`skills/style-lab/` 只是指回仓库根目录的软链接（无重复副本）。

## 使用

在已装该插件的会话里直接要视觉方案，无需输入 `/style-lab`。中英文均自动触发：

- *"看看这个产品适合什么风格"* / *"批量出几版设计稿"* / *"出个 moodboard"*
- *"做成 Stripe / Linear / Vercel 这样"*——从参考 URL 提取品牌 DNA（配色、渐变、字体）
- 直接贴一份 PRD / 产品描述

## 迭代

出完第一批之后：

| 你说 | 模式 | 结果 |
|---|---|---|
| *"再来几个不一样的"* | 全新-不同 | 再出 N 个风格，排除之前展示过的全部 |
| *"02 这个方向再多看几版"* | 精修 | 对选中风格出 N 个变体（配色 / 字体 / 密度 / 主视觉 / 调性） |
| *"做成 [Linear / Stripe / Vercel] 这样"* + URL | 参考驱动 | 变体全落在品牌 DNA 内，沿家族内子轴变化 |
| *"在这个风格下再换几种排版"* | 排版探索 | 风格不变，只变页面布局（单栏、便当格、侧栏、价格对比） |

状态保存在 `<output-dir>/state.json`，跨会话保留；被选中的变体以 `★ Picked` 徽标重现。对比页每张卡片有 **✓ Pick this**、**🔗 Copy link**，以及按变体的**备注框**配 **Copy all feedback**。选定赢家后，运行 DESIGN.md 提取器输出 Google-Stitch 规范，供下游编码代理读取。

## 输出结构

```
<output-dir>/
  state.json                       # 批次、选择、参考摘要
  index.html                       # 跨所有批次的顶层标签页
  batch-1/
    01-modern-dark/index.html      # 一个独立变体
    02-bento-grid/index.html
    index.html                     # 带侧栏目录的本批次对比页
    comparison-bundle.html         # 可选：单文件构建（--bundle）
```

打开 `<output-dir>/index.html`，顶部标签切换批次，每个标签配侧栏目录和桌面/平板/手机视口切换。

## 预览服务器

`scripts/serve_preview.py <output-dir>` 重新生成对比页并启动后台 HTTP 服务器，自动检测环境：

- **本地** → `http://localhost:PORT/index.html`
- **SSH**（通过 `$SSH_CONNECTION` 检测）→ 额外打印可直接粘贴的 `ssh -N -L` 隧道命令。可用 `--host <user@host>` 或 `$STYLE_LAB_SSH_HOST` 强制。

- 停止：`serve_preview.py <output-dir> --kill`——全部回收：`serve_preview.py --kill-all`
- 无法做隧道：`generate_index.py <batch-dir> --bundle` 写出可从 `file://` 打开的单文件 `comparison-bundle.html`

## 仓库结构

```
SKILL.md                       # 完整的面向代理规范（自动加载）
assets/                        # 对比页 + 顶层页模板
references/
  style-catalog.md             # ~80 个视觉风格及词汇
  product-style-mapping.md     # 产品类型 → 推荐风格集
  visual-signatures.md         # 知名品牌 DNA 目录
  iteration-modes.md           # Mode A/B/C/D 状态机
  layout-catalog.md            # 命名页面布局（Mode D）
  design-md-spec.md            # Google Stitch DESIGN.md 规范
  comparison-page-tradeoffs.md # 对比页设计笔记
scripts/
  generate_index.py            # 构建本批次对比页
  generate_root_index.py       # 构建顶层标签页
  serve_preview.py             # 重新生成 + 服务 + SSH/本地检测
  extract_brand_dna.py         # 从 URL 拉取配色/渐变/字体
  extract_design_md.py         # 定稿后从选中变体输出 DESIGN.md
  init_iteration.py            # 迁移扁平输出目录 → 分批结构
  validate_variant.py          # 对生成变体做合理性检查
evals/evals.json               # 行为评测套件（含双语触发）
.claude-plugin/                # 插件 + marketplace 清单
skills/style-lab/              # 软链接回根目录（插件格式要求）
```

完整代理规范（风格挑选规则、精修轴、参考驱动流程、失败模式）见 [`SKILL.md`](./SKILL.md)。
