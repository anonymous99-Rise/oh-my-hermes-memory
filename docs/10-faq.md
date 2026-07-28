# 10 — FAQ

This document answers the questions most operators ask when they first encounter the dual-store architecture. The answers are short. For deep dives, follow the cross-references.

## "Why three surfaces and not one?"

Three surfaces exist because each has a different strength:

| Surface | Strength |
|---|---|
| `~/.hermes/.env` | Holds credential values; auto-loaded into `os.environ` |
| L1 (`MEMORY.md` / `USER.md`) | Auto-injected into the system prompt; tracked via `useCount`; editable via `hermes journey` |
| L0 (OMH project memory) | Unlimited size (no character cap on blocks); review-first approval; durable and recoverable |

If you only used one surface, you would either:

- Hit the 2,200 / 1,375 char hard cap (L1 only)
- Run out of the 6,000-char system-tier render budget (L0 system tier only)
- Have to put credentials in chat (no `.env` boundary)
- Have no audit trail (no review-first approval)

Three surfaces is the minimum-viable configuration that respects all four real constraints.

See [`01-architecture-overview.md`](01-architecture-overview.md) for the full reasoning.

## "Is this the same as AGENTS.md / CLAUDE.md?"

No. AGENTS.md and CLAUDE.md are project-level instruction files. They tell the agent *how to behave in this project*. They are not memory surfaces; they are configuration files.

The dual-store architecture is for *facts the agent should remember*, not *instructions the agent should follow*. The two are complementary.

## "Why not just use a real database (SQLite, etc.)?"

A real database is the right choice if:

- You have hundreds of facts
- You need semantic search (not just keyword matching)
- You need cross-device sync
- You need versioning or time-travel queries

OMH project memory is a JSON-on-disk store. It scales to hundreds of facts without trouble. It does not provide semantic search. It does not provide cross-device sync.

If you outgrow OMH, see [`09-migration-guide.md`](09-migration-guide.md) for paths to mnemosyne, Penfield, or a custom SQLite + sqlite-vec setup.

## "Why not auto-approve memory writes?"

Auto-approve sounds convenient. It is dangerous.

Reasons:

1. The agent's mental model of what is "important to remember" diverges from the operator's mental model within weeks. Auto-approve lets the agent silently accumulate memory that the operator does not want.
2. Once memory is auto-approved, the operator does not see what is being written. The audit trail is gone.
3. Auto-approve makes credential leaks more likely. The review-first step is the natural place to catch a credential value accidentally written to memory.

The dual-store architecture defaults to `auto_approve_safe: false` and `mode: review-first`. The operator must explicitly approve every memory write. This is intentional.

If the operator wants to delegate a category of facts (e.g. "auto-approve any fact about installed Python packages"), they can do so with explicit per-session delegation. The default is no delegation.

## "How does this relate to OpenClaw?"

It does not. OpenClaw is a separate AI operating system with its own memory architecture (`~/.openclaw/workspace/MEMORY.md`, `memory/YYYY-MM-DD.md`, `.learnings/`, `DREAMS.md`). OpenClaw and Hermes do not share memory surfaces.

If you use both, keep them separate. The dual-store architecture is for Hermes + OMH only.

## "What happens if OMH is uninstalled?"

If OMH is uninstalled:

- The OMH plugin (`~/.hermes/plugins/omh/`) is removed.
- The OMH MCP tools (`omh_status`, `omh_recommend`, etc.) are removed.
- The OMH project memory (`~/.omh/memory/`) remains on disk but is no longer accessible to Hermes.
- L1 MEMORY.md / USER.md remain on disk and are still injected into the system prompt.

If the operator reinstalls OMH, the project memory comes back. If the operator does not, the L1 surfaces still work (they are independent of OMH).

The migration away from OMH (back to a flat L1-only setup) is straightforward: see [`09-migration-guide.md`](09-migration-guide.md).

## "What's the difference between a system-tier block and an L1 entry?"

Both are auto-injected into the system prompt on every turn. The differences are:

