# Security model — secure-my-profile

## What this protects against

- Casual discovery of a personal Hermes profile in **TUI / Desktop / `hermes profile list`** on a shared account.
- Accidental use of your personal profile by someone who can open the same Hermes UI.
- Storing a **plaintext password** in the skill, chat, or config (only a salted PBKDF2-HMAC-SHA256 hash is kept).

## What this does **not** protect against

- Root or full filesystem access to the same user home (stash is still readable under `~/.hermes/vault/stashed/`).
- Someone who can read `vault.env` and offline-brute the password (use a strong password).
- Chat/session logs that record that you ran hide/show.
- Telegram/Discord remote unlock without a local password channel.
- Malware running as your user.

## Platforms

Supported and designed for **macOS and Linux** only (POSIX paths, bash aliases under `~/.local/bin`, `chmod` 600/700). Windows is out of scope.

## Design choices

| Choice | Reason |
|---|---|
| Move profile dir out of `profiles/` | Hermes only lists dirs under `profiles/`; no core patch required |
| Vault under **default** `~/.hermes/vault/` | Unlock still works when personal profile is offline |
| Hash in `vault.env` chmod 600 | Secrets stay out of SKILL.md and config.yaml |
| PBKDF2-SHA256, 600k iters, random salt | Stdlib only; slows casual guessing |
| Run from default profile only | Avoids moving a live HERMES_HOME out from under the process |
| Alias stub while hidden | `~/.local/bin/<slug>` does not silently open a missing profile |

## Operational tips

1. Use a long unique password; treat it like a disk passphrase.
2. Prefer local TUI for setup/hide/show.
3. Restart Desktop after hide if the UI caches profile names.
4. Phase 2 (optional, not implemented): encrypt the stashed tree with `age` or a gocryptfs mount for stronger offline protection.
5. OS-level isolation (separate Unix user) is still stronger if others have shell access and you do not trust them.

## Incident notes

- If `config.json` says `hidden` but the directory is missing from both `profiles/` and `stashed/`, stop and investigate before creating a new empty profile (data may have been moved manually).
- `--force` setup rewrites the password hash; it does not delete stashed data.
