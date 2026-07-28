# 03 — Character Limits

This document lists every character limit that affects memory writes in the dual-store architecture, with the exact source location in code and what to do when you hit each one.

The limits are real. They are not configurable in most cases. Pretending they do not exist leads to silent truncation or hard rejection.

## Quick reference table

| Surface | Cap | Configurable? | Truncation behaviour |
|---|---|---|---|
| `~/.hermes/.env` value | None in practice; constrained by file system | n/a | n/a |
| L1 `MEMORY.md` per entry | 2,200 chars | No (Hermes memory tool hard cap) | Hard reject by `memory` tool |
| L1 `USER.md` per entry | 1,375 chars | No (Hermes memory tool hard cap) | Hard reject by `memory` tool |
| L0 approved record summary | 240 chars after `_redact` | No | Silent truncation by `_redact(value)[:240]` |
| L0 block value | `--limit` per block (default 2,000) | Yes (per block, via `--limit` arg) | Hard reject by `build_memory_block` |
| L0 system-tier render budget | 6,000 chars across all system blocks | No | Silent drop by `render_memory_blocks` |
| L0 number of blocks | None | n/a | n/a |
| L0 number of records | None | n/a | n/a |
| OMH skill `description` field | 1,024 chars | No (skill frontmatter validator) | Truncation to 57 chars in skill index |
| OMH skill `name` field | 64 chars | No | Hard reject |
| Full `SKILL.md` content | 100,000 chars (~36k tokens) | No | Hard reject |

The two limits that bite hardest in practice are the **240-char record summary** and the **6,000-char system-tier render budget**. Both silently degrade the user experience. The L1 limits (2,200 / 1,375) are hard rejects — the agent sees the rejection immediately.

## L1 — `MEMORY.md` (2,200 chars per entry)

### Source

`Hermes memory tool` — the `memory` action exposed to the agent. The cap is enforced by the tool's schema validator, not by the agent. When the agent calls `memory(action="add", content=...)` with content > 2,200 chars, the tool returns:

```
Blocked: content exceeds 2,200 char hard cap for MEMORY.md entries.
```

or, depending on the agent version:

```
Memory at N/M chars. Adding this entry (X chars) would exceed the limit.
```

Either way, the add is refused. The agent must shorten the entry or split it.

### What it actually is

`MEMORY.md` is the file at `~/.hermes/memories/MEMORY.md`. The memory tool reads it, treats it as a sequence of memory entries, and renders each entry as a memory graph node (id `memory:memory:N`). The 2,200-char limit is the per-entry cap.

If the operator wants more than one entry in `MEMORY.md`, they are allowed — each entry is independently ≤ 2,200 chars. The total file size is not capped.

### What to do when you hit it

- **Compress the wording.** Often the entry is verbose. Cutting examples, removing redundant disclaimers, and using shorter sentences can recover 200–400 chars.
- **Split into two entries.** If the fact has two natural parts, write them as two separate entries. Each gets its own `useCount` tracking.
- **Move to L0.** If the entry is genuinely long and cannot be cut, move it to an L0 reference-tier block and leave a short pointer in L1.

The wrong move is to keep adding to MEMORY.md without splitting. The wrong move is to invent a separate "MEMORY.md notes" file outside the memory tool. Both defeat the point of L1.

## L1 — `USER.md` (1,375 chars per entry)

### Source

Same Hermes memory tool. The cap is enforced separately for the `user` profile vs the `memory` profile.

### What it actually is

`USER.md` is the file at `~/.hermes/memories/USER.md`. It holds user-profile information: name, language preference, response style, role. It is shorter than MEMORY.md because user-profile information is naturally shorter than technical detail.

### What to do when you hit it

- User-profile information is genuinely short. If you are hitting 1,375 chars, the entry probably contains technical detail that does not belong in USER.md.
- Move the technical detail to MEMORY.md (which has 825 more chars of headroom) or to an L0 block.

## L0 — Approved record summary (240 chars after `_redact`)

### Source

