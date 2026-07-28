# 04 — Credential Routing (Reference)

This reference is the agent-side expansion of [`docs/04-credential-routing.md`](../../docs/04-credential-routing.md). The main docs document explains the policy; this reference explains how the agent implements the policy in practice.

## The agent's responsibilities

The agent has three responsibilities regarding credentials:

1. **Recognize** — identify when a fact is or describes a credential.
2. **Route** — put credential values in `.env`; put credential workflows in L0.
3. **Protect** — never expose credential values, either by writing them to memory or by echoing them in chat.

Each responsibility is detailed below.

## Recognizing a credential

A credential is any value that, if disclosed to a third party, lets them impersonate the user or break into a system the user controls.

Common credential types:

- **Passwords** — Windows login, WSL user/root, GitHub account, database root
- **API keys** — OpenAI (`sk-...`), Anthropic (`sk-ant-...`), GitHub PAT (`ghp_...`), AWS access keys
- **OAuth tokens** — Slack bot (`xoxb-...`), Discord bot, Google OAuth refresh
- **SSH credentials** — SSH private keys (file contents), SSH key passphrases
- **Database credentials** — PostgreSQL connection strings with embedded passwords
- **Webhook secrets** — Stripe signing secret, GitHub webhook secret
- **Encryption keys** — GPG passphrases, age identities, LUKS passphrases
- **Vendor credentials** — Docker registry tokens, npm auth tokens

### How the agent recognizes them in chat

When the operator or another agent provides a value, the agent checks:

1. Does the value look like a credential format? (Random string, base64, hex, prefix like `sk-` or `ghp_`.)
2. Does the surrounding context indicate credential? ("Here is my password", "use this API key", "the root password is").
3. Does the operator or another agent name the credential explicitly? ("Add the GitHub PAT", "remember the database password".)

If any of (1), (2), (3) is yes, treat the value as a credential.

### How the agent recognizes them in code

When the agent sees code that contains a credential-shaped string:

```python
api_key = "sk-abc123def456"  # clearly a credential
password = "hunter2"         # clearly a credential
auth_token = "ghp_abc123"    # clearly a credential
```

The agent must not write the value to memory. Instead, the agent:

1. Notes that the code contains a credential.
2. Refers the operator to remove the credential from the code (use env vars).
3. Captures the workflow in L0 with the env var name, not the value.

## Routing a credential

### Credential value → `~/.hermes/.env`

The agent's role is to tell the operator to append the value to `.env`. The agent does not write the value directly.

```bash
# Agent's instruction to operator:
# "Append this line to ~/.hermes/.env:
#   KEY_NAME=<the credential value>
# Replace <the credential value> with the actual value."
```

The operator opens `.env` in their editor, appends the line, saves, and confirms.

The agent then verifies the credential is accessible:

```bash
# In a Hermes-driven shell, after restart:
python3 -c "import os; print(os.environ.get('KEY_NAME', '<unset>'))"
```

The agent does not see the value (the print goes to the operator's terminal, not to the agent's transcript by default).

### Credential workflow → L0 reference-tier block

```bash
omh memory block-set <service>-auth \
    --value "<workflow description referencing the env var by name>" \
    --description "<service> authentication workflow." \
    --limit <cap> \
    --tier reference
```

The block value names the env var, describes how the credential is used, and sets safety rules. It does not contain the credential value.

Example for WSL Kali:

```bash
omh memory block-set wsl-kali-workflow \
    --value 'WSL Kali authentication uses env var WSL_KALI_PWD for both user and root access. Normal usage: wsl -d kali-linux enters as spacex, then su root and provide WSL_KALI_PWD. Alt: wsl -d kali-linux -u root <cmd>. SAFETY: never auto-invoke su root or pipe the value in scripts; always get explicit per-session consent.' \
    --description 'WSL Kali access workflow.' \
    --limit 1500 \
    --tier reference
```

The block contains the env var name (`WSL_KALI_PWD`) but not the value (`spacex`).

## Protecting a credential

The agent must never expose a credential value. This means:

1. **Never echo in chat.** If the operator pastes a credential into chat, the agent acknowledges without echoing the value.

   ```bash
   # Operator says: "Here's my database password: hunter2"
   # Agent's response:
   # "I see you've provided the database credential. I've noted that auth uses the env var DB_PASSWORD. 
   #  Please append DB_PASSWORD=hunter2 to ~/.hermes/.env. I will not write the literal value to memory."
   ```

2. **Never write to memory.** Even block values that "feel local" can be exfiltrated by prompt injection. The agent must not write credential values to any memory surface.

