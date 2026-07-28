# 06 — Capture and Approve Flow

This document is the operator's manual for the OMH review-first capture flow. Every approved record (the short-fact tier of L0) goes through this flow. Every operator who approves memory writes must understand it.

## The flow at a glance

```
operator (or agent) → omh memory capture → candidate → omh memory review → operator approves → omh memory approve → approved record → ~/.omh/memory/records/
                                                                          ↘ operator rejects → omh memory reject → no record
```

The agent can capture. The agent can review. The agent cannot approve. The operator is the gate.

## Capture

The capture step creates a candidate. Candidates live at `~/.omh/memory/candidates/<candidate_id>.json` until they are approved or rejected.

### Command

```bash
omh memory capture \
    --type {fact,decision,lesson,procedure,episode} \
    --content "<raw source text, hashed but not persisted>" \
    --tag <tag1> --tag <tag2> \
    --source <source-name> \
    --source-ref <reference> \
    [--stdin] \
    [--scope-kind {project,target,thread,run}] \
    [--scope-ref <scope-ref>] \
    [--ttl-days <int>] \
    [--stale-after-days <int>] \
    "<summary>"
```

### What goes in the summary

The summary is the only field that survives into the approved record. It is hard-capped at 240 chars (after `_redact`). It must be:

- Self-contained — a future agent with no other context must understand the fact from the summary alone
- Actionable — the agent must be able to use the fact to make a decision
- Free of credentials — no `password`, `secret`, `token`, `private-key`, `api_key`, `apikey` substrings (see [`04-credential-routing.md`](04-credential-routing.md))
- Free of the trigger substrings — use `authentication`, `credential`, `env var` instead

### What goes in the type

| Type | When to use |
|---|---|
| `fact` | A statement of reality: "the user prefers tabs over spaces" |
| `decision` | A choice that was made: "we picked OMH because of its review-first approval model" |
| `lesson` | Something learned from a failure or surprise: "do not pipe the credential value into su; the safety layer rejects it" |
| `procedure` | A repeatable sequence: "to install OMH on Windows, run A then B then C" (rarely used in memory — procedures belong in reference-tier blocks) |
| `episode` | An event log: "on 2026-07-28 the operator installed OMH and the doctor reported 30/30 ok" |

Most operator-driven captures are `fact` or `decision`. Lessons come from agent self-reports after failures. Episodes are the most ephemeral and are typically not written to memory at all.

### What goes in tags

Tags are how the operator and the agent find the record later. They should be:

- Specific enough to disambiguate (`memory-architecture`, not just `memory`)
- Stable (not `current-task` — that is session state)
- Lowercase, hyphenated

Examples of good tags:

```
memory-architecture
memory-policy
credential-routing
wsli-kali
omh-install
```

Examples of bad tags:

```
misc, things, notes
temp, current, today
memory1, fact2
```

### What goes in source and source-ref

- `source`: who or what produced the fact. Common values:
  - `user-2026-07-28` — the operator said this in chat
  - `agent-2026-07-28` — the agent observed this
  - `cli` — the operator ran an omh command and observed this
  - `external:<service-name>` — pulled from outside Hermes (rare)
- `source-ref`: a stable identifier for the source. Common values:
  - A date: `2026-07-28`
  - A session ID: `chat-2026-07-28-001`
  - A document path: `~/.omh/runtime/state.json`
  - A commit hash: `git rev-parse HEAD`
  - Empty string if there is no natural reference

The source-ref is not strictly required but is extremely useful for audit. If the operator ever needs to verify where a fact came from, the source-ref is the trail.

### What goes in scope

The scope determines which future sessions can recall the record:

- `scope-kind: project` (default) — global to the user's OMH home. Every session can recall.
- `scope-kind: target` — scoped to a specific Hermes target (e.g. `desktop`, `telegram`). Useful when the operator runs multiple Hermes surfaces and wants to partition memory.
- `scope-kind: thread` — scoped to a single conversation thread. Disappears when the thread ends.
- `scope-kind: run` — scoped to a single cron run. Most ephemeral.

For most operator-driven captures, the default `scope-kind: project` is correct.

### What goes in stale_after_days

Default is 90 days. After 90 days the record's `state` becomes `stale` in `omh memory status`. This is a hint, not a deletion.

Tune it:

- `--stale-after-days 30` for facts that change quickly (e.g. "current task is X")
- `--stale-after-days 365` for stable facts (e.g. "the operator's preferred shell is Git Bash")
- `--stale-after-days 0` to disable staleness (the record is permanent until explicitly rejected)

### Example capture

```bash
omh memory capture \
    --type fact \
    --tag credential-routing \
    --tag memory-policy \
    --source "user-2026-07-28" \
    --source-ref "omh-install-session" \
    --stale-after-days 365 \
    "WSL Kali authentication uses env var WSL_KALI_PWD for both user and root; never auto-invoke su root or pipe the value in scripts; always get explicit per-session consent first."
```

The summary is exactly 244 chars — over the 240-char limit. OMH will truncate it. The operator should rephrase to 240 chars or fewer, or move the content to a reference-tier block.

