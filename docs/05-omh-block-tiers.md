# 05 — OMH Block Tiers

This document explains the two tiers of OMH memory blocks: `system` (auto-injected every turn) and `reference` (on-demand read). It covers when to use which tier, what the trade-offs are, and how the rendering works.

## Quick decision rule

| Use `tier=system` when | Use `tier=reference` when |
|---|---|
| The fact is needed at the start of every session | The fact is durable but rarely consulted |
| The fact is short enough that the 6,000-char render budget can absorb it | The fact is longer than the per-block limit supports at system tier |
| The fact has a stable shape and rarely changes | The fact may be re-read multiple times in one session |
| The fact is meta (about the architecture itself) | The fact is operational (about a specific tool or runbook) |

In practice, the canonical layout is:

- One or two **system-tier blocks** carrying the "always need" content (env baseline, user preferences, memory architecture itself).
- Many **reference-tier blocks** carrying the long procedures, runbooks, environment notes, troubleshooting guides.
- One L1 MEMORY.md index entry pointing at the system-tier block labels and the most important reference-tier block labels.

## The two tiers in detail

### System tier

System-tier blocks live at `~/.omh/memory/blocks/system/<label>.json`. They are rendered into the system prompt on every turn by the OMH memory provider.

#### Rendering

The renderer is `render_memory_blocks` in `omh/memory_blocks.py`:

```python
def render_memory_blocks(
    blocks: tuple[MemoryBlock, ...] | list[MemoryBlock],
    *,
    budget_chars: int = DEFAULT_SYSTEM_RENDER_BUDGET_CHARS,  # 6,000
) -> str:
    if not blocks:
        return ""
    lines = ["<memory_blocks>"]
    used = 0
    omitted: list[str] = []
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
    lines.append("</memory_blocks>")
    return "\n".join(lines)
```

Each block is wrapped in an XML-ish element:

```xml
<memory_blocks>
  <block-label>
    <description>One-line purpose statement.</description>
    <metadata>chars_current=3376 chars_limit=5800</metadata>
    <value>The full block content, which is what the agent actually reads.</value>
  </block-label>
  ...
  <omitted reason="render_budget_exhausted" budget_chars="6000">block-that-didnt-fit</omitted>
</memory_blocks>
```

The `<value>` field is what the agent sees and can reason about. The `<description>` and `<metadata>` lines are metadata the agent can ignore.

#### Render budget

`DEFAULT_SYSTEM_RENDER_BUDGET_CHARS = 6000`. This is a **single budget across all system-tier blocks combined**, not per-block. The renderer walks blocks in label order (alphabetical) and drops any block whose rendered element would push the running total past 6,000 chars. The dropped blocks still exist on disk; they just do not render.

#### When blocks get dropped silently

This is the most important detail: dropping is silent. The agent does not get a warning. If a system-tier block does not appear in the system prompt, the agent has no way to know the block exists unless it explicitly calls `omh memory blocks` (CLI) or `omh_memory(action="blocks")` (MCP tool).

Mitigation:

- Run `omh memory blocks --tier system` periodically and check the `chars` column against the budget.
- Keep the system-tier render total under 5,000 chars to leave room for growth.
- Promote rarely-needed system-tier blocks to reference tier.

### Reference tier

Reference-tier blocks live at `~/.omh/memory/blocks/reference/<label>.json`. They are *not* rendered into the system prompt. Instead, the OMH memory provider renders a label-only index into the system prompt:

```xml
<memory_block_index>
  <block label="windows-env-quirks" chars="914" limit="2500">Windows MSYS/Python/PATH gotchas. Read on demand before any Python venv work or file copy on Windows.</block>
  <block label="wsl-kali-workflow" chars="964" limit="2500">WSL Kali access workflow. Credential referenced as $WSL_KALI_PWD from ~/.hermes/.env. Read on demand for any Linux-side operation.</block>
  <block label="cli-executors" chars="1096" limit="2500">Authorized CLI executors with paths, versions, and routing policy. Read on demand before launching a coding tool.</block>
  <block label="omh-install-state" chars="1040" limit="2500">OMH install details, paths, and known issues. Read on demand before OMH troubleshooting or update.</block>
  <block label="codegraph-integration" chars="1008" limit="2500">codegraph 1.5.0 install + MCP integration + OMH workflow. Read on demand before any codebase navigation task.</block>
</memory_block_index>
```

The full value is read on demand via:

- CLI: `omh memory block-set ... --tier reference` to write, `cat ~/.omh/memory/blocks/reference/<label>.json` to read directly.
- MCP tool: `omh_memory(action="read", label="<label>")` to read via the agent's tool surface.

