---
name: secure-my-profile
description: Password-hide a Hermes personal profile from TUI/Desktop.
version: 0.2.0
author: Ahmed, Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [security, profiles, privacy, vault, personal]
    category: security
    related_skills: []
    requires_tools: [terminal]
required_environment_variables:
  - name: VAULT_PASSWORD
    prompt: Vault password (personal profile lock/unlock)
    help: "Entered via Hermes secure secret dialog — never typed into chat. Used once then scrubbed."
    required_for: "hide / show / setup / change-password"
  - name: VAULT_NEW_PASSWORD
    prompt: New vault password (setup or change-password)
    help: "Only for setup --force or change-password. Secure dialog only; never chat."
    required_for: "setup (new password) / change-password"
    optional: true
---

# Secure My Profile

Password-gated hide/show for one Hermes **named profile** (default slug `personal`). When hidden, the profile directory is moved out of `~/.hermes/profiles/` so TUI and Desktop stop listing it. Unlock restores it after password check.

This is a **skill** (slash `/secure-my-profile`), not a Hermes core plugin. Real work lives in `scripts/secure_profile.py`.

## When to Use

- You share a VPS shell/Desktop with others and want a personal profile off the list when idle.
- Bootstrap a personal profile + vault in one flow.
- Lock (`hide`) / unlock (`show`) that profile with a password **from this chat** (Desktop/TUI secure dialog) or a local TTY.
- Change the vault password later.

**Not** for: encrypting the whole disk, multi-user OS isolation, or locking the default `~/.hermes` profile.

## How password entry works (chat-safe)

Hermes already has a **secure secret path** the model never sees:

1. Skill frontmatter declares `VAULT_PASSWORD` under `required_environment_variables`.
2. On `/secure-my-profile …` (or `skill_view`), if the var is missing, Desktop/TUI opens a **`secret.request` masked overlay** (same system used for skill API keys).
3. The value is stored only for the process / dotenv passthrough — **not** injected into the model prompt, tool args, or assistant text.
4. The agent runs `secure_profile.py`, which reads `VAULT_PASSWORD` from the environment, verifies the PBKDF2 hash, then **scrubs** `VAULT_PASSWORD` / `VAULT_NEW_PASSWORD` from process env and `~/.hermes/.env`.
5. Next lock/unlock re-prompts. Nothing is saved to memory, SKILL notes, or ByteRover.

```text
You  ──slash──►  Hermes skill load
                   │
                   ├─ secret.request overlay (masked; model never sees value)
                   │     │
                   │     ▼
                   │  env VAULT_PASSWORD  (ephemeral)
                   │
                   ▼
              secure_profile.py hide|show
                   │  PBKDF2 verify vs vault/vault.env
                   │  move profile  profiles/ ↔ vault/stashed/
                   ▼
              scrub VAULT_* from env + .env
```

**Telegram / Discord / plain messaging:** Hermes will **not** collect secrets in-band (`gateway_setup_hint`). Use **Desktop, TUI, or local CLI**, or a trusted SSH shell with env injection you control.

**Never** paste the password into the chat composer as normal text — that would enter the session transcript and the model context.

## Prerequisites

- Hermes installed (`hermes` on PATH) for profile create / gateway stop.
- Python 3.10+ (stdlib only: no pip packages).
- Run lock/unlock from the **default** agent — not while `HERMES_HOME` is the secured profile.
- Desktop/TUI (or local TTY) for password capture. Messaging-only gateways cannot safely collect the password.

## How to Run

Always invoke the script with `terminal`; never invent passwords or write them into files/chat/memory.

Resolve the skill directory from the load banner (`[Skill directory: …]`), then:

```bash
python3 "<SKILL_DIR>/scripts/secure_profile.py" <command> [flags]
```

| User intent | Command |
|---|---|
| First-time bootstrap | `... setup` or `... setup --slug personal` |
| Check state (no password needed if already set up) | `... status` |
| Hide / lock | `... hide` (alias: `lock`) |
| Show / unlock | `... show` (alias: `unlock`) |
| Rotate password | `... change-password` |

Optional setup flags: `--force`, `--no-create-profile`, `--hide-now`, `--slug NAME`.

Chat/Desktop: complete the **secure secret dialog** when Hermes prompts for `VAULT_PASSWORD` (and `VAULT_NEW_PASSWORD` when rotating). Do not put the password on argv.

