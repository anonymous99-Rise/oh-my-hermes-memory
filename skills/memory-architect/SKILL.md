---
name: memory-architect
description: Use when designing or auditing a Hermes Agent memory architecture. Decide which surface a fact belongs in (L1 MEMORY.md, L0 OMH project memory system/reference tier, or ~/.hermes/.env) and route the write accordingly.
version: 1.0.0
author: anonymous99-Rise
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [memory, architecture, dual-store, oh-my-hermes, routing, decision-tree]
    related_skills: [plan, requesting-code-review, systematic-debugging]
---

# Memory Architect

This skill is the agent-side entry point for the dual-store memory architecture described in the `oh-my-hermes-memory` project. It teaches the agent when to write to which surface and how to do it without violating the architecture's invariants.

Use it whenever the agent is about to:

- Capture a new memory candidate (operator-facing or self-driven)
- Read existing memory to answer a question
- Migrate an existing memory surface to the dual-store architecture
- Audit an existing setup for consistency

Do not use it for:

- General project planning (use `plan`)
- Bug investigations unrelated to memory (use `systematic-debugging`)
- Code review of non-memory code (use `requesting-code-review`)

## Overview

The architecture has three surfaces:

1. **`~/.hermes/.env`** — credentials and secrets only. Auto-loaded into `os.environ`. Referenced by env var name in every other surface.
2. **L1 Hermes memory tool** (`~/.hermes/memories/MEMORY.md` and `USER.md`) — short index pointers injected into every session's system prompt. Hard caps of 2,200 chars (MEMORY) and 1,375 chars (USER).
3. **L0 OMH project memory** (`~/.omh/memory/`) — durable storage for everything else. Subdivided into:
   - **Approved records** — atomic facts (≤240 chars after `_redact`), review-first approved by the operator.
   - **Reference-tier blocks** — long procedures, runbooks, environment notes. Listed by label in the system prompt; full value read on demand via `omh_memory(action="read", label=X)`.
   - **System-tier blocks** — content needed every session. Auto-injected under a 6,000-char render budget shared across all system-tier blocks.

The decision tree (described in detail in the references below) routes every fact to exactly one surface based on two questions:

1. Is this a credential?
2. Is it needed at the start of every session?

The agent never decides the tier autonomously. The agent captures or sets; the operator approves.

## When to Use

Triggers:

- The user says "remember this" or "remember that I prefer X."
- The user makes a decision worth remembering.
- The agent encounters a fact that will affect future behavior.
- The user asks "do you remember X?" and the agent wants to verify before answering.
- The user asks for a memory audit or migration plan.
- The user wants to add a credential to the system.
- The user wants to clean up memory.

Counter-triggers (use other skills):

- General planning: `plan`
- Bug investigation unrelated to memory: `systematic-debugging`
- Code review: `requesting-code-review`
- Workflow execution that has nothing to do with memory: `omh-idea-to-deploy`, `omh-build-failure-triage`, etc.

## Decision Tree (Summary)

The full decision tree is in [`references/03-decision-tree.md`](references/03-decision-tree.md). The summary:

```
Q0: Is this a credential?                    → ~/.hermes/.env (value)
                                                       L0 reference-tier block (workflow)
   Q1: Needed at start of every session?      → Q2
      Q2: Can the fact fit in ≤240 chars?     → L0 approved record
         Q4: Fits in 6000-char render budget?  → L0 system-tier block
                                                 Q5: Use reference-tier block
   Q3: One-off event or process log?          → do not store
```

The agent applies the tree by walking top to bottom. The first question whose answer is unambiguous determines the destination.

## The Five Invariants

The dual-store architecture has five invariants. The agent must respect all five; violating any one breaks the architecture.

### Invariant 1 — No information loss

Compression is never the answer to "I'm out of space." If a fact does not fit in the current surface, move it to a surface that does not have the size cap. Never shorten a fact to make it fit.

### Invariant 2 — No autonomous approval

Every L0 write (block-set, record capture) is a *candidate*. The candidate is not a record until the operator approves. Auto-approve requires explicit per-session user delegation; the default is review-first.

### Invariant 3 — No credentials in memory

Credential values live only in `~/.hermes/.env`. Memory surfaces reference credentials by env var name. The OMH safety layer aggressively redacts any summary containing `password`, `secret`, `token`, `private-key`, `api_key`, `apikey` substrings. Avoid these substrings even in non-credential contexts.

### Invariant 4 — No platform mixing

The dual-store architecture is for Hermes + OMH only. OpenClaw, custom log files, mnemosyne, and other systems have their own memory surfaces. Do not route facts across them. The boundary is what makes the audit story work.

### Invariant 5 — No silent truncation