| | L1 MEMORY.md entry | L0 system-tier block |
|---|---|---|
| Cap | 2,200 chars per entry | 6,000 chars total render budget across all system-tier blocks |
| Injected by | Hermes memory tool | OMH memory provider |
| Format | Plain markdown | XML-ish wrapper |
| Curation | `hermes journey list / inspect / edit / delete` | `omh memory block-set / block-remove / blocks` |
| useCount tracking | Yes | No |
| Pin | Yes | No (workaround: keep a pointer in another system block) |

Use L1 for content that benefits from `useCount` tracking and the `hermes journey` interface. Use L0 system-tier for content that pairs naturally with OMH artifacts.

## "What if I want to store a credential in OMH anyway?"

Don't.

The credential routing rule ([`04-credential-routing.md`](04-credential-routing.md)) is non-negotiable. Credentials live only in `~/.hermes/.env`. The OMH safety layer will redact credentials anyway, but the rule exists because:

1. The safety layer is a tripwire, not a wall. It can be bypassed by block values.
2. Once a credential is in OMH memory, removing it requires manual intervention.
3. The audit trail of a leaked credential is harder to reconstruct if it went through OMH.

If you have a legitimate use case that seems to require a credential in OMH, the answer is to redesign the use case. Reference the credential by env var name.

## "Why is the system-tier render budget 6,000 chars?"

It is the default in `omh/memory_blocks.py`. The constant is `DEFAULT_SYSTEM_RENDER_BUDGET_CHARS = 6000`. There is no setting to change it; it is hardcoded.

In practice, 6,000 chars accommodates 2–3 medium-sized system blocks (env baseline + user preferences + memory architecture itself). If you need more, distribute the content across reference-tier blocks and keep the system-tier blocks as a tight index.

## "Can I have multiple system-tier blocks of the same label?"

No. Block labels must be unique. The `block-set` command refuses to create a duplicate:

```
omh: error: a block with label 'my-label' already exists
```

To replace a block, use `block-set` again with the same label. The new value overwrites the old.

To have two blocks with similar content, use different labels (e.g. `cli-executors` and `cli-executors-routing`).

## "What is the difference between 'capture' and 'block-set'?"

| | `capture` | `block-set` |
|---|---|---|
| Output | Candidate in `~/.omh/memory/candidates/` | Block in `~/.omh/memory/blocks/{system,reference}/` |
| Approval required | Yes (operator approves) | No (operator writes directly) |
| Truncation | 240 chars via `_redact` | None (per-block `--limit` enforced) |
| Use for | Atomic facts (≤ 240 chars) | Long procedures, content > 240 chars |

Use `capture` for atomic facts you want the operator to review. Use `block-set` for long content you have already decided to write.

## "How do I know if a fact is atomic enough for capture?"

A fact is atomic enough if it can be written in a single sentence under 240 characters without losing meaning. Examples:

- "User prefers Chinese responses." (atomic)
- "OMH path B is broken — don't retry." (atomic)
- "User prefers concise responses with structured status updates; verbose paragraphs are discouraged." (atomic, 130 chars)

Examples of non-atomic facts that should be blocks instead:

- "WSL Kali workflow: distro kali-linux WSL 2. Default login user spacex..." (long procedure)
- "Windows MSYS quirks: (1) python3 shim issue, (2) write_text CRLF injection, (3) cmd //c pattern breaks..." (long procedure)
- "codegraph integration: codegraph 1.5.0 installed at... MCP servers registered in claude, codex, hermes..." (long procedure)

## "Why does OMH redact summaries with the word 'password' even when no credential is involved?"

False positives are accepted as a cost of preventing true positives. The OMH safety layer is intentionally aggressive. If your summary needs to mention authentication without being redacted, use these substitutions:

- `password` → `authentication`, `auth`, `credential`, `login`
- `secret` → `credential`, `env var`, `private data`
- `token` → `credential`, `env var`, `authentication value`
- `private-key` → `SSH credential`, `signing key`
- `api_key` → `API credential`, `env var`
- `apikey` → `API credential`, `env var`

See [`04-credential-routing.md`](04-credential-routing.md) for the full substitution table.

## "How do I share my dual-store memory with another operator?"

You don't. The dual-store memory is per-operator. Each operator has their own `~/.hermes/` and `~/.omh/`.