## Review

The review step is a read-only inspection of pending candidates. It produces review cards the operator can act on.

### Command

```bash
omh memory review [--candidate <candidate_id>] [--limit <int>]
```

Without flags, `review` returns up to 10 (default limit) pending candidates with their full summary, tags, type, source, scope, and staleness. With `--candidate`, it returns one specific candidate. With `--limit N`, it returns up to N.

### Output shape

Each candidate review card looks like:

```json
{
  "candidate_id": "cand_3ac915372a6bd2cb",
  "type": "fact",
  "summary": "OMH dual-store memory mechanism: L0 project memory lives at ~/.omh/memory/...",
  "tags": ["memory-mechanism", "dual-store"],
  "source": "agent-2026-07-28",
  "source_ref": "omh-install-session",
  "scope": {"kind": "project", "ref": "default"},
  "stale_after_days": 90,
  "created_at": "2026-07-28T07:46:11Z",
  "safety": {
    "safe_to_auto_approve": true,
    "review_reasons": [],
    "status": "safe"
  },
  "status": "pending_review"
}
```

The `safety` block is the OMH classifier's verdict:

- `safe_to_auto_approve: true` + `review_reasons: []` + `status: safe` — clean. Operator can approve.
- `safe_to_auto_approve: false` + `review_reasons: ["sensitive_credential_like_text"]` — OMH detected trigger substrings. Operator must rephrase or reject.
- `safe_to_auto_approve: false` + `review_reasons: ["long_content_requires_review"]` — the content is > 2,400 chars. Operator must split or move to a block.
- `safe_to_auto_approve: false` + `review_reasons: ["raw_log_or_traceback"]` — OMH detected what looks like a stack trace. Operator must rewrite as a fact, not paste a log.

The operator should treat every `review_reasons` as a hard stop. Do not approve a candidate that OMH has flagged.

## Approve

The approve step graduates a candidate to `~/.omh/memory/records/mem_<hash>.json`.

### Command

```bash
omh memory approve <candidate_id> [--approved-by <approver-name>]
```

The `--approved-by` defaults to `operator`. Operators should set it to a stable identifier (e.g. `user-2026-07-28`) for audit clarity.

### What approve does

1. Moves the candidate from `~/.omh/memory/candidates/` to `~/.omh/memory/records/`.
2. Sets `approved_at` to the current UTC time.
3. Sets `approved_by` to the value of `--approved-by`.
4. Generates a `record_id` (a content hash) that uniquely identifies the record.
5. Writes a review entry to `~/.omh/memory/reviews/`.
6. Rebuilds `~/.omh/memory/index.json`.

### What approve does NOT do

- It does not validate the summary. If the summary is bad, the operator already saw it in review.
- It does not deduplicate. Two candidates with identical summaries produce two approved records. The operator should reject one.
- It does not propagate the fact to other sessions. Other sessions see the record only when they `omh memory recall` it or when an L0 block index renders it.

## Reject

The reject step is for candidates that should not become records.

### Command

```bash
omh memory reject <candidate_id> [--rejected-by <rejecter-name>] [--reason "<reason text>"]
```

### What reject does

1. Marks the candidate as `status: "rejected"` in place (the file is not deleted; the audit trail is preserved).
2. Sets `rejected_at`, `rejected_by`, `rejection_reason`.
3. Writes a review entry to `~/.omh/memory/reviews/`.
4. Rebuilds the index.

Rejected candidates stay on disk in `~/.omh/memory/candidates/` indefinitely. They can be cleaned up with `omh memory reset` (operator-only, never run without explicit operator confirmation).

### When to reject

- The candidate is a duplicate of an existing record.
- The candidate is a one-off event that does not need durable storage.
- The candidate contains trigger substrings that the operator could not rephrase around.
- The candidate is a procedure that belongs as a reference-tier block.
- The candidate has the wrong type (operator meant `decision`, agent captured `fact`).

The operator should always provide a `--reason`. The reason becomes part of the audit trail and helps the agent understand what to do differently next time.

## Recall

The recall step is how a session retrieves approved records.

### Command

```bash
omh memory recall <query> [--limit N] [--include-stale] [--executor <label>] [--session-id <id>]
```

### How it works

`omh memory recall` uses deterministic keyword matching (not embeddings, not LLM call) to find records whose summary contains tokens from the query. The default `--limit` is 5. The match is case-insensitive and word-boundary-aware.

### Example

```bash
omh memory recall "memory policy credential"
```

Returns up to 5 records whose summaries contain `memory`, `policy`, or `credential` (after token normalization).

### When to use

The agent uses recall when:

- It encounters a task that touches a domain covered by an approved record (e.g. "memory policy" — recall the records tagged `memory-policy`)
- The operator asks "do you remember X?" and the agent wants to confirm before answering
- The agent is about to make a decision and wants to check past decisions on similar topics

The agent does not use recall when:

- The system-tier blocks already contain the relevant info
- The reference-tier blocks already contain the relevant info and have been read
- The fact is short enough to verify against the L1 MEMORY.md index

## Inspect

The inspect step is a read-only view of one record or candidate.

### Command

```bash
omh memory inspect <candidate_id>
```

Returns the full candidate or record JSON, including `content_ref` (hash and length of the source content), `created_at`, all metadata, and any safety flags.

### When to use

The operator uses inspect to:

- Verify a record landed correctly
- Check the source-ref trail
- Audit a record before deciding to reject it

## Block management

The capture/approve flow is for records. Block management has its own commands.

### block-set

```bash
omh memory block-set <label> \
    --value "<full text>" \
    --description "<one-line purpose>" \
    --limit <per-block cap> \
    --tier {system,reference}
```

Creates or replaces a block. The `--limit` defaults to 2,000. The `--tier` defaults to `system`.

If the value exceeds `--limit`, the command fails with `MemoryBlockError`. The operator must either shorten the value, raise the limit, or split into multiple blocks.

### block-remove

```bash
omh memory block-remove <label> --tier {system,reference}
```

Removes a block. The label and tier must match an existing block. If they do not match, the command fails.

Note: the default tier for `block-remove` is `system`, but if the block was created at `reference` tier, the command must specify `--tier reference`. Mismatch is a common operator mistake.

### blocks (list)

```bash
omh memory blocks [--tier {system,reference}]
```

Lists blocks. Without `--tier`, returns both tiers. With `--tier`, filters.

The output is JSON with each block's label, tier, chars, limit, headroom_chars, and over_limit.

## Provider

The provider subsystem is for operators who want to back OMH project memory with an external store (e.g. cloud sync, SQLite + sqlite-vec, mnemosyne). It is not used in the default local-only setup.

```bash
omh memory provider --help
omh memory provider status
omh memory provider switch <backend-name>
```

For the dual-store architecture, the default `local_json` backend is sufficient. Operators should only switch providers when they have a concrete need (multi-device sync, search beyond keyword matching, archival).

## Dream

The dream subsystem is OMH's memory consolidation. It runs nightly (or on demand) to merge related records, mark duplicates, and propose promotions from reference to system tier.

```bash
omh memory dream --help
```

Operators should not run dream manually unless they have read the consolidation logic. Default behavior is to schedule dream via OMH's internal cron.

## Status

The status command is the operator's dashboard.

```bash
omh memory status [--json]
```

Returns:

- `counts`: candidates, approved_records, pending_review, review_records, stale
- `policy`: mode, backend, review_required, auto_approve_safe, store_dir
- `store`: memory_dir, candidate_dir, record_dir, review_dir
- `hermes_memory`: comparison of Hermes memory files against OMH records (which facts are in Hermes but not OMH, and vice versa)

Operators should check status weekly. Red flags:

- `candidates > 50`: review backlog is too large. Cull stale candidates.
- `approved_records > 500`: scope creep. Consider migrating to a real database.
- `auto_approve_safe: true`: someone flipped the policy. Verify it was intentional.
- `mode` not equal to `review-first`: someone changed the policy. Verify.

## Backup and restore

OMH does not have a built-in backup command. The operator's backup strategy is:

```bash
# Backup
tar czf omh-memory-backup-$(date +%Y-%m-%d).tar.gz ~/.omh/memory/

# Restore
tar xzf omh-memory-backup-2026-07-28.tar.gz -C /
```

The `~/.omh/memory/` directory is self-contained. Back it up before any major operation (e.g. OMH upgrade, manual edits to `index.json`).

## What the agent should do during the flow

The agent:

- Captures facts it wants to remember (with `--source "agent-2026-07-28"`).
- Reviews candidates it captured (read-only inspection).
- Cannot approve its own captures.
- Can recall records it needs at runtime.
- Should propose captures to the operator via chat when the operator expresses a preference or makes a decision worth remembering.

The agent:

- Does not capture silently. Every capture should be visible to the operator.
- Does not approve its own captures. Even if `auto_approve_safe: true` is set, the agent should still surface what it auto-approved.
- Does not delete candidates or records. The operator decides.

## Failure modes and recovery

### "My capture is redacted to [redacted]"

OMH detected trigger substrings. Rewrite the summary to avoid `password`, `secret`, `token`, `private-key`, `api_key`, `apikey`. See [`04-credential-routing.md`](04-credential-routing.md) for substitutions.

### "My capture was truncated to 240 chars"

The summary is too long. Either rephrase in fewer chars, or move the content to a reference-tier block.

### "My block-set fails with 'is X chars against a Y-char limit'"

The block value exceeds `--limit`. Either raise `--limit`, shorten the value, or split into multiple blocks.

### "My approved record is missing from session recall"

Recall uses keyword matching. The record's summary may not contain the tokens the agent searched for. Try a different query. If the record is critical, add a pointer in L1 MEMORY.md or in a system-tier block.

### "My system-tier block does not render"

The 6,000-char render budget is exhausted. Run `omh memory blocks --tier system` to see which block was dropped. Move it to reference tier or compress existing blocks.