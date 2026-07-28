# 09 — Migration Guide

This document is for operators who already have an existing memory surface and want to migrate to the dual-store architecture. It covers migrations from:

- A flat `~/.hermes/memories/MEMORY.md` and `USER.md` (the default Hermes setup)
- A flat `~/.hermes/.env` with credentials mixed in
- A different memory plugin (mnemosyne, Penfield, retaindb, etc.)
- A custom file-based memory system
- An OMH memory that has been used in `auto_approve_safe: true` mode

Each migration preserves the existing content; nothing is deleted until the new architecture is verified.

## Migration overview

The migration is a four-step process:

1. **Inventory** — read the existing memory surfaces and classify every fact by the decision tree.
2. **Reroute** — for each classification, write to the correct surface (L1, L0 system, L0 reference, `.env`).
3. **Index** — write a new L1 MEMORY.md and USER.md that point at the new tiers.
4. **Verify** — confirm every original fact is in the new architecture before deleting the original files.

The migration is not a one-shot operation. Operators typically spend an afternoon on it. The result is a memory architecture that scales indefinitely.

## From flat MEMORY.md and USER.md

### Step 1 — back up

```bash
mkdir -p /tmp/migration-backup-$(date +%Y-%m-%d)
cp ~/.hermes/memories/MEMORY.md /tmp/migration-backup-$(date +%Y-%m-%d)/
cp ~/.hermes/memories/USER.md /tmp/migration-backup-$(date +%Y-%m-%d)/
ls /tmp/migration-backup-$(date +%Y-%m-%d)/
# MEMORY.md
# USER.md
```

### Step 2 — read and classify

Read both files line by line. For each non-empty line, classify by [`02-decision-tree.md`](02-decision-tree.md):

| If the line is about… | Route to… |
|---|---|
| A credential value or env var name | `~/.hermes/.env` (value) + L0 reference block (workflow) |
| The user's preferred language, response style, name | L0 system-tier block (small) |
| The shell convention, host baseline | L0 system-tier block (medium) |
| A long procedure or environment quirk | L0 reference-tier block |
| An atomic fact (≤240 chars) | L0 approved record (capture → approve) |
| A one-off event ("installed OMH on date X") | drop |

### Step 3 — write to the new tiers

For each classification:

```bash
# Reference-tier block (long procedures)
omh memory block-set <label> --value "<full text>" --description "<purpose>" --limit 5000 --tier reference

# System-tier block (small, needed every session)
omh memory block-set <label> --value "<full text>" --description "<purpose>" --limit 2000 --tier system

# Approved record (atomic facts)
omh memory capture --type fact --tag <tag> "<summary>"
omh memory approve <candidate_id>

# Credential
echo "KEY_NAME=value" >> ~/.hermes/.env
```

### Step 4 — write the new L1

```markdown
Memory index — L1 pointer to L0. Complete text lives in OMH blocks and records at ~/.omh/memory/. L0 system blocks: <list>. L0 reference blocks: <list>. L0 approved records: <list>. Credentials: <list of env vars>. Update policy: omh update && omh install && re-apply plugin_pack.py:216 patch && omh doctor.
```

This entry should be ≤ 1,500 chars. If it is longer, the original MEMORY.md had content that was not migrated; investigate.

### Step 5 — verify

```bash
# Old
wc -c ~/.hermes/memories/MEMORY.md
# (now small — just the index)

# New tier counts
omh memory status
# approved_records: N
omh memory blocks | grep -c reference
# M
omh memory blocks | grep -c system
# K
```

Verify that the original content is fully represented in the new tiers:

```bash
# Extract the content of all system-tier and reference-tier blocks
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

# Compare to the backup
diff <(cat /tmp/migration-backup-$(date +%Y-%m-%d)/MEMORY.md) <(cat <<EOF
[output from above]
EOF
)
```

If the diff shows missing content, the migration is incomplete. Re-classify and re-write.

### Step 6 — clean up

Once the diff is empty (or only shows intentional drops for one-off events):

```bash
# Remove the backup once you are confident
rm -rf /tmp/migration-backup-$(date +%Y-%m-%d)
```

## From a flat ~/.hermes/.env with credentials mixed in

