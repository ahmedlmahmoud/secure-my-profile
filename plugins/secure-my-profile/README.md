# secure-my-profile (Hermes plugin)

Password-gated hide/show for one Hermes **named profile** (default `personal`).

## Pieces

| Piece | Path |
|---|---|
| Engine | `engine.py` + `lib/` |
| Slash (no LLM) | `/secure-my-profile` via `__init__.py` |
| REST backend | `dashboard/plugin_api.py` → `/api/plugins/secure-my-profile/` |
| Desktop UI | `~/.hermes/desktop-plugins/secure-my-profile/plugin.js` |

**No skill.** Password is request-scoped only (dialog body / getpass). Durable secret = PBKDF2 hash in `~/.hermes/vault/vault.env`.

## Daily use (Desktop)

1. ⌘K → **Reload desktop plugins** (once after install)
2. Settings → Plugins → ensure **Secure My Profile** is on
3. ⌘K → **Hide personal profile** / **Show personal profile**
4. Enter vault password in the dialog

Status chip bottom-right: `personal: open` / `personal: locked`.

## Slash (plugin handler, no agent turn)

```text
/secure-my-profile status
/secure-my-profile hide|show     # needs real TTY (local CLI), else use Desktop
```

## Enable (already done on this host)

```bash
hermes plugins enable secure-my-profile
# restart dashboard so plugin_api mounts:
systemctl --user restart hermes-dashboard
# restart gateway so slash registers:
systemctl --user restart hermes-gateway
```

## API (local dashboard only)

- `GET  /api/plugins/secure-my-profile/status`
- `POST /api/plugins/secure-my-profile/hide`  `{ "password": "…" }`
- `POST /api/plugins/secure-my-profile/show`  `{ "password": "…" }`
- `POST /api/plugins/secure-my-profile/setup`
- `POST /api/plugins/secure-my-profile/change-password`

Auth: same dashboard session token Desktop already uses. Not a public domain API.
