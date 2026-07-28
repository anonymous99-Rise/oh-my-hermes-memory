#!/usr/bin/env python3
"""
route-fact.py — Suggest which memory surface a new fact should land in.

This script does NOT write anything. It suggests the destination tier
and prints the exact command to capture / write the fact. The operator
still has to approve the write.

Usage:
    python scripts/route-fact.py --text "User prefers Chinese responses" --frequency every
    python scripts/route-fact.py --text "Build command requires FOO=1" --frequency occasional
    python scripts/route-fact.py --text "GitHub PAT" --sensitive

Options:
    --text TEXT         The fact to route (required).
    --frequency FREQ    How often the fact is needed: every, occasional, rare (default: occasional).
    --sensitive         Flag that the fact contains a credential.
    --size CHARS        Size of the fact in characters (default: auto-detect).
    --json              Emit machine-readable JSON instead of human-readable text.

Exit codes:
    0  Success (suggestion printed).
    1  Invalid arguments.
    2  The fact contains a credential (operator should route to .env instead).
"""

import argparse
import json
import re
import sys


# OMH safety layer trigger substrings (from omh/workflows/memory.py line 1410)
TRIGGER_SUBSTRINGS = ("secret", "token", "password", "private-key", "api_key", "apikey")

# Common credential patterns
CREDENTIAL_PATTERNS = [
    re.compile(r"\bsk-[a-zA-Z0-9-_]{20,}"),                # OpenAI/Anthropic keys
    re.compile(r"\bghp_[a-zA-Z0-9]{30,}"),                  # GitHub PAT
    re.compile(r"\bxox[baprs]-[a-zA-Z0-9-]{10,}"),          # Slack tokens
    re.compile(r"\bAIza[0-9A-Za-z-_]{35}"),                # Google API keys
    re.compile(r"\bAKIA[0-9A-Z]{16}"),                      # AWS access keys
    re.compile(r"\bgh[oprsu]_[a-zA-Z0-9]{30,}"),             # GitHub other tokens
    re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),  # JWT
]


def detect_credential(text: str) -> bool:
    """Return True if the text looks like a credential value or workflow description."""
    lowered = text.lower()
    if any(t in lowered for t in TRIGGER_SUBSTRINGS):
        return True
    for pattern in CREDENTIAL_PATTERNS:
        if pattern.search(text):
            return True
    return False


def detect_size(text: str) -> int:
    """Return the size of the text in characters."""
    return len(text)


def suggest_tier(args) -> dict:
    """Return the suggested tier and command based on the input."""
    text = args["text"]
    frequency = args["frequency"]
    sensitive = args.get("sensitive", False)
    size = args.get("size") or detect_size(text)

    # Q0: is this a credential?
    is_credential = sensitive or detect_credential(text)
    if is_credential:
        return {
            "tier": "env-only",
            "reason": "credential detected (sensitive flag or trigger substring). Values live in ~/.hermes/.env.",
            "command": None,
            "next_steps": [
                "Append KEY_NAME=<value> to ~/.hermes/.env (operator-only write).",
                "Capture the workflow in an L0 reference-tier block, referencing the env var by name.",
            ],
        }

    # Q1: is it needed every session?
    if frequency == "every":
        # Q2: can it fit in 240 chars?
        if size <= 240:
            # Q4: system tier budget — we can't know the running total without reading OMH,
            # so we suggest an L0 approved record (which is also fine).
            return {
                "tier": "L0 approved record",
                "reason": "needed every session, fits in 240 chars",
                "command": (
                    f'omh memory capture --type fact --tag <tag1> --tag <tag2> '
                    f'--source "agent-2026-07-28" --source-ref "<ref>" "{text}"'
                ),
                "next_steps": [
                    "Run the suggested capture command.",
                    "Surface the candidate to the operator for review.",
                    "Operator runs `omh memory review <candidate_id>` then `omh memory approve <candidate_id>`.",
                    "If the fact is truly needed every session and is short, the operator may promote it to a system-tier block.",
                ],
            }

        # Q4 / Q5: longer than 240, system tier or reference tier?
        return {
            "tier": "L0 system-tier block (or reference-tier if not every session)",
            "reason": "needed every session, longer than 240 chars (record summary hard cap)",
            "command": (
                f'omh memory block-set <label> --value "{text}" '
                f'--description "<one-line purpose>" --limit <cap, e.g. 5800> --tier system'
            ),
            "next_steps": [
                "Before writing, run `omh memory blocks --tier system` to check the render budget.",
                "If the budget is exhausted, route to reference tier instead.",
                "Run the suggested block-set command.",
                "Add a pointer in L1 MEMORY.md.",
            ],
        }

    # Q3: one-off event?
    if frequency == "rare" and size > 240:
        return {
            "tier": "do not store",
            "reason": "rarely needed and longer than 240 chars; use session_search instead",
            "command": None,
            "next_steps": [
                "If this fact is genuinely durable, capture it as an L0 reference-tier block.",
                "If it's a one-off event, do not store it. The session transcript is searchable via session_search.",
            ],
        }

    # Q3: one-off event or process log?
    if frequency == "rare" and size <= 240:
        return {
            "tier": "do not store",
            "reason": "rarely needed; the fact is ephemeral or already in the session transcript",
            "command": None,
            "next_steps": [
                "If the operator explicitly wants this captured, run `omh memory capture` with a stable tag.",
                "Otherwise, do not store. session_search will find it in the transcript if needed.",
            ],
        }

    # Default: occasional, not every session
    if size <= 240:
        return {
            "tier": "L0 approved record",
            "reason": "durable, not needed every session, fits in 240 chars",
            "command": (
                f'omh memory capture --type fact --tag <tag1> --tag <tag2> '
                f'--source "agent-2026-07-28" --source-ref "<ref>" "{text}"'
            ),
            "next_steps": [
                "Run the suggested capture command.",
                "Surface the candidate to the operator for review.",
                "Operator runs `omh memory review <candidate_id>` then `omh memory approve <candidate_id>`.",
            ],
        }

    return {
        "tier": "L0 reference-tier block",
        "reason": "durable, not needed every session, longer than 240 chars (record summary hard cap)",
        "command": (
            f'omh memory block-set <label> --value "{text}" '
            f'--description "<one-line purpose>" --limit <cap, e.g. 5000> --tier reference'
        ),
        "next_steps": [
            "Run the suggested block-set command.",
            "Verify the write: `omh memory blocks | grep <label>`.",
            "Add a pointer in L1 MEMORY.md if the block is referenced often.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Suggest which memory surface a fact should land in."
    )
    parser.add_argument("--text", required=True, help="The fact to route.")
    parser.add_argument(
        "--frequency",
        choices=["every", "occasional", "rare"],
        default="occasional",
        help="How often the fact is needed.",
    )
    parser.add_argument(
        "--sensitive",
        action="store_true",
        help="Flag that the fact contains a credential.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=None,
        help="Size of the fact in characters (default: auto-detect from --text).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    suggestion = suggest_tier(
        {
            "text": args.text,
            "frequency": args.frequency,
            "sensitive": args.sensitive,
            "size": args.size,
        }
    )

    if args.json:
        print(json.dumps(suggestion, indent=2, ensure_ascii=False))
    else:
        print(f"Suggested tier: {suggestion['tier']}")
        print(f"Reason: {suggestion['reason']}")
        if suggestion["command"]:
            print(f"\nCommand:\n  {suggestion['command']}")
        if suggestion["next_steps"]:
            print("\nNext steps:")
            for step in suggestion["next_steps"]:
                print(f"  - {step}")

    if suggestion["tier"] == "env-only":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())