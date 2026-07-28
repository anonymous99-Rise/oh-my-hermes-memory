# 08 — Troubleshooting

This document is the troubleshooting runbook. When something goes wrong with the dual-store memory architecture, look here first. The entries are organized by symptom, with diagnosis and resolution steps.

## "Memory tool rejects my add with character limit error"

Symptom:

```
Memory at 1,985/2,200 chars. Adding this entry (450 chars) would exceed the limit.
Consolidate now: use 'replace' to merge overlapping entries...
```

Diagnosis: the entry is too long for the L1 surface.

Resolution:

1. Move the long content to an L0 reference-tier block: `omh memory block-set <label> --value "..." --tier reference --limit 5000`.
2. In L1 MEMORY.md, add a pointer: `See L0 reference block <label>.`
3. The pointer is ~50 chars, well within the 2,200-char cap.

## "My OMH record is silently truncated to 240 chars"

Symptom: an `omh memory approve` succeeds, but the persisted record's `summary` is 240 chars regardless of what you submitted.

Diagnosis: `_redact(value)` in `omh/workflows/memory.py` line 1400 returns `value[:240]` for non-sensitive content and `"[redacted]"` for sensitive content. The 240-char limit is hard.

Resolution:

1. If the content is short enough to fit in 240 chars, rephrase. Remove filler words.
2. If the content is longer, route to a reference-tier block. Records are not the right surface for long content.

## "My OMH record is redacted to [redacted]"

Symptom: the candidate's `summary` is the literal string `[redacted]` (10 chars).

Diagnosis: OMH's safety layer detected a trigger substring (`secret`, `token`, `password`, `private-key`, `api_key`, `apikey`).

Resolution:

1. Identify which substring triggered the redaction. The summary will give hints.
2. Rephrase the summary to avoid the trigger. See [`04-credential-routing.md`](04-credential-routing.md) for substitutions.
3. Re-capture. Approve if the new summary passes.

## "My OMH block-set fails with 'is X chars against a Y-char limit'"

Symptom:

```
omh: error: block 'my-label' is 5,500 chars against a 5,000-char limit
```

Diagnosis: the `--value` exceeds the `--limit`.

Resolution:

1. Raise the limit: `omh memory block-set <label> --value "..." --limit 6000`. The limit is operator-controlled.
2. Or split the content into two related blocks (e.g. `my-label-part1` and `my-label-part2`).
3. Or shorten the content. Often a long value can be cut by 20% without losing meaning.

## "My system-tier block does not appear in the system prompt"

Symptom: I wrote a system-tier block with `omh memory block-set <label> --tier system ...`. It does not appear in the next session's system prompt.

Diagnosis: the 6,000-char system-tier render budget is exhausted.

Resolution:

1. Run `omh memory blocks --tier system` and look at the `chars` column. Identify blocks that exceed the budget.
2. Move the largest block to reference tier: re-write with `--tier reference`.
3. Or compress existing system-tier blocks.
4. Re-run the session. The block should now appear.

## "I cannot find an approved record with omh memory recall"

Symptom: `omh memory recall "my query"` returns nothing, but I know the record exists.

Diagnosis: OMH recall uses deterministic keyword matching. The query tokens must appear in the record's `summary` field.

Resolution:

1. Read the record directly: `cat ~/.omh/memory/records/mem_*.json` and find the `summary` field.
2. Identify the tokens in the summary.
3. Re-run the recall query with those tokens.
4. If the record is critical, add a pointer to it in a system-tier block. Future sessions find it via the pointer, not via recall.

## "hermes journey delete says 'memory index N out of range'"

Symptom: `hermes journey delete memory:memory:1 --yes` returns `memory index 1 out of range`.

Diagnosis: the `memory:memory:N` index is 0-based, but the user assumed 1-based.

Resolution: list with `hermes journey list` to see the actual index. Use the correct index. Alternatively, use the Hermes memory tool with `action="remove"` and the entry's content hash.

## "OMH plugin manifest shows invalid SHA"

Symptom: `omh doctor` reports `plugin_manifest: invalid` and `plugin_bundle_current: invalid`.

Diagnosis: the SHA-256 of an installed plugin file does not match the SHA in the plugin manifest. Common causes:
- Line endings changed between source and installed (LF vs CRLF)
- A file was edited after the manifest was generated
- The manifest was generated against a different package version than what was installed

Resolution:

