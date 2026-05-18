# style-lab

[English](./README.md) | 简体中文

一个 Claude Code 技能：把产品描述变成 3–5 个**风格迥异**、各自独立的单页 HTML 设计稿，再加一个对比页，几秒钟就能逐版翻看。

尽早定下视觉方向收益很高，但过程很慢——设计师通常先做 2–3 个方向，创始人反馈，再迭代。`style-lab` 把这个循环压缩了：丢给它一份单页说明或 PRD，拿回多个真实 HTML 页面，每个都坚定地走一条不同的视觉语言，并排呈现。点开翻看，指着最打动你的那版，方向就定了。

产出的是**可直接运行的 HTML**，不是截图，也不是 React。任意浏览器打开即可，无需构建步骤，几秒钟就能*感受*到设计。

## 安装

本仓库是一个 Claude Code 插件。在任意 Claude Code 会话中：

```
/plugin install koko-t7i/style-lab
```

或把它加入某个 marketplace，通过 `/plugin marketplace` 安装——`.claude-plugin/marketplace.json` 和 `.claude-plugin/plugin.json` 都已配置好。`skills/style-lab/` 只是一层指回仓库根目录的软链接，因此不存在会漂移的重复副本。

## 使用

在已安装该插件的会话里，直接向 Claude Code 要视觉方案即可。技能会在类似下面这些说法上自动触发：

- *"看看这个产品适合什么风格"* / *"做一轮设计探索"* / *"批量出几版设计稿"*
- *"先做几个原型看看感觉"* / *"出个 moodboard"* / *"我还没想好走哪个方向"*
- *"做成 Stripe / Linear / Aurpay 这样"*——从参考 URL 中提取品牌 DNA（配色、渐变、字体），并应用到每一版
- 或者直接贴一份 PRD / 产品描述，要几个视觉创意

不需要显式输入 `/style-lab`。对应的英文说法同样会触发该技能——见 [English version](./README.md)。

## 迭代

出完第一批之后：

| 你说 | 模式 | 发生什么 |
|---|---|---|
| *"再来几个不一样的"* | 全新-不同 | 再出一批 N 个风格，排除之前展示过的全部 |
| *"02 这个方向再多看几版"* | 精修 | 对选中风格出 N 个变体，沿该风格特定的轴变化（配色 / 字体 / 密度 / 主视觉设备 / 调性） |
| *"做成 [Linear / Stripe / Aurpay] 这样"* + 参考 URL | 参考驱动 | 从 URL 提取品牌 DNA，生成的变体全部落在该 DNA 内部，但沿家族内子轴变化 |
| *"在这个风格下再换几种排版"* | 排版探索 | 风格锁定后，保持风格不变，只变化页面布局/构图（单栏、便当格、侧栏工作区、价格对比） |

状态保存在 `<output-dir>/state.json`，跨会话保留。被选中的变体也记录在那里，并在下一轮迭代的对比页中以 `★ Picked` 徽标呈现。

在对比页里，每张变体卡片都有一个 **✓ Pick this** 按钮（复制一段可直接粘贴的选择语句，省得你再打字说选了哪个）、一个 **🔗 Copy link** 按钮（在手机/另一台设备上打开该变体），以及一个按变体的**备注框**和 **Copy all feedback** 按钮——逐版记下反应，一次性全部粘回去，驱动更聚焦的精修轮次。

当你最终选定赢家时，运行 DESIGN.md 提取器，输出一份 Google-Stitch 格式的设计规范，下游编码代理（Cursor / Claude Code）可在之后每次提示中读取。

## 输出结构

```
<output-dir>/
  state.json                       # 批次、选择、参考摘要
  index.html                       # 跨所有批次的顶层标签页
  batch-1/
    01-modern-dark/index.html      # 一个独立变体
    02-bento-grid/index.html
    03-cyberpunk-hud/index.html
    index.html                     # 带侧栏目录的本批次对比页
  batch-2/
    ...
  batch-1/comparison-bundle.html   # 可选：单个自包含文件（--bundle）
```

打开 `<output-dir>/index.html`，用顶部标签页在批次间切换。每个标签页展示该批次的变体，配侧栏目录和视口切换（桌面 / 平板 / 手机）。被选中的变体会带一个蓝色 `★ Picked` 徽标。

## 预览服务器

`scripts/serve_preview.py <output-dir>` 会根据当前 state.json 重新生成每个批次的对比页，并启动一个后台 HTTP 服务器。它会自动检测你是在本地机器还是 SSH 会话中：

- **本地**：只打印 `http://localhost:PORT/index.html`——打开即用。
- **SSH**（通过 `$SSH_CONNECTION` 检测）：还会打印一条可直接粘贴的 `ssh -N -L PORT:localhost:PORT <host>` 隧道命令。可通过传 `--host <user@host>` 或设置 `$STYLE_LAB_SSH_HOST` 强制走这条分支。

用 `python3 scripts/serve_preview.py <output-dir> --kill` 停止服务器，或用 `python3 scripts/serve_preview.py --kill-all` 回收所有跨会话/目录启动过的预览服务器。

对于无法做 SSH 隧道的用户（受限的笔记本，只想要一个文件），改为生成一个单独的自包含文件：`python3 scripts/generate_index.py <batch-dir> --bundle` 会写出内联了每个变体的 `comparison-bundle.html`——直接从 `file://` 打开即可，无需服务器。

## 仓库结构

```
SKILL.md                     # 完整的面向代理的规范（由 Claude Code 自动加载）
assets/
  index_template.html        # 本批次对比页模板（侧栏目录 + iframe 堆叠）
  root_index_template.html   # 顶层标签页模板（每批次一个标签）
references/
  style-catalog.md           # ~80 个风格迥异的视觉风格及词汇
  product-style-mapping.md   # 产品类型 → 推荐风格集
  visual-signatures.md       # 知名品牌 DNA 目录（Stripe、Linear、Apple 等）
  iteration-modes.md         # "再来一轮"的 Mode A/B/C/D 状态机
  layout-catalog.md          # Mode D 排版探索的命名页面布局
  design-md-spec.md          # Google Stitch DESIGN.md 规范，定稿后交接
  comparison-page-tradeoffs.md  # 关于对比页本身的设计笔记
scripts/
  generate_index.py          # 构建本批次对比页
  generate_root_index.py     # 构建顶层标签页
  serve_preview.py           # 重新生成 + 服务 + 自动检测 SSH/本地
  extract_brand_dna.py       # 从 URL 拉取配色、渐变、字体
  extract_design_md.py       # 定稿后，从选中变体输出 DESIGN.md
  init_iteration.py          # 把迭代前的扁平输出目录迁移到分批结构
  validate_variant.py        # 对生成的变体做合理性检查
evals/
  evals.json                 # 行为评测套件（含双语触发提示）
.claude-plugin/
  plugin.json                # 插件清单
  marketplace.json           # marketplace 条目
skills/
  style-lab/                 # 软链接回根目录（插件格式要求）
.gitignore                   # 忽略缓存 + 临时探索产物
```

完整的代理规范（风格挑选规则、精修轴、参考驱动流程、失败模式）请阅读 [`SKILL.md`](./SKILL.md)。