This is a different migration. The credentials are already in `.env`, but the operator may have behavioral settings mixed in. Per Hermes AGENTS.md, `.env` is for secrets only; behavioral settings go to `config.yaml`.

### Step 1 — back up

```bash
cp ~/.hermes/.env /tmp/env-backup-$(date +%Y-%m-%d).env
```

### Step 2 — classify each line

| If the line is… | Action |
|---|---|
| `KEY=value` where KEY is in the credential list (see [`04-credential-routing.md`](04-credential-routing.md)) | keep in `.env` |
| `KEY=value` where KEY is a behavioral setting (timeout, model, threshold, feature flag) | move to `~/.hermes/config.yaml` |
| A comment explaining a credential | keep in `.env` |
| A comment explaining a behavioral setting | move to `config.yaml` or delete |

### Step 3 — write the new files

The `.env` file should now contain only credentials. The `config.yaml` file should contain only behavioral settings.

```bash
# Create new .env with only credentials
grep -E "^[A-Z_]+=|^# " /tmp/env-backup-...env | grep -v -E "TIMEOUT|MODEL|LOG_LEVEL|FEATURE_FLAG|DEBUG" > ~/.hermes/.env.new
mv ~/.hermes/.env.new ~/.hermes/.env

# Behavioral settings go to config.yaml
# (manual edit; config.yaml format is YAML)
```

### Step 4 — verify

```bash
# .env should not contain any behavioral settings
grep -iE "TIMEOUT|MODEL|LOG_LEVEL|FEATURE_FLAG|DEBUG" ~/.hermes/.env
# (no output expected)

# config.yaml should contain them
grep -iE "TIMEOUT|MODEL|LOG_LEVEL|FEATURE_FLAG|DEBUG" ~/.hermes/config.yaml
# (expected output)
```

## From a different memory plugin

If the operator is using mnemosyne, Penfield, retaindb, or another memory plugin, the migration is more involved. The existing plugin's data is in a different format (often a SQLite database or a cloud service).

### Step 1 — export from the existing plugin

Each plugin has its own export command:

- `mnemosyne` — typically `mnemosyne export --format json > /tmp/mnemosyne-export.json`
- `Penfield` — typically `penfield export --output /tmp/penfield-export.json`
- `retaindb` — typically `retaindb dump > /tmp/retaindb-dump.sql`

Consult the plugin's documentation.

### Step 2 — convert to the dual-store format

The export is a list of records. Each record has:

- A unique identifier
- A creation timestamp
- A content field (the fact)
- Optionally, tags, source, scope

For each record, classify by the decision tree and write to the new tier.

### Step 3 — preserve the original plugin

Do not uninstall the existing plugin until the dual-store architecture is verified. The migration is non-destructive; both systems coexist until the operator is confident.

### Step 4 — schedule a verification window

Run the dual-store architecture for at least one week before uninstalling the original plugin. If the new architecture is missing facts the operator relies on, the original plugin is the fallback.

## From a custom file-based memory system

Operators who have built their own memory system (e.g. a directory of markdown files) have a similar migration path:

1. Inventory the existing files.
2. Classify each file's content by the decision tree.
3. Write to the new tiers.
4. Verify by comparing.
5. Back up and delete the original.

The migration script can be automated with a small shell or Python script if the volume is high.

## From auto-approve OMH memory

If the operator has been running OMH with `auto_approve_safe: true`, the migration is to flip the policy and review the existing approved records.

### Step 1 — flip the policy

```bash
omh memory provider config auto_approve_safe false
omh memory status --json | jq .policy.auto_approve_safe
# false
```

### Step 2 — review existing approved records

The existing approved records were created without operator review. They may contain facts the operator does not want, or facts that are inaccurate. Review them:

```bash
omh memory status --json | jq -r '.counts.approved_records'
# (number of records to review)

# Read each record's content via the record_id
ls ~/.omh/memory/records/
# mem_<hash>.json files
```

### Step 3 — reject what does not belong

For each record that should not be there:

```bash
# Reject by content hash
omh memory reject <record_id> --reason "pre-auto-approve review"
```

Or directly remove from disk:

```bash
# More aggressive; the index needs rebuilding after this
rm ~/.omh/memory/records/mem_<hash>.json
# Rebuild index
omh memory status # triggers rebuild
```

