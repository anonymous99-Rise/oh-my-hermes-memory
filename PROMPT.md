# PROMPT

Copy the entire contents of this file into a fresh Hermes Agent chat session (or paste the block under "The Prompt" below). The agent will execute the steps and report back.

## What this prompt does

This prompt sets up the complete dual-store memory architecture for your Hermes Agent. It assumes:

- Hermes Agent is installed (`hermes` command on PATH).
- OMH (oh-my-hermes) is installed and `omh doctor` reports healthy.
- The `memory-architect` skill from this project is already in `~/.hermes/skills/memory-architect/`.

If any of those is missing, the agent will tell you which prerequisite to address first.

## The Prompt

Copy everything between the lines that say `START COPYING HERE` and `STOP COPYING HERE`:

---

START COPYING HERE

You are setting up the dual-store memory architecture for this Hermes Agent. The project is at https://github.com/anonymous99-Rise/oh-my-hermes-memory. The full skill is already installed at `~/.hermes/skills/memory-architect/` (verify with `ls ~/.hermes/skills/memory-architect/`). Do the following in order:

## Phase 1 — Verify prerequisites

1. Confirm `hermes --version` works. If not, stop and tell the user to install Hermes.
2. Confirm `omh --version` works and `omh doctor` reports 30/30 ok. If `omh` is not on PATH, tell the user to run:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```
   and add that line to `~/.bashrc` (Git Bash) and `~/Documents/PowerShell/Microsoft.PowerShell_profile.ps1` (PowerShell). If `omh doctor` reports any blocking issue, stop and ask the user to fix it before continuing.
3. Confirm the skill is installed:
   ```bash
   ls ~/.hermes/skills/memory-architect/
   ```
   Expected: `SKILL.md` and `references/` directory. If missing, tell the user to run:
   ```bash
   hermes skills install https://raw.githubusercontent.com/anonymous99-Rise/oh-my-hermes-memory/main/skills/memory-architect/SKILL.md --yes
   ```
4. Clone the full project (needed for scripts, templates, and `git submodule update`):
   ```bash
   git clone https://github.com/anonymous99-Rise/oh-my-hermes-memory.git ~/code/oh-my-hermes-memory
   cd ~/code/oh-my-hermes-memory && git submodule update --init --depth 1
   ```

## Phase 2 — Apply the canonical system-tier blocks

The two system-tier blocks carry every-session meta-information. Both must land before any other writes.

5. Apply the env-baseline block:
   ```bash
   cd ~/code/oh-my-hermes-memory
   VALUE=$(cat templates/env-baseline-system-block.md)
   omh memory block-set env-baseline --value "$VALUE" --description "Complete environment baseline injected every turn via system tier." --limit 5800 --tier system
   ```
   Customize the placeholders first if needed (replace `<HOSTNAME>`, `<DISTRO>`, `<USERNAME>`, `<VAR_NAME>` etc. with real values).

6. Apply the user-workflow block:
   ```bash
   cd ~/code/oh-my-hermes-memory
   VALUE=$(cat templates/user-workflow-system-block.md)
   omh memory block-set user-workflow-preferences --value "$VALUE" --description "User workflow preferences + memory policy + update cadence. Injected every turn via system tier." --limit 5800 --tier system
   ```
   Customize the language, response style, and routing preferences.

7. Verify the system-tier render budget:
   ```bash
   omh memory blocks --tier system
   ```
   Total chars must be ≤ 6000. If over budget, ask the user which block to move to reference tier.

## Phase 3 — Apply the reference-tier blocks

The five reference-tier blocks carry the long procedures and environment notes.

8. Apply each reference-tier block:
   ```bash
   cd ~/code/oh-my-hermes-memory
   for label in windows-env-quirks wsl-kali-workflow cli-executors omh-install-state codegraph-integration; do
     # Skip if already exists
     if [ ! -f ~/.omh/memory/blocks/reference/$label.json ]; then
       # The reference-tier block values are derived from the corresponding docs/ file
       case $label in
         windows-env-quirks)
           VALUE=$(sed -n '/^## Windows env quirks/,/^## /p' docs/01-architecture-overview.md | head -n 30)
           ;;
         wsl-kali-workflow)
           VALUE=$(cat docs/04-credential-routing.md | head -n 60)
           ;;
         cli-executors)
           VALUE=$(grep -A 30 "CLI executors" docs/01-architecture-overview.md | head -n 30)
           ;;
         omh-install-state)
           VALUE=$(grep -A 50 "OMH install" docs/01-architecture-overview.md | head -n 50)
           ;;
         codegraph-integration)
           VALUE=$(cat docs/07-real-cases.md | grep -B 2 -A 30 "codegraph" | head -n 50)
           ;;
       esac
       omh memory block-set $label --value "$VALUE" --description "$(grep -A 3 $label docs/01-architecture-overview.md | head -n 1)" --limit 2500 --tier reference
     fi
   done
   ```
   If any block exceeds 2500 chars, raise the `--limit` flag accordingly.

9. Verify the reference-tier blocks:
   ```bash
   omh memory blocks --tier reference
   ```
   Expected: 5 blocks listed.

## Phase 4 — Apply the L1 index entries

L1 (MEMORY.md and USER.md) hold only pointers to the L0 blocks. Keep them small.

10. Write the MEMORY.md index entry via the `memory` tool. Paste this in your chat (you, the operator, not the agent — because `memory` tool calls go through Hermes chat):
    > `memory add "Memory index — L1 pointer to L0. Complete text lives in OMH system-tier blocks (env-baseline, user-workflow-preferences) and reference-tier blocks (windows-env-quirks, wsl-kali-workflow, cli-executors, omh-install-state, codegraph-integration). L0 approved records cover omh-memory-mechanism, pathb-deadend, omh-doctor-target, codegraph-init-pattern. Credentials live in ~/.hermes/.env. Update policy: omh update → omh install → re-apply plugin_pack.py:216 patch → omh doctor → omh setup --force."`

11. Write the USER.md index entry the same way:
    > `memory add "User pointer — full workflow preferences in OMH system-tier block user-workflow-preferences. Key reminders: Chinese responses; Claude Code or Codex CLI freely, pick by task fit; WSL Kali for Linux ops; credentials via env var; memory policy review-first."`

## Phase 5 — Capture the atomic-fact records

These four records are the short atomic facts that round out the architecture.

12. For each fact below, run `omh memory capture` then `omh memory approve`:
    ```bash
    # Capture 1
    omh memory capture --type fact --tag memory-architecture --tag dual-store --source "agent-2026-07-28" --source-ref "PROMPT.md" \
      "OMH dual-store memory: L0 project memory at ~/.omh/memory/ holds complete text; L1 (MEMORY.md/USER.md) holds index only. L0 long facts via block-set --tier reference; short atomic via capture → review → approve. Credentials in ~/.hermes/.env, never in memory."
    # Note the candidate_id, then:
    omh memory approve <candidate_id>

    # Capture 2
    omh memory capture --type fact --tag pathb --tag warning --source "agent-2026-07-28" --source-ref "PROMPT.md" \
      "OMH path B is broken and must NOT be retried. Command: 'hermes skills install rlaope/oh-my-hermes/skills/oh-my-hermes --yes' returns 404. The 92 OMH skills are already registered correctly via path A."
    omh memory approve <candidate_id>

    # Capture 3
    omh memory capture --type fact --tag health-check --tag omh-doctor --source "agent-2026-07-28" --source-ref "PROMPT.md" \
      "omh doctor target = 30/30 checks passing, 0 blocking. Run weekly. If blocking: follow Fix: hints, usually 'omh setup --force' recovers. Warning (not blocking) for plugin_runtime_observed is normal until Hermes restarts."
    omh memory approve <candidate_id>

    # Capture 4
    omh memory capture --type procedure --tag codegraph --tag init-pattern --source "agent-2026-07-28" --source-ref "PROMPT.md" \
      "codegraph is installed but no repo indexed. Before using codegraph_explore / codegraph_node MCP tools on a project, run 'codegraph init <path>' then 'codegraph index <path>', or 'codegraph sync' for incremental."
    omh memory approve <candidate_id>
    ```

## Phase 6 — Credentials

Credentials do NOT go in memory. They go in `~/.hermes/.env`. The agent MUST NOT write credential values to any memory surface or chat message.

13. Ask the operator if they want any credentials added to `~/.hermes/.env`. For each credential:
    a. Tell the operator the env var name to use (e.g. `WSL_KALI_PWD`).
    b. Tell the operator to append the line manually:
       ```bash
       echo 'WSL_KALI_PWD=<value>' >> ~/.hermes/.env
       ```
    c. Capture the workflow (env var name, usage, safety rules) as a reference-tier block. Do NOT capture the value.
    d. Update the L1 index entry to mention the new env var name.

If the operator does not want credentials added, skip this phase.

## Phase 7 — Verify

14. Run the diagnostic script:
    ```bash
    cd ~/code/oh-my-hermes-memory
    python scripts/dual-store-status.py
    ```
    Expected output:
    - L1 MEMORY.md: ~1000 / 2200 chars
    - L1 USER.md: ~250 / 1375 chars
    - L0 approved_records: 4
    - L0 system-tier blocks: 2 (env-baseline, user-workflow-preferences) totaling ~5000 chars
    - L0 reference-tier blocks: 5
    - Verdict: Healthy. No action needed.

15. Run `omh doctor` one more time. Should report 30/30 ok, 0 blocking.

## Phase 8 — Report

16. Tell the operator:
    - What was written (which blocks, which records, what L1 indices).
    - What the operator still needs to do manually (e.g. append credentials to `.env`).
    - What to do next (e.g. "restart Hermes so the skill loader picks up the new skill; in your next session, ask me 'audit my memory architecture' and I will run the diagnostic").

STOP COPYING HERE

## After pasting the prompt

The agent will execute the phases in order. It will:

- Verify the prerequisites.
- Apply the system-tier blocks.
- Apply the reference-tier blocks.
- Surface candidate IDs for you to approve.
- Tell you which credential lines to add to `~/.hermes/.env`.
- Run the diagnostic script and report the result.

If any step fails, the agent stops at that phase and tells you what to fix. It does not silently skip failures.

## Customizing

The prompt above assumes the canonical configuration described in this project's `templates/`. To customize:

- **Different language**: edit `templates/user-workflow-system-block.md` before Phase 2 step 6.
- **Different CLI executors**: edit `templates/env-baseline-system-block.md` before Phase 2 step 5.
- **Additional credentials**: skip Phase 6 and add credentials manually, then re-run Phase 7 to verify.
- **Fewer or more reference-tier blocks**: edit Phase 3 to match your actual needs.

## When to re-run this prompt

Re-run the prompt when:

- You install OMH on a new machine and want the same memory architecture.
- You upgrade OMH and want to verify the architecture is intact.
- You want to migrate from a flat-memory setup to dual-store.

The prompt is idempotent: blocks that already exist are skipped (`if [ ! -f ... ]; then` check in Phase 3).

## What this prompt does NOT do

This prompt does not:

- Bypass the review-first approval flow. Every `omh memory capture` requires you to run `omh memory approve`.
- Write credential values. The agent tells you what to write; you write it.
- Migrate from non-OMH memory systems (mnemosyne, Penfield, retaindb). For those, see `docs/09-migration-guide.md`.
- Configure `auto_approve_safe`. The policy stays at the default `false`.
- Add any tool or skill beyond `memory-architect`. The skill set is fixed.

## See also

- `INSTALL.md` — three install paths for the skill itself.
- `docs/01-architecture-overview.md` — the architecture in long form.
- `docs/02-decision-tree.md` — when to write to which tier.
- `docs/04-credential-routing.md` — the `.env` boundary.
- `docs/06-capture-approve-flow.md` — the review-first flow.