# 06 — Capture and Approve (Reference)

This reference is the agent-side expansion of [`docs/06-capture-approve-flow.md`](../../docs/06-capture-approve-flow.md). The main docs document explains the operator's view; this reference explains the agent's view.

## The agent's role in the flow

The agent:

1. Captures candidates (via `omh memory capture`).
2. Reviews candidates (via `omh memory review`).
3. Does NOT approve candidates. The operator does.
4. Recalls records (via `omh memory recall`).
5. Inspects records (via `omh memory inspect`).

The agent surfaces every action to the operator in chat. The agent waits for explicit operator approval before considering a candidate an approved record.

## Capture step (agent's actions)

### When the agent captures

The agent captures when:

- The operator says "remember this" or equivalent.
- The agent self-observes a durable pattern.
- An architectural decision is made.
- A lesson from a failure is worth remembering.

In each case, the agent walks the decision tree (see [`03-decision-tree.md`](03-decision-tree.md)) and routes the fact to the appropriate surface. For atomic facts, the agent captures via `omh memory capture`. For longer content, the agent uses `omh memory block-set` (no review needed).

### What the agent puts in the summary

The agent must produce a summary that:

- Fits in 240 chars (after `_redact`).
- Is self-contained (a future agent with no other context can understand the fact).
- Avoids trigger substrings (`password`, `secret`, `token`, `private-key`, `api_key`, `apikey`).
- Is in the user's preferred language (Chinese in the canonical setup).

The agent rewrites the summary until it meets these criteria. If the fact cannot be expressed in 240 chars, the agent routes to a block instead.

### What the agent puts in the metadata

- `--type`: `fact`, `decision`, `lesson`, `procedure`, or `episode`.
- `--tag`: one or more stable, hyphenated tags.
- `--source`: who or what produced the fact (e.g. `user-2026-07-28`, `agent-2026-07-28`).
- `--source-ref`: a stable identifier for the source (e.g. a date, a session ID).
- `--scope-kind`: default `project`.
- `--stale-after-days`: default 90. Override for facts that change quickly.

### Example capture

```bash
omh memory capture \
    --type fact \
    --tag memory-architecture \
    --tag dual-store \
    --source "user-2026-07-28" \
    --source-ref "omh-install-session" \
    --stale-after-days 365 \
    "OMH dual-store memory: L0 project memory at ~/.omh/memory/ holds complete text; L1 (MEMORY.md/USER.md) holds index only. L0 long facts via block-set --tier reference; short atomic via capture → review → approve. Credentials in ~/.hermes/.env, never in memory."
```

The agent gets back a candidate_id.

### What the agent does after capture

The agent surfaces the candidate to the operator in chat:

> "I've captured a fact for review:
> - Type: fact
> - Tags: memory-architecture, dual-store
> - Summary: `OMH dual-store memory: ...`
> - Source: user-2026-07-28
> - Candidate ID: `cand_xxx`
>
> Run `omh memory review cand_xxx` to inspect, then `omh memory approve cand_xxx` or `omh memory reject cand_xxx --reason '...'`."

The agent waits for the operator's decision. The agent does NOT consider the fact approved until the operator runs `omh memory approve`.

## Review step (agent's actions)

### When the agent reviews

The agent reviews candidates:

- Before surfacing them to the operator (sanity check).
- When the operator asks "show me pending memory writes."
- When checking the capture queue length.

### What the agent checks

For each candidate, the agent inspects:

1. `summary` — does it accurately convey the fact? Does it avoid trigger substrings? Is it under 240 chars (which is automatic, but worth checking)?
2. `type` — is the type appropriate? (E.g. `decision` for a decision, `lesson` for a lesson.)
3. `tags` — are the tags useful for future search?
4. `source` and `source-ref` — are they sufficient for audit?
5. `scope` — is the scope right? (Default `project` is usually correct.)
6. `safety` — what does OMH's classifier say? Any `review_reasons`?

If any check fails, the agent surfaces the issue to the operator before the operator approves:

> "I reviewed the candidate `cand_xxx`:
> - Summary looks good.
> - Type is appropriate.
> - Tags could be more specific; suggest `memory-architecture` and `oh-my-hermes`.
> - Source is correct.
> - Safety verdict: `safe_to_auto_approve: true`, no review reasons.
>
> Run `omh memory approve cand_xxx` if you want to land it, or `omh memory reject cand_xxx --reason '...'` if not."

## Approval step (operator's actions; agent waits)

The agent does not approve. The operator does, via `omh memory approve <id>`.

