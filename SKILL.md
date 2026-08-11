---
name: secure-my-profile
description: Password-hide a Hermes personal profile from TUI/Desktop.
version: 0.1.0
author: Ahmed, Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [security, profiles, privacy, vault, personal]
    category: security
    related_skills: []
    requires_tools: [terminal]
---

# Secure My Profile

Password-gated hide/show for one Hermes **named profile** (default slug `personal`). When hidden, the profile directory is moved out of `~/.hermes/profiles/` so TUI and Desktop stop listing it. Unlock restores it after password check.

This is a **skill** (slash `/secure-my-profile`), not a Hermes core plugin. Real work lives in `scripts/secure_profile.py`.

## When to Use

- You share a VPS shell/Desktop with others and want a personal profile off the list when idle.
- Bootstrap a personal profile + vault in one flow.
- Lock (`hide`) / unlock (`show`) that profile with a password.
- Change the vault password later.

**Not** for: encrypting the whole disk, multi-user OS isolation, or locking the default `~/.hermes` profile.

## Prerequisites

- Hermes installed (`hermes` on PATH) for profile create / gateway stop.
- Python 3.10+ (stdlib only: no pip packages).
- Run lock/unlock from the **default** agent — not while `HERMES_HOME` is the secured profile.
- Interactive TUI/CLI for password prompts. Messaging gateways cannot safely collect the password; tell the user to run from local TUI, or use `VAULT_PASSWORD` only on a trusted local shell.

## How to Run

Always invoke the script; never invent passwords or write them into files/chat.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/secure_profile.py" <command> [flags]
```

| User intent | Command |
|---|---|
| First-time bootstrap | `... setup` or `... setup --slug personal` |
| Check state | `... status` |
| Hide / lock | `... hide` (alias: `lock`) |
| Show / unlock | `... show` (alias: `unlock`) |
| Rotate password | `... change-password` |

Optional setup flags: `--force`, `--no-create-profile`, `--hide-now`, `--slug NAME`.

Non-interactive local only: `VAULT_PASSWORD=...` (never log it). Profile slug override for setup without TTY: `VAULT_PROFILE=personal`.

## Quick Reference

```text
/secure-my-profile setup
/secure-my-profile status
/secure-my-profile hide
/secure-my-profile show
/secure-my-profile change-password
```

On-disk (default home only — always reachable when personal is locked):

```text
~/.hermes/vault/config.json      # non-secret state
~/.hermes/vault/vault.env        # chmod 600: salt + PBKDF2 hash only
~/.hermes/vault/stashed/<slug>/  # profile lives here when hidden
~/.hermes/profiles/<slug>/       # profile lives here when visible
```

## Procedure

### 1. Setup (first use)

1. Confirm you are on the **default** profile (`hermes profile` / banner).
2. Run:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/secure_profile.py" setup
```

3. Script asks for profile slug (default `personal`) and password twice.
4. It writes `~/.hermes/vault/`, stores **hash only**, and runs `hermes profile create <slug>` if missing.
5. Report paths from script output. Do not echo the password.

If setup already exists and user wants redo: add `--force`.

### 2. Status (no password)

```bash
python3 "${HERMES_SKILL_DIR}/scripts/secure_profile.py" status
```

### 3. Hide

```bash
python3 "${HERMES_SKILL_DIR}/scripts/secure_profile.py" hide
```

Script: password check → best-effort gateway stop → move profile to `vault/stashed/` → stub alias → update config.

### 4. Show

```bash
python3 "${HERMES_SKILL_DIR}/scripts/secure_profile.py" show
```

Script: password check → restore to `profiles/` → restore alias → print `hermes -p <slug> chat`.

### 5. Change password

```bash
python3 "${HERMES_SKILL_DIR}/scripts/secure_profile.py" change-password
```

## Safety rules for the agent

1. **Never** put the password in the command line argv, SKILL notes, memory, or chat.
2. Prefer interactive terminal so `getpass` can run; do not scrape password from user message into a file.
3. If the user is on Telegram/Discord only: explain they must run setup/hide/show from local TUI/CLI (or a trusted SSH session with `VAULT_PASSWORD`).
4. If hide/show refuses because `HERMES_HOME` is the secured profile: tell them `hermes profile use default` first.
5. After hide/show, suggest restarting Hermes Desktop if the profile list looks stale.
6. Read `references/security.md` for the threat model before promising “encrypted” or “unbreakable.”

## Pitfalls

- **Default profile cannot be secured** — only a named profile under `profiles/`.
- **Shared root access** still sees `~/.hermes/vault/stashed/` — this is hide-from-list, not full crypto.
- **Alias stub**: `~/.local/bin/<slug>` prints “locked” while hidden; restored on show.
- **Sticky default**: if sticky pointed at the secured profile, hide resets it to `default`.
- **Wrong home**: always use default Hermes skills install so `/secure-my-profile` works while personal is stashed.

## Verification

```bash
python3 "${HERMES_SKILL_DIR}/scripts/secure_profile.py" status
# setup_complete: true

hermes profile list
# after hide: secured slug must NOT appear as a named profile
# after show: slug appears again
```

Wrong password must exit non-zero with `error: wrong password` and must not move directories.

After install: `/reload-skills` (or new session) so `/secure-my-profile` is registered.
