User workflow preferences (set on install day, complete):

Language: Chinese. Respond in Chinese unless user switches. Structured, explicit status updates preferred over terse confirmations.

Coding executor: pick freely between Claude Code and Codex CLI — do NOT ask which each time. Default is claude-code via OMH. Routing hint: short interactive sessions → claude; long batch / CI / review tasks → codex (better non-interactive flags: codex exec, codex review). Switch OMH default via: omh setup --default-executor codex --force (or claude-code / hermes / choose).

Shell routing: Linux-side operations (network scans, security tools, Linux-only tooling) → WSL Kali by default. Windows-side operations → native Windows shell (Git Bash for POSIX, PowerShell for native Windows APIs).

OMH profile: full (92 skills, ~32k up-front context). Do not trim unless user asks. Skills invoked via Use OMH <skill-name> for: <request> syntax (see ~/.omh/skills/ for list; omh list gives overview).

Memory policy: dual-store. L1 (Hermes memory tool = MEMORY.md/USER.md) is index-only. L0 (OMH project memory at ~/.omh/memory/) holds complete text. Long facts → omh memory block-set --tier reference; short atomic facts → omh memory capture → review → approve. Credentials (passwords, tokens, API keys) → ~/.hermes/.env ONLY, never in memory/chat/script literals. Before any credential-using action (su root, API call with key), get explicit per-session consent. All L0 writes go through review-first; user approves via omh memory approve <id>. Auto-approve only when user explicitly delegates a category.

Update cadence: omh doctor weekly. omh update monthly (and re-apply plugin_pack.py:216 patch after each update). omh memory-sync periodically for review (Use OMH memory-sync for: review stale memories).

What user does NOT want: agent autonomously approving memory without explicit delegation; compressing/cutting memory for size reasons (use L0 blocks instead, never trim); OpenClaw ↔ Hermes memory mixing (keep separate).

---

To use this template, customize the values, then apply via:

    omh memory block-set user-workflow-preferences --value "<file content>" --description "User workflow preferences + memory policy + update cadence. Injected every turn via system tier." --limit 5800 --tier system

Or use `./scripts/apply-template.sh user-workflow --apply`.