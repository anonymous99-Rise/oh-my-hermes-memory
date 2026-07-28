# 01 — Architecture Overview

This document is the canonical entry point for the dual-store memory architecture. It defines every storage surface, names the rules that move facts between surfaces, and shows how a real session actually uses the architecture.

Read this once end to end before touching any other document in this folder. Every other document assumes you have this mental model.

## The Single Sentence

> **Three storage surfaces, one routing rule, one approval rule, zero information loss.**

The three surfaces are:

1. **`~/.hermes/.env`** — credentials and other short secrets.
2. **L1: Hermes memory tool** (`MEMORY.md`, `USER.md`) — a tiny pointer file that is injected into every session's system prompt. The pointer says "the real text is over there."
3. **L0: OMH project memory** (`~/.omh/memory/`) — the actual durable store for everything else, including everything that would not fit in L1.

The single routing rule is:

> Pick the surface by how often the fact is needed and how big the fact is. The decision tree is in [`02-decision-tree.md`](02-decision-tree.md).

The single approval rule is:

> The user approves every OMH project-memory write before it lands. No exceptions unless the user explicitly delegates a category of facts in this session.

The zero-information-loss rule is:

> Never compress a fact to make it fit. Move it to a surface that does not have the size cap, or split it into multiple blocks that the user can review one at a time.

## Why three surfaces, not one

The temptation is to say "just use OMH project memory for everything." This is wrong for two reasons.

### Reason 1 — system prompt budget

OMH project memory is not automatically injected into every session. Only **system-tier blocks** are auto-injected, and they share a 6,000-character render budget. If you put *every* durable fact in system-tier blocks, you will run out of render budget within a few categories of facts and the rest will be silently dropped by `render_memory_blocks` (`omh/memory_blocks.py`).

Reference-tier blocks solve this by being on-demand only — they show up as a label listing in the system prompt and the agent reads the value when it actually needs it. But reference-tier blocks still cost the operator attention: every reference-tier block is a "you might want to look at this" signal, and the cumulative noise is real.

L1 (`MEMORY.md`, `USER.md`) is a different solution to the same problem. It is not OMH at all — it is Hermes's own memory tool. The memory tool has its own trade-offs (2,200 / 1,375 chars hard limit per entry) but it is the *only* surface that:

- is always available without OMH being installed
- is rendered as a plain-text block the agent sees verbatim on session start
- has a built-in `useCount` field that lets Hermes rank which memory entries are actually being consulted
- shows up in `hermes journey list / inspect / edit / delete` for human curation

The dual-store architecture uses L1 as the **index** and L0 as the **library**. The index is what makes the library navigable.

### Reason 2 — information loss boundaries

When a fact goes into L1, it must be short. When a fact goes into an L0 approved record, its summary is hard-capped at 240 characters (this is what `_redact` in `omh/workflows/memory.py` enforces). When a fact goes into an L0 block, its value can be any length up to the per-block `--limit` (default 2,000, max ~5,000 in practice).

These three boundaries are not interchangeable. If you put a 500-character fact into an L1 entry, you are 23% of the way to the cap and you have not left room for growth. If you put a 500-character fact into an L0 approved record, you get a 240-character silent truncation. If you put a 500-character fact into an L0 block, the full 500 characters land without truncation.

The routing rule exists so the operator can predict, in advance, exactly what shape a fact will take once it lands.

## The exact surfaces

### Surface 1 — `~/.hermes/.env` (credentials)

**What lives here:** Any value that, if disclosed, would let a third party impersonate the user or break into a system the user controls. Passwords, API keys, OAuth tokens, SSH passphrases, signing keys. Nothing else.

**What does not live here:** Behavior settings, feature flags, model selections, timeouts, paths. Those belong in `~/.hermes/config.yaml` (see Hermes AGENTS.md: *".env is for secrets only"*).

**Loaded:** Hermes reads `~/.hermes/.env` at process startup and exposes every key as an environment variable. Anything in the file is visible to any process the user runs, and visible to the agent via `os.environ[...]` (if the agent has a tool that can read it; the agent must explicitly ask).

**Read by humans:** `cat ~/.hermes/.env`, or `python -c "import os; print(os.environ.get('KEY_NAME'))"`.

**Read by the agent:** Only when the operator explicitly grants access. The agent cannot read `.env` through the `read_file` tool — Hermes intercepts that path with a hard "Access denied" error because it is marked as a credential store. The agent must use `terminal` with `python3 -c "import os; print(os.environ['KEY_NAME'])"` or equivalent, and only after the operator has approved the read.

**Audit story:** Every read of `.env` is logged in the user's shell history (for `cat`) or in the OMH runtime observation ledger (if the agent does it via the terminal tool). The operator can review either.

**Single hard rule:** The literal value of any `.env` key must never appear in any of the following surfaces:

- An L1 MEMORY.md / USER.md entry
- An L0 approved record (the OMH safety layer would redact it anyway, but the rule is the rule)
- An L0 block's `value` field
- A chat message
- A script literal (use `"${KEY_NAME}"` not `"literal value"`)

Reference the value by env var name. Let the runtime substitute the literal at use time.

### Surface 2 — L1 `~/.hermes/memories/MEMORY.md` (the index)

**What lives here:** A short pointer to the L0 blocks and records. The pointer tells the next session: "Here are the durable facts you need to know about. They are in OMH project memory at these labels."

**Hard cap:** 2,200 characters per entry. There can be more than one entry (memory graph node IDs `memory:memory:N`), but each entry must be ≤ 2,200 chars.

**Injected:** Every session. By Hermes itself, not by OMH.

**Read by the agent:** Always. It is part of the system prompt.

**Curation tool:** `hermes journey list / inspect / edit / delete` and the `memory` tool exposed by the memory provider.

**Audit story:** `hermes journey --json` dumps the full graph including `useCount`, `pinned`, `createdBy`, `timestamp` for every node.

**Recommended size:** ≤ 1,200 chars in practice. Leave headroom for growth and for the operator to add entries without immediately hitting the cap.

**When you write here:** You are writing to the system prompt of every future session. Be conservative. Every line is paid on every turn.

**What goes here:** Only the index — block labels, record labels, the credential reference convention, the update policy. Not the actual content.

### Surface 3 — L0 OMH project memory (`~/.omh/memory/`)

**What lives here:** The actual durable content. Long procedures, decision rationales, environment baselines, user preferences, credential references (by name), observation summaries, runbooks, troubleshooting notes, anything that would not fit in L1.

**Hard caps:**

| Sub-surface | Hard cap | Adjustable? |
|---|---|---|
| Approved record summary | 240 chars (hard truncate via `_redact`) | No |
| Block value | per-block `--limit` (default 2,000) | Yes (per-block) |
| System-tier render budget | 6,000 chars across all system-tier blocks | No (single budget) |
| Number of blocks | None | n/a |
| Number of approved records | None | n/a |

**Injected:**

- System-tier blocks: every session, by the OMH memory provider's `render_pack()` method.
- Reference-tier blocks: only as a label listing in the system prompt. Full value read on demand via `omh_memory(action="read", label=...)` MCP tool.

**Read by the agent:**

- System-tier blocks: implicitly, by seeing them in the system prompt.
- Reference-tier blocks: by calling the `omh_memory` MCP tool with `action="read"` and a `label` parameter.
- Approved records: by calling `omh memory recall <query>` on the CLI, or by reading `~/.omh/memory/records/*.json` directly.

**Curation tool:** `omh memory {capture, review, approve, reject, recall, blocks, block-set, block-remove, status, provider, dream}`.

**Audit story:** `omh memory status --json` returns counts, store paths, and policy settings. `cat ~/.omh/memory/records/*.json` shows full record payloads. `cat ~/.omh/memory/blocks/{system,reference}/*.json` shows full block payloads.

**When you write here:** You are writing to a file under the user's home directory. The operator approves each write. The file is local-only by default — no cloud sync unless the operator configures the `omh memory provider` subsystem.

## L0 sub-surfaces in detail

### L0.A — Approved records (`~/.omh/memory/records/`)

Approved records are the **short-fact** tier of L0. They are created by `omh memory capture` and graduate to `~/.omh/memory/records/` only after `omh memory approve <candidate_id>`.

A record has:

- `summary` (≤ 240 chars after `_redact`, hard-capped)
- `record_type` (`fact`, `decision`, `lesson`, `procedure`, `episode`)
- `tags`
- `scope` (`project`, `target`, `thread`, `run`)
- `source`, `source_ref`
- `staleness` (default 90 days; the record becomes "stale" after that)
- `approved_by`, `approved_at`

A record does NOT have a place for long content. The `content_ref` field carries only a SHA-256 and length — the raw content is never persisted. This is by design: records are short.

If you find yourself wanting to write a 300-character fact as a record, write it as a block instead.

### L0.B — Reference-tier blocks (`~/.omh/memory/blocks/reference/`)

Reference-tier blocks are the **on-demand library** of L0. They show up in the system prompt as a label listing (the `<memory_block_index>` element) but the full value is read on demand.

A reference-tier block has:

- `label` (filename-safe; lowercase letters, digits, `-`, `_`; 1–63 chars; starts alphanumeric)
- `description` (one-line purpose statement shown to the agent)
- `value` (the actual content, up to `--limit`)
- `limit` (per-block cap; default 2,000)
- `tier` = `"reference"`

The block's value is the most natural place to put long procedures, runbooks, decision rationales, environment notes, and any content the agent might need but does not need every turn.

