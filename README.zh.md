# oh-my-hermes-memory

> Hermes Agent + OMH（oh-my-hermes）的完整 dual-store 记忆架构。
> 一次性解决 "memory tool 字符上限" 问题。

## 这是什么

本项目记录并打包了一套**三层记忆架构**，作者从 2026 年 7 月在 Windows 10 + Hermes 桌面 + OMH 插件的真实使用中提炼而来。它回答一个问题：

> **"如何给 Hermes Agent 装一套能扛过所有字符上限、绝不悄悄丢信息、也绝不自动审批写入的持久记忆？"**

答案是 **dual-store 架构**：明确的路由规则 + review-first 捕获流程 + 把凭据隔离在专属区域的约定。

## 为什么需要这个

Hermes Agent 内置的 `memory` 工具会在每个会话的 system prompt 中注入短文本。它有两个硬性上限：

| 文件 | 单条上限 |
|---|---|
| `MEMORY.md` | **2,200 字符** |
| `USER.md` | **1,375 字符** |

当项目超出这些上限时，常见的失败模式是：

- 用户要求 agent "压缩" 记忆 → 信息丢失
- agent 自创审批流程、悄悄累积记忆、不让用户审 → 信任崩塌
- 凭据泄漏到 memory 文件 → 风险累积
- 用户把记忆拆成多条 → 召回质量下降、编辑脆弱

本项目用一套单一架构同时替换掉这四种失败模式，agent、运维、工具三边都同意。

## 架构

```
                ┌─────────────────────────────────────────────┐
                │  ~/.hermes/.env  （仅凭据）                  │
                │  WSL_KALI_PWD=***                            │
                │  ← 用 env var 名字引用，绝不写明文           │
                └─────────────────────────────────────────────┘
                                    │
                                    │ （用 env var 名引用）
                                    │
        ┌───────────────────────────┼─────────────────────────────┐
        │                           │                             │
┌───────▼────────────────┐  ┌────────▼────────────┐  ┌─────────────▼─────────────┐
│  L1（memory tool）      │  │  L0 OMH 项目记忆  │  │  L0 OMH 项目记忆         │
│  MEMORY.md / USER.md   │  │  memory --tier=     │  │  --tier=reference         │
│                        │  │  system             │  │                           │
│  仅索引（约 400 +      │  │                     │  │  长 fact 库。             │
│  约 150 字符）         │  │  每轮自动注入。    │  │  标签列在 system prompt   │
│                        │  │  6000 字符渲染     │  │  里，需要时通过           │
│  指向 L0 blocks        │  │  预算，单块         │  │  `omh_memory(action=read, │
│  和 records。          │  │  5800 上限。        │  │  label=X)` MCP 工具       │
│                        │  │                     │  │  按需读取。               │
│  已批准的 records      │  │  装"每轮必读"       │  │  无字符上限。             │
│  （各 240 字符）      │  │  的完整文本。       │  │  装完整流程、             │
│  在 OMH records 里。   │  │                     │  │  runbook、环境笔记。     │
└────────────────────────┘  └─────────────────────┘  └───────────────────────────┘
```

## 三层决策规则

当 agent 遇到一个想记住的 fact 时，用以下规则路由到唯一一层。完整版本在 [`docs/02-decision-tree.md`](docs/02-decision-tree.md)：

| 问题 | 落点 |
|---|---|
| 是凭据吗（密码、token、API key）？ | **`.env` only** —— 绝不进 memory |
| 每个会话开始都需要吗？ | **L1 MEMORY.md 索引条目**（≤ 2,200 字符）OR **L0 system-tier block**（渲染预算总 ≤ 6,000 字符） |
| 是短 atomic fact（≤ 240 字符）？ | **L0 approved record**（capture → review → approve） |
| 是长流程或工作流（> 240 字符）？ | **L0 reference-tier block**（单块 limit 2,000–5,000 字符） |
| 是一次性事件或过程日志？ | **不要存** —— 让 `session_search` 找 |

## 快速开始

### 1. 克隆（OMH 作为子模块）

```bash
git clone --recurse-submodules https://github.com/anonymous99-Rise/oh-my-hermes-memory.git
cd oh-my-hermes-memory
git submodule update --init   # 拉取 rlaope/oh-my-hermes 到 ./submodule-omh/
```

### 2. 读架构概览

从 [`docs/01-architecture-overview.md`](docs/01-architecture-overview.md) 开始。它用真实示例走完每一个存储层。

### 3. 用 `memory-architect` skill

[`skills/memory-architect/SKILL.md`](skills/memory-architect/SKILL.md) 是 agent 侧的入口。当一个 Hermes + OMH agent 准备写记忆条目时，加载这个 skill 决定往哪写。

### 4. 应用模板

`templates/` 目录有现成可粘贴的 blocks 和索引条目：

- `templates/env-baseline-system-block.md` —— 标准 L0 system block（环境基线）
- `templates/user-workflow-system-block.md` —— 标准 L0 system block（用户工作流偏好）
- `templates/index-entry-memory.md` —— 400 字符 L1 MEMORY.md 索引条目
- `templates/index-entry-user.md` —— 150 字符 L1 USER.md 索引条目