1. If the issue is line endings: see Case 1 in [`07-real-cases.md`](07-real-cases.md). The fix is to patch `omh/install/plugin_pack.py:216` to use binary mode.
2. If a file was edited: revert the edit, or run `omh setup --force` to regenerate.
3. If the package version mismatched: run `omh update && omh install && omh setup --force`.

## "My ~/.hermes/.env is not loaded"

Symptom: I appended `WSL_KALI_PWD=spacex` to `~/.hermes/.env`, but a fresh shell shows `WSL_KALI_PWD: unbound variable`.

Diagnosis: Hermes reads `.env` at startup. A fresh shell that does not inherit Hermes's environment does not see the variable.

Resolution:

- If the agent is running inside Hermes, the variable should be visible. Restart Hermes to pick up the new value.
- If a standalone shell is sourcing `.env`, use `set -a; source ~/.hermes/.env; set +a` to load it.
- If you need the variable in a script, `source ~/.hermes/.env` first.

## "OMH memory status shows high candidate backlog"

Symptom: `omh memory status` shows `candidates: 100+`.

Diagnosis: the agent is capturing faster than the operator is approving. The review queue is growing.

Resolution:

1. `omh memory review --limit 100` to see the backlog.
2. Approve or reject in bulk. The `omh memory approve` and `omh memory reject` commands each take one candidate at a time; consider writing a small script to batch.
3. Consider whether the agent is over-capturing. Tighten the decision tree: only capture facts that are durable and needed.

## "I cannot read ~/.hermes/.env from the agent"

Symptom: the agent tries to read `~/.hermes/.env` and gets `Access denied`.

Diagnosis: Hermes intercepts reads of `~/.hermes/.env` with a hard "Access denied" error because it is marked as a credential store.

Resolution:

- This is by design. The agent must read individual env vars via `os.environ.get('KEY_NAME')` or shell-native `$KEY_NAME`, with explicit operator approval.
- If the agent has a legitimate need to read a specific credential, the operator must approve the read in this session.
- Do not work around the protection by copying the file or chmod-ing it. The protection is at the agent level, not the filesystem level.

## "Memory tool writes work but the change does not persist"

Symptom: I called `memory add "..."` and got a success message. The next session does not show the entry.

Diagnosis: Hermes writes to `~/.hermes/memories/MEMORY.md` synchronously, but the system prompt render reads the file at session start. If the file was edited after session start, the running session does not pick it up.

Resolution:

- This is correct behavior. The agent does not see memory writes within the same session. The next session sees them.
- If you need to verify the write: `cat ~/.hermes/memories/MEMORY.md` to see the file content directly.

## "omh memory block-remove returns 'removed: false'"

Symptom:

```json
{"label": "my-block", "removed": false, "tier": "system"}
```

Diagnosis: the block was created with `--tier reference`, but `block-remove` defaults to `--tier system`. The label and tier do not match.

Resolution:

```bash
omh memory block-remove my-block --tier reference
```

If unsure which tier, list first:

```bash
omh memory blocks
# Look for the block in the output; the tier is shown.
```

## "OMH provider status shows 'package_absent'"

Symptom: `hermes memory status` reports `Plugin: omh` but `Provider: omh` with `available` and the OMH plugin's `omh_memory` tool returns `package_absent` or similar.

Diagnosis: the OMH Python package is not importable from the Hermes process environment. This can happen if:
- OMH was installed in a venv that Hermes does not use
- Hermes's own venv shadows the OMH venv
- A dependency is missing

Resolution:

1. Verify OMH is installed: `omh --version`. If that works, the package is installed somewhere.
2. Verify the OMH plugin bundle is in `~/.hermes/plugins/omh/`. If it is missing, re-run `omh setup --force`.
3. Restart Hermes. The plugin loader caches state at startup.

## "I have too many reference-tier blocks"

Symptom: `omh memory blocks --tier reference` returns 50+ blocks. The index in the system prompt is large.

Diagnosis: scope creep. The operator has accumulated too many procedures.

Resolution:

1. `omh memory sync` to find stale blocks (the tool has its own staleness logic for records; for blocks, the operator is the curator).
2. Cull: `omh memory block-remove <label> --tier reference` for blocks that no longer apply.
3. Group: combine related blocks under a single label. E.g. `windows-env-quirks-python` and `windows-env-quirks-shell` → `windows-env-quirks`.
4. Migrate: if you have hundreds of blocks, OMH is the wrong tool. Use a real database (SQLite + sqlite-vec, mnemosyne).