### L0.C — System-tier blocks (`~/.omh/memory/blocks/system/`)

System-tier blocks are the **always-injected** subset of L0 blocks. They render into the system prompt on every turn via the OMH memory provider's `render_memory_blocks()` function, sharing a 6,000-char budget across all system-tier blocks.

A system-tier block has the same shape as a reference-tier block, except `tier` = `"system"`.

The 6,000-char budget is **shared** — three 2,000-char system blocks exhaust the budget. The renderer drops overflow blocks rather than truncating them (`omh/memory_blocks.py` line 240: "the first block that would exceed it, and every block after, is dropped"). The dropped blocks still exist on disk; they just do not render.

System-tier blocks are the right place for content that is needed every session and is short enough to fit:

- The user's name, language preference, response style
- The shell convention (Git Bash / PowerShell / cmd.exe split)
- The CLI executors that are authorized, with paths and versions
- The host environment baseline (Python version, working directory, OMH install state)
- The memory architecture itself (so the agent knows L0 exists)

If a fact is needed every session but is longer than ~3,000 chars, it does not belong in a system-tier block. Either split it across two system-tier blocks (still risky given the 6,000-char budget) or move it to a reference-tier block and have L1 point to it.

### L0.D — Candidates (`~/.omh/memory/candidates/`)

Candidates are pending approved records. They are created by `omh memory capture` and live in `~/.omh/memory/candidates/` until the operator approves or rejects them via `omh memory approve` / `omh memory reject`.

Candidates are not a normal landing surface — they are intermediate state. Do not write directly into this directory. Use `omh memory capture` so the metadata (timestamps, scope, tags, source, staleness) is set correctly.

### L0.E — Reviews (`~/.omh/memory/reviews/`)

Reviews are the audit trail of every approve / reject decision. They are managed by OMH. Operators rarely read them, but they exist for forensic purposes.

### L0.F — Index (`~/.omh/memory/index.json`)

A machine-readable index of every approved record and block. OMH rebuilds it after each write. Operators rarely touch it.

## What an actual session looks like

A new session starts. The agent sees:

1. Hermes's built-in system prompt, which includes `MEMORY.md` and `USER.md`. Both are pointers. Together they are ~1,200 chars.
2. The OMH plugin's tool schemas, which include `omh_memory`, `omh_status`, `omh_recommend`, `omh_context`, `omh_capabilities`, `omh_gather_evidence`, `omh_hud`, `omh_interact`, `omh_role`, `omh_probe`.
3. The OMH memory provider's `render_pack()` output, which includes the rendered system-tier blocks (~5,000 chars) and a label listing of reference-tier blocks (~200 chars).
4. The OMH skill index — names and one-line descriptions of all 92 OMH skills. Skills themselves are loaded on demand via `tool_search`.

The agent's first move, when it sees a memory write opportunity, is to consult this project. The skill `skills/memory-architect/SKILL.md` is the agent-side entry point. The skill walks the agent through the decision tree (this folder's `02-decision-tree.md`), the credential routing rules (`04-credential-routing.md`), and the block-tier selection rules (`05-omh-block-tiers.md`).

The agent captures or sets the fact. The operator approves. The fact lands.

A future session sees the same memory surfaces, populated with the fact. The next agent reads it. Information preserved.

## Why this is not just "OMH memory plus some text"

There is a real risk that an operator reads the docs/ folder, sees the diagram, and thinks "I already have OMH, this is overengineering." Three reasons it is not:

1. **The character caps are real.** The 240-char record summary hard cap, the 2,000-char per-block limit, the 6,000-char system-tier render budget, and the 2,200-char MEMORY.md limit all exist in the actual code. Pretending they do not exist leads to silent truncation.

2. **The `.env` boundary is real.** The OMH safety layer will redact any summary containing the literal strings `secret`, `token`, `password`, `private-key`, `api_key`, or `apikey`. If you do not route credentials to `.env` first, you either lose them to redaction or accidentally bypass the safety layer by writing them somewhere unguarded.

3. **The review-first approval is real.** OMH is in `mode: "review-first"` and `review_required: true` by default. `auto_approve_safe` is `false`. The agent cannot legally or architecturally bypass the operator's review without explicit per-session delegation. Pretending the operator can be removed from the loop leads to un-audited memory accumulation, which destroys trust.

The dual-store architecture is not a stylistic choice. It is the minimum-viable configuration that respects all three real constraints at once.

## Next steps

Read [`02-decision-tree.md`](02-decision-tree.md) for the routing rule in detail.
Then [`03-character-limits.md`](03-character-limits.md) for the exact cap numbers and where they come from.
Then [`04-credential-routing.md`](04-credential-routing.md) for the `.env` boundary in detail.