# 01 — When to Use (Reference)

This reference expands on the trigger and counter-trigger conditions for the `memory-architect` skill. The main `SKILL.md` lists the headlines; this document lists the edge cases and decision points in detail.

## Trigger conditions in detail

### Trigger 1 — Operator intent

The operator explicitly asks the agent to remember something.

Examples:

- "Remember that I prefer Chinese responses."
- "Note that the WSL Kali credential is in `.env`."
- "Save this: I always run `omh doctor` before committing."
- "Add to memory: omh-install-state is in the reference-tier block."

In each case, the agent should:

1. Recognize the operator's intent (the verb "remember" / "note" / "save" / "add to memory").
2. Walk the decision tree (Q0 → Q1 → Q2 → Q3 → Q4 → Q5).
3. Capture or set the fact.
4. Surface the candidate to the operator for approval.

### Trigger 2 — Agent self-observation

The agent notices a pattern in the operator's behavior or preferences that is worth remembering.

Examples:

- The operator has asked the agent to use Chinese three times in a row. The agent observes: "this operator prefers Chinese."
- The operator has consistently routed Linux questions to WSL Kali. The agent observes: "this operator uses WSL Kali by default."
- The operator has explicitly chosen claude-code over codex as the OMH default. The agent observes: "this operator prefers claude-code as OMH default."

In each case, the agent should:

1. Verify the pattern is real (not a one-off). A pattern requires at least three consistent observations OR one explicit statement.
2. Walk the decision tree.
3. Propose the capture in chat (do not auto-capture). The operator may or may not want the fact remembered.

### Trigger 3 — Architectural decision

A decision is made that future sessions need to know about.

Examples:

- The operator chose OMH over other memory plugins because of its review-first approval model.
- The operator chose Claude Code as the OMH default executor.
- The operator chose to put the project memory in `~/.omh/memory/` rather than a custom location.

These are typically `decision` typed records:

```bash
omh memory capture --type decision --tag architecture \
    "Decision: use OMH for project memory because its review-first policy matches the operator's trust model."
```

### Trigger 4 — Lesson from a failure

The agent or operator encounters a failure that teaches a lesson worth remembering.

Examples:

- "Do not pipe the credential value into `su`; the safety layer rejects it."
- "Windows MSYS `python -m venv` silently fails; use `uv venv`."
- "`omh memory capture` truncates summaries to 240 chars; use `block-set` for long content."

These are typically `lesson` typed records:

```bash
omh memory capture --type lesson --tag pitfall \
    "Lesson: omh memory capture truncates summaries to 240 chars; route long content to reference-tier blocks."
```

### Trigger 5 — Operator asks "do you remember X?"

The operator asks the agent to recall a fact.

Examples:

- "Do you remember my shell preference?"
- "What did we decide about codegraph?"
- "Where do I store the WSL Kali credential?"

In each case, the agent should:

1. Search L1 (`hermes journey --json`).
2. Search L0 reference-tier block labels (`omh memory blocks`).
3. Search L0 approved records (`omh memory recall "<query>"`).
4. Read the relevant block on demand if needed.
5. Answer based on the memory surfaces, not on guessing.

If the fact is not in any memory surface, the agent says so honestly and offers to capture it for next time.

### Trigger 6 — Memory audit request

The operator asks for a memory audit.

Examples:

- "Show me everything in memory."
- "Is my memory architecture healthy?"
- "Run the dual-store status script."

The agent runs `python scripts/dual-store-status.py` and reports the output.

### Trigger 7 — Migration request

The operator asks to migrate from an existing setup to the dual-store architecture.

Examples:

- "Migrate my flat MEMORY.md to the new architecture."
- "Convert my mnemosyne data to OMH."
- "Help me clean up my memory."

The agent follows [`09-migration-guide.md`](../../docs/09-migration-guide.md) for the migration plan.

### Trigger 8 — Credential addition request