OMH refuses to silently truncate block values that exceed `--limit` (`MemoryBlockError`). The agent catches the error, raises it to the operator, and lets the operator decide: raise the limit, split the block, or shorten the content. Do not catch and retry with a shorter value.

## Workflow

The agent applies this skill in five steps:

### Step 1 — Receive the fact

The agent is about to write a memory entry. The trigger can be:

- Operator intent ("remember this")
- Agent self-observation ("the operator prefers X; I should remember")
- Architectural decision ("we chose OMH because of Y")
- Lesson from a failure ("don't pipe credentials into su")

In every case, the agent pauses and asks: *what surface does this fact belong in?*

### Step 2 — Walk the decision tree

Apply [`references/03-decision-tree.md`](references/03-decision-tree.md). The first question (Q0: is this a credential?) is the most important. If the answer is yes, the fact routes to `.env` and a workflow entry to L0 reference tier.

### Step 3 — Capture or set

Based on the destination surface, the agent runs the appropriate command:

- `.env` value: tell the operator to append it; do not write it from chat.
- L0 reference-tier block: `omh memory block-set <label> --value "..." --tier reference --limit <cap>`
- L0 system-tier block: `omh memory block-set <label> --value "..." --tier system --limit <cap>` (verify render budget)
- L0 approved record: `omh memory capture --type <type> --tag <tag> --source <src> "<summary>"`

For full command syntax, see [`references/06-capture-approve.md`](references/06-capture-approve.md).

### Step 4 — Surface the candidate to the operator

The agent does not auto-approve. The agent presents the candidate to the operator in chat, with:

- The summary
- The destination tier
- The tags
- Any safety verdicts from OMH
- A request for explicit approval or rejection

The operator reviews the candidate and either approves (`omh memory approve <id>`) or rejects (`omh memory reject <id> --reason "..."`).

### Step 5 — Verify and report

After approval, the agent verifies the fact landed:

- For records: `omh memory status | grep approved`
- For blocks: `omh memory blocks | grep <label>`

The agent reports success to the operator in chat. If the candidate was rejected, the agent notes the rejection reason and adjusts future behavior.

## Common Pitfalls

### Pitfall 1 — Agent over-captures

The agent captures every preference, every decision, every observation. The operator's review queue grows. The agent gets fatigued.

Fix: walk the decision tree strictly. Only capture facts that are durable and needed.

### Pitfall 2 — Agent under-captures

The agent captures only what the operator explicitly says. Operator forgets to mention a preference; the agent never captures it; future sessions redo the work.

Fix: at the end of a long session, the agent offers a "what should we remember?" review. Capture the high-value facts.

### Pitfall 3 — Agent puts credentials in memory

The agent writes a credential value into a memory summary. OMH redacts it (good) or the agent bypasses the safety layer with a block value (bad).

Fix: always check Q0 first. If the fact is a credential, route to `.env`.

### Pitfall 4 — Agent tries to "fix" full L1 by compressing

The agent hits the 2,200-char L1 cap and starts compressing. Information is lost.

Fix: move the long content to an L0 reference-tier block. Leave a pointer in L1.

### Pitfall 5 — Agent bypasses operator approval

The agent sets `auto_approve_safe: true` or otherwise bypasses the review-first policy.

Fix: do not change the policy without explicit operator approval per session. The default is review-first; keep it that way.

### Pitfall 6 — Agent duplicates facts

The agent captures the same fact twice. Two records land in L0. The operator is confused.

Fix: before capture, recall or list existing records with similar tags. Skip duplicates.

## Verification Checklist

After any memory write, the agent verifies:

- [ ] The candidate or block landed where the agent intended.
- [ ] The operator was shown the candidate and approved or rejected it.
- [ ] The destination surface's cap was not exceeded.
- [ ] For system-tier blocks, the render budget was not exhausted.
- [ ] No credential values appear in any memory summary.
- [ ] The L1 MEMORY.md index entry points at the new block or record.
- [ ] No silent truncation occurred.

## Reference Material

This skill links to progressive-disclosure reference files. The agent loads them on demand, not all at once.

- [`references/01-when-to-use.md`](references/01-when-to-use.md) — detailed trigger and counter-trigger conditions.
- [`references/02-dual-store.md`](references/02-dual-store.md) — the three surfaces in detail.
- [`references/03-decision-tree.md`](references/03-decision-tree.md) — the full decision tree.
- [`references/04-credential-routing.md`](references/04-credential-routing.md) — credential handling in detail.
- [`references/05-block-tiers.md`](references/05-block-tiers.md) — system-tier vs reference-tier blocks.
- [`references/06-capture-approve.md`](references/06-capture-approve.md) — capture, review, approve, reject flow.
- [`references/07-real-cases.md`](references/07-real-cases.md) — six real-world worked examples.
- [`references/08-troubleshooting.md`](references/08-troubleshooting.md) — common failures and fixes.

