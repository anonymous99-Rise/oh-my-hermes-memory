Environment baseline (set on install day, complete — supersedes earlier MEMORY.md fragments):

Host: <HOSTNAME> host at <HOMEDIR>. Three shells in use: Git Bash (POSIX default), PowerShell (native Windows APIs), cmd.exe. WSL: <DISTRO> distro, WSL <VERSION>.

Python: 3.11.15 (uv-managed at <UV_HOME>). WindowsApps python3 (3.13) shim FAILS for python -m venv — use uv venv --python 3.11 <win-path> + uv pip install instead, then verify dir exists.

WSL Kali: distro <DISTRO> WSL <VERSION>. Default login user <USERNAME> (low-privilege). User password AND root password are BOTH stored as env var <VAR_NAME> (value <same string>) in ~/.hermes/.env. Use ${<VAR_NAME>} in scripts — never put the literal value anywhere. Default usage: wsl -d <DISTRO> enters as <USERNAME>, then su root + enter <VAR_NAME> value. Alt: wsl -d <DISTRO> -u root <cmd> (non-interactive root). SAFETY: never auto-invoke su root or pipe the value in scripts; always get explicit per-session consent first.

CLI executors on PATH: omh 1.0.3 (C:\Users\Administrator\.local\bin\omh.exe), claude (Claude Code) 2.1.215 (C:\nvm4w\nodejs\claude.cmd), codex (Codex CLI) 0.145.0 (C:\nvm4w\nodejs\codex.cmd), hermes (C:\Users\Administrator\AppData\Local\hermes\bin\), uv 0.11.32. OMH default executor = claude-code (set via omh setup --default-executor claude-code --force). Routing policy: do NOT ask which each time — pick by task fit (short/interactive → claude; long batch/CI/review → codex). Switch default: omh setup --default-executor codex --force.

OMH install: 92 workflow skills + 4 ULW family, scope=user, full profile. Plugin bundle at <HERMES_PLUGINS>/omh (60 files, LF, manifest SHA-matched). omh doctor 30/30 ok as of install. Known Windows bug patched in place: omh/install/plugin_pack.py:216 was write_text → write_bytes (CRLF fix); re-apply after every omh update/omh install (gets reverted). Path B (hermes skills install rlaope/oh-my-hermes/skills/oh-my-hermes) is BROKEN — 404, do NOT retry; 92 skills are correctly registered as local source via path A. Update flow: omh update && omh install && (re-apply plugin_pack.py:216 patch) && omh doctor && omh setup --force.

codegraph: 1.5.0 installed at C:\nvm4w\nodejs\codegraph. Registered as MCP in all 3 runtimes (claude ✓, codex enabled, hermes ✓). OMH skill omh-codegraph-refresh is the workflow for repo codemap refresh. NO repo initialized yet — run codegraph init <path> per-repo before using MCP tools. Subcommands: codegraph_explore, codegraph_node, codegraph_callers, codegraph_callees, codegraph_impact.

Memory architecture (dual-store, set on install day): L1 (Hermes memory tool = MEMORY.md/USER.md) holds ESSENTIAL INDEX ONLY — points to L0 blocks. L0 (OMH project memory at ~/.omh/memory/) holds complete text — long facts via omh memory block-set --tier reference (on-demand read via omh_memory action=read label=X), short atomic facts via capture → review → approve (240 char summary hard cap). Credentials (e.g. WSL_KALI_PWD) live in ~/.hermes/.env, NEVER in memory/chat/script literals. All L0 writes go through review-first; user approves via omh memory approve <candidate_id>. Auto-approve requires explicit per-session user delegation.

Communication: user speaks Chinese; respond Chinese unless they switch. Structured status updates preferred over terse.

---

To use this template, replace the angle-bracketed placeholders with your actual values, then apply via:

    omh memory block-set env-baseline --value "<file content>" --description "Complete environment baseline injected every turn via system tier." --limit 5800 --tier system

Or use `./scripts/apply-template.sh env-baseline --apply`.