The reference-tier index is cheap — 5 blocks at ~250 chars each = ~1,250 chars in the system prompt, well under the 6,000-char budget for system tier.

#### When the agent actually reads

The agent reads a reference-tier block when:

- It encounters a task that matches the block's `description` (e.g. "before any Python venv work on Windows" → read `windows-env-quirks`).
- It explicitly needs the value (e.g. "what is the WSL Kali workflow?" → read `wsl-kali-workflow`).
- The L1 MEMORY.md index entry names the block.

The agent does not read a reference-tier block when:

- It has no reason to (this is the point of reference tier — cheap index, on-demand value).
- It is in a session where the operator has restricted which blocks the agent can read (this is enforced by the OMH `pre_tool_call` hook).

## How to choose between system and reference

### Step 1 — Will the agent forget this fact without it?

If the agent would forget the fact (or worse, do something wrong because it forgot) within a single session, the fact should be system tier.

Examples of facts the agent would forget:

- The shell convention (Git Bash for POSIX, PowerShell for native)
- The CLI executors that are authorized (and which one to pick for which task)
- The credential routing rule (reference env var names, never values)
- The memory architecture itself (so the agent knows L0 exists)

Examples of facts the agent would not forget:

- A specific command to run (the agent can read the block when it needs to run it)
- A specific troubleshooting runbook (the agent reads it when troubleshooting, not before)
- A specific environment quirk (the agent reads it when about to do the affected operation)
- A specific OMH install detail (the agent reads it when debugging OMH)

### Step 2 — Is the fact short enough for the system tier budget?

If the fact is over ~3,000 chars, do not put it in system tier — even one such block would dominate the budget. Put it in reference tier.

If the fact is between 1,000 and 3,000 chars and is needed every session, the operator must decide: is this fact more important than the other system-tier blocks? If yes, it goes in system tier. If no, it goes in reference tier with a one-line pointer in a system-tier block.

If the fact is under 1,000 chars and is needed every session, default to system tier.

### Step 3 — Is the fact likely to change?

Stable facts (env baseline, shell convention, credential routing rule) belong in system tier. They are unlikely to need replacement; the operator is paying the render cost forever.

Volatile facts (active project name, current task, recent decisions) do *not* belong in any tier. They are session-local. If the operator insists on capturing them, reference tier with a short TTL.

### Step 4 — Decision summary

| Condition | Tier |
|---|---|
| Needed every session, short, stable | system |
| Needed every session, long (>3,000 chars), stable | split across two reference blocks, both indexed from a system block |
| Durable but rarely consulted | reference |
| Session-local, will not survive across sessions | do not store |
| Will change within the next 30 days | reference (so the operator can `block-remove` cleanly) |

## Per-block character limits

The per-block `--limit` is operator-controlled. The default is 2,000 chars. The OMH CLI accepts any positive integer.

Practical patterns:

- `--limit 2000` — default; short facts, atomic entries
- `--limit 5000` — long procedures, runbooks, environment notes
- `--limit 5800` — large system-tier blocks (still under the 6,000-char render budget, with headroom for the XML wrapper)

The CLI rejects values that exceed `--limit` with `MemoryBlockError`:

```
omh: error: block 'my-label' is 5,500 chars against a 5,000-char limit
```

This is a hard reject, not a silent truncation. The operator must raise the limit, split the block, or shorten the content.

## When the system-tier render budget exhausts

Real-world example: the operator has three system-tier blocks totaling 6,100 chars. The third block (alphabetically last) is dropped at render time. The agent has no idea the third block exists.

Diagnosis:

```bash
omh memory blocks --tier system
```

Output:

```
[system] env-baseline                    chars=3376  limit=5800
[system] user-workflow-preferences       chars=2016  limit=5800
[system] wsl-kali-workflow               chars=964   limit=2500  ← dropped
```

Mitigation:

- Move the third block to reference tier: `omh memory block-set <label> --tier reference ...`
- Or compress the existing blocks so the third fits.
- Or raise the render budget (not currently supported; would require patching OMH).

## Mixed-tier layouts (real examples)

### Layout 1 — minimal

- L1 MEMORY.md: 1,200 chars. Points to env-baseline block.
- L0 system blocks: env-baseline (3,000 chars).
- L0 reference blocks: (none).
- L0 approved records: 3 atomic facts.

Use case: a new operator with a clean install. Most content lives in env-baseline; only truly atomic facts are separate records.

### Layout 2 — typical

