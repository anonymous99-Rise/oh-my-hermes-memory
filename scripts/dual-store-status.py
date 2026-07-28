#!/usr/bin/env python3
"""
dual-store-status.py — Report the current state of the dual-store memory architecture.

Prints a dashboard of:
- L1 (memory tool): MEMORY.md / USER.md char counts and headroom
- L0 (OMH project memory): candidates, approved records, blocks by tier
- .env credentials referenced in memory surfaces
- Overall health verdict

Exit codes:
    0  Healthy
    1  Warning (one or more checks have issues but no immediate action required)
    2  Critical (one or more checks have blocking issues)

Usage:
    python scripts/dual-store-status.py
    python scripts/dual-store-status.py --json
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys


def home() -> pathlib.Path:
    return pathlib.Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or "~").expanduser()


def hermes_home() -> pathlib.Path:
    return pathlib.Path(os.environ.get("HERMES_HOME") or (home() / "AppData" / "Local" / "hermes")).expanduser()


def omh_home() -> pathlib.Path:
    return pathlib.Path(os.environ.get("OMH_HOME") or (home() / ".omh")).expanduser()


def safe_read_bytes(path: pathlib.Path) -> bytes:
    try:
        return path.read_bytes()
    except (OSError, FileNotFoundError):
        return b""


def safe_run(cmd: list, **kw) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, **kw)
        return result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def get_hermes_memory_files() -> dict:
    mem_dir = hermes_home() / "memories"
    out = {}
    for label, fname in [("MEMORY.md", "MEMORY.md"), ("USER.md", "USER.md")]:
        p = mem_dir / fname
        if p.exists():
            out[label] = {
                "path": str(p),
                "chars": len(safe_read_bytes(p)),
            }
        else:
            out[label] = {"path": str(p), "chars": 0}
    out["MEMORY.md"]["cap"] = 2200
    out["USER.md"]["cap"] = 1375
    out["MEMORY.md"]["headroom"] = max(0, out["MEMORY.md"]["cap"] - out["MEMORY.md"]["chars"])
    out["USER.md"]["headroom"] = max(0, out["USER.md"]["cap"] - out["USER.md"]["chars"])
    return out


def get_omh_status() -> dict:
    """Run `omh memory status --json` and parse the result."""
    out = safe_run(["omh", "memory", "status", "--json"])
    if not out:
        return {"available": False}
    try:
        return {"available": True, "data": json.loads(out)}
    except json.JSONDecodeError:
        return {"available": False, "raw": out}


def get_omh_blocks() -> dict:
    out = safe_run(["omh", "memory", "blocks"])
    if not out:
        return {"system": [], "reference": []}
    try:
        d = json.loads(out)
        return {
            "system": [b for b in d.get("blocks", []) if b.get("tier") == "system"],
            "reference": [b for b in d.get("blocks", []) if b.get("tier") == "reference"],
        }
    except json.JSONDecodeError:
        return {"system": [], "reference": []}


def get_env_credentials() -> dict:
    env_path = hermes_home() / ".env"
    if not env_path.exists():
        return {"path": str(env_path), "credentials": []}

    raw = safe_read_bytes(env_path).decode("utf-8", errors="replace")
    credentials = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key = line.split("=", 1)[0].strip()
            if re.match(r"^[A-Z][A-Z0-9_]*$", key):
                credentials.append(key)

    # Find which memory surfaces reference each credential
    refs = {}
    for cred in credentials:
        refs[cred] = []
        for tier in ["system", "reference"]:
            block_dir = omh_home() / "memory" / "blocks" / tier
            if block_dir.exists():
                for f in block_dir.glob("*.json"):
                    content = safe_read_bytes(f).decode("utf-8", errors="replace")
                    if cred in content:
                        refs[cred].append(f"{tier}/{f.stem}")

    return {
        "path": str(env_path),
        "credentials": [
            {"name": c, "referenced_in": refs.get(c, [])} for c in credentials
        ],
    }


def render_dashboard(hermes_mem: dict, omh_status: dict, omh_blocks: dict, env_creds: dict) -> tuple[str, int]:
    lines = []
    issues = []

    # L1
    lines.append("L1 (memory tool)")
    for label, data in hermes_mem.items():
        if "cap" in data:
            pct = (data["chars"] / data["cap"] * 100) if data["cap"] else 0
            lines.append(
                f"  {label}: {data['chars']} / {data['cap']} chars "
                f"({pct:.1f}% used, headroom {data['headroom']})"
            )
            if pct >= 90:
                issues.append(f"{label} is {pct:.1f}% full")
        else:
            lines.append(f"  {label}: {data['chars']} chars (no cap)")

    # L0
    lines.append("")
    lines.append("L0 (OMH project memory)")
    if not omh_status.get("available"):
        lines.append("  (omh memory status not available — is omh installed and on PATH?)")
        issues.append("omh CLI not reachable")
    else:
        d = omh_status.get("data", {})
        counts = d.get("counts", {})
        lines.append(f"  candidates: {counts.get('candidates', 0)}")
        lines.append(f"  approved_records: {counts.get('approved_records', 0)}")
        if counts.get("candidates", 0) > 50:
            issues.append(f"capture queue has {counts['candidates']} pending candidates (>50)")

        sys_total = 0
        lines.append("  blocks:")
        for b in omh_blocks.get("system", []):
            sys_total += b.get("chars", 0)
            lines.append(f"    [system] {b['label']}: {b['chars']} / {b.get('limit', '?')}")
        for b in omh_blocks.get("reference", []):
            lines.append(f"    [reference] {b['label']}: {b['chars']} / {b.get('limit', '?')}")
        if omh_blocks.get("system"):
            lines.append(f"  total system tier: {sys_total} chars (render budget 6000)")
            if sys_total > 6000:
                issues.append(f"system tier exceeds render budget ({sys_total} > 6000)")
        ref_total = sum(b.get("chars", 0) for b in omh_blocks.get("reference", []))
        lines.append(f"  total reference tier: {ref_total} chars (unlimited)")

    # .env
    lines.append("")
    lines.append(".env credentials")
    if not env_creds.get("credentials"):
        lines.append(f"  (none found at {env_creds.get('path', '?')})")
    else:
        lines.append(f"  path: {env_creds['path']}")
        for cred in env_creds["credentials"]:
            refs = cred["referenced_in"]
            ref_str = ", ".join(refs) if refs else "(not referenced in any memory surface)"
            lines.append(f"  {cred['name']}: referenced in {ref_str}")

    # Verdict
    lines.append("")
    lines.append("Verdict")
    if not issues:
        lines.append("  Healthy. No action needed.")
        verdict_code = 0
    elif any("exceeds render budget" in i or "CLI not reachable" in i for i in issues):
        lines.append(f"  Critical: {len(issues)} issue(s)")
        for issue in issues:
            lines.append(f"    - {issue}")
        verdict_code = 2
    else:
        lines.append(f"  Warning: {len(issues)} issue(s)")
        for issue in issues:
            lines.append(f"    - {issue}")
        verdict_code = 1

    return "\n".join(lines), verdict_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Report dual-store memory architecture status.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    hermes_mem = get_hermes_memory_files()
    omh_status = get_omh_status()
    omh_blocks = get_omh_blocks()
    env_creds = get_env_credentials()

    if args.json:
        payload = {
            "hermes_memory": hermes_mem,
            "omh_status": omh_status,
            "omh_blocks": omh_blocks,
            "env_credentials": env_creds,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    else:
        output, code = render_dashboard(hermes_mem, omh_status, omh_blocks, env_creds)
        print(output)
        return code


if __name__ == "__main__":
    sys.exit(main())