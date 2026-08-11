# Security model — secure-my-profile

## What this protects against

- Casual discovery of a personal Hermes profile in **TUI / Desktop / `hermes profile list`** on a shared account.
- Accidental use of your personal profile by someone who can open the same Hermes UI.
- Storing a **plaintext password** in the skill, chat, memory, or durable config (only a salted PBKDF2-HMAC-SHA256 hash is kept in `vault.env`).
- **Model-visible** password entry: chat uses Hermes **`secret.request`** (masked overlay). The raw value is never placed in the assistant/user model transcript as ordinary text when the Desktop/TUI path is used correctly.

## What this does **not** protect against

- Root or full filesystem access to the same user home (stash is still readable under `~/.hermes/vault/stashed/`).
- Someone who can read `vault.env` and offline-brute the password (use a strong password).
- Chat/session logs that record that you ran hide/show (command names, not the password, if you used secret.request).
- **Pasting the password into the chat composer** as a normal message (that *does* enter the transcript and model context — never do this).
- Telegram/Discord remote unlock without a local/Desktop secret channel.
- Malware running as your user.
- A brief window where Hermes skill secret-capture may write `VAULT_PASSWORD` into `~/.hermes/.env` before `secure_profile.py` scrubs it (race if the process is killed mid-run).

## Chat password path (design)

| Stage | Where the secret lives | Model sees it? |
|---|---|---|
| User types in Desktop/TUI secret overlay | UI buffer only | No |
| Hermes `secret.respond` → env / dotenv | Process + optional `.env` line | No (not in tool JSON result) |
| `secure_profile.py` verify | Process memory during PBKDF2 | No |
| After command `finally` | Scrubbed from env + dotenv | N/A |
| Durable vault | Salt + hash in `vault/vault.env` | No |

Agent rules reinforce: no `memory` / ByteRover of the password, no argv embedding, no re-export after scrub.

## Platforms

Supported and designed for **macOS and Linux** only (POSIX paths, bash aliases under `~/.local/bin`, `chmod` 600/700). Windows is out of scope.

## Design choices

| Choice | Reason |
|---|---|
| Move profile dir out of `profiles/` | Hermes only lists dirs under `profiles/`; no core patch required |
| Vault under **default** `~/.hermes/vault/` | Unlock still works when personal profile is offline |
| Hash in `vault.env` chmod 600 | Secrets stay out of SKILL.md and config.yaml |
| PBKDF2-SHA256, 600k iters, random salt | Stdlib only; slows casual guessing |
| Run from default (or non-target) profile only | Avoids moving a live HERMES_HOME out from under the process |
| Alias stub while hidden | `~/.local/bin/<slug>` does not silently open a missing profile |
| `required_environment_variables: VAULT_PASSWORD` | Triggers Hermes secure secret dialog on skill load (Desktop/TUI) |
| Scrub `VAULT_PASSWORD` after every CLI run | Unlock password is one-shot — unlike permanent API keys Hermes usually keeps in `.env` |
| `VAULT_NEW_PASSWORD` optional + required on non-TTY change | Prevents re-hashing the current password by mistake |

## Operational tips

1. Use a long unique password; treat it like a disk passphrase.
2. Prefer **Desktop / TUI secret dialog** or local TTY — never messaging-chat paste.
3. Restart Desktop after hide if the UI caches profile names.
4. Phase 2 (optional, not implemented): encrypt the stashed tree with `age` or a gocryptfs mount for stronger offline protection.
5. OS-level isolation (separate Unix user) is still stronger if others have shell access and you do not trust them.
6. If a secret dialog appears on **status** only, skip it — status does not need the password.

## Incident notes

- If `config.json` says `hidden` but the directory is missing from both `profiles/` and `stashed/`, stop and investigate before creating a new empty profile (data may have been moved manually).
- `--force` setup rewrites the password hash; it does not delete stashed data.
- If hide/show fails with “wrong password”, the script must not leave partial moves; verify with `status` and `hermes profile list`.
- If `VAULT_PASSWORD=` still appears in `~/.hermes/.env` after a command, re-run any subcommand or manually delete those keys (do not print the value).