The operator asks to add a credential to the system.

Examples:

- "Add the GitHub PAT."
- "Save my database password."
- "Remember the WSL root password."

The agent routes to `~/.hermes/.env`. The agent does not write the credential value in chat.

## Counter-trigger conditions in detail

### Counter-trigger 1 — General planning

The operator asks for project planning that does not involve memory.

Example: "Plan a sprint for adding a new feature."

Use the `plan` skill, not `memory-architect`.

### Counter-trigger 2 — Bug investigation

The operator reports a bug that is unrelated to memory.

Example: "The `git push` command is failing with error X."

Use `systematic-debugging`, not `memory-architect`.

### Counter-trigger 3 — Code review

The operator asks for code review of non-memory code.

Example: "Review this Python script."

Use `requesting-code-review`, not `memory-architect`.

### Counter-trigger 4 — Workflow execution

The operator asks for a workflow that is not memory-related.

Example: "Deploy the application to staging."

Use the appropriate OMH workflow skill (e.g. `omh-deploy-and-monitor`), not `memory-architect`.

### Counter-trigger 5 — Generic chat

The operator is having a conversation that does not involve memory.

Example: "Tell me a joke."

Do not load any skill. The agent responds directly.

## Edge cases

### Edge case 1 — Operator says "remember this" for a transient event

The operator says: "Remember that I just deployed version 1.0 to production."

This is a one-off event. It does not belong in memory. The agent should push back:

> "This is a deployment event that has already happened. It will not affect future sessions unless we expect to deploy 1.0 to production again. If you want to remember the deployment workflow (the steps that worked), that's worth capturing. If you want to remember a specific past event, it is more useful in a session transcript than in memory. Should I capture the workflow or skip?"

The operator decides.

### Edge case 2 — Operator says "remember" but the fact is implicit

The operator says: "I prefer working in the morning."

The fact is a preference. It is needed every session (affects how the agent should schedule work). It is a short atomic fact. It belongs in an L0 system-tier block.

The agent should still ask: "Is this an absolute preference, or context-dependent (e.g. 'I work in the morning when not on call')?" The exact wording matters.

### Edge case 3 — Multiple facts in one statement

The operator says: "Remember that I prefer Chinese, structured status updates, and concise responses."

This is three facts. Each routes independently. The agent captures three records:

```bash
omh memory capture --type fact --tag language "<240-char summary of Chinese preference>"
omh memory capture --type fact --tag style "<240-char summary of structured status preference>"
omh memory capture --type fact --tag style "<240-char summary of concise responses preference>"
```

Each gets its own `candidate_id` and its own approval.

### Edge case 4 — Operator contradicts an existing memory entry

The operator says: "I no longer prefer concise responses. I prefer verbose explanations."

The agent:

1. Recalls the existing memory entry.
2. Captures a new entry: "User no longer prefers concise responses; now prefers verbose explanations."
3. Notes to the operator that the old entry should be rejected.
4. The operator runs `omh memory reject <old-id> --reason "superseded by <new-id>"`.

### Edge case 5 — Operator wants to delete a memory entry

The operator says: "Forget that I said X."

The agent:

1. Recalls the existing entry.
2. Proposes: "I found the entry. To remove it, run `omh memory reject <id> --reason 'operator request'` (for records) or `omh memory block-remove <label> --tier <tier>` (for blocks). I can do it for you with your confirmation."
3. The operator confirms.
4. The agent runs the command.

The agent does not delete memory without explicit operator confirmation.

## Verification after triggering

After any memory-related action, the agent verifies:

- [ ] The fact landed in the intended surface.
- [ ] The operator was shown the candidate and approved or rejected it.
- [ ] No silent truncation occurred.
- [ ] The destination surface's cap was not exceeded.
- [ ] For system-tier blocks, the render budget was not exhausted.
- [ ] No credential values appear in any memory summary.

If any check fails, the agent surfaces the failure to the operator in chat.