Trusted local shell only: `VAULT_PASSWORD=…` (never log it). Setup without TTY slug: `VAULT_PROFILE=personal`.

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

1. Confirm you are **not** inside the secured profile (`hermes profile` / banner). Default or any other named profile is fine.
2. User runs `/secure-my-profile setup` (or you run the script after skill load).
3. Desktop/TUI: complete secure dialog for **new** vault password (`VAULT_PASSWORD` and/or `VAULT_NEW_PASSWORD`). TTY: script prompts twice via getpass.
4. Script writes `~/.hermes/vault/`, stores **hash only**, runs `hermes profile create <slug>` if missing, then **scrubs** password env.
5. Report paths from script output. **Do not** echo, paraphrase, or store the password. **Do not** call `memory` / `brv_curate` about the password.

If setup already exists and user wants redo: add `--force`.

### 2. Status (password optional)

```bash
python3 "<SKILL_DIR>/scripts/secure_profile.py" status
```

If Hermes still opens a secret dialog because `VAULT_PASSWORD` is declared, the user may **skip** it — status does not need the password. Never invent a password to “satisfy” setup.

### 3. Hide

```bash
python3 "<SKILL_DIR>/scripts/secure_profile.py" hide
```

Flow: secure password capture (if needed) → PBKDF2 verify → best-effort gateway stop → move profile to `vault/stashed/` → stub alias → update config → **scrub password env**.

### 4. Show

```bash
python3 "<SKILL_DIR>/scripts/secure_profile.py" show
```

Flow: secure password capture → verify → restore to `profiles/` → restore alias → print `hermes -p <slug> chat` → **scrub**.

### 5. Change password

```bash
python3 "<SKILL_DIR>/scripts/secure_profile.py" change-password
```

Needs **current** `VAULT_PASSWORD` and **new** `VAULT_NEW_PASSWORD` (chat: two secure dialogs / env values; TTY: interactive prompts). Non-interactive mode refuses to reuse the current password as the new one.

## Safety rules for the agent

1. **Never** put the password in argv, SKILL notes, memory, ByteRover, chat replies, or tool-call argument strings.
2. **Never** ask the user to paste the password as a normal chat message. Prefer Hermes **secret.request** (skill env capture) or a real TTY `getpass`.
3. After any password-bearing command, the script scrubs env; do **not** re-export or re-save `VAULT_PASSWORD`.
4. If the user is on Telegram/Discord only: explain they must run hide/show from **Desktop / TUI / local CLI** (or trusted SSH). Do not collect the password in messaging chat.
5. If hide/show refuses because `HERMES_HOME` is the secured profile: tell them switch away first (`hermes profile use default` or open another profile).
6. After hide/show, suggest restarting Hermes Desktop if the profile list looks stale.
7. Read `references/security.md` before promising “encrypted” or “unbreakable.”
8. Wrong password → report script error only; do not retry by guessing; do not log attempted secrets.

## Pitfalls

- **Default profile cannot be secured** — only a named profile under `profiles/`.
- **Shared root access** still sees `~/.hermes/vault/stashed/` — hide-from-list, not full crypto.
- **Hermes secret capture normally persists API keys** in `.env`; this skill **deliberately scrubs** `VAULT_PASSWORD` after each run so unlock is one-shot.
- **Status + required env**: skill load may offer a secret dialog; user can skip for status-only.
- **Alias stub**: `~/.local/bin/<slug>` prints “locked” while hidden; restored on show.
- **Sticky default**: if sticky pointed at the secured profile, hide resets it to `default`.
- **Wrong home**: install under the **default** Hermes skills tree so `/secure-my-profile` works while personal is stashed.

## Verification

```bash
python3 "<SKILL_DIR>/scripts/secure_profile.py" status
# setup_complete: true

hermes profile list
# after hide: secured slug must NOT appear as a named profile
# after show: slug appears again

# Password must not linger (no matches expected):
grep -E '^(VAULT_PASSWORD|VAULT_NEW_PASSWORD)=' ~/.hermes/.env || true
```

Wrong password must exit non-zero with `error: wrong password` and must not move directories.

After install or SKILL.md edits: new session or skill rescan so `/secure-my-profile` picks up `required_environment_variables`.