- L1 MEMORY.md: 1,200 chars. Points to env-baseline + 5 reference block labels.
- L0 system blocks: env-baseline (3,000 chars) + user-workflow-preferences (2,000 chars).
- L0 reference blocks: 5–10 long procedures (each 1,000–5,000 chars).
- L0 approved records: 5–10 atomic facts.

Use case: an operator with a few months of usage. Long procedures have accumulated; system tier holds the stable meta-information.

### Layout 3 — heavy

- L1 MEMORY.md: 1,500 chars. Points to env-baseline + 20 reference block labels.
- L0 system blocks: env-baseline (3,500 chars) + user-workflow-preferences (2,500 chars).
- L0 reference blocks: 20–50 long procedures (each 1,000–5,000 chars).
- L0 approved records: 30–50 atomic facts.

Use case: a power operator with active projects. The reference-tier index is large; the system-tier budget is tight but manageable.

### Layout 4 — pathological

- L0 system blocks: 10 system-tier blocks totaling 8,000 chars. The renderer drops 4.
- L0 reference blocks: 200 reference-tier blocks. The index is 5,000 chars and dominates the system prompt.

This layout is broken. Too many system-tier blocks; too many reference-tier blocks. The operator should cull aggressively (`omh memory sync`) or migrate to a real database.

## Common mistakes

### Mistake 1 — Everything to system tier

The operator puts everything in system tier because "the agent needs it." The renderer drops half the blocks. The agent silently forgets half the facts. The operator never knows.

Fix: reference tier for everything except the meta-fact layer.

### Mistake 2 — Reference tier for facts needed every session

The operator puts the shell convention in reference tier "to save system tier budget." The agent forgets the convention and uses PowerShell when it should use Git Bash, or vice versa.

Fix: the few facts that are truly needed every session go in system tier. The reference-tier index is not a substitute.

### Mistake 3 — No L1 index

The operator puts a system-tier block in place and skips the L1 MEMORY.md pointer. The block renders every session, but if the operator needs to delete or edit the block, they have to remember its label. There is no visible record outside the system prompt.

Fix: every L0 block gets a one-line pointer in L1 MEMORY.md. The pointer is cheap.

### Mistake 4 — L1 index that duplicates block content

The operator puts the full block content in L1 MEMORY.md because "the agent needs to see it." This violates the index-only principle; the L1 budget is wasted on content that is already in L0.

Fix: L1 entries are pointers. They name the block label and one-line description. They do not repeat the content.

## The label naming convention

Block labels are filenames. Constraints (from `omh/memory_blocks.py`):

- 1–63 characters
- Lowercase letters, digits, `-`, `_`
- Must start alphanumeric

Recommended conventions:

- Use hyphens, not underscores: `windows-env-quirks`, not `windows_env_quirks`.
- Group related blocks with a common prefix: `cli-executors`, `cli-executors-routing`, `cli-executors-fallback`.
- Avoid generic names like `notes`, `block-1`, `temp`. The label is part of the index the agent sees; it should be self-describing.
- Date stamps belong in the description, not the label. A block is current until it is removed; the label should not go stale.

## What the agent sees in practice

A new session starts. The system prompt contains:

```
<hermes-built-in-memory>
  <memory:memory:0>...index entry...</memory:memory:0>
  <memory:profile:1>...user pointer...</memory:profile:1>
</hermes-built-in-memory>

<memory_blocks>
  <env-baseline>
    <description>Complete environment baseline injected every turn via system tier. Hosts, paths, CLI executors, WSL Kali workflow, OMH install state, codegraph integration, memory architecture.</description>
    <metadata>chars_current=3376 chars_limit=5800</metadata>
    <value>Host: Windows 10 host at C:\Users\Administrator\. Three shells in use...</value>
  </env-baseline>
  <user-workflow-preferences>
    <description>User workflow preferences + memory policy + update cadence. Injected every turn via system tier.</description>
    <metadata>chars_current=2016 chars_limit=5800</metadata>
    <value>User workflow preferences (set 2026-07-28, complete): Language: Chinese...</value>
  </user-workflow-preferences>
</memory_blocks>

<memory_block_index>
  <block label="windows-env-quirks" chars="914" limit="2500">Windows MSYS/Python/PATH gotchas. Read on demand before any Python venv work or file copy on Windows.</block>
  ...
</memory_block_index>

<omh_memory_tool_schema>...</omh_memory_tool_schema>
```

The agent sees the index, the system-tier blocks, and the tool schema. The reference-tier block values are one tool call away.

This is the dual-store architecture in action.