# 02 — Decision Tree

This document is the routing rule. Every durable fact the agent wants to remember goes through the questions in this file. The output is exactly one of the surfaces defined in [`01-architecture-overview.md`](01-architecture-overview.md): `~/.hermes/.env`, L1 `MEMORY.md` index entry, L0 system-tier block, L0 reference-tier block, L0 approved record, or *do not store at all*.

The tree is ordered. Walk it top to bottom. The first question whose answer is unambiguous tells you where the fact lands. Do not skip questions; do not reorder them.

## The tree at a glance

```
                ┌─────────────────────────────────┐
                │ Q0: Is this a credential?       │
                └─────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              │ yes                   │ no
              ▼                       ▼
       ┌──────────────┐         ┌──────────────────────────┐
       │ ~/.hermes/   │         │ Q1: Is it needed every    │
       │ .env ONLY    │         │     session?              │
       │ (never mem)  │         └──────────────────────────┘
       └──────────────┘                   │
                              ┌──────────┴──────────┐
                              │ yes                  │ no
                              ▼                      ▼
                    ┌───────────────────┐    ┌──────────────────────────────┐
                    │ Q2: Can the fact   │    │ Q3: Is it a one-off event    │
                    │ fit in ≤240 chars?│    │     or process log?          │
                    └───────────────────┘    └──────────────────────────────┘
                              │                            │
                  ┌───────────┴────────┐                   ▼
                  │ yes                │ no           ┌──────────┐
                  ▼                    ▼             │  Do not  │
          ┌────────────────┐  ┌──────────────┐       │  store.  │
          │ L0 approved    │  │ Q4: Does it  │       │ Use      │
          │ record (with   │  │ fit in ≤6000 │       │ session_ │
          │ L1 pointer)    │  │ chars total  │       │ search.  │
          └────────────────┘  │ render budget│       └──────────┘
                              │ across all   │
                              │ system tier  │      (terminal node)
                              │ blocks?      │
                              └──────────────┘
                                  │
                      ┌───────────┴───────────┐
                      │ yes                   │ no
                      ▼                       ▼
              ┌──────────────────┐    ┌──────────────────┐
              │ L0 system-tier   │    │ L0 reference-    │
              │ block (with L1   │    │ tier block (with │
              │ pointer to its   │    │ L1 pointer to    │
              │ label)           │    │ its label)       │
              └──────────────────┘    └──────────────────┘
```

Each question, in detail, below.

## Q0 — Is this a credential?

A credential is any value that, if disclosed to a third party, lets them impersonate the user or break into a system the user controls. Concretely:

- Passwords (account passwords, server passwords, root passwords)
- API keys (OpenAI, Anthropic, GitHub, etc.)
- OAuth tokens and refresh tokens
- SSH passphrases and private keys
- Database connection strings that embed credentials
- Webhook secrets
- Encryption keys

If the answer is *yes*, the fact lands in `~/.hermes/.env`. Stop here. Do not write the literal value anywhere else.

The fact that the credential *exists* — the username, the service it grants access to, the path to the env var that holds it — is *not itself a credential*. That meta-fact can be written to memory as long as the literal value is not. See [`04-credential-routing.md`](04-credential-routing.md) for the exact convention.

If the answer is *no*, continue to Q1.

## Q1 — Is it needed at the start of every session?

This is a frequency question, not a content question. The answer is *yes* if:

- The fact affects how the agent should *greet* the user (e.g. preferred language, preferred response style, user name)
- The fact affects how the agent should *route* requests (e.g. which shell to use, which CLI executors are authorized, which tool is the default)
- The fact affects how the agent should *behave* without prompting (e.g. "do not auto-approve memory", "use Chinese", "credential reference convention is `${VAR_NAME}`")

If the answer is *yes*, the fact belongs in a surface that is auto-injected. Continue to Q2.

If the answer is *no*, continue to Q3.

## Q2 — Can the fact fit in ≤240 chars (summary form)?

This is the L0 approved record hard cap. `_redact` in `omh/workflows/memory.py` enforces this. A fact that is needed every session but is longer than 240 chars should not be an approved record — it would be silently truncated, and the truncated version would be all the agent ever sees.

If the answer is *yes*, the fact lands as an L0 approved record. The capture flow is:

