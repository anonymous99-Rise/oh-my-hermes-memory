# oh-my-hermes-memory

> Complete dual-store memory architecture for Hermes Agent + OMH (oh-my-hermes).
> Solves the "memory tool character limit" problem once and for all.

## What This Is

This project documents and packages a **three-tier memory architecture** that the
author derived from real-world usage on Windows 10 + Hermes desktop + OMH plugin
in July 2026. It is designed to answer one question:

> **"How do I give a Hermes Agent durable memory that survives all character
> limits, never silently loses information, and never auto-approves a write?"**

The answer is a **dual-store architecture** with explicit routing rules, a
review-first capture flow, and a credential-routing convention that keeps
secrets out of every memory surface.

## Why This Exists

Hermes Agent's built-in `memory` tool injects short text into every session's
system prompt. It has two hard limits:

| File | Hard limit per entry |
|---|---|
| `MEMORY.md` | **2,200 chars** |
| `USER.md` | **1,375 chars** |

When a project outgrows these limits, the typical failure modes are:

- The user asks the agent to "compress" the memory. Information is lost.
- The agent invents its own approval workflow and silently accumulates memory
  without user review. Trust erodes.
- Credentials leak into the memory file because there is nowhere else to put
  them. Risk compounds.
- The user splits memory across many entries. Recall quality drops. Edits
  become fragile.

This project replaces all four failure modes with a single architecture that
the agent, the operator, and the tools can all agree on.

## The Architecture

```
                ┌─────────────────────────────────────────────┐
                │  ~/.hermes/.env  (secrets only)             │
                │  WSL_KALI_PWD=***                            │
                │  ← referenced by name, never literal        │
                └─────────────────────────────────────────────┘
                                    │
                                    │ (referenced by env var name)
                                    │
        ┌───────────────────────────┼─────────────────────────────┐
        │                           │                             │
┌───────▼────────────────┐  ┌────────▼────────────┐  ┌─────────────▼─────────────┐
│  L1 (memory tool)      │  │  L0 OMH project     │  │  L0 OMH project memory    │
│  MEMORY.md / USER.md   │  │  memory --tier=     │  │  --tier=reference         │
│                        │  │  system             │  │                           │
│  INDEX ONLY (~400 +    │  │                     │  │  Long fact library.       │
│  ~150 chars)           │  │  Auto-injected      │  │  Listed by label in the    │
│                        │  │  every turn.        │  │  system prompt; full text  │
│  Points to L0 blocks   │  │  6000-char render   │  │  read on demand via        │
│  and records.          │  │  budget, per-block  │  │  `omh_memory(action=read,  │
│                        │  │  limit 5800.        │  │  label=X)` MCP tool.      │
│  Approved records      │  │  Carries complete   │  │  No character cap.        │
│  (240 chars each)      │  │  text for things    │  │  Carries full procedures,  │
│  live in OMH records. │  │  needed every turn. │  │  workflows, runbooks.      │
└────────────────────────┘  └─────────────────────┘  └───────────────────────────┘
```

## Three-Tier Decision Rule

When the agent encounters a fact it wants to remember, it routes the fact to
exactly one tier using this rule. Full version in
[`docs/02-decision-tree.md`](docs/02-decision-tree.md):

| Question | Tier |
|---|---|
| Is it a credential (password, token, API key)? | **`.env` only** — never memory |
| Is it needed at the start of **every** session? | **L1 MEMORY.md index entry** (≤2,200 chars) OR **L0 system-tier block** (≤6,000 chars total render budget) |
| Is it a short atomic fact (≤240 chars)? | **L0 approved record** (capture → review → approve) |
| Is it a long procedure or workflow (>240 chars)? | **L0 reference-tier block** (per-block limit 2,000–5,000 chars) |
| Is it a one-off event or process log? | **Do not store** — let `session_search` find it |

## Quick Start

### 1. Clone with OMH as a submodule

```bash
git clone --recurse-submodules https://github.com/anonymous99-Rise/oh-my-hermes-memory.git
cd oh-my-hermes-memory
git submodule update --init   # pulls rlaope/oh-my-hermes into ./submodule-omh/
```

### 2. Read the architecture overview

Start with [`docs/01-architecture-overview.md`](docs/01-architecture-overview.md).
It walks through every storage layer with real examples.

### 3. Use the `memory-architect` skill

The skill at [`skills/memory-architect/SKILL.md`](skills/memory-architect/SKILL.md)
is the agent-side entry point. When a Hermes + OMH agent is about to write a
memory entry, it loads this skill to decide where to put it.

### 4. Apply templates

The `templates/` directory contains ready-to-paste blocks and index entries:

- `templates/env-baseline-system-block.md` — the canonical L0 system block for
  environment baseline (host, paths, CLI executors, OMH install state).
- `templates/user-workflow-system-block.md` — the canonical L0 system block for
  user workflow preferences (language, executor routing, shell routing).
- `templates/index-entry-memory.md` — a 400-char L1 MEMORY.md index entry that
  points to the L0 blocks above.
- `templates/index-entry-user.md` — a 150-char L1 USER.md index entry.

### 5. Run the diagnostic script

```bash
python scripts/dual-store-status.py
```

Prints the current state of L1 (`~/.hermes/memories/MEMORY.md` and `USER.md`),
L0 OMH project memory (blocks + approved records), and `.env` credential
references. Reports whether the architecture is intact.

### 6. Route new facts with the helper script

```bash
python scripts/route-fact.py --text "User prefers concise responses" --frequency every
python scripts/route-fact.py --text "Build command requires setting FOO=1" --frequency occasional
python scripts/route-fact.py --text "GitHub PAT" --sensitive
```

The script suggests which tier a new fact should land in and prints the
exact command to capture / write it.

## Repository Layout

```
oh-my-hermes-memory/
├── README.md                                    ← this file
├── LICENSE                                      ← MIT
├── CHANGELOG.md                                 ← version history
├── .gitignore
├── docs/                                        ← 10 long-form docs
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
│       ├── SKILL.md                             ← main skill (12–15k chars)
│       └── references/                          ← progressive-disclosure refs
│           ├── 01-when-to-use.md
│           ├── 02-dual-store.md
│           ├── 03-decision-tree.md
│           ├── 04-credential-routing.md
│           ├── 05-block-tiers.md
│           ├── 06-capture-approve.md
│           ├── 07-real-cases.md
│           └── 08-troubleshooting.md
├── scripts/                                     ← utility scripts
│   ├── route-fact.py
│   ├── dual-store-status.py
│   └── apply-template.sh
├── templates/                                   ← ready-to-paste blocks
│   ├── env-baseline-system-block.md
│   ├── user-workflow-system-block.md
│   ├── index-entry-memory.md
│   └── index-entry-user.md
├── examples/                                    ← end-to-end worked examples
│   ├── case-01-omh-install/
│   ├── case-02-credential-routing/
│   ├── case-03-multi-tier-fact/
│   └── case-04-migration-from-flat-memory/
└── submodule-omh/                               ← git submodule → rlaope/oh-my-hermes
```

## Key Design Principles

1. **No information loss.** Compression is never the answer to "I'm out of
   space." Add a layer; do not trim an existing fact.

2. **No autonomous approval.** Every OMH project-memory write goes through
   review-first. The agent captures a candidate; the operator approves. Auto-
   approve requires explicit per-session delegation.

3. **No credentials in memory.** Passwords, tokens, and keys live only in
   `~/.hermes/.env`. They are referenced by env var name. The literal value
   never appears in any memory summary, chat message, or script literal.

4. **No platform mixing.** OMH project memory is the only durable store for
   AI-related memory. Other systems (e.g. OpenClaw, custom log files) must
   not be reused — the boundary is what makes the audit story work.

5. **No silent truncation.** OMH blocks refuse to silently truncate content
   that exceeds the per-block limit. The user is told the content did not
   land and must either split the block or raise the limit explicitly.

## Relationship to OMH

This project **consumes** OMH; it does not modify OMH. OMH provides:

- `~/.omh/memory/` — the project memory store
- `omh memory block-set / capture / approve / recall` — the CLI surface
- The `omh_memory` and `omh_context` MCP tools that the agent uses at runtime
- The OMH plugin (`hermes/plugins/omh/`) that registers those tools

If OMH upgrades and the OMH plugin's tool schemas change, the
[`docs/08-troubleshooting.md`](docs/08-troubleshooting.md) file documents the
expected migration path.

The submodule at `submodule-omh/` is a vendored copy of `rlaope/oh-my-hermes`
for offline reference. It is not required at runtime — Hermes Agent reads the
installed OMH plugin, not this submodule.

## Contributing

Issues and PRs welcome. The project is small enough that a maintainer review
can happen within a day. Before opening a PR, please:

1. Read [`docs/10-faq.md`](docs/10-faq.md) — many questions are already answered.
2. Open an issue describing the problem you want to solve.
3. Keep PRs focused — one architectural concern per PR.

## Author

Built by `anonymous99-Rise` in July 2026, derived from real usage on a
Windows 10 machine running Hermes Agent desktop + OMH plugin. The architecture
was refined over one long session that started with "install OMH" and ended
with "publish what we learned."

## License

MIT. See [`LICENSE`](LICENSE).