`omh/workflows/memory.py` lines 1400–1410:

```python
def _redact(value: str) -> str:
    if _looks_sensitive(value):
        return "[redacted]"
    return value[:240]
```

This is the function called from `_build_candidate` (line 740) and `_approve` (line 767):

```python
"summary": _redact(summary.strip())[:500],
"summary": _redact(str(candidate.get("summary", "")))[:500],
```

Note: the function returns `value[:240]` for non-sensitive content, but the outer slice `[:500]` would only kick in for sensitive content (which is replaced with the literal `"[redacted]"` — 10 chars). The effective cap for non-sensitive content is **240 chars**.

### Why this is the real cap

Even though the outer code reads `[:500]`, `_redact` itself clamps to 240 for any non-sensitive value. So when you `omh memory capture` a 300-char summary:

- `_looks_sensitive("300-char text")` returns `False`
- `_redact` returns `value[:240]` — 240 chars
- The outer `[:500]` is a no-op because the value is already 240 chars
- The candidate's `summary` field is 240 chars

The agent never sees a warning. The candidate's summary is silently truncated.

### What to do when you hit it

- **Rephrase.** A 240-char summary that fits in 240 chars and conveys the full fact is a writing skill. Often the 300-char version can be cut to 240 without losing meaning.
- **Split into two records.** If the fact really has two parts, write two records. Each gets a tag and a `candidate_id`.
- **Move to a block.** If the fact is a long procedure, it does not belong as a record. Capture it as a reference-tier block instead.

### The sensitive-content trap

If the summary contains any of the substrings `secret`, `token`, `password`, `private-key`, `api_key`, or `apikey`, `_looks_sensitive` returns `True` and `_redact` returns the literal string `"[redacted]"`. The candidate's summary becomes `"[redacted]"` — 10 chars.

This is the safety layer. It is what stops credentials from accidentally being written into a durable memory surface. But it is also what destroys summaries that contain the substring `password` even when the word is being used in a non-credential context (e.g. "Password-less SSH login uses public-key auth" — the substring `password` is present).

**Mitigation:** avoid credential-related words in summaries. Refer to credentials by env var name. Example:

- ❌ `WSL Kali root password is spacex, same as user password` → redacted to `[redacted]`
- ✅ `WSL Kali authentication uses ${WSL_KALI_PWD}; both user and root auth from the same env var` → passes through

The substitution `password` → `authentication`, `auth`, or `credential` (where credential is not in the trigger list — let me check) is generally safe. The trigger list is exactly:

```
secret, token, password, private-key, api_key, apikey
```

Anything outside that list passes through.

## L0 — Block value (`--limit` per block)

### Source

`omh/memory_blocks.py` line 130:

```python
def build_memory_block(
    label: str,
    value: str,
    *,
    description: str = "",
    limit: int = DEFAULT_BLOCK_LIMIT_CHARS,  # default 2,000
    tier: str = SYSTEM_TIER,
) -> MemoryBlock:
    ...
    text = str(value or "")
    if len(text) > limit:
        raise MemoryBlockError(
            f"block {normalized_label!r} is {len(text)} chars against a {limit}-char limit"
        )
```

When `omh memory block-set <label> --value "..." --limit 2000` is called with value > 2,000 chars, OMH raises a hard error:

```
omh: error: block 'my-label' is 2,500 chars against a 2,000-char limit
```

### What it actually is

The `--limit` is a per-block cap, not a system-wide cap. Each block can have a different `--limit`. Common patterns:

- `--limit 2000` (default) — short facts
- `--limit 5800` — large system-tier blocks (still under the 6,000-char system render budget)
- `--limit 5000` — large reference-tier blocks

### What to do when you hit it

- **Raise the limit.** The limit is operator-controlled. `omh memory block-set <label> --limit 5000 --value "..."` accepts any positive integer.
- **Split into multiple blocks.** If the content is logically two pieces, two blocks each with a smaller `--limit` work fine.
- **Use progressive disclosure.** Move the long-form detail to a reference-tier block; keep a short pointer in a system-tier block.