### Step 4 — recapture the good records

For records the operator wants to keep, no action is needed. They are already approved and indexed.

For records the operator wants to keep but in a different tier (e.g. they want to move a record to a reference-tier block):

1. `rm ~/.omh/memory/records/mem_<hash>.json`
2. `omh memory block-set <label> --value "<full content>" --tier reference --limit 5000`
3. `omh memory status` to rebuild the index.

## Common pitfalls

### Pitfall 1 — losing facts during migration

The most common pitfall. The operator re-classifies a fact incorrectly and drops it.

Mitigation: back up everything before any migration. Run the dual-store architecture alongside the old system for at least one week. Compare counts and content.

### Pitfall 2 — over-categorizing

The operator splits every fact into its own tier or block, leading to fragmentation. Recall becomes hard.

Mitigation: default to fewer, larger blocks. Combine related facts into one block. Use approved records only for true atomic facts.

### Pitfall 3 — under-categorizing

The operator puts everything in one tier (usually system). The system-tier render budget exhausts and the renderer drops blocks.

Mitigation: follow the decision tree strictly. Most facts should end up in reference tier.

### Pitfall 4 — forgetting the .env boundary

The operator migrates credentials into L0 memory summaries. OMH safety redacts them to `[redacted]`.

Mitigation: walk Q0 (is this a credential?) first for every fact. If yes, route to `.env` and reference by env var name in memory.

### Pitfall 5 — migrating without a backup

The operator deletes the old memory files before verifying the new architecture.

Mitigation: never delete the backup until the verification step is complete. Even then, keep the backup for at least one month before final deletion.

## Tools to help the migration

### script: `scripts/dual-store-status.py`

Lists the current state of all three surfaces:

```bash
python scripts/dual-store-status.py
```

Output:

```
L1 (memory tool)
  MEMORY.md: 1085 / 2200 chars (49% used, headroom 1115)
  USER.md: 278 / 1375 chars (20% used, headroom 1097)

L0 (OMH project memory)
  candidates: 0
  approved_records: 4
  blocks:
    [system] env-baseline: 3376 / 5800
    [system] user-workflow-preferences: 2016 / 5800
    [reference] windows-env-quirks: 914 / 2500
    [reference] wsl-kali-workflow: 964 / 2500
    [reference] cli-executors: 1096 / 2500
    [reference] omh-install-state: 1040 / 2500
    [reference] codegraph-integration: 1008 / 2500
  total system tier: 5392 / 6000 (89.9% used)
  total reference tier: 5022 chars (unlimited)

.env credentials:
  WSL_KALI_PWD (referenced in: wsl-kali-workflow, env-baseline)

Overall: healthy. No action needed.
```

### script: `scripts/route-fact.py`

For a new fact, suggests the correct tier:

```bash
python scripts/route-fact.py --text "User prefers concise responses" --frequency every
# Suggested tier: L0 system-tier block
# Reason: short, needed every session
# Suggested command:
#   omh memory block-set user-style --value "..." --tier system --limit 500
```

### script: `scripts/apply-template.sh`

Apply the canonical templates from `templates/`:

```bash
./scripts/apply-template.sh env-baseline
# Creates ~/.omh/memory/blocks/system/env-baseline.json with the canonical content
```

The templates in `templates/` are starting points. The operator should customize them for their specific setup.

## When the migration is done

- The old memory files are backed up to a safe location.
- The new dual-store architecture is populated and verified.
- The original files have been deleted (or archived).
- The operator has run a week of new sessions without missing any facts.

The dual-store architecture is the new normal. Future memory writes follow the decision tree. Future memory reads use `omh memory recall` or `omh_memory(action="read")`. The operator's habits shift from "edit MEMORY.md" to "add a block to L0 with a label."

## Help

If the migration hits an unexpected snag:

1. Re-read [`08-troubleshooting.md`](08-troubleshooting.md).
2. Open an issue at https://github.com/anonymous99-Rise/oh-my-hermes-memory/issues with:
   - The operator's OS and Python version
   - The original memory format (paste a small sample, scrubbed of credentials)
   - The attempted migration steps
   - The exact error or unexpected behavior

The maintainer (`anonymous99-Rise`) responds within a day or two for clearly-described migrations.