# Case 1 — OMH Install on Windows 10

This example walks through the canonical install of OMH on a Windows 10 host running Hermes Agent desktop. It is the same scenario documented in [`docs/07-real-cases.md`](../../docs/07-real-cases.md), reproduced here as a self-contained worked example.

## Scenario

- Operator: an Hermes Agent desktop user on Windows 10
- Goal: install OMH plugin, get `omh doctor` reporting 30/30
- Date: 2026-07-28 (a fictional install date; the example is illustrative)

## Steps

### 1. Try the official install script

```bash
curl -fsSL https://raw.githubusercontent.com/rlaope/oh-my-hermes/main/install.sh | sh
```

Expected output:

```
OMH installer
Install oh-my-hermes without touching system Python packages.

      [note] Channel: preview
      [note] Source ref: main
      [note] Mode: venv
[1/3] Create isolated Python environment at /c/Users/Administrator/.local/share/omh/venv
      [ok] done
[2/3] Install OMH package
      [failed] Install OMH package
      sh: line 4: /c/Users/Administrator/.local/share/omh/venv/bin/python: No such file or directory
```

This is the WindowsApps python3 shim issue. The venv is not created even though `python3 -m venv` exits 0.

### 2. Switch to `uv venv`

```bash
uv venv --python 3.11 ~/.local/share/omh/venv
# or with a Windows-style path:
# uv venv --python 3.11 C:\Users\Administrator\.local\share\omh\venv
```

Expected output:

```
Using CPython 3.11.15
Creating virtual environment at: /c/Users/Administrator/.local/share/omh/venv
```

### 3. Install OMH via `uv pip`

```bash
uv pip install --python ~/.local/share/omh/venv/Scripts/python.exe \
    "https://github.com/rlaope/oh-my-hermes/archive/refs/heads/main.zip"
```

Expected output:

```
Resolved 1 package in 18.37s
   Building oh-my-hermes @ https://github.com/rlaope/oh-my-hermes/archive/refs/heads/main.zip
      Built oh-my-hermes @ https://github.com/rlaope/oh-my-hermes/archive/refs/heads/main.zip
Prepared 1 package in 15.90s
Installed 1 package in 269ms
 + oh-my-hermes==1.0.3 (from https://github.com/rlaope/oh-my-hermes/archive/refs/heads/main.zip)
```

### 4. Symlink `omh.exe` into `~/.local/bin`

```bash
ln -s ~/.local/share/omh/venv/Scripts/omh.exe ~/.local/bin/omh.exe
export PATH="$HOME/.local/bin:$PATH"
omh --version
# omh 1.0.3
```

### 5. Run `omh setup`

```bash
omh setup --scope user --full --yes --default-executor claude-code --language zh
```

### 6. Diagnose `omh doctor`

```bash
omh doctor
```

If the doctor reports 2 blocking issues around `plugin_manifest` and `plugin_bundle_current`, patch `omh/install/plugin_pack.py:216`:

```python
# Before
target.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
# After
target.write_bytes(item.read_bytes())
```

Then:

```bash
rm -rf ~/.local/share/omh/venv/Lib/site-packages/omh/install/__pycache__
omh setup --scope user --full --yes --default-executor claude-code --language zh --force
omh doctor
```

Expected final output:

```
OMH doctor complete.
Summary
  Status: ok
  Checks: 30/30 passing
  Issues: 0 blocking, 1 warning(s)
```

## Outcome

- OMH 1.0.3 installed.
- 92 workflow skills available.
- `omh doctor` 30/30 ok.
- PATH set: `omh` on Git Bash, PowerShell, cmd.exe.

## What the agent captures

```bash
omh memory block-set windows-env-quirks \
    --value "Windows env quirks (MSYS/Git-Bash + uv-managed Python 3.11.15 + Hermes): (1) WindowsApps python3 shim exits 0 from 'python3 -m venv' but creates no dir — use 'uv venv --python 3.11 <win-style-path>' + 'uv pip install', then verify dir exists. (2) pathlib.Path.write_text() injects CRLF on Windows and silently breaks byte-faithful SHA256 manifests — use write_bytes(read_bytes()) for any byte-faithful copy. (3) MSYS 'cmd //c ...' drops to interactive cmd — invoke /c/Windows/System32/cmd.exe /D /C directly with Windows-style paths. (4) After OMH install, omh/install/plugin_pack.py:216 was patched (write_text → write_bytes); re-apply after every omh update (gets reverted)." \
    --description "Windows MSYS/Python/PATH gotchas. Read on demand before any Python venv work or file copy on Windows." \
    --limit 2500 \
    --tier reference
```

```bash
omh memory block-set omh-install-state \
    --value "OMH install state: omh 1.0.3 from rlaope/oh-my-hermes archive (preview channel). scope=user, full profile (92 workflow skills + 4 ULW family), Claude Code default executor. OMH home: ~/.omh. Plugin bundle: ~/.hermes/plugins/omh (60 files, LF, manifest SHA-matched). PATH: omh on PATH in Git Bash / PowerShell / cmd.exe. Known Windows bug patched in place: omh/install/plugin_pack.py:216 was write_text → write_bytes (CRLF fix); re-apply after every omh update." \
    --description "OMH install details, paths, and known issues." \
    --limit 2500 \
    --tier reference
```

```bash
omh memory block-set cli-executors \
    --value "CLI executors authorized: omh 1.0.3, claude (Claude Code) 2.1.215, codex (Codex CLI) 0.145.0, hermes, uv 0.11.32. OMH default executor = claude-code. Routing: short/interactive → claude; long batch/CI/review → codex." \
    --description "Authorized CLI executors with paths, versions, and routing policy." \
    --limit 2500 \
    --tier reference
```

```bash
omh memory block-set env-baseline \
    --value "<contents of templates/env-baseline-system-block.md>" \
    --description "Complete environment baseline injected every turn via system tier." \
    --limit 5800 \
    --tier system
```

## What the operator should verify

```bash
python scripts/dual-store-status.py
```

Should print:

```
L1 (memory tool)
  MEMORY.md: 1085 / 2200 chars (49% used, headroom 1115)
  USER.md: 278 / 1375 chars (20% used, headroom 1097)

L0 (OMH project memory)
  candidates: 0
  approved_records: 4
  blocks:
    [system] env-baseline: 3376 / 5800
    [reference] windows-env-quirks: 914 / 2500
    [reference] wsl-kali-workflow: 964 / 2500
    [reference] cli-executors: 1096 / 2500
    [reference] omh-install-state: 1040 / 2500
    [reference] codegraph-integration: 1008 / 2500
  total system tier: 5392 chars (render budget 6000)
  total reference tier: 5022 chars (unlimited)

.env credentials:
  WSL_KALI_PWD (referenced in: wsl-kali-workflow, env-baseline)

Verdict
  Healthy. No action needed.
```

## Lessons

1. The WindowsApps `python3` shim does not create venvs. Use `uv venv`.
2. `omh/install/plugin_pack.py:216` has a CRLF bug on Windows. Patch it.
3. The dual-store architecture is what makes the long content (env baseline, install state, workflows) survive across sessions without character-limit pain.