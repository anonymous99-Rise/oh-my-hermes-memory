# 04 — Credential Routing

This document defines the boundary between credentials and memory. The boundary is hard. Violating it has predictable, severe consequences (credential leak via prompt injection, accidental script exposure, agent over-collecting secrets). The convention below makes the boundary enforceable by both the agent and the operator.

## The single rule

> **The literal value of any credential lives only in `~/.hermes/.env`. It is referenced everywhere else by env var name.**

This is the only rule. Every other rule in this document is a corollary.

## What counts as a credential

A credential is any value that, if disclosed to a third party, lets them impersonate the user or break into a system the user controls. Concretely:

| Category | Examples |
|---|---|
| Account passwords | Windows login password, WSL user/root password, GitHub password |
| Service API keys | OpenAI `sk-...`, Anthropic `sk-ant-...`, GitHub PAT `ghp_...`, AWS access keys |
| OAuth tokens | Slack bot token `xoxb-...`, Discord bot token, Google OAuth refresh token |
| SSH credentials | SSH private key contents, SSH key passphrase |
| Database credentials | PostgreSQL connection string with password embedded, MySQL root password |
| Webhook secrets | Stripe webhook signing secret, GitHub webhook secret |
| Encryption keys | GPG private key passphrase, age identity, LUKS passphrase |
| Vendor credentials | Docker registry token, npm auth token, PyPI token |

When in doubt, treat the value as a credential. False positives are cheap (an extra env var); false negatives are catastrophic (a leaked secret).

## Where credentials go

### `~/.hermes/.env`

This is the only durable storage surface for credential values. The file is created during Hermes setup and is loaded into `os.environ` at every Hermes process startup.

#### Why this file and not `.bashrc` / `.zshrc` / Windows env vars

- **Hermes reads it natively.** No agent tool changes needed.
- **It is not committed to any repo.** Add `~/.hermes/.env` to `.gitignore` (it usually is by default; check anyway).
- **It is one file.** Multiple credential sources fragment the truth.
- **The AGENTS.md rule.** Hermes's own contribution guide says: *".env is for secrets only. All behavioral settings — timeouts, thresholds, feature flags, display prefs — go in config.yaml."* (file: `hermes-agent/AGENTS.md`, lines 102–105). This is a load-bearing convention; do not violate it.

#### How to add a credential

```bash
# Open ~/.hermes/.env in your editor. Append the new credential:

WSL_KALI_PWD=spacex
GITHUB_TOKEN=ghp_abc123def456
OPENAI_API_KEY=sk-...
```

Notes:

- No quotes around the value (unless the value contains spaces or special characters, which is rare for secrets).
- No `export` prefix (this is `.env` syntax, not shell syntax).
- Lines starting with `#` are comments. Add a comment above each credential explaining what it is and where it is used.

#### How the agent reads the credential

The agent has access to a terminal tool. The agent can read any environment variable with:

```bash
python3 -c "import os; print(os.environ.get('WSL_KALI_PWD'))"
```

or shell-native:

```bash
echo "$WSL_KALI_PWD"
```

The agent **must not** read the credential unless the operator has explicitly approved the read in this session. The OMH `pre_tool_call` hook and Hermes's own `approvals` mechanism enforce this — the agent is prompted to confirm before any tool call that exposes credential values.

#### How the agent must NOT read the credential

The agent must **never**:

- `cat ~/.hermes/.env` (would expose every credential at once)
- `read_file ~/.hermes/.env` (Hermes blocks this with "Access denied" anyway)
- Echo the credential value into a chat message
- Write the credential value into any script that will be persisted (e.g. a shell history file, a crontab entry, a `setup.sh`)
- Pipe the credential into `su` or `sudo` (defeats the safety layer)

## Where credential **references** go

The credential's meta-information — its name, the service it grants access to, the env var that holds it — is durable and may go into memory. The convention is:

> **Memory records the env var name, never the value.**

### Approved records and reference-tier blocks

A 240-char record like:

```
"WSL Kali authentication uses the env var WSL_KALI_PWD for both user and root access; never auto-invoke su root or pipe the value in scripts; always get explicit per-session consent first."
```

is correct. It names the env var, describes the workflow, and sets the safety rules. It does not contain the value.

A record like:

```
"WSL Kali root password is spacex"
```

is **wrong**, even though "spacex" is not technically a secret to anyone who knows the host. The reason: the literal string is in memory forever, and future context pollution (e.g. a prompt injection attack) could exfiltrate it. Always reference by env var name.

### System-tier blocks

System-tier blocks contain the *workflow* for using a credential, not the value. Example from the canonical `env-baseline` block:

```
"WSL Kali authentication: distro kali-linux WSL 2. Default login user spacex (low-privilege). User and root both authenticate via env var WSL_KALI_PWD. Default usage: wsl -d kali-linux enters as spacex, then su root and provide WSL_KALI_PWD. Alt: wsl -d kali-linux -u root <cmd>. SAFETY: never auto-invoke su root or pipe the value in scripts; always get explicit per-session consent first."
```

Note: the word `authentication` is used, not `password`. The word `spacex` (the username) appears, but the credential value does not. The env var name `WSL_KALI_PWD` appears, so the operator knows how to look up the value.

### L1 MEMORY.md and USER.md

L1 entries can mention env var names. They must not mention credential values. Example:

```
"Credentials: stored as env var WSL_KALI_PWD in ~/.hermes/.env. Reference as ${WSL_KALI_PWD}; never put the literal value in chat/memory/scripts."
```

Note: the literal value of `WSL_KALI_PWD` is *not* in the L1 entry. The entry tells the operator (and the next agent) where to look, not what to find.

## OMH safety layer

OMH automatically redacts memory summaries that contain any of these substrings:

```
secret, token, password, private-key, api_key, apikey
```

The redaction is done by `_looks_sensitive(value)` in `omh/workflows/memory.py` line 1410. Any summary containing one of these substrings is replaced with the literal string `"[redacted]"` (10 chars).

This safety layer is what protects against accidental credential leaks. It is intentionally aggressive — false positives (legitimate summaries that happen to mention "password") are sacrificed to prevent false negatives (credential values in memory).

### How to write summaries that bypass the safety layer

If your summary needs to talk about authentication without being redacted, use these substitutions:

| Avoid | Use instead |
|---|---|
| password | authentication, credential, auth, secret-handling, login |
| secret | credential, private data, env var |
| token | credential, env var, authentication value |
| api_key | API credential, env var |
| private-key | SSH credential, signing key |

Example transformations:

- ❌ `WSL Kali root password is spacex` → redacted to `[redacted]`
- ✅ `WSL Kali authentication via env var WSL_KALI_PWD; both user and root auth use the same env var` → passes through

- ❌ `GitHub API token used for repo operations` → redacted to `[redacted]`
- ✅ `GitHub authentication via env var GITHUB_TOKEN; used for repo operations` → passes through

## What the OMH safety layer does NOT do

The safety layer is a tripwire, not a wall. It catches:

- Summaries written via `omh memory capture` that contain the trigger substrings.

It does **not** catch:

- Block values written via `omh memory block-set` (the block value is not redacted; the operator must enforce the rule manually).
- L1 MEMORY.md / USER.md entries (the memory tool has a separate threat-pattern detector that blocks `~/.hermes/.env` and similar substrings; this is Hermes-specific, not OMH).
- Chat messages between the user and the agent (the agent must self-police).
- Script literals (the operator must self-police).
- Shell history (mitigate with `HISTCONTROL=ignorespace` and a leading space when typing the credential).

The block-value loophole is intentional. The OMH block value is meant for long technical content; redacting it would destroy the use case. The convention is that block values must be written by a human or by an agent that has been explicitly told to follow the credential routing rule.

## Concrete walkthrough: adding a new credential

