# 03 — Decision Tree (Reference)

This reference is the agent-side expansion of [`docs/02-decision-tree.md`](../../docs/02-decision-tree.md). The main docs document explains the *what* and *why* of the decision tree; this reference explains the *how* — how the agent applies the tree in practice.

## How the agent uses this reference

When the agent is about to write a memory entry, it walks the tree top to bottom. The first question whose answer is unambiguous determines the destination. If no question yields a clear answer, the agent defaults to:

- `.env` if the fact is a credential
- L0 reference-tier block otherwise

Reference tier is the safest default because:

- It is not auto-injected (no risk of system prompt bloat)
- It has no per-block size cap (operator can set `--limit 5000`)
- It is searchable via the label index
- It does not require operator approval per write

## The tree, annotated for agents

### Q0 — Is this a credential?

The agent's check:

1. Does the fact contain a literal value that, if disclosed, lets a third party impersonate the user or break into a system? Examples: a password string, an API key string, an OAuth token.
2. Does the fact describe *how to access* a credential? Examples: "WSL Kali root uses the same password as user spacex." This is not a credential itself; it is a credential workflow.

If the answer to (1) is yes: the literal value goes to `~/.hermes/.env`. Stop. Do not write the value anywhere else. Even in chat.

If the answer to (1) is no but the answer to (2) is yes: the workflow goes to L0 (typically reference-tier). The credential's env var name appears in the workflow.

If the answer to both is no: continue to Q1.

#### Common agent mistakes on Q0

- Mistake: "The fact is `password = 'spacex'` and I just need to remember the value." — Wrong. The value goes to `.env` and you reference `${WSL_KALI_PWD}` from the workflow.
- Mistake: "I'll write 'password = spacex' to a block; it's local-only." — Wrong. The block value is searchable by the agent and any future prompt injection attack could exfiltrate it.
- Mistake: "The summary contains the substring 'password' but the value is just the username." — Even so, the OMH safety layer redacts it. Rephrase.

### Q1 — Is it needed at the start of every session?

The agent's check:

1. Does the fact affect how the agent should *greet* the user? (Language, response style, name.) → yes.
2. Does the fact affect how the agent should *route* requests? (Default shell, authorized CLI executors, default memory surface.) → yes.
3. Does the fact affect how the agent should *behave* without prompting? (No auto-approve; credential reference convention; no compression of memory.) → yes.
4. Does the fact change often within a session? (Current task, recent decisions, active file being edited.) → no.
5. Will the fact be relevant for less than 7 days? (Temporary preference, one-time observation.) → no.

If the answer to (1), (2), or (3) is yes: continue to Q2.
If the answer to (4) or (5) is yes: skip to Q3.

#### Common agent mistakes on Q1

- Mistake: "This is needed every session, I'll put it in L0 system tier." — The fact may be needed every session but be too long. Check Q2 first.
- Mistake: "This is needed every session, I'll add it to MEMORY.md." — MEMORY.md has a 2,200-char cap. Check Q2 first.
- Mistake: "This is just a session preference, no need to capture." — Session preferences that affect the *next* session are durable. "I am working on file X" is not durable (the next session will not be working on file X); "I prefer tabs over spaces" is durable.

### Q2 — Can the fact fit in ≤240 chars (summary form)?

The agent's check:

1. Can the complete fact be written in a single sentence under 240 chars?
2. Does the sentence contain trigger substrings? (`password`, `secret`, `token`, `private-key`, `api_key`, `apikey`)

If both checks pass: the fact goes to L0 approved record.

```bash
omh memory capture --type <type> --tag <tag> --source "agent-2026-07-28" --source-ref "<ref>" "<summary under 240 chars>"
```

The agent surfaces the candidate to the operator:

> "I've captured a fact for review: `<summary>`. Candidate ID: `<id>`. Run `omh memory review <id>` to inspect, then `omh memory approve <id>` or `omh memory reject <id> --reason '...'`."

If check (1) fails: continue to Q4.
If check (2) fails: rephrase the summary to avoid the trigger substrings. See [`04-credential-routing.md`](04-credential-routing.md) for substitutions.

#### Common agent mistakes on Q2

- Mistake: "I'll write a 300-char summary and let OMH truncate." — OMH silently truncates to 240. The truncated version may not convey the fact. Either rephrase in 240 chars or move to a block.
- Mistake: "I'll write 'password = X' and trust the safety layer to redact." — The safety layer does redact, but the redaction produces `[redacted]`, which is useless. Always rephrase proactively.
- Mistake: "I'll write a one-sentence summary but split the fact across multiple sentences." — Multiple sentences can each independently convey a fact, but a 240-char summary is one tight sentence, not a paragraph.

### Q3 — Is it a one-off event or process log?

The agent's check:

1. Will the fact be relevant for less than 7 days? (One-time deployment, single chat session outcome, today's date.) → yes (do not store).
2. Is the fact a transcript or process log? ("I ran command X, output Y.") → yes (do not store, use `session_search` instead).
3. Is the fact session-local state? ("I am editing file Y.") → yes (do not store).

If the answer to any of (1), (2), (3) is yes: do not store. The fact is either ephemeral or already captured in the session transcript.

If the answer to all is no: continue to Q4.

#### Common agent mistakes on Q3

- Mistake: "The operator mentioned today's date, I'll save it." — Today's date is not durable. The next session has a different "today."
- Mistake: "I'll capture the output of every command I run." — Command outputs are process logs. Capture the *lesson* (Q4 path), not the log itself.
- Mistake: "The operator asked me to remember X, so I must capture it." — Even if the operator asked, the agent still walks the tree. Some operator requests are for ephemeral facts. Push back politely and offer to capture a durable version instead.

### Q4 — Does it fit in the 6,000-char system-tier render budget across all system-tier blocks?

The agent's check:

1. Run `omh memory blocks --tier system` and add up the `chars` column.
2. If the running total + the new fact's chars ≤ 6,000: yes, route to system tier.
3. If the running total + the new fact's chars > 6,000: no, route to reference tier.

When routing to system tier:

```bash
omh memory block-set <label> \
    --value "<full content under 5,800 chars>" \
    --description "<one-line purpose>" \
    --limit <per-block cap, typically 2,000-5,800> \
    --tier system
```

The agent surfaces the write to the operator (block writes do not require approval, but the operator should see what was written).

When routing to reference tier: see Q5.

#### Common agent mistakes on Q4

- Mistake: "I'll just add another system-tier block, the budget is large." — The budget is 6,000 chars total, not per block. Three 2,000-char blocks exhaust it. Check the running total.
- Mistake: "I'll set `--limit 10000` to bypass the system-tier render budget." — The renderer uses `budget_chars=DEFAULT_SYSTEM_RENDER_BUDGET_CHARS` (6,000), not the block's `--limit`. A 10,000-char block is rendered as a 10,000-char element, exceeding the budget and being dropped.
- Mistake: "I'll keep the fact in reference tier but also add a pointer in system tier." — That's the right pattern, but the agent should not put the *content* in the system-tier pointer. The pointer names the reference-tier block label.

### Q5 — Use a reference-tier block

The default destination for durable, longer-than-240-char facts that are not needed every session.

```bash
omh memory block-set <label> \
    --value "<full content under --limit>" \
    --description "<one-line purpose>" \
    --limit <per-block cap, typically 2,000-5,000> \
    --tier reference
```

The agent surfaces the write to the operator.

#### Common agent mistakes on Q5

- Mistake: "I'll set `--limit 5000` for everything." — The limit is per-block. If the content is 800 chars, `--limit 2000` is fine. If the content is 4,500 chars, `--limit 5000` is correct. Match the limit to the content.
- Mistake: "I'll create a block per topic instead of combining related blocks." — Fragmentation hurts recall. Combine related facts into one block with a descriptive label.

## What the agent does after routing

After determining the destination:

1. Run the appropriate command.
2. Verify the write succeeded.
3. If the destination was L0, surface the candidate or write to the operator.
4. Update L1 MEMORY.md if the new entry should be indexed.
5. Report success or failure to the operator in chat.

For L0 approved records specifically, the operator must approve before the record lands. The agent surfaces the candidate and waits.

For L0 block writes (reference or system tier), the write lands immediately. The agent surfaces what was written.

## What the agent does not do

- Auto-approve memory writes. The operator decides.
- Compress facts to make them fit. Move them to a different surface.
- Write credential values to memory. Route to `.env`.
- Migrate from another memory system without operator approval.
- Edit or delete existing memory without operator approval.

## Examples

### Example 1 — Operator says "remember I prefer Chinese"

```bash
# Q0: not a credential
# Q1: needed every session (affects response language)
# Q2: can fit in 240 chars
# → L0 approved record

omh memory capture --type fact --tag language --source "user-2026-07-28" --source-ref "<chat-id>" \
    "User prefers Chinese responses; respond in Chinese unless user switches language."

# Surface to operator:
# "Captured fact for review: 'User prefers Chinese responses...'. Candidate ID: cand_xxx. Run `omh memory review cand_xxx` then approve or reject."
```

### Example 2 — Operator adds WSL Kali credential

```bash
# Q0: IS a credential (literal value 'spacex')
# → ~/.hermes/.env

# Agent tells operator:
# "Append WSL_KALI_PWD=spacex to ~/.hermes/.env. I will reference the env var by name in any memory surface; I will not write the literal value."
```

### Example 3 — Operator makes an architectural decision

```bash
# Q0: not a credential
# Q1: needed every session (affects routing decisions)
# Q2: 200 chars, atomic
# → L0 approved record (decision type)

omh memory capture --type decision --tag architecture --source "user-2026-07-28" \
    "Decision: OMH is the project memory plugin because its review-first policy matches the operator's trust model."
```

### Example 4 — Operator wants to remember a long procedure

```bash
# Q0: not a credential
# Q1: needed occasionally, not every session
# Q2: 900 chars, too long for record
# Q4: 900 chars would fit in 6,000 system budget (running total 4,500 + 900 = 5,400 < 6,000), but it's not needed every session
# Q5: use reference-tier block

omh memory block-set wsl-kali-workflow \
    --value "<900-char procedure including the WSL_KALI_PWD env var reference>" \
    --description "WSL Kali access workflow." \
    --limit 1500 \
    --tier reference
```

### Example 5 — Operator hits the system-tier render budget

```bash
# Existing system blocks total 5,800 chars. New fact is 500 chars. Total 6,300 > 6,000.
# Q4: no (would exceed budget)
# Q5: yes (reference tier)

# The agent:
# 1. Identifies the largest system-tier block.
# 2. Recommends moving it to reference tier.
# 3. Writes the new fact to reference tier.
# 4. Adds a pointer in the remaining system-tier block.

# Move: omh memory block-set <largest-block> --tier reference --value "<existing value>" --description "<existing>" --limit 2000
# Add: omh memory block-set <new-fact> --tier reference --value "<new>" --description "<desc>" --limit 1000
# Update L1: memory add "L0 reference blocks: <list including new>"
```