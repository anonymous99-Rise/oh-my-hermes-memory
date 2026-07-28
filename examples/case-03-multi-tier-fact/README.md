# Case 3 — Multi-Tier Fact Routing

This example walks through routing three related facts to three different tiers. It demonstrates how the decision tree works in practice for a non-trivial case.

## Scenario

The operator has just finished installing OMH and wants to record:

1. "WSL Kali is the default Linux shell for Hermes operations."
2. "The shell convention is Git Bash for POSIX, PowerShell for native Windows APIs."
3. "CLI executors authorized: omh, claude, codex, hermes, uv. Pick by task fit."

Each fact has different characteristics and routes to a different tier.

## Decision walk

### Fact 1: "WSL Kali is the default Linux shell"

- Q0: Is it a credential? No.
- Q1: Is it needed every session? Yes (the agent must know the default shell on every session start).
- Q2: Can it fit in ≤240 chars? Yes (under 200 chars).
- Q4 (implied): Is it short enough for system tier? Yes.
- **Destination**: L0 system-tier block (small).

### Fact 2: "The shell convention is Git Bash for POSIX, PowerShell for native Windows APIs"

- Q0: No.
- Q1: Yes (needed every session).
- Q2: Yes (under 240 chars).
- Q4 (implied): Yes, fits in system tier budget.
- **Destination**: L0 system-tier block (small).

### Fact 3: "CLI executors authorized with paths and routing policy"

- Q0: No.
- Q1: Yes (the agent must know which executors are authorized on every session start).
- Q2: No — over 240 chars (it includes paths, versions, and routing policy).
- Q4 (implied): It could fit in system tier, but it's not needed every session (rarely consulted mid-session).
- **Destination**: L0 reference-tier block.

## Commands

### Fact 1 — system-tier block

```bash
omh memory block-set linux-default \
    --value "Linux operations default to WSL Kali. Distribution: kali-linux WSL 2. Default user: spacex. Authentication via env var WSL_KALI_PWD." \
    --description "Default Linux shell for Hermes operations." \
    --limit 200 \
    --tier system
```

### Fact 2 — system-tier block

```bash
omh memory block-set shell-convention \
    --value "Shell routing: Linux-side operations (network scans, security tools, Linux-only tooling) → WSL Kali. Windows-side operations → native Windows shell. Within native Windows, Git Bash for POSIX paths and POSIX tools; PowerShell for native Windows APIs and COM/WMI." \
    --description "Shell routing policy." \
    --limit 500 \
    --tier system
```

### Fact 3 — reference-tier block

```bash
omh memory block-set cli-executors \
    --value "CLI executors authorized: omh 1.0.3 (C:\Users\Administrator\.local\bin\omh.exe), claude (Claude Code) 2.1.215 (C:\nvm4w\nodejs\claude.cmd), codex (Codex CLI) 0.145.0 (C:\nvm4w\nodejs\codex.cmd), hermes (C:\Users\Administrator\AppData\Local\hermes\bin\), uv 0.11.32 (C:\Users\Administrator\AppData\Local\hermes\bin\uv.exe). OMH default executor is currently claude-code (set by 'omh setup --default-executor claude-code --force'). Routing policy: do NOT ask which each time — pick by task fit. Short interactive sessions → claude; long batch / CI / review tasks → codex (Codex has better non-interactive flags: codex exec, codex review). To switch OMH default executor: 'omh setup --default-executor codex --force' or 'claude-code' or 'hermes' or 'choose'." \
    --description "Authorized CLI executors with paths, versions, and routing policy." \
    --limit 2500 \
    --tier reference
```

## Common mistake: putting it all in system tier

If the operator (or agent) decides "everything is needed every session, put it all in system tier", the result is:

```
total system tier: ~1500 chars (linux-default + shell-convention + cli-executors)
```

This is well within the 6,000-char budget. But:

- The agent sees `cli-executors` every turn, even though it rarely needs the full content (paths and versions).
- The system prompt bloats, slowing down every turn.
- If the operator later wants to add another system-tier block (e.g. `env-baseline`), it has less budget.

The right pattern: keep `cli-executors` in reference tier (where it lives now), with a one-line pointer in `env-baseline` (system tier):

```bash
omh memory block-set env-baseline \
    --value "Environment baseline (set 2026-07-28): Host Windows 10. Shells: Git Bash, PowerShell, cmd.exe. WSL: kali-linux WSL 2. Default user: spacex. Authentication via env var WSL_KALI_PWD. OMH home: ~/.omh. Plugin bundle: ~/.hermes/plugins/omh. codegraph 1.5.0 at C:\nvm4w\nodejs\codegraph (MCP: claude, codex, hermes). OMH default executor: claude-code. Memory architecture: dual-store (L1 index, L0 OMH project memory, .env credentials). See reference-tier blocks for: windows-env-quirks, wsl-kali-workflow, cli-executors, omh-install-state, codegraph-integration." \
    --description "Complete environment baseline injected every turn via system tier." \
    --limit 5800 \
    --tier system
```

## Outcome

- `linux-default` and `shell-convention` are in system tier (small, needed every session).
- `cli-executors` is in reference tier (larger, needed occasionally).
- `env-baseline` consolidates the system-tier facts into one block with pointers to reference-tier blocks.
- The agent sees the system-tier blocks every turn and can read reference-tier blocks on demand via `omh_memory(action="read", label=X)`.

## Lessons

1. The decision tree routes each fact independently. Facts with different characteristics go to different tiers.
2. Do not put everything in system tier just to "be safe." Reserve system tier for facts truly needed every session.
3. Use `env-baseline` (or similar) as a system-tier index to reference-tier blocks. The agent sees the index every turn and reads on demand.
4. Run `omh memory blocks --tier system` periodically to check the render budget. If the budget is exhausted, move large blocks to reference tier.