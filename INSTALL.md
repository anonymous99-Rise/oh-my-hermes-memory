# INSTALL

Three ways to install the `memory-architect` skill into your Hermes Agent. Pick the one that matches your setup.

## Path 1 — One-liner install via `hermes skills install` (recommended)

The fastest path. Hermes fetches the SKILL.md directly from the public GitHub raw URL and installs it into your local skills directory.

```bash
hermes skills install https://raw.githubusercontent.com/anonymous99-Rise/oh-my-hermes-memory/main/skills/memory-architect/SKILL.md --yes
```

This installs the SKILL.md and any references under it. After the command succeeds, restart your Hermes session so the skill loader picks up the new skill.

If your Hermes session is already running, the new skill becomes visible after a fresh session start. The CLI itself does not need a restart.

## Path 2 — Install from a GitHub tap

If you have a working GitHub API path (no proxies that block `api.github.com`):

```bash
hermes skills tap add anonymous99-Rise/oh-my-hermes-memory
hermes skills install anonymous99-Rise/oh-my-hermes-memory/skills/memory-architect --yes
```

This registers the repository as a skill source ("tap") and then installs the skill from the tap. Future `hermes skills update` calls will pull from this tap automatically.

## Path 3 — Clone the repo and link locally

For developers, offline environments, or anyone who wants full control over upgrades:

```bash
git clone https://github.com/anonymous99-Rise/oh-my-hermes-memory.git ~/code/oh-my-hermes-memory
mkdir -p ~/.hermes/skills/memory-architect
ln -s ~/code/oh-my-hermes-memory/skills/memory-architect/SKILL.md ~/.hermes/skills/memory-architect/SKILL.md
ln -s ~/code/oh-my-hermes-memory/skills/memory-architect/references ~/.hermes/skills/memory-architect/references
```

To upgrade later:

```bash
cd ~/code/oh-my-hermes-memory
git pull
```

The skill picks up the latest content on the next Hermes session.

## Verify the install

After any of the three paths, verify the skill is installed:

```bash
hermes skills list | grep memory-architect
```

You should see `memory-architect` listed with source `local` and status `enabled`.

## Verify the install is complete

The skill consists of one `SKILL.md` plus eight `references/*.md` files. All nine must be present:

```bash
ls -1 ~/.hermes/skills/memory-architect/
# SKILL.md
# references/

ls -1 ~/.hermes/skills/memory-architect/references/
# 01-when-to-use.md
# 02-dual-store.md
# 03-decision-tree.md
# 04-credential-routing.md
# 05-block-tiers.md
# 06-capture-approve.md
# 07-real-cases.md
# 08-troubleshooting.md
```

If a file is missing, re-run the install with `--force`:

```bash
hermes skills install https://raw.githubusercontent.com/anonymous99-Rise/oh-my-hermes-memory/main/skills/memory-architect/SKILL.md --force --yes
```

## Update the skill

The skill is versioned with the OMH-memory project. To pick up the latest version:

- **Path 1 / Path 2**: re-run the install command. Hermes will overwrite the existing skill files.
- **Path 3**: `git pull` in `~/code/oh-my-hermes-memory`. The symlinks pick up the new content automatically.

There is no automatic update mechanism. Operators upgrade manually when they want the latest content.

## Uninstall

```bash
rm -rf ~/.hermes/skills/memory-architect
```

If you used Path 3 with symlinks, also `rm` the clone directory if you no longer need it:

```bash
rm ~/code/oh-my-hermes-memory
```

## Use the skill

In a Hermes chat session, invoke the skill by triggering its description phrase. The SKILL.md description starts with "Use when designing or auditing a Hermes Agent memory architecture." so any request that mentions memory, dual-store, or architecture triggers a load.

Example invocations:

- "Remember that I prefer Chinese responses." (the agent loads `memory-architect` to decide how to write the fact).
- "Where should I store the WSL Kali credential?" (the agent loads to consult the credential routing rules).
- "Audit my current memory architecture." (the agent loads to run the dual-store status check).

The skill is just one tool in the agent's toolbox. It does not auto-run. The agent loads it when the task matches the trigger.

## Companion files

The skill is the entry point. The full project lives at https://github.com/anonymous99-Rise/oh-my-hermes-memory and includes:

- `docs/` — 10 long-form documents covering every aspect of the dual-store architecture in detail.
- `scripts/` — `route-fact.py` (suggest tier for a new fact), `dual-store-status.py` (one-shot health check), `apply-template.sh` (apply preset templates).
- `templates/` — 4 ready-to-paste templates for env-baseline, user-workflow, and L1 index entries.
- `examples/` — 4 worked cases (OMH install, credential routing, multi-tier facts, migration from flat memory).

Install the skill first; consult the companion files only when the skill's references are insufficient.