# secure-my-profile

Password-gated **hide/show** for one Hermes named profile (default: `personal`).

**Product = Hermes Python plugin + Desktop plugin.** No skill session. Password is request-scoped (dialog body); durable secret is a PBKDF2 hash in `~/.hermes/vault/vault.env`.

| Half | Install path | Role |
|---|---|---|
| **Hermes plugin** | `$HERMES_HOME/plugins/secure-my-profile/` | Engine + `/secure-my-profile` slash + REST `plugin_api` |
| **Desktop plugin** | `$HERMES_HOME/desktop-plugins/secure-my-profile/plugin.js` | ⌘K palette + password dialog → `ctx.rest` |

Works with **remote Desktop → remote gateway**: Desktop UI prompts locally; hide/show runs on the VPS via the existing dashboard session.

---

## Install (VPS / Hermes host)

```bash
# 1. Clone
git clone https://github.com/ahmedlmahmoud/secure-my-profile.git
cd secure-my-profile

# 2. Install Python plugin into HERMES_HOME
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/plugins"
rsync -a --delete plugins/secure-my-profile/ "$HERMES_HOME/plugins/secure-my-profile/"

# 3. Enable + restart so plugin_api mounts and slash registers
hermes plugins enable secure-my-profile
# restart dashboard (API) + gateway (slash)
systemctl --user restart hermes-dashboard hermes-gateway
# or however you run them: hermes dashboard / hermes gateway
```

Confirm in logs:
```text
Mounted plugin API routes: /api/plugins/secure-my-profile/
```

## Install (Desktop machine)

Desktop loads plugins from **`$HERMES_HOME/desktop-plugins/` on the machine running the Desktop app**.

```bash
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"   # or your Desktop profile home
mkdir -p "$HERMES_HOME/desktop-plugins/secure-my-profile"
cp desktop-plugins/secure-my-profile/plugin.js \
   "$HERMES_HOME/desktop-plugins/secure-my-profile/plugin.js"
```

Then in Desktop:
1. **⌘K → Reload desktop plugins**
2. Settings → Plugins → **Secure My Profile** on
3. ⌘K → **Hide / Show personal profile**

If Desktop talks to a **remote** gateway, the Python half must already be installed+enabled on that host (step above). The Desktop half only needs `plugin.js` locally.

### One-host (Desktop + gateway same machine)

```bash
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
rsync -a plugins/secure-my-profile/ "$HERMES_HOME/plugins/secure-my-profile/"
mkdir -p "$HERMES_HOME/desktop-plugins/secure-my-profile"
cp desktop-plugins/secure-my-profile/plugin.js \
   "$HERMES_HOME/desktop-plugins/secure-my-profile/plugin.js"
hermes plugins enable secure-my-profile
# restart dashboard + gateway, then Desktop: Reload desktop plugins
```

---

## First-time setup

If vault is not configured yet:
- Desktop: ⌘K → **Setup personal profile vault** (password dialog), **or**
- CLI on host with a real TTY:
  ```bash
  hermes  # then /secure-my-profile setup
  # or:
  python3 -c "import sys; sys.path.insert(0,'$HERMES_HOME/plugins/secure-my-profile'); import engine; print(engine.setup(password='…'))"
  ```

Existing vault from the old skill is reused (`~/.hermes/vault/`). No re-setup needed if `vault.env` already has the hash.

## Daily use

| Action | How |
|---|---|
| Hide | ⌘K → **Hide personal profile** → password |
| Show | ⌘K → **Show personal profile** → password |
| Status | ⌘K chip / `/secure-my-profile status` |

When hidden, `profiles/personal` is moved to `vault/stashed/personal` so TUI/Desktop stop listing it.

## Security model

- **Always re-prompt** — no sticky `secret.request` / parent-env unlock
- Password only in POST body (Desktop) or getpass (CLI TTY)
- Durable store: salted PBKDF2-HMAC-SHA256 (600k iters) in `vault/vault.env` (chmod 600)
- Not full-disk encryption; not multi-user OS isolation

## Slash (plugin handler — no LLM)

```text
/secure-my-profile status
/secure-my-profile hide|show     # needs real TTY; prefer Desktop dialog
/secure-my-profile setup
/secure-my-profile change-password
```

## API (local dashboard, session-token auth)

```text
GET  /api/plugins/secure-my-profile/status
POST /api/plugins/secure-my-profile/hide|show|setup|change-password
```

Not a public domain API — routes on the existing Hermes dashboard/gateway.

## Uninstall

```bash
hermes plugins disable secure-my-profile   # if available
rm -rf "$HERMES_HOME/plugins/secure-my-profile"
rm -rf "$HERMES_HOME/desktop-plugins/secure-my-profile"
# restart dashboard/gateway; Desktop: Reload desktop plugins
# vault data left intact under $HERMES_HOME/vault/
```

## License

MIT — see `LICENSE`.