If you want to share facts with another operator:

1. Document the fact in a shared document (e.g. a wiki page, a team handbook).
2. The other operator reads the document and writes the fact into their own dual-store architecture.

Sharing memory surfaces directly is not a feature of the architecture. It is by design — memory is personal context, not shared state.

## "What's the smallest viable dual-store setup?"

The minimum setup is:

- `~/.hermes/.env` — at least one credential
- L1 MEMORY.md — a single index entry of ≤ 2,200 chars pointing at…
- L0 system-tier block — `env-baseline` with the actual content

This is the smallest configuration that demonstrates the architecture. It scales up from here.

## "What's the largest viable dual-store setup?"

Practical upper bounds:

- 50 system-tier blocks (render budget exhausted past this)
- 500 reference-tier blocks (render index becomes unwieldy past this)
- 1,000 approved records (operator review queue becomes unwieldy past this)

Past these limits, migrate to a real database. See [`09-migration-guide.md`](09-migration-guide.md) for migration paths.

## "How does this scale across multiple Hermes sessions?"

Each session sees the same memory surfaces, populated with the same content. There is no per-session memory partition by default. If the operator wants per-session memory, use `omh memory capture --scope-kind thread --scope-ref <thread-id>`.

If the operator runs multiple Hermes surfaces (desktop + Telegram + Discord), each surface can have a different OMH scope. The default is `scope-kind: project`, which is global. Use `scope-kind: target --scope-ref <surface-name>` for per-surface memory.

## "Can I export my dual-store memory?"

Yes. The directory `~/.omh/memory/` is self-contained. Back it up with `tar czf`:

```bash
tar czf omh-memory-backup-$(date +%Y-%m-%d).tar.gz ~/.omh/memory/
```

L1 memory is at `~/.hermes/memories/`. Include that in the backup too:

```bash
tar czf hermes-memory-backup-$(date +%Y-%m-%d).tar.gz ~/.hermes/memories/
```

`.env` is at `~/.hermes/.env`. Include that separately and store it encrypted:

```bash
gpg -c ~/.hermes/.env
# Creates ~/.hermes/.env.gpg; delete the plaintext after
```

## "Can I import memory from another tool?"

Yes, with caveats. See [`09-migration-guide.md`](09-migration-guide.md) for the migration paths from mnemosyne, Penfield, retaindb, and custom file-based systems.

The migration is non-destructive. Both systems coexist until the operator verifies the new architecture.

## "What's the future of this project?"

The project's scope is intentionally narrow. It documents and packages a specific architecture for a specific use case (Hermes + OMH on a single operator's machine). Future directions may include:

- A Python library that automates the decision tree (the `scripts/route-fact.py` script is the seed)
- A `omh memory migrate` command that takes a directory of legacy memory and routes each fact to the correct tier
- A `omh memory audit` command that scores the operator's memory architecture for consistency

These are not in scope today. The maintainer welcomes PRs that add them.

## "Where do I report bugs?"

- This project's bugs: https://github.com/anonymous99-Rise/oh-my-hermes-memory/issues
- OMH bugs (e.g. the `plugin_pack.py:216` line-ending issue): https://github.com/rlaope/oh-my-hermes/issues
- Hermes Agent bugs: https://github.com/nousresearch/hermes-agent/issues

When reporting a bug, include:

- The exact command that produced the bug
- The exact output (including any traceback)
- The OS and Python version
- The relevant version numbers (`omh --version`, `hermes --version`)

## "How can I contribute?"

PRs welcome. The project is small. Before opening a PR:

1. Read the existing docs to understand the architecture.
2. Open an issue describing the change you want to make.
3. Keep PRs focused — one architectural concern per PR.
4. Run `python scripts/dual-store-status.py` before and after your change to verify nothing is broken.

## "Is this project affiliated with Nous Research or the Hermes Agent team?"

No. This is a personal project by `anonymous99-Rise` that consumes Hermes Agent and OMH as dependencies. It is not affiliated with, endorsed by, or supported by Nous Research or the maintainers of `rlaope/oh-my-hermes`.

Issues with Hermes Agent or OMH should be filed in their respective repositories, not here.