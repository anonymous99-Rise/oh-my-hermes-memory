Memory index — L1 pointer to L0. Complete text lives in OMH system-tier blocks (rendered every turn via OMH memory provider) and reference-tier blocks (on-demand read via omh_memory tool action=read label=X).

L0 system blocks (auto-injected every turn, ~5392 chars total / 6000 budget):
- env-baseline: host, shells, Python, WSL Kali, CLI executors, OMH install, codegraph integration, memory architecture
- user-workflow-preferences: language, executor routing, shell routing, OMH profile, memory policy, update cadence

L0 reference blocks (read on demand via omh memory blocks → omh memory read): windows-env-quirks, wsl-kali-workflow, cli-executors, omh-install-state, codegraph-integration.

L0 approved records (omh memory recall <query>): omh-memory-mechanism, pathb-deadend, omh-doctor-target, codegraph-init-pattern.

Credentials: stored as env var WSL_KALI_PWD (value spacex) in the Hermes env file. Reference as ${WSL_KALI_PWD}; never put literal value anywhere.

Update policy: omh update → omh install → re-apply plugin_pack.py:216 patch → omh doctor → omh setup --force.

---

To use this template, customize the labels and credential names, then write via the memory tool in Hermes chat:

    memory add "<file content>"

The memory tool will write it to MEMORY.md as a single entry. Adjust the size to fit under the 2,200-char cap.