## "I cannot tell which surface a fact should go to"

Symptom: a new fact comes up, and I do not know whether it belongs in L1, L0 system tier, L0 reference tier, or `.env`.

Resolution: walk the decision tree in [`02-decision-tree.md`](../docs/02-decision-tree.md). The first question (Q0: is this a credential?) is the most important. If the answer is yes, route to `.env` immediately.

If after walking the tree you are still unsure, route to L0 reference tier. Reference tier is the safest default — content there is preserved without being injected every turn, and the operator can promote it to system tier later if needed.

## "I lost an approved record I wanted to keep"

Symptom: I rejected a candidate by mistake. It is gone from `~/.omh/memory/records/`.

Diagnosis: rejection is permanent in the sense that the record does not move to `records/`, but the candidate stays in `candidates/` with `status: "rejected"`. The content is recoverable from the candidate file.

Resolution:

1. `ls ~/.omh/memory/candidates/` to find the rejected candidate.
2. Read it: `cat ~/.omh/memory/candidates/cand_<id>.json`.
3. Re-capture with a new summary if needed.

## "I need to migrate from one OMH version to another"

Symptom: I want to upgrade OMH from 1.0.3 to 1.1.0 (or whatever the next version is).

Resolution:

1. Back up `~/.omh/memory/`:
   ```bash
   tar czf omh-memory-backup-$(date +%Y-%m-%d).tar.gz ~/.omh/memory/
   ```
2. Run `omh update`. This pulls the latest version.
3. Run `omh install`. This refreshes the skill pack.
4. Re-apply the `omh/install/plugin_pack.py:216` patch. It is reverted on every update.
5. Run `omh doctor`. Verify 30/30 passing.
6. Run `omh setup --force` if `omh doctor` flags any manifest issues.
7. Verify memory surfaces: `omh memory status`, `cat ~/.hermes/memories/MEMORY.md`.

## "I forgot which env var holds a credential"

Symptom: I need to use a credential but cannot remember the env var name.

Diagnosis: the env var name is in memory somewhere, but the operator does not know where.

Resolution:

1. `grep -E "^[A-Z_]+=" ~/.hermes/.env` to list all env var names.
2. `hermes journey --json | python3 -c "import json, sys; d=json.load(sys.stdin); [print(e['body']) for e in d.get('memory', [])]"` to dump L1 content.
3. `omh memory blocks | python3 -c "import json, sys; ..."` to dump L0 block labels and descriptions.
4. The credential's metadata (env var name, purpose) is in one of these surfaces. The literal value is only in `.env`.

## Emergency recovery

If the dual-store architecture is corrupted beyond normal troubleshooting:

1. **Do not panic.** The data is on disk. It is recoverable.
2. **Back up first.** `cp -r ~/.hermes/memories ~/.omh/memory ~/.hermes/.env /tmp/recovery-backup-$(date +%Y-%m-%d)/`.
3. **Inspect manually.** Each memory file is JSON. Read it.
4. **Re-create the architecture.** Start with `~/.hermes/.env`, then L1 MEMORY.md and USER.md, then L0 blocks and records. The CLI tools can re-write everything; the data does not need to be re-typed.
5. **If OMH is broken.** Reinstall OMH (`uv pip install --force-reinstall ...`). OMH does not depend on memory content for its own operation.

## When in doubt, read the source

The OMH source is at:

```
~/.local/share/omh/venv/Lib/site-packages/omh/
```

Key files:

- `omh/workflows/memory.py` — capture, review, approve, reject, recall, status
- `omh/memory_blocks.py` — block-set, block-remove, blocks list, render
- `omh/memory_provider.py` — provider subsystem, render_pack
- `omh/commands/memory.py` — CLI entry point
- `omh/commands/memory_parser.py` — argparse definitions

If a behavior is unclear, read the source. The architecture is small enough that one afternoon of source reading gives the operator full understanding.

## Reporting issues upstream

If you find a bug in OMH (like the `plugin_pack.py:216` line-ending issue), report it at:

```
https://github.com/rlaope/oh-my-hermes/issues
```

Include:
- OMH version (`omh --version`)
- Operating system and Python version
- Exact command that produced the bug
- Exact output (including any traceback)
- Workaround you applied

The maintainer (`rlaope`) is responsive. The patch in this project is one possible workaround; the upstream fix may differ.