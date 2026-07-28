# OMH Submodule (placeholder)

This directory should contain the OMH (oh-my-hermes) Python package source, vendored as a git submodule.

## Status

As of the initial commit (2026-07-28), the submodule was not initialized in this checkout due to GitHub network reliability issues during the build. The submodule is declared in `.gitmodules` at the root of this repository:

```ini
[submodule "submodule-omh"]
    path = submodule-omh
    url = https://github.com/rlaope/oh-my-hermes.git
    branch = main
```

## Initializing the submodule

After cloning this repository, run:

```bash
git submodule update --init --depth 1
```

This will populate `submodule-omh/` with the OMH source code.

## What is OMH?

OMH (oh-my-hermes) is the upstream project this repository depends on. It provides:

- The OMH Python package (installed by `omh setup`)
- The 92 workflow skills in `~/.omh/skills/`
- The OMH plugin bundle at `~/.hermes/plugins/omh/`
- The OMH memory subsystem (`omh memory ...`)

This repository consumes OMH; it does not modify OMH. The submodule is vendored only for offline reference.

## When to update the submodule

When OMH releases a new version:

```bash
cd submodule-omh
git fetch origin
git checkout main
cd ..
git add submodule-omh
git commit -m "chore: update OMH submodule"
```

OMH updates typically include new skills, new memory tools, and bug fixes. After updating the submodule, re-apply the `omh/install/plugin_pack.py:216` CRLF workaround (see [`docs/07-real-cases.md`](../docs/07-real-cases.md) Case 1).

## Reference

- OMH GitHub: https://github.com/rlaope/oh-my-hermes
- OMH docs: https://rlaope.github.io/oh-my-hermes/docs/
