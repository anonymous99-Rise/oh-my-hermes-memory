# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0] - 2026-07-28

### Added
- Complete dual-store memory architecture for Hermes Agent + OMH (oh-my-hermes)
- 10 documentation files covering architecture, decision trees, character limits, credential routing, block tiers, capture/approve flow, real cases, troubleshooting, migration, FAQ
- `memory-architect` skill with 8 reference files for progressive disclosure
- 3 utility scripts: `route-fact.py` (auto-decide where a fact belongs), `dual-store-status.py` (one-shot L0/L1 health), `apply-template.sh` (apply preset templates)
- 4 templates: env-baseline system block, user-workflow system block, MEMORY.md index entry, USER.md index entry
- 4 example cases covering OMH install, credential routing, multi-tier facts, migration from flat memory
- OMH integration as a git submodule pointing at `rlaope/oh-my-hermes`
- Initial author: anonymous99-Rise, derived from real-world usage on Windows 10 + Hermes desktop

### Notes
- This project does NOT modify OMH; it consumes OMH as a dependency.
- All memory writes go through review-first capture flow. The user (operator) approves every OMH project-memory candidate before it lands in `~/.omh/memory/`.
- Credentials never appear in any memory summary, chat message, or script literal. They live only in the user's local `~/.hermes/.env` file and are referenced by env var name.