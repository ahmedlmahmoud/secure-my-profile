# secure-my-profile

**Password-hide a Hermes personal profile from TUI & Desktop.**

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) skill that bootstraps a personal profile, stores only a salted password hash, and **moves the profile out of Hermes’ scan path** when locked — so shared shell / Desktop users don’t see it in the profile list.

```text
/secure-my-profile setup   → create vault + profile
/secure-my-profile hide    → lock (off the list)  ← password via secure dialog
/secure-my-profile show    → unlock (back on the list)
/secure-my-profile status  → is it locked?
```

On **Hermes Desktop / TUI**, the password is collected with the built-in **`secret.request`** masked overlay (model never sees it). The CLI then verifies a PBKDF2 hash and **scrubs** `VAULT_PASSWORD` so it is not memorized in `.env`.

> **Platforms:** macOS & Linux · **Python:** 3.10+ (stdlib only) · **Hermes:** profiles under `~/.hermes`

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-blue)](#)
[![Hermes](https://img.shields.io/badge/Hermes-skill-purple)](https://github.com/NousResearch/hermes-agent)

---

## Why this exists

Hermes profiles are great for multi-mission agents, but **there is no built-in way to lock or hide a profile** from TUI/Desktop. If family or teammates share the same VPS account, every profile is visible.

`secure-my-profile` is a practical fix for **casual shared access**:

| Problem | What this skill does |
| --- | --- |
| Profile shows in Desktop / `hermes profile list` | Moves it to `~/.hermes/vault/stashed/` |
| Password in skill files / chat / memory | Never — only PBKDF2 hash in `vault.env`; chat uses Hermes secret dialog + one-shot scrub |
| Personal agent offline while locked | Vault lives on the **default** home so `/secure-my-profile show` still works |
| Accidental open via `~/.local/bin/<slug>` | Replaces alias with a “locked” stub |

**Not** full multi-user OS isolation or disk encryption. Root (or anyone with full home access) can still open the stash. See [Threat model](#threat-model).

---

## Install

### Option A — clone into default Hermes skills (recommended)

The skill must live under the **default** Hermes home so it still works when the personal profile is locked:

```bash
mkdir -p ~/.hermes/skills/security
git clone https://github.com/ahmedlmahmoud/secure-my-profile.git \
  ~/.hermes/skills/security/secure-my-profile
```

Start a **new Hermes session** (or your client’s skill rescan) so `/secure-my-profile` appears.

### Option B — run the CLI directly from a checkout

```bash
git clone https://github.com/ahmedlmahmoud/secure-my-profile.git
cd secure-my-profile
python3 scripts/secure_profile.py setup
python3 scripts/secure_profile.py status
```

---

## Quick start

Run from the **default** Hermes profile (not from inside the personal one):

```bash
# 1. Bootstrap (asks for profile slug + password)
python3 ~/.hermes/skills/security/secure-my-profile/scripts/secure_profile.py setup

# 2. Confirm it exists
hermes profile list

# 3. Lock when you’re done
python3 ~/.hermes/skills/security/secure-my-profile/scripts/secure_profile.py hide
hermes profile list          # secured slug should be gone

# 4. Unlock to work again
python3 ~/.hermes/skills/security/secure-my-profile/scripts/secure_profile.py show
hermes -p personal chat      # or whatever slug you chose
```

In chat (after skills are loaded):

```text
/secure-my-profile setup
/secure-my-profile hide
/secure-my-profile show
/secure-my-profile status
/secure-my-profile change-password
```

---

## How it works

```text
~/.hermes/
├── profiles/
│   └── personal/          ← visible (unlocked)
├── vault/
│   ├── config.json        ← non-secret state
│   ├── vault.env          ← chmod 600 · salt + PBKDF2 hash only
│   └── stashed/
│       └── personal/      ← hidden (locked)
└── skills/security/secure-my-profile/
    ├── SKILL.md
    └── scripts/secure_profile.py
```

**Hide** = `shutil.move` from `profiles/<slug>` → `vault/stashed/<slug>`  
**Show** = reverse move after password verify  

Hermes only lists directories under `profiles/`, so the profile disappears from TUI/Desktop without patching Hermes core.

Password: **PBKDF2-HMAC-SHA256**, random 16-byte salt, **600 000** iterations. Compared with `hmac.compare_digest`. Never written to `SKILL.md` by the script.

**Chat path:** skill frontmatter declares `VAULT_PASSWORD` → Hermes Desktop/TUI `secret.request` → env passthrough into `secure_profile.py` → verify → **scrub** env + dotenv. Messaging gateways cannot collect secrets in-band.

---

## Commands

| Command | Password? | Description |
| --- | --- | --- |
| `setup` | set new | Create vault, hash, optional `hermes profile create` |
| `status` | no | Setup state, visible vs stashed |
| `hide` / `lock` | yes | Stop gateway (best-effort), move to stash, stub alias |
| `show` / `unlock` | yes | Restore profile + alias |
| `change-password` | yes | Rotate hash |

### Setup flags

```bash
python3 scripts/secure_profile.py setup --slug personal
python3 scripts/secure_profile.py setup --force              # reconfigure
python3 scripts/secure_profile.py setup --no-create-profile  # vault only
python3 scripts/secure_profile.py setup --hide-now           # lock immediately after setup
```

### Non-interactive (local automation only)

```bash
VAULT_PASSWORD='…' python3 scripts/secure_profile.py hide
VAULT_PASSWORD='old' VAULT_NEW_PASSWORD='new' \
  python3 scripts/secure_profile.py change-password
```

Do **not** put passwords in shell history on shared machines. Prefer interactive TUI.

---

## Safety rules

1. Always run hide/show from a profile that is **not** the secured one (default or another named profile).
2. Never put the password in normal chat text, memory, ByteRover, or skill files — use the **secure secret dialog** or TTY getpass.
3. Messaging gateways (Telegram/Discord) cannot use `secret.request` — use Desktop, TUI, or SSH.
4. Restart **Hermes Desktop** after hide if the UI still shows a cached profile name.
5. Use a long, unique password.
6. Expect `VAULT_PASSWORD` to be **absent** from `~/.hermes/.env` after each successful command (one-shot scrub).

---

## Threat model

**Protects against**

- Casual discovery in TUI / Desktop / `hermes profile list` on a shared account
- Accidental use of your personal agent by someone who can open the same Hermes UI
- Plaintext password sitting in the skill repo

**Does not protect against**

- Root or full access to your home directory (stash is still on disk)
- Offline brute-force of a weak password against `vault.env`
- Chat logs that show you ran hide/show
- Malware running as your user

Optional hardening (not included): encrypt the stashed tree with `age` / gocryptfs, or run personal Hermes as a separate Unix user.

Full notes: [`references/security.md`](./references/security.md)

---

## Repo layout

```text
secure-my-profile/
├── README.md
├── LICENSE
├── SKILL.md                 # Hermes skill → slash /secure-my-profile
├── .gitignore
├── references/
│   └── security.md
└── scripts/
    ├── secure_profile.py    # CLI entry
    └── lib/
        ├── paths.py
        ├── crypto.py
        ├── config.py
        └── profile_ops.py
```

---

## Development

```bash
python3 scripts/secure_profile.py --help
python3 scripts/secure_profile.py status   # exit 1 if not set up yet
```

No third-party Python dependencies. Exercised against real Hermes `profile create` / `list` / move on macOS; same POSIX paths target Linux VPS installs.

---

## License

[MIT](./LICENSE) © [ahmedlmahmoud](https://github.com/ahmedlmahmoud)

---

## Credits

Built for [Hermes Agent](https://github.com/NousResearch/hermes-agent) by [ahmedlmahmoud](https://github.com/ahmedlmahmoud).