1. `omh memory capture --type <fact|decision|lesson|procedure|episode> --tag <tag1> --tag <tag2> --source <source> --source-ref <ref> "<summary>"` — the summary must be the *complete fact* in ≤240 chars. If you cannot write it in 240 chars, the answer to Q2 was actually *no*.
2. `omh memory review --candidate <candidate_id>` — review the candidate, check the summary reads correctly, check the tags and scope make sense.
3. `omh memory approve <candidate_id> --approved-by <operator-name>` — the operator (user) approves.
4. Add a pointer to the record's `candidate_id` in L1 MEMORY.md if the record is referenced often enough that the operator wants it indexed.

If the answer is *no*, continue to Q4.

### Why this is the right cap, even when 240 feels small

The 240-char cap is real because `_redact(value)` returns `value[:240]` for non-sensitive content and `"[redacted]"` for content that contains `secret`, `token`, `password`, `private-key`, `api_key`, or `apikey` substrings. There is no setting that raises it. There is no `omh memory capture --no-truncate` flag.

If you find yourself wanting to write a 300-character record, that is a signal that the fact is not a short atomic fact. It is a piece of a longer story. Put the longer story in a block (Q4 path) and reference the block from a 240-char record.

## Q3 — Is it a one-off event or process log?

This is the "do not store" check. Many facts the agent considers for memory are actually ephemeral:

- "I just ran `git push` and it succeeded" — that is a transient state, not a durable fact
- "The user said `hello` in the last message" — that is the conversation transcript, not a memory
- "Today's date is 2026-07-28" — that is the current date, not a fact to remember
- "I am currently in the middle of editing `main.py`" — that is working state, not a memory

If the answer is *yes*, do not write to any surface. The fact is either discoverable from the session transcript (`session_search` exists for exactly this purpose) or it is not durable at all.

If the answer is *no* (the fact is durable but not needed every session), continue to Q4.

### Why "do not store" is a legitimate answer

The agent's instinct is to capture everything. This is wrong for two reasons:

1. **Storage growth without information value.** Every fact added is a fact that must be searched later. Searching is cheap; reading irrelevant facts is expensive in attention.
2. **Approval fatigue.** Every capture creates a review queue entry. If the operator is asked to approve 50 facts a day, the operator stops paying attention. The review-first safety model breaks down.

If the fact is not durable, do not write it. If the fact is durable but rarely needed, write it as a reference-tier block (Q4 no-branch).

## Q4 — Does it fit in the 6,000-char system-tier render budget across all system-tier blocks?

System-tier blocks are auto-injected every turn. The renderer (`omh/memory_blocks.py` `render_memory_blocks`) has a 6,000-char budget across all system-tier blocks combined. If the new fact would push the total over 6,000 chars, the new block is dropped, not truncated.

If the answer is *yes* (the new fact + all existing system-tier block chars ≤ 6,000), the fact lands as a new system-tier block. The block-set flow is:

1. `omh memory block-set <label> --value "<full text>" --description "<one-line purpose>" --limit <per-block cap, e.g. 5800> --tier system` — the value must be the *complete fact* with no truncation. If `--limit` would be exceeded, OMH raises an error rather than silently truncating.
2. Verify the block landed: `omh memory blocks --tier system`.
3. Add a pointer to the block's label in L1 MEMORY.md so the operator can find it.

If the answer is *no* (the budget is exhausted or the fact itself is > 5,800 chars), continue to Q5.

### Why system-tier is not "just bigger L1"

L1 MEMORY.md is injected verbatim by Hermes. L0 system-tier blocks are injected by OMH via XML-ish wrapper elements. They have different shapes, different audit stories, different curation tools.

| Concern | L1 MEMORY.md | L0 system-tier block |
|---|---|---|
| Injected by | Hermes memory provider | OMH memory provider |
| Schema | plain markdown | `<memory_blocks>` XML-ish wrapper |
| Curation tool | `hermes journey` | `omh memory block-set / block-remove` |
| UseCount tracking | Yes (Hermes graph) | No |
| Pin / unpin | Yes | No |
| Cap | 2,200 chars per entry | 2,000 chars per block; 6,000 chars total budget |

Use L0 system-tier for content that needs OMH's curation tools or that pairs naturally with other OMH artifacts (e.g. you have a reference-tier block on the same topic, and you want both blocks to live in one place). Use L1 MEMORY.md for content that benefits from Hermes's `useCount` tracking and the `hermes journey` interface.

## Q5 — Use a reference-tier block