### 5. 跑诊断脚本

```bash
python scripts/dual-store-status.py
```

打印 L1（`~/.hermes/memories/MEMORY.md` 和 `USER.md`）、L0 OMH 项目记忆（blocks + approved records）和 `.env` 凭据引用的当前状态。报告架构是否完整。

### 6. 用路由脚本判断新 fact 该去哪

```bash
python scripts/route-fact.py --text "用户偏好简洁回复" --frequency every
python scripts/route-fact.py --text "构建命令需要设 FOO=1" --frequency occasional
python scripts/route-fact.py --text "GitHub PAT" --sensitive
```

脚本建议新 fact 应该落在哪一层，并打印准确的 capture/write 命令。脚本**不执行**写入 —— 运维仍需审批。

## 仓库结构

```
oh-my-hermes-memory/
├── README.md                                    ← 本文件（中文）
├── README.zh.md                                 ← 英文版
├── LICENSE                                      ← MIT
├── CHANGELOG.md                                 ← 版本历史
├── SUBMODULE.md                                 ← 子模块初始化说明
├── .gitignore
├── docs/                                        ← 10 篇长文档
│   ├── 01-architecture-overview.md
│   ├── 02-decision-tree.md
│   ├── 03-character-limits.md
│   ├── 04-credential-routing.md
│   ├── 05-omh-block-tiers.md
│   ├── 06-capture-approve-flow.md
│   ├── 07-real-cases.md
│   ├── 08-troubleshooting.md
│   ├── 09-migration-guide.md
│   └── 10-faq.md
├── skills/                                      ← Hermes skill
│   └── memory-architect/
│       ├── SKILL.md                             ← 主 skill（12–15k 字符）
│       └── references/                          ← 渐进披露
│           ├── 01-when-to-use.md
│           ├── 02-dual-store.md
│           ├── 03-decision-tree.md
│           ├── 04-credential-routing.md
│           ├── 05-block-tiers.md
│           ├── 06-capture-approve.md
│           ├── 07-real-cases.md
│           └── 08-troubleshooting.md
├── scripts/                                     ← 工具脚本
│   ├── route-fact.py
│   ├── dual-store-status.py
│   └── apply-template.sh
├── templates/                                   ← 现成可粘贴 blocks
│   ├── env-baseline-system-block.md
│   ├── user-workflow-system-block.md
│   ├── index-entry-memory.md
│   └── index-entry-user.md
├── examples/                                    ← 端到端实操案例
│   ├── case-01-omh-install/
│   ├── case-02-credential-routing/
│   ├── case-03-multi-tier-fact/
│   └── case-04-migration-from-flat-memory/
└── submodule-omh/                               ← git submodule → rlaope/oh-my-hermes
```

## 关键设计原则

1. **不丢信息。** "空间不够"永远不是压缩的答案。加一层；不要裁已有的 fact。

2. **不自动审批。** 每个 L0 项目记忆写入都走 review-first。agent 捕获候选；运维审批。除非用户在本次会话明确委托某一类 facts，否则 auto-approve 不开。

3. **memory 里不放凭据。** 密码、token、key 只在 `~/.hermes/.env`。用 env var 名引用。明文从不出现在任何 memory summary、聊天消息、脚本字面量里。

4. **不跨平台混合。** OMH 项目记忆是 AI 记忆的唯一持久存储。其他系统（OpenClaw、自定义日志文件等）不能复用 —— 这条边界让审计故事成立。

5. **不静默截断。** OMH blocks 拒绝静默截断超出 `--limit` 的内容。运维被告知内容没有落地，必须拆分 block 或显式提高 limit。

## 与 OMH 的关系

本项目**消费** OMH，不修改 OMH。OMH 提供：

- `~/.omh/memory/` —— 项目记忆存储
- `omh memory block-set / capture / approve / recall` —— CLI 表面
- `omh_memory` 和 `omh_context` MCP 工具（agent 在运行时用）
- OMH 插件（`hermes/plugins/omh/`）注册这些工具

如果 OMH 升级并且 OMH 插件的工具 schema 变了，[`docs/08-troubleshooting.md`](docs/08-troubleshooting.md) 记录了预期的迁移路径。

`submodule-omh/` 是 `rlaope/oh-my-hermes` 的 vendored 副本，仅供离线参考。运行时**不依赖**它 —— Hermes Agent 读的是已装的 OMH 插件，不是这个 submodule。

## 贡献

欢迎提 issue 和 PR。项目足够小，运维审阅可以一天内完成。提 PR 前请：

1. 读 [`docs/10-faq.md`](docs/10-faq.md) —— 很多问题已经有答案。
2. 开 issue 描述你想解决的问题。
3. PR 保持聚焦 —— 一个 PR 一个架构关切点。

## 作者

由 `anonymous99-Rise` 于 2026 年 7 月构建，来自 Windows 10 + Hermes Agent 桌面 + OMH 插件的真实使用。架构在一个从 "安装 OMH" 开始、以 "把我们学到的发表出来" 结束的长时间会话中精炼而成。

## 许可

MIT。详见 [`LICENSE`](LICENSE)。