3. **Never pipe into scripts.** `echo "$CREDENTIAL" | su root` is forbidden. The agent must use interactive `su` or non-interactive `wsl -d kali-linux -u root <cmd>` (which does not require the credential at all).

4. **Never include in tool output.** When the agent calls a tool, the tool's output is part of the conversation transcript. If the tool echoes the credential (e.g. `cat ~/.hermes/.env` output), the transcript contains the credential.

5. **Never log.** If the agent runs a script that logs its inputs, the credential may land in a log file. The agent must use scripts that do not log credentials.

## What the agent does when it sees a credential in the input

If the operator pastes a credential value into chat:

1. Acknowledge without echoing the value.
2. Ask the operator to append the value to `~/.hermes/.env`.
3. Capture the credential's *workflow* (env var name, usage pattern, safety rules) in L0 reference-tier block.
4. If the credential value appears anywhere in the conversation transcript (operator's message, agent's previous output), tell the operator to:
   - Rotate the credential immediately (assume compromise).
   - Delete the session transcript if possible (some platforms support this).
   - Audit recent chat history for the value.

If another agent pastes a credential value into the conversation:

1. Same as above, but also flag to the operator that the agent may have been compromised or misconfigured.
2. Recommend the operator check the other agent's configuration and recent activity.

If the credential value appears in a tool's output (e.g. `cat` of a config file that contains an embedded credential):

1. Do not include the output in the agent's response. Truncate it.
2. Tell the operator that the tool's output contained a credential.
3. Recommend the operator:
   - Rotate the credential.
   - Remove the embedded credential from the source file (use env vars).

## OMH safety layer interaction

OMH automatically redacts any summary containing these substrings:

```
secret, token, password, private-key, api_key, apikey
```

The agent should write summaries that avoid these substrings, even when describing non-credential topics. For example:

- ❌ `The user's password manager is X` → redacted to `[redacted]`
- ✅ `The user's credential manager is X` → passes through

- ❌ `Authentication uses a shared secret` → redacted to `[redacted]`
- ✅ `Authentication uses an env var named WSL_KALI_PWD` → passes through

For substitutions, see [`docs/04-credential-routing.md`](../../docs/04-credential-routing.md).

## What the agent does when the OMH safety layer redacts its summary

If the agent captures a candidate and OMH redacts the summary:

1. Read the safety verdict:
   ```bash
   omh memory review --candidate <id>
   ```
2. Look at `safety.review_reasons`. Common reasons:
   - `sensitive_credential_like_text` — trigger substring found
   - `long_content_requires_review` — content > 2,400 chars
   - `raw_log_or_traceback` — content looks like a stack trace
3. Take action based on the reason:
   - `sensitive_credential_like_text` → rephrase the summary to avoid the trigger substring.
   - `long_content_requires_review` → split the content into two summaries, or move to a block.
   - `raw_log_or_traceback` → rewrite the content as a fact (not a log).

After rephrasing, re-capture. The new candidate should pass the safety layer.

## What the agent does when reading `.env` is needed

The agent sometimes needs to read an env var (e.g. to authenticate a CLI tool). The flow:

1. Verify the operator has explicitly approved the read in this session.
2. Read the var via `os.environ.get('KEY_NAME')` or `$KEY_NAME`.
3. Use the value in the immediate operation only.
4. Do not log, store, or echo the value.

If the operator has not approved, the agent asks:

> "I need to read the env var KEY_NAME to authenticate CLI tool X. Do you approve this read in this session?"

The operator decides. If yes, the read proceeds. If no, the agent finds an alternative (e.g. defer the operation, ask the operator to run it manually).

## Emergency: credential leak

If a credential value accidentally lands in any memory surface:

1. Rotate the credential immediately.
2. Delete the memory entry:
   - L1: `hermes journey delete memory:memory:N --yes`
   - L0 record: `omh memory reject <id>` (if still a candidate) or `rm ~/.omh/memory/records/mem_*.json`
   - L0 block: `omh memory block-remove <label> --tier <tier>`
3. Audit for copies: `~/.omh/runtime/state.json`, `~/.omh/runtime/*.jsonl`, journey graph, session transcripts.
4. Tell the operator.
5. Review the agent's recent actions.

The agent does not silently delete the entry without operator confirmation. The agent does not delay rotation ("let me check first") because the credential is already exposed.

## Summary

The agent's job:

1. Recognize credentials by format, context, and explicit naming.
2. Route values to `.env` and workflows to L0.
3. Protect values from chat echoes, memory writes, script pipes, tool output, and logs.
4. Tell the operator when something has gone wrong.

When in doubt: route to `.env`, reference by env var name in memory, and ask the operator before reading.