The companion project at https://github.com/anonymous99-Rise/oh-my-hermes-memory contains the full `docs/` folder with the architecture in long form, plus templates, scripts, and examples.

## Runtime Evidence

The agent can confirm the architecture is intact by running:

```bash
python scripts/dual-store-status.py
```

The script reports:

- L1 MEMORY.md / USER.md char counts and headroom
- L0 candidate and approved record counts
- L0 block counts by tier, with chars vs limit
- `.env` credential names (not values) and which memory surfaces reference each

The script exits 0 if the architecture is healthy. Non-zero exit indicates an issue; see [`references/08-troubleshooting.md`](references/08-troubleshooting.md).

## One-Shot Recipes

### Recipe 1 — Operator says "remember I prefer concise responses"

```bash
# 1. Decide tier: needed every session, short atomic fact → L0 system-tier block
# 2. Capture
omh memory block-set user-style --value "User prefers concise responses with structured status updates; verbose paragraphs discouraged." --description "User response style preference." --limit 500 --tier system
# 3. Add a pointer in L1 MEMORY.md (via memory tool)
# 4. Verify
omh memory blocks | grep user-style
```

### Recipe 2 — Operator says "add the GitHub PAT to memory"

```bash
# 1. Decide tier: credential → ~/.hermes/.env ONLY. Do not write the value in chat.
# 2. Tell the operator
echo "Append the following to ~/.hermes/.env:
  GITHUB_TOKEN=<your-token-here>
Then add a memory entry that references the env var by name."
# 3. Operator adds the credential manually
# 4. Capture the workflow reference
omh memory block-set github-auth --value "GitHub authentication uses env var GITHUB_TOKEN; used for repo operations. To set: append GITHUB_TOKEN=<value> to ~/.hermes/.env. Never put the literal value in memory or chat." --description "GitHub PAT workflow." --limit 500 --tier reference
# 5. Add pointer in L1
```

### Recipe 3 — Agent encounters a credential in chat

```bash
# 1. Acknowledge without echoing the value
# "I see you've provided a credential. I'll reference it by env var name; please add the value to ~/.hermes/.env if it isn't already there."
# 2. Move credential reference to a block (no value)
omh memory block-set <service>-auth --value "Auth uses env var <KEY_NAME>; value lives in ~/.hermes/.env. Never put the literal value in memory or chat." --description "<service> auth workflow." --limit 500 --tier reference
# 3. Audit recent chat and session transcript for the literal value; if found, alert the operator to rotate the credential
```

### Recipe 4 — Operator asks "do you remember X?"

```bash
# 1. Search L1
hermes journey --json | python3 -c "
import json, sys
d = json.load(sys.stdin)
for e in d.get('memory', []):
    if 'X' in e['body'].lower():
        print(e['body'])
"
# 2. Search L0 reference-tier blocks by label
omh memory blocks | python3 -c "
import json, sys
d = json.load(sys.stdin)
for b in d.get('blocks', []):
    if 'X' in b.get('label', '').lower() or 'X' in b.get('description', '').lower():
        print(b['label'], '-', b['description'])
"
# 3. Read the relevant block on demand
cat ~/.omh/memory/blocks/reference/<label>.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d['value'])
"
# 4. Or recall L0 approved records
omh memory recall "X"
```

### Recipe 5 — End-of-session review

```bash
# The agent proposes memory candidates for the operator to approve
omh memory review --limit 10
# Operator approves or rejects each
omh memory approve <id>
omh memory reject <id> --reason "..."
```

## Catalog Metadata

```yaml
catalog:
  family: retained-knowledge
  subfamily: memory-architecture
  role: memory-keeper
  quality_tier: evidence-gated
  related_skills: [plan, requesting-code-review, systematic-debugging]
  external_resources:
    - https://github.com/anonymous99-Rise/oh-my-hermes-memory
  required_environment: [omh, hermes-agent, python3]
  optional_environment: [uv, git]
```

## Boundary

This skill does not:

- Read credential values. The agent reads env var names but never the values.
- Auto-approve memory writes. The operator approves.
- Migrate other systems (mnemosyne, Penfield, retaindb) automatically. Migration is operator-driven.
- Bypass the OMH safety layer. If a summary is redacted, the agent rewrites it.
- Modify OMH itself. The agent consumes OMH; it does not patch it (the operator may apply workarounds like the `plugin_pack.py:216` patch manually).
- Provide cross-device sync. The dual-store architecture is local-only by default.

This skill prepares and routes memory writes. The actual write happens through `omh memory capture`, `omh memory block-set`, the `memory` tool, or direct file edits to `~/.hermes/.env`. The skill does not perform these writes itself — it instructs the agent (or operator) on how to perform them.