The wrong move is to silently truncate. OMH refuses to silently truncate, which is the right design. The operator must take one of the explicit actions above.

## L0 — System-tier render budget (6,000 chars)

### Source

`omh/memory_blocks.py` line 247:

```python
DEFAULT_SYSTEM_RENDER_BUDGET_CHARS = 6000
```

And `render_memory_blocks`:

```python
def render_memory_blocks(blocks, *, budget_chars=DEFAULT_SYSTEM_RENDER_BUDGET_CHARS):
    ...
    for block in blocks:
        element = _render_block(block)
        if omitted or used + len(element) > max(budget_chars, 0):
            omitted.append(block.label)
            continue
        used += len(element)
        lines.append(element)
    if omitted:
        lines.append(
            f'  <omitted reason="render_budget_exhausted" budget_chars="{budget_chars}">'
            f"{', '.join(omitted)}</omitted>"
        )
```

The renderer drops entire blocks (not partial blocks) when the budget is exhausted. The dropped blocks still exist on disk; they just do not render into the system prompt.

### What it actually is

Every system-tier block contributes its rendered XML-ish element to the system prompt:

```xml
<memory_blocks>
  <block-label>
    <description>...</description>
    <metadata>chars_current=N chars_limit=M</metadata>
    <value>...</value>
  </block-label>
  ...
  <omitted reason="render_budget_exhausted" budget_chars="6000">block-c, block-d</omitted>
</memory_blocks>
```

The `<value>...</value>` plus the wrapping tags count toward the 6,000-char budget. The metadata line and description line also count.

### What to do when you hit it

- **Audit existing system-tier blocks.** Run `omh memory blocks --tier system` and look at the `chars` column. Identify the largest blocks.
- **Move large blocks to reference tier.** If a block is needed every session but rarely consulted, move it to reference tier. The label still shows up in the index, but the value is read on demand.
- **Compress wording.** System-tier blocks should be terse. Often the value can be cut by 30% without losing meaning.
- **Split into two system-tier blocks.** Both render. Both contribute to the budget. Use this only as a last resort.

The wrong move is to add more system-tier blocks without checking the running total. The wrong move is to set `--limit 10000` on a single system-tier block — the renderer drops it the same way, but the operator loses the signal that the block is over budget.

## L0 — Number of blocks and records

### Source

There is no source. OMH does not cap the number of blocks or approved records. The directory listing at `~/.omh/memory/blocks/{system,reference}/` and `~/.omh/memory/records/` grows without bound.

### Practical limits

- **Filesystem limits** — inodes on Linux/macOS, file system max entries per directory on Windows (NTFS default is roughly 2 billion entries per directory). Operators will hit filesystem limits long before OMH limits.
- **Render performance** — every system-tier block is rendered on every turn. 100 system-tier blocks = 100 file reads + 100 XML wrappers per turn. Expect noticeable latency past ~50 system-tier blocks.
- **Search quality** — `omh memory recall` and `omh memory read` work fine with hundreds of entries, but human curation via `omh memory blocks` listing becomes hard past ~50 entries per tier.

### What to do when you approach practical limits

- **Cull.** Run `omh memory sync` periodically. Mark stale records for rejection. Remove blocks that no longer apply.
- **Split by scope.** OMH supports `--scope-kind {project, target, thread, run}`. Use scope to partition memory. Project-scope is global; target-scope is per Hermes target; thread-scope is per conversation; run-scope is per cron job.
- **Migrate off OMH.** If you are routinely above 500 entries, OMH is the wrong tool. Use a real database (SQLite + sqlite-vec, mnemosyne, or Penfield). See [`09-migration-guide.md`](09-migration-guide.md) for migration paths.

## Skill `description` field (1,024 chars max, truncated to 57 in index)

### Source

`tools/skill_manager_tool.py::_validate_frontmatter`:

```python
MAX_DESCRIPTION_LENGTH = 1024
```

And `agent/skill_utils.py::extract_skill_description`:

```python
return description[:57] + "..."
```

### What it actually is

The `description` field of a SKILL.md frontmatter is shown to the agent in two places:

1. The full description (up to 1,024 chars) in `skills_list()` and `skill_view()`.
2. A truncated version (first 57 chars + `...`) in the system prompt's skill index.

The agent uses the truncated version for routing decisions (which skill should I load?). The full version is read after the agent decides to load the skill.

### What to do when you hit it

- **Front-load the trigger phrase.** The first 57 chars should answer "Use when X" without truncation.
- **Move detail to the body.** The description is a trigger, not a manual. The body of SKILL.md is the manual.

## Skill `name` field (64 chars max)

### Source

`tools/skill_manager_tool.py`:

```python
MAX_NAME_LENGTH = 64
```

### What it actually is

The skill name appears in the system prompt skill index and in the `Use OMH <name> for: ...` invocation syntax. Operators read it; agents parse it.

### What to do when you hit it

- Use hyphens, not underscores. `my-cool-skill` not `my_cool_skill`.
- Drop words that do not change the meaning. `omh-memory-architect` not `omh-memory-architecture-design-skill`.

## Full `SKILL.md` content (100,000 chars)

### Source

`tools/skill_manager_tool.py`:

```python
MAX_SKILL_CONTENT_CHARS = 100_000
```

### What to do when you approach it

- Move detail to `references/` subdirectory and link from the SKILL.md body.
- Peer skills in the `software-development/` category are 8–14k chars. If you are pushing 20k+, split.

## `omh memory status --json` shape

Not a limit, but useful reference for the script `scripts/dual-store-status.py`:

```json
{
  "counts": {
    "approved_records": 4,
    "candidates": 4,
    "pending_review": 0
  },
  "policy": {
    "auto_approve_safe": false,
    "backend": "local_json",
    "capture_enabled": true,
    "mode": "review-first",
    "review_required": true,
    "store_dir": "C:\\Users\\Administrator\\.omh\\memory"
  },
  "store": {
    "memory_dir": "C:\\Users\\Administrator\\.omh\\memory",
    "record_dir": "C:\\Users\\Administrator\\.omh\\memory\\records",
    "candidate_dir": "C:\\Users\\Administrator\\.omh\\memory\\candidates",
    "review_dir": "C:\\Users\\Administrator\\.omh\\memory\\reviews"
  },
  "hermes_memory": {
    "files": [
      {"label": "MEMORY.md", "chars": 1085, "cap": 2200, "headroom_chars": 1115},
      {"label": "USER.md", "chars": 278, "cap": 1375, "headroom_chars": 1097}
    ]
  }
}
```

The `headroom_chars` value is the operator's most important signal — it tells them how much room is left before the next hard reject.

## What to do when multiple limits fire at once

Real-world scenario: you want to write a 1,500-char fact that is needed every session.

1. Q1 says it is needed every session.
2. Q2 says it does not fit in 240 chars.
3. Q4 says it would fit in a 6,000-char system-tier render budget (the existing system blocks total 4,500 chars, so 1,500 chars of headroom remain).
4. Q4 answer is yes → land it as a system-tier block.

Or:

1. Q1 says it is needed every session.
2. Q2 says it does not fit in 240 chars.
3. Q4 says it would push system-tier render budget to 7,500 chars (over the 6,000 cap).
4. Q4 answer is no → split into two reference-tier blocks. Both show in the index. Both are read on demand.

The decision tree in [`02-decision-tree.md`](02-decision-tree.md) handles this automatically. The character limits in this document are the inputs to the decision tree.

## Summary

- 240 chars is the silent truncation that hurts the most.
- 2,200 / 1,375 chars are the hard rejects that the agent sees immediately.
- 6,000 chars is the silent drop that hurts the most for system-tier blocks.
- `--limit` per block is operator-controlled and should be tuned to the content.

When in doubt, write the fact as a reference-tier block with `--limit 5000`. That has no silent failure mode. If the operator wants it auto-injected, promote to system-tier and watch the render budget.