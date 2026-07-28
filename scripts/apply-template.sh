#!/usr/bin/env bash
# apply-template.sh — Apply a preset template to OMH project memory.
#
# Usage:
#   ./scripts/apply-template.sh <template-name>
#
# Templates:
#   env-baseline       - L0 system-tier block with the canonical env baseline
#   user-workflow      - L0 system-tier block with the canonical user workflow
#   memory-index       - L1 MEMORY.md index entry that points at the L0 blocks
#   user-index         - L1 USER.md index entry that points at the L0 blocks
#   all                - Apply all of the above
#
# This script does NOT modify OMH. It prints the omh memory block-set
# commands so the operator can review before running them. To actually
# apply, pass --apply (operator-only).
#
# Options:
#   --apply            Run the commands instead of printing them.
#   --dry-run          Print what would be done without doing anything (default).

set -euo pipefail

TEMPLATES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/templates"

usage() {
    cat <<EOF
Usage: $0 <template-name> [--apply|--dry-run]

Templates:
  env-baseline       L0 system-tier block with the canonical env baseline
  user-workflow      L0 system-tier block with the canonical user workflow
  memory-index       L1 MEMORY.md index entry
  user-index         L1 USER.md index entry
  all                All of the above

Options:
  --apply            Run the commands instead of just printing them
  --dry-run          Print only (default)
EOF
}

apply_template() {
    local name="$1"
    local apply_mode="$2"

    case "$name" in
        env-baseline)
            local desc="Complete environment baseline injected every turn via system tier. Hosts, paths, CLI executors, WSL Kali workflow, OMH install state, codegraph integration, memory architecture."
            local value="$(cat "$TEMPLATES_DIR/env-baseline-system-block.md")"
            local cmd=(omh memory block-set env-baseline --value "$value" --description "$desc" --limit 5800 --tier system)
            if [[ "$apply_mode" == "apply" ]]; then
                "${cmd[@]}"
            else
                printf 'omh memory block-set env-baseline \\\n    --value "<contents of templates/env-baseline-system-block.md>" \\\n    --description "%s" \\\n    --limit 5800 \\\n    --tier system\n' "$desc"
            fi
            ;;
        user-workflow)
            local desc="User workflow preferences + memory policy + update cadence. Injected every turn via system tier."
            local value="$(cat "$TEMPLATES_DIR/user-workflow-system-block.md")"
            local cmd=(omh memory block-set user-workflow-preferences --value "$value" --description "$desc" --limit 5800 --tier system)
            if [[ "$apply_mode" == "apply" ]]; then
                "${cmd[@]}"
            else
                printf 'omh memory block-set user-workflow-preferences \\\n    --value "<contents of templates/user-workflow-system-block.md>" \\\n    --description "%s" \\\n    --limit 5800 \\\n    --tier system\n' "$desc"
            fi
            ;;
        memory-index)
            local value="$(cat "$TEMPLATES_DIR/index-entry-memory.md")"
            if [[ "$apply_mode" == "apply" ]]; then
                # Use the memory tool. Since this is a Bash script, we can't
                # call the memory tool directly. The operator must run this
                # in their Hermes chat session.
                cat <<EOF
To apply the MEMORY.md index entry, paste the following into your Hermes chat:
---
$value
---
The chat will use the memory tool to write it.
EOF
            else
                cat <<EOF
The MEMORY.md index entry would be:
---
$value
---
EOF
            fi
            ;;
        user-index)
            local value="$(cat "$TEMPLATES_DIR/index-entry-user.md")"
            if [[ "$apply_mode" == "apply" ]]; then
                cat <<EOF
To apply the USER.md index entry, paste the following into your Hermes chat:
---
$value
---
The chat will use the memory tool to write it.
EOF
            else
                cat <<EOF
The USER.md index entry would be:
---
$value
---
EOF
            fi
            ;;
        all)
            apply_template env-baseline "$apply_mode"
            apply_template user-workflow "$apply_mode"
            apply_template memory-index "$apply_mode"
            apply_template user-index "$apply_mode"
            ;;
        *)
            echo "Unknown template: $name" >&2
            usage
            exit 1
            ;;
    esac
}

main() {
    if [[ $# -lt 1 ]]; then
        usage
        exit 1
    fi

    local template_name="$1"
    shift

    local apply_mode="dry-run"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --apply)
                apply_mode="apply"
                shift
                ;;
            --dry-run)
                apply_mode="dry-run"
                shift
                ;;
            *)
                echo "Unknown option: $1" >&2
                usage
                exit 1
                ;;
        esac
    done

    apply_template "$template_name" "$apply_mode"
}

main "$@"