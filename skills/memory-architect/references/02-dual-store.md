# 02 — Dual Store (Reference)

This reference expands on the three storage surfaces. The main `SKILL.md` lists the headlines; this document describes each surface's exact location, format, capabilities, and limits.

## Surface 1 — `~/.hermes/.env`

### Location and format

`~/.hermes/.env` is a flat text file. Each line is either:

- A blank line
- A comment (starts with `#`)
- A `KEY=VALUE` declaration

Example:

```
# WSL KALI CREDENTIALS (added 2026-07-28, per user instruction)
WSL_KALI_PWD=spacex

# GITHUB AUTH
GITHUB_TOKEN=ghp_abc123def456
```

### Loading

Hermes loads `.env` at process startup. The exact mechanism is in Hermes's source code; from the operator's perspective, every key in `.env` becomes available as `os.environ['KEY']` and as a shell variable after Hermes injects them.

### What can live here

Per Hermes AGENTS.md: `.env` is for secrets only. Behavioral settings (timeouts, model, threshold, feature flag) belong in `~/.hermes/config.yaml`.

### What cannot live here

- Comments longer than necessary. Each comment should be one short line explaining what the credential is for.
- Multi-line values. `.env` syntax does not support multi-line.
- Encrypted values. `.env` is plaintext; encryption is the operator's job (use `gpg -c` to back up).

### Read protection

Hermes intercepts reads of `~/.hermes/.env` via the `read_file` tool with a hard "Access denied" error. This is to prevent agents from accidentally reading every credential at once.

The agent can read individual env vars via:

- `os.environ.get('KEY_NAME')` in Python
- `$KEY_NAME` in shell
- Specific CLI commands that need the credential

Each of these requires explicit operator approval for the specific read.

### Write protection

The agent should never write to `~/.hermes/.env` directly via the `write_file` tool. The agent's role is to *tell the operator to append a credential*, not to write it. This is to prevent the agent from accidentally overwriting existing credentials.

When the agent needs a new credential, the recommended flow is:

1. Agent: "Append this line to `~/.hermes/.env`: `KEY_NAME=value`."
2. Operator: appends the line manually (in their editor of choice).
3. Operator: confirms the credential is set.
4. Agent: references the env var by name in memory.

## Surface 2 — L1 Hermes memory tool

### Location and format

The L1 surfaces are at:

- `~/.hermes/memories/MEMORY.md`
- `~/.hermes/memories/USER.md`

These are markdown files. Each file is a sequence of memory entries. The memory tool writes to these files synchronously.

The file format is plain markdown. Each entry is rendered as a memory graph node:

- MEMORY.md entries: nodes `memory:memory:N` (where N is 0-indexed)
- USER.md entries: nodes `memory:profile:N`

### Injected into system prompt

The memory tool injects each entry into the system prompt on every session start. The total prompt injection is the sum of all entry bodies.

### Cap

| File | Cap per entry | Cap per file |
|---|---|---|
| MEMORY.md | 2,200 chars | none (multiple entries allowed) |
| USER.md | 1,375 chars | none |

The per-entry cap is enforced by the memory tool's schema validator. The per-file cap is unenforced; multiple entries can coexist up to the operator's taste.

### Graph tracking

Each memory entry has graph metadata:

- `useCount` — how many sessions have read this entry. Higher means more important.
- `pinned` — if true, the entry does not decay in useCount ranking.
- `createdBy` — `memory` (agent wrote) or `human` (operator wrote directly).
- `state` — `active` or `archived`.

The graph is queryable via `hermes journey --json` and editable via `hermes journey edit <id>` / `delete <id>`.

### Tool surface

The agent interacts with L1 via:

- The `memory` tool (provided by the memory provider plugin; usually `omh` after OMH install). Actions: `add`, `remove`, `edit`.
- The `hermes journey list / inspect / edit / delete` CLI commands.

The `memory` tool is the agent's primary write interface. `hermes journey` is the operator's primary inspection interface.

### Recommended content

L1 entries should be **pointers**, not full content. They should:

- Name the L0 block or record the operator cares about
- Describe in one line what the L0 entry is for
- Reference the env var name for credentials (not the value)
- Be self-contained (the operator should understand the entry without reading the L0 surface)

The total size of all L1 entries should be small — say, 1,500 chars or less. This leaves headroom for growth and keeps the system prompt lean.

### Anti-patterns

L1 entries should NOT:

- Duplicate L0 block content. The operator will maintain two copies.
- Contain credential values. Always reference by env var name.
- Be long procedures. Move them to L0 reference-tier blocks.
- Be session-local state. Session-local state does not survive across sessions.

## Surface 3 — L0 OMH project memory

### Location and format

L0 lives at `~/.omh/memory/`. The directory structure:

```
~/.omh/memory/
├── blocks/
│   ├── system/<label>.json
│   └── reference/<label>.json
├── records/
│   └── mem_<hash>.json
├── candidates/
│   └── cand_<hash>.json
├── reviews/
│   └── review_<hash>.json
├── index.json
└── (other internal files)
```

Each file is JSON.

### Sub-surfaces

#### Approved records

`~/.omh/memory/records/mem_<hash>.json`. Each record contains:

- `candidate_id` (the original candidate it came from)
- `record_id` (a content hash)
- `summary` (the only field persisted to operator-visible content; ≤ 240 chars after `_redact`)
- `record_type` (`fact`, `decision`, `lesson`, `procedure`, `episode`)
- `tags`
- `scope` (`project`, `target`, `thread`, `run`)
- `source`, `source_ref`
- `staleness` (`stale_after_days`, `stale_after` timestamp)
- `approved_by`, `approved_at`

Records are short. They are the atomic-fact tier of L0.

#### Reference-tier blocks

`~/.omh/memory/blocks/reference/<label>.json`. Each block contains:

- `label` (filename-safe identifier)
- `description` (one-line purpose)
- `value` (the content; up to `--limit`)
- `limit` (per-block cap)
- `tier` = `"reference"`

Blocks can be any length (subject to the per-block `--limit`). They are the long-form tier of L0.

#### System-tier blocks

`~/.omh/memory/blocks/system/<label>.json`. Same format as reference-tier blocks, except `tier` = `"system"`. Subject to the 6,000-char render budget across all system-tier blocks.

#### Candidates

`~/.omh/memory/candidates/cand_<hash>.json`. Pending records. Same format as records except `status: "pending_review"` and no `approved_*` fields.

#### Reviews

`~/.omh/memory/reviews/review_<hash>.json`. Audit trail of approve/reject decisions. Operator rarely reads these.

#### Index

`~/.omh/memory/index.json`. Machine-readable index of every approved record and block. Rebuilt by OMH after each write.

### Injected into system prompt

The OMH memory provider's `render_pack()` runs on every turn. It produces:

```xml
<memory_blocks>
  <!-- system-tier blocks in label order -->
  <block-label>
    <description>...</description>
    <metadata>chars_current=N chars_limit=M</metadata>
    <value>...</value>
  </block-label>
  ...
</memory_blocks>
<memory_block_index>
  <!-- reference-tier blocks in label order, no values -->
  <block label="..." chars="..." limit="...">description</block>
  ...
</memory_block_index>
```

The agent sees the rendered output on every turn.

### Tool surface

The agent interacts with L0 via:

- The `omh memory {capture, review, approve, reject, recall, status, inspect, blocks, block-set, block-remove, provider, dream}` CLI commands.
- The `omh_memory` MCP tool (action: `status`, `blocks`, `read`, `consolidation`).
- The `omh_context` MCP tool (returns compact OMH operating context, can include prompt context).

### Recommended content

L0 should hold:

- All long-form content (> 240 chars).
- All content that needs operator review before landing.
- All content that benefits from being searchable across sessions.

L0 should NOT hold:

- Credentials (use `.env`).
- Session-local state (use session transcripts, search via `session_search`).
- Facts that are needed every session and are short (use L1 or L0 system-tier block).

## Surfaces in summary

| | `~/.hermes/.env` | L1 MEMORY.md / USER.md | L0 OMH project memory |
|---|---|---|---|
| Holds | credential values | pointers | facts (atomic + long) |
| Cap | none | 2,200 / 1,375 chars per entry | 240 chars per record summary; per-block limit; 6,000 chars system tier render budget |
| Approval flow | none | none (synchronous write) | review-first (capture → review → approve) |
| Injected | into `os.environ` | into system prompt | system-tier auto-injected; reference-tier listed by label only |
| Curation tool | operator's editor | `hermes journey` | `omh memory *` |
| Read protection | Hermes blocks `read_file` of `.env` | none | none |
| Typical content | passwords, tokens, API keys | block labels, record IDs, env var names | long procedures, atomic facts, workflows |

The three surfaces are complementary. Each is the right home for a different kind of fact. The decision tree in [`03-decision-tree.md`](03-decision-tree.md) routes every fact to the right home.