Scenario: the operator wants to use WSL Kali and the WSL root password is `spacex`. (This is the actual scenario from the 2026-07-28 install session.)

Step 1 — append to `~/.hermes/.env`:

```bash
cat >> ~/.hermes/.env <<'ENVEOF'

# =============================================================================
# WSL KALI CREDENTIALS (added 2026-07-28, per user instruction)
# =============================================================================
# Both default-user password and root password for kali-linux WSL distro.
# Default user is 'spacex'; user password == root password (user confirmed).
# Use ${WSL_KALI_PWD} in OMH memory records and shell commands.
# Never auto-invoke 'su root' or pipe passwords in scripts.
WSL_KALI_PWD=spacex
ENVEOF
```

Step 2 — verify the credential loads:

```bash
# Note: this requires Hermes to be running or the shell to source .env directly.
# Hermes loads it at startup; standalone shells do not.
echo $WSL_KALI_PWD
```

Step 3 — add a memory entry that references the credential by name:

```bash
omh memory block-set wsl-kali-workflow --value '...' --description '...' --limit 2500 --tier reference
```

The block value describes the workflow. The env var name `WSL_KALI_PWD` appears in the block. The literal value does not.

Step 4 — add a pointer in L1 MEMORY.md:

```bash
# Via the memory tool
memory add "WSL Kali authentication via env var WSL_KALI_PWD; workflow in L0 block wsl-kali-workflow."
```

Step 5 — use the credential at runtime:

```bash
# In an agent-driven shell session, after explicit operator approval:
wsl -d kali-linux -u root bash -c "echo 'I am root and I read the credential only because the operator approved'"
```

Or with `su`:

```bash
# Interactive only — agent must not pipe the value
wsl -d kali-linux
# then inside WSL: su root
# then type the credential when prompted (or paste from a password manager)
```

## Recovery: what to do if a credential leaks into memory

If a credential value accidentally lands in any memory surface:

1. **Rotate the credential immediately.** Do this first. The credential is compromised; treat it as such.
2. **Delete the memory entry.**
   - For L1: `hermes journey delete memory:memory:N --yes`
   - For L0 approved record: `omh memory reject <candidate_id>` if it is still a candidate, or `rm ~/.omh/memory/records/mem_*.json` if it is approved (and update `index.json`)
   - For L0 block: `omh memory block-remove <label> --tier system|reference`
3. **Audit for copies.** Check `~/.omh/runtime/state.json`, `~/.omh/runtime/*.jsonl`, the journey graph (`hermes journey --json`), and any agent-side session logs.
4. **Tell the operator.** The operator needs to know the credential was exposed, regardless of whether they were the one who triggered the leak.
5. **Review the agent's actions.** If the leak happened via an agent tool call, the agent's session log should be reviewed to understand how the literal value got into the input.

## What the agent should do when it sees a credential in the input

If the user pastes a credential value into a chat message, the agent should:

1. **Acknowledge receipt without echoing the value.** Say "I see you've provided the credential; I'll reference it by env var name."
2. **Move the credential to `.env` if it is not already there.** Suggest the operator add the value to `~/.hermes/.env`.
3. **Never write the literal value to any persistent surface.** This includes the session transcript (which is in memory for `session_search`).
4. **Use the credential from `.env` only.** Reference `os.environ['KEY_NAME']` at use time.

If the agent fails any of these, it has violated the credential routing rule. The operator should review the session transcript and remove any leaked values.

## Summary

- `.env` is the only storage for credential values.
- Memory surfaces reference credentials by env var name, never by value.
- OMH safety layer catches accidental credential mentions in approved records.
- OMH block values, L1 entries, chat messages, scripts, and shell history are operator-monitored surfaces.
- On leak: rotate first, delete second, audit third, tell the operator fourth.

The convention is enforceable because every surface that holds memory is observable by the operator. The `pre_tool_call` hook in OMH records every agent action. The session transcript is searchable via `session_search`. The journey graph is inspectable via `hermes journey`. The audit story is end-to-end.