The fact lands as a reference-tier block. The block-set flow is:

1. `omh memory block-set <label> --value "<full text>" --description "<one-line purpose>" --limit <per-block cap, typically 2000–5000> --tier reference` — the value must be the *complete fact*.
2. Verify: `omh memory blocks --tier reference`.
3. Add a pointer to the block's label in L1 MEMORY.md if the operator wants the block to be findable from the L1 index.

Reference-tier blocks are the workhorse of the dual-store architecture. They hold the long procedures, the environment notes, the troubleshooting runbooks, the credential workflow details — every fact that is durable but is not needed every session.

### When the per-block limit is itself the constraint

The default `--limit` is 2,000 chars. For a long procedure, raise it. The OMH CLI accepts any positive integer, but in practice the per-block file gets unwieldy past ~5,000 chars. For content longer than 5,000 chars, split into two reference-tier blocks with related labels (e.g. `windows-env-quirks-python` and `windows-env-quirks-shell`).

## What about pinning?

Hermes memory nodes have a `pinned` field. Pinned nodes do not decay in `useCount` ranking. OMH blocks do not have a pinning mechanism in the current CLI surface. If the operator wants a reference-tier block to be prominent, the workaround is:

1. Keep a system-tier block that lists the reference-tier block's label and a one-line purpose. The agent sees the system-tier block every turn and is more likely to consult the reference-tier block.

This is what the canonical `env-baseline` system-tier block does: it lists the labels of `windows-env-quirks`, `wsl-kali-workflow`, `cli-executors`, `omh-install-state`, and `codegraph-integration` reference-tier blocks with one-line descriptions. The agent sees the list every turn and knows where to look.

## What about overlapping blocks?

It is fine to have multiple blocks that reference the same fact from different angles. Example:

- A `wsl-kali-workflow` reference-tier block holds the full procedure for using WSL Kali.
- The `env-baseline` system-tier block mentions WSL Kali at a high level.

Both are correct. The reference-tier block has the detail; the system-tier block has the pointer. The operator should not feel pressure to deduplicate aggressively. Storage is cheap; recall confusion is expensive.

## What about stale facts?

OMH approved records carry a `staleness` field with `stale_after_days: 90` by default. After 90 days the record's `state` becomes `stale` in `omh memory status`. This is a hint, not a deletion.

Reference-tier and system-tier blocks do not have an automatic staleness mechanism. The operator is expected to `omh memory block-remove` a block when the fact is no longer true. To find candidates for removal:

```bash
omh memory status --json | python -c "
import json, sys
d = json.load(sys.stdin)
records = d.get('counts', {})
print('candidates:', records.get('candidates', 0))
print('approved:', records.get('approved_records', 0))
print('stale:', records.get('stale', 0))
"
```

Then `omh memory inspect <candidate_id>` to read the candidate and `omh memory reject <candidate_id>` if it should be removed.

## What if I want to migrate an existing flat-memory file?

See [`09-migration-guide.md`](09-migration-guide.md). The short version: do not try to convert in place. Read the existing MEMORY.md / USER.md, classify each line by this decision tree, and place each line in its correct tier as a fresh write.

## Quick reference: surface selection

| Fact type | Surface |
|---|---|
| Password, API key, OAuth token | `~/.hermes/.env` only |
| Username, service name, env var name (the credential's *meta*) | L0 reference-tier block or L0 approved record (no value) |
| Language, response style, user name | L0 system-tier block (small) or L1 USER.md |
| Shell convention, CLI executors, host baseline | L0 system-tier block (large) |
| Routing policy ("claude for short, codex for long") | L0 system-tier block |
| Memory policy ("review-first, no auto-approve") | L0 system-tier block |
| Environment quirk procedure ("Windows MSYS caveat") | L0 reference-tier block |
| Troubleshooting runbook ("if `omh doctor` shows X, run Y") | L0 reference-tier block |
| Atomic fact ("the user prefers tabs over spaces") | L0 approved record (≤ 240 chars) |
| Decision rationale ("we picked OMH because it has review-first") | L0 approved record |
| Working state ("I am editing file X right now") | Do not store |
| Today's date, current time | Do not store |
| Session-local output ("just printed 50 lines of log") | Do not store |

## Decision tree in script form

For automation, see [`scripts/route-fact.py`](../scripts/route-fact.py). The script implements this tree and prints the suggested command. It does not execute the command — the operator still has to approve.