The agent waits for the operator's decision. If the operator approves, the agent verifies the record landed:

```bash
omh memory status --json | grep approved_records
```

If the operator rejects, the agent notes the rejection reason and adjusts:

```bash
# Agent logs the rejection
echo "Candidate cand_xxx rejected with reason: '<reason>'" >> /tmp/agent-memory-log
```

The agent does not retry the rejected candidate. The agent may capture a new candidate with a different summary if the operator's reason suggests a rephrasing.

## Reject step (operator's actions; agent waits)

When the operator rejects, the agent:

1. Reads the rejection reason (`omh memory review --candidate <id>` or `cat ~/.omh/memory/candidates/cand_<id>.json`).
2. Learns from the reason. If the reason is "wrong tier", the agent captures to a different tier next time. If the reason is "duplicate", the agent checks for duplicates before capturing next time.
3. Does not silently re-capture. The operator's rejection is a signal that needs to be respected.

## Recall step (agent's actions)

### When the agent recalls

The agent recalls when:

- It needs a fact that is in an L0 approved record (not in a system-tier block).
- The operator asks "do you remember X?"
- The agent is about to make a decision and wants to check past decisions on similar topics.

### How the agent recalls

```bash
omh memory recall "<query>" --limit 5
```

The query is a space-separated list of keywords. OMH does deterministic keyword matching; no LLM call.

### Example

```bash
omh memory recall "credential routing"
```

Returns up to 5 approved records whose summaries contain `credential` or `routing` (after token normalization).

### What the agent does with the result

The agent reads each returned record's summary and incorporates it into its reasoning. The agent may read the full record via `omh memory inspect <id>` if the summary is insufficient.

The agent cites the record by candidate_id or record_id when using its content:

> "Per the approved record `mem_xxxxx` (captured 2026-07-28): the WSL Kali credential lives in `~/.hermes/.env` as `WSL_KALI_PWD`..."

## Inspect step (agent's actions)

### When the agent inspects

The agent inspects when:

- It needs the full record (not just the summary).
- It is auditing a memory surface.
- It is debugging a memory-related issue.

### How the agent inspects

```bash
omh memory inspect <candidate_id>
# Returns the full candidate or record JSON.
```

The agent reads the `summary`, `tags`, `source`, `scope`, `staleness`, and `safety` fields. The agent does not write to the record during inspection; inspect is read-only.

## Block write step (agent's actions)

For long content, the agent uses `omh memory block-set` directly. This does not require operator approval.

```bash
omh memory block-set <label> \
    --value "<full content>" \
    --description "<one-line purpose>" \
    --limit <per-block cap> \
    --tier {system,reference}
```

The agent:

1. Chooses the tier per [`05-block-tiers.md`](05-block-tiers.md).
2. Sets the limit based on the content length.
3. Verifies the render budget if writing system tier.
4. Surfaces the write to the operator.
5. Updates L1 MEMORY.md if the block is referenced often.

## Block read step (agent's actions)

### When the agent reads a block

- The agent is working on a task that matches the block's label or description.
- The L1 index points to the block.
- The operator explicitly asks for the block's content.

### How the agent reads a block

```bash
# Via the OMH MCP tool
omh_memory(action="read", label="<label>")

# Or via the terminal
cat ~/.omh/memory/blocks/<tier>/<label>.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(d['value'])
"
```

The agent uses the block content in its reasoning.

## Capture queue management

### When the queue grows

If `omh memory status` shows `candidates > 50`, the agent surfaces to the operator:

> "The capture queue is large (XX candidates). Consider:
> 1. Reviewing and approving/rejecting in bulk.
> 2. Tightening the capture criteria (fewer captures).
> 3. Running `omh memory review --limit 100` to see the backlog."

### Tightening capture criteria

The agent can offer to walk through recent captures and identify patterns:

> "Looking at the last 20 candidates, I see many `episode`-type captures for one-off events. The decision tree says these should not be captured. Should I tighten my criteria to only capture durable facts?"

The operator decides.

## What the agent does NOT do

- Approve its own captures.
- Modify the OMH policy (`auto_approve_safe`, `mode`).
- Delete records without operator approval.
- Edit records without operator approval.
- Write credential values to any memory surface.

## Summary

- Capture via `omh memory capture`; surface to operator.
- Review before surfacing; check summary, type, tags, source, safety.
- Operator approves via `omh memory approve`; agent waits.
- Recall via `omh memory recall`; agent cites records by id.
- Block writes via `omh memory block-set`; surface to operator; no approval needed.

The agent is the writer and the reader. The operator is the approver.