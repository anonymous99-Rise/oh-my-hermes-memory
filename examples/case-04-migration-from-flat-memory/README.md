# Case 4 — Migration from Flat Memory

This example walks through migrating a flat `~/.hermes/memories/MEMORY.md` and `USER.md` to the dual-store architecture. The hypothetical operator has been running Hermes Agent for six months and has accumulated mixed content in their flat memory files.

## Scenario

- Operator: an Hermes Agent user with six months of usage
- Starting state: 2,500-char MEMORY.md, 1,400-char USER.md
- Mixed content: shell conventions, CLI paths, install notes, troubleshooting, project history, credential references, decision rationales
- Goal: migrate to dual-store without losing any fact

## Steps

### 1. Back up

```bash
mkdir -p /tmp/migration-backup-$(date +%Y-%m-%d)
cp ~/.hermes/memories/MEMORY.md /tmp/migration-backup-$(date +%Y-%m-%d)/
cp ~/.hermes/memories/USER.md /tmp/migration-backup-$(date +%Y-%m-%d)/
```

### 2. Read both files

```bash
cat /tmp/migration-backup-$(date +%Y-%m-%d)/MEMORY.md
cat /tmp/migration-backup-$(date +%Y-%m-%d)/USER.md
```

Example content of a flat MEMORY.md:

```
- Shell: Git Bash on Windows, PowerShell for native APIs.
- Claude Code path: C:\nvm4w\nodejs\claude.cmd.
- WSL Kali: default user spacex, root password is spacex.
- Installed OMH on 2026-07-28, omh doctor 30/30 ok.
- Decision: chose OMH over other options because of review-first policy.
- Troubleshooting: omh doctor blocking on plugin manifest means patch plugin_pack.py:216.
- Project: oh-my-hermes-memory (creating a memory architecture).
- (50 more lines of mixed content)
```

Example content of a flat USER.md:

```
- Language: Chinese.
- Response style: structured status updates.
- Executor: Claude Code or Codex CLI freely.
- WSL Kali for Linux ops.
- (10 more lines of preference)
```

### 3. Classify each line

| Line | Classification | Destination |
|---|---|---|
| "Shell: Git Bash on Windows, PowerShell for native APIs." | needed every, short atomic | L0 system-tier block (or L1 entry) |
| "Claude Code path: C:\nvm4w\nodejs\claude.cmd." | needed occasionally, atomic | L0 reference-tier block (cli-executors) |
| "WSL Kali: default user spacex, root password is spacex." | credential reference (partial) | `~/.hermes/.env` + L0 reference block (workflow) |
| "Installed OMH on 2026-07-28" | one-off event | drop |
| "Decision: chose OMH because of review-first" | decision, atomic | L0 approved record |
| "Troubleshooting: omh doctor blocking on plugin manifest means patch plugin_pack.py:216" | long procedure | L0 reference-tier block (omh-install-state) |
| "Project: oh-my-hermes-memory" | session-local state | drop |

### 4. Write to the new tiers

```bash
# Reference blocks
omh memory block-set shell-convention --value "..." --tier system --limit 500
omh memory block-set cli-executors --value "..." --tier reference --limit 2500
omh memory block-set wsl-kali-workflow --value "..." --tier reference --limit 2500
omh memory block-set omh-install-state --value "..." --tier reference --limit 2500

# Approved records
omh memory capture --type decision --tag architecture "Decision: OMH is the project memory plugin because its review-first policy matches the operator's trust model."

# Credentials
echo "WSL_KALI_PWD=spacex" >> ~/.hermes/.env
```

### 5. Write the new L1 MEMORY.md

Replace the existing content with a short index entry:

```bash
# In Hermes chat:
memory add "Memory index — L1 pointer to L0. Complete text lives in OMH blocks. L0 system blocks: env-baseline, shell-convention. L0 reference blocks: cli-executors, wsl-kali-workflow, omh-install-state, windows-env-quirks. Credentials: WSL_KALI_PWD in ~/.hermes/.env."
```

### 6. Write the new L1 USER.md

```bash
memory add "User pointer — full workflow preferences in OMH system-tier block user-workflow-preferences. Key reminders: Chinese responses; Claude Code or Codex CLI freely; WSL Kali for Linux ops."
```

### 7. Verify

```bash
# Old sizes
wc -c ~/.hermes/memories/MEMORY.md ~/.hermes/memories/USER.md
# (now small — just the index entries)

# New tier counts
omh memory status
# approved_records: 1
omh memory blocks
# (5 reference + 2 system)
```

### 8. Verify by content extraction

Extract the content of all blocks and compare to the backup:

```bash
omh memory blocks | python3 -c "
import json, sys, pathlib
d = json.load(sys.stdin)
for b in d.get('blocks', []):
    p = pathlib.Path.home() / '.omh' / 'memory' / 'blocks' / b['tier'] / (b['label'] + '.json')
    if p.exists():
        j = json.loads(p.read_text(encoding='utf-8'))
        print('=== ' + j['label'] + ' ===')
        print(j['value'])
        print()
"
```

Manually compare this output to the backup. If anything is missing, classify it and add it to the appropriate tier.

### 9. Clean up

Once verified:

```bash
rm -rf /tmp/migration-backup-$(date +%Y-%m-%d)
```

## Outcome

- Original content is fully migrated to L0 (with the exception of dropped one-off events).
- Credentials are in `.env`, referenced by env var name.
- L1 MEMORY.md and USER.md are short index entries.
- Total L0 content size is several KB across multiple blocks (vs. the original 3,900 chars in two flat files).
- The architecture scales — the operator can add more blocks without hitting any cap.

## Lessons

1. Migration is a classification exercise, not a copy.
2. Walk each line of the original memory through the decision tree.
3. Some lines (one-off events) should be dropped, not migrated.
4. Credentials must be migrated to `.env`, not memory.
5. Verify by extracting the new content and comparing to the original.
6. Keep the backup until the verification is complete.