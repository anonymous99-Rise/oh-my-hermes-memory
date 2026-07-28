# 05 — Block Tiers (Reference)

This reference is the agent-side expansion of [`docs/05-omh-block-tiers.md`](../../docs/05-omh-block-tiers.md). The main docs document explains the system tier and reference tier; this reference explains how the agent decides which tier a fact belongs in.

## Tier comparison

| | System tier | Reference tier |
|---|---|---|
| Rendered into system prompt | Yes, always | No (listed by label only) |
| Reading mechanism | implicit (agent sees it) | explicit (agent calls `omh_memory(action="read", label=X)`) |
| Render budget | 6,000 chars shared across all system-tier blocks | n/a |
| Per-block limit | `--limit`, typically 2,000-5,800 | `--limit`, typically 2,000-5,000 |
| Operator visibility | every session | on-demand |
| Use for | stable meta-facts, env baseline, user preferences, memory architecture itself | long procedures, runbooks, environment quirks, troubleshooting |

## When the agent should write to system tier

The agent writes to system tier when:

1. The fact is needed at the start of every session (Q1 of the decision tree = yes).
2. The fact is short enough that the 6,000-char render budget can absorb it.
3. The fact is stable (unlikely to change in the next 30 days).
4. The fact has meta-quality: it is about the architecture itself, the user's preferences, or the environment baseline.

Examples of facts that should be in system tier:

- "User communicates in Chinese; respond in Chinese unless switched."
- "Linux operations default to WSL Kali. Authentication via env var WSL_KALI_PWD."
- "Shell routing: Git Bash for POSIX, PowerShell for native Windows."
- "Memory architecture: dual-store; L1 index, L0 OMH project memory, .env credentials."

Examples of facts that should NOT be in system tier:

- A 3,000-char troubleshooting runbook (too long).
- A specific install command (rarely needed, easy to find in scripts).
- A recent architectural decision (the operator may want to reverse it; better as reference).

## When the agent should write to reference tier

The agent writes to reference tier when:

1. The fact is durable (will be relevant for more than 7 days).
2. The fact is longer than 240 chars.
3. The fact is needed occasionally, not every session.
4. The fact is operational (about a specific tool, runbook, or environment).

Examples:

- "Windows MSYS quirks: (1) python3 shim issue, (2) write_text CRLF injection, (3) cmd //c pattern breaks..."
- "WSL Kali workflow including the credential reference."
- "OMH install state: omh-install v1.0.3, plugin at ~/.hermes/plugins/omh, known bug at plugin_pack.py:216."
- "codegraph 1.5.0 install + 3-runtime MCP integration."

## What the agent does at runtime

When the agent is operating:

1. System-tier blocks are part of the system prompt. The agent reads them as if they were any other context.
2. Reference-tier blocks are not in the system prompt. The agent knows they exist (from the index) but must explicitly read them when needed.

The agent should:

- Treat system-tier blocks as "always true."
- Treat reference-tier blocks as "true if I read them; otherwise I do not know."

## The render budget constraint

The 6,000-char system-tier render budget is shared across all system-tier blocks. If the budget is exhausted, additional blocks are silently dropped.

The agent should:

1. Before writing a new system-tier block, check the running total: `omh memory blocks --tier system`.
2. If the running total + new fact's chars > 6,000, route to reference tier.
3. Do not attempt to bypass the budget by setting `--limit` higher on a system-tier block. The renderer uses the budget constant, not the block's limit.

## The index-of-reference-tier-blocks constraint

Reference-tier blocks are listed by label in the system prompt via `<memory_block_index>`. The index size is `sum of label + description + metadata chars per block`. If the operator has hundreds of reference-tier blocks, the index becomes large.

The agent should:

1. Run `omh memory blocks --tier reference` periodically to see the count.
2. If the count is high (> 50), consider culling or grouping related blocks.

## Mixed-tier layouts in practice

### Layout 1 — minimal

- L1 MEMORY.md: ~1,200 chars. Points to env-baseline block.
- L0 system blocks: env-baseline (3,000 chars).
- L0 reference blocks: none.
- L0 approved records: 3 atomic facts.

For a new operator. Most content lives in env-baseline; only truly atomic facts are separate records.

### Layout 2 — typical

- L1 MEMORY.md: ~1,200 chars. Points to env-baseline + 5 reference block labels.
- L0 system blocks: env-baseline (3,000 chars) + user-workflow-preferences (2,000 chars).
- L0 reference blocks: 5-10 long procedures (each 1,000-5,000 chars).
- L0 approved records: 5-10 atomic facts.

For an operator with a few months of usage.

### Layout 3 — heavy

- L1 MEMORY.md: ~1,500 chars. Points to env-baseline + 20 reference block labels.
- L0 system blocks: env-baseline (3,500 chars) + user-workflow-preferences (2,500 chars).
- L0 reference blocks: 20-50 long procedures.
- L0 approved records: 30-50 atomic facts.

For a power operator with active projects.

### Layout 4 — pathological

- L0 system blocks: 10 system-tier blocks totaling 8,000 chars. The renderer drops 4.
- L0 reference blocks: 200 reference-tier blocks. The index is 5,000 chars.

This is broken. Cull aggressively or migrate to a real database.

## Common agent mistakes

### Mistake 1 — Putting everything in system tier

The agent decides that every fact is "important" and puts it in system tier. The render budget exhausts. Half the facts are silently dropped.

Fix: default to reference tier. Promote to system tier only when the fact is truly needed every session.

### Mistake 2 — Putting nothing in system tier

The agent is conservative and puts everything in reference tier. The agent has to read blocks on every relevant turn, which is slow.

Fix: keep at least env-baseline and user-workflow-preferences in system tier. They are needed every session.

### Mistake 3 — No L1 index

The agent writes system-tier blocks but does not update L1 MEMORY.md. The operator has no external record of the block labels.

Fix: every system-tier block gets a one-line pointer in L1 MEMORY.md.

### Mistake 4 — L1 index that duplicates block content

The agent writes the full block content in L1 MEMORY.md "to be safe." This violates the index-only principle.

Fix: L1 entries are pointers. They name the block label and one-line description.

## What the agent does at block-write time

1. Decide tier (system or reference) per the rules above.
2. Check the render budget if writing system tier.
3. Run `omh memory block-set <label> --value "..." --description "..." --limit <cap> --tier <system|reference>`.
4. Verify the block landed: `omh memory blocks`.
5. Surface the write to the operator.
6. Update L1 MEMORY.md if the block is referenced often.

The agent does not need operator approval for a block write (unlike an approved record). Block writes are synchronous and operator-visible via `omh memory blocks`. The operator can `omh memory block-remove` if they want to undo.

## What the agent does at block-read time

### Reading system-tier blocks

The agent does not need to do anything special. The block content is part of the system prompt.

### Reading reference-tier blocks

The agent calls `omh_memory(action="read", label="<label>")` via the MCP tool. This returns the block's full value.

Alternatively, the agent can `cat ~/.omh/memory/blocks/reference/<label>.json` via the terminal tool (if the operator has approved shell access).

The agent reads a reference-tier block when:

- The block's label matches the current task.
- The block's description matches the current task.
- The L1 index points to the block.
- The operator explicitly asks for the block's content.

The agent does not read a reference-tier block when:

- The task does not match the block's label or description.
- The block is already in the system prompt (i.e. it is a system-tier block).
- The agent is operating under tight token budget and the block is unlikely to be needed.

## Promoting a reference-tier block to system tier

Sometimes the agent realizes a reference-tier block is needed every session after all (e.g. the agent has read it 10 times in the last week). The agent can promote it:

```bash
# 1. Read the current block
cat ~/.omh/memory/blocks/reference/<label>.json

# 2. Re-write at system tier
omh memory block-set <label> --value "<current value>" --description "<current>" --limit <cap> --tier system

# 3. Verify the render budget is not exhausted
omh memory blocks --tier system

# 4. Remove the reference-tier version
omh memory block-remove <label> --tier reference
```

The agent surfaces the promotion to the operator.

## Demoting a system-tier block to reference tier

The reverse operation:

```bash
# 1. Re-write at reference tier
omh memory block-set <label> --value "<current value>" --description "<current>" --limit <cap> --tier reference

# 2. Remove the system-tier version
omh memory block-remove <label> --tier system

# 3. Verify
omh memory blocks
```

The agent surfaces the demotion to the operator.

## Summary

- System tier: small, stable, needed every session.
- Reference tier: long, durable, needed occasionally.
- The agent decides the tier based on the rules above.
- The agent verifies the render budget before writing to system tier.
- The agent updates L1 MEMORY.md when a new block is referenced.