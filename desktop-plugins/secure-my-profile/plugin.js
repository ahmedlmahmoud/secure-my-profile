/**
 * secure-my-profile — Desktop half.
 * Palette + password dialog → ctx.rest → Python plugin_api on the Hermes host.
 * No skill session. Password never sticks in env.
 *
 * Folder name MUST equal id: desktop-plugins/secure-my-profile/plugin.js
 */
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  PALETTE_AREA,
  STATUSBAR_AREAS,
  Tip,
  cn,
  haptic,
  host,
  useQuery,
  useQueryClient
} from '@hermes/plugin-sdk'
import { jsx, jsxs, Fragment } from 'react/jsx-runtime'
import { useCallback, useEffect, useState } from 'react'

const ID = 'secure-my-profile'

/** @type {null | ((path: string, opts?: object) => Promise<any>)} */
let restFn = null

function call(path, opts) {
  if (!restFn) {
    return Promise.reject(new Error('plugin REST not bound'))
  }
  return restFn(path, opts)
}

function detailMessage(err) {
  const d = err && (err.detail || err.message || err)
  if (d && typeof d === 'object') {
    return d.error || d.message || JSON.stringify(d)
  }
  if (typeof d === 'string') {
    // FastAPI often: "401: {...}" — try extract
    const m = d.match(/\{.*\}/)
    if (m) {
      try {
        const j = JSON.parse(m[0])
        return j.error || j.detail || d
      } catch {
        /* fall through */
      }
    }
    return d
  }
  return String(err || 'request failed')
}

function PasswordDialog({ open, title, description, submitLabel, onClose, onSubmit }) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (open) {
      setValue('')
      setBusy(false)
    }
  }, [open, title])

  const submit = useCallback(async () => {
    if (!value || busy) return
    setBusy(true)
    try {
      await onSubmit(value)
      setValue('')
      onClose()
    } catch (err) {
      host.notifyError(err, detailMessage(err))
      setBusy(false)
    }
  }, [value, busy, onSubmit, onClose])

  if (!open) return null

  return jsx(Dialog, {
    open: true,
    onOpenChange: next => {
      if (!next && !busy) onClose()
    },
    children: jsx(DialogContent, {
      showCloseButton: false,
      children: jsxs('form', {
        className: 'grid gap-3',
        onSubmit: e => {
          e.preventDefault()
          void submit()
        },
        children: [
          jsxs(DialogHeader, {
            children: [
              jsx(DialogTitle, { children: title }),
              description
                ? jsx(DialogDescription, { children: description })
                : null
            ]
          }),
          jsx(Input, {
            autoFocus: true,
            type: 'password',
            disabled: busy,
            value,
            placeholder: 'Vault password',
            onChange: e => setValue(e.target.value)
          }),
          jsxs(DialogFooter, {
            children: [
              jsx(Button, {
                type: 'button',
                variant: 'ghost',
                disabled: busy,
                onClick: onClose,
                children: 'Cancel'
              }),
              jsx(Button, {
                type: 'submit',
                disabled: busy || !value,
                children: busy ? '…' : submitLabel
              })
            ]
          })
        ]
      })
    })
  })
}

function SetupDialog({ open, onClose }) {
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [slug, setSlug] = useState('personal')
  const [busy, setBusy] = useState(false)
  const qc = useQueryClient()

  useEffect(() => {
    if (open) {
      setPw('')
      setPw2('')
      setSlug('personal')
      setBusy(false)
    }
  }, [open])

  if (!open) return null

  return jsx(Dialog, {
    open: true,
    onOpenChange: next => {
      if (!next && !busy) onClose()
    },
    children: jsx(DialogContent, {
      showCloseButton: false,
      children: jsxs('form', {
        className: 'grid gap-3',
        onSubmit: e => {
          e.preventDefault()
          if (pw.length < 8) {
            host.notify({ kind: 'error', message: 'Password must be at least 8 characters' })
            return
          }
          if (pw !== pw2) {
            host.notify({ kind: 'error', message: 'Passwords do not match' })
            return
          }
          setBusy(true)
          call('/setup', {
            method: 'POST',
            body: { password: pw, slug: slug || 'personal', force: false, create_profile: true }
          })
            .then(r => {
              host.notify({ kind: 'success', message: r.message || 'Vault ready' })
              void qc.invalidateQueries({ queryKey: [ID, 'status'] })
              onClose()
            })
            .catch(err => {
              host.notifyError(err, detailMessage(err))
              setBusy(false)
            })
        },
        children: [
          jsxs(DialogHeader, {
            children: [
              jsx(DialogTitle, { children: 'Setup personal vault' }),
              jsx(DialogDescription, {
                children: 'Creates a password hash only (never stored in plaintext). Default profile slug: personal.'
              })
            ]
          }),
          jsx(Input, {
            autoFocus: true,
            disabled: busy,
            value: slug,
            placeholder: 'Profile slug',
            onChange: e => setSlug(e.target.value)
          }),
          jsx(Input, {
            type: 'password',
            disabled: busy,
            value: pw,
            placeholder: 'New vault password (min 8)',
            onChange: e => setPw(e.target.value)
          }),
          jsx(Input, {
            type: 'password',
            disabled: busy,
            value: pw2,
            placeholder: 'Confirm password',
            onChange: e => setPw2(e.target.value)
          }),
          jsxs(DialogFooter, {
            children: [
              jsx(Button, {
                type: 'button',
                variant: 'ghost',
                disabled: busy,
                onClick: onClose,
                children: 'Cancel'
              }),
              jsx(Button, {
                type: 'submit',
                disabled: busy || !pw || !pw2,
                children: busy ? '…' : 'Setup'
              })
            ]
          })
        ]
      })
    })
  })
}

function ChangePasswordDialog({ open, onClose }) {
  const [cur, setCur] = useState('')
  const [nw, setNw] = useState('')
  const [nw2, setNw2] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (open) {
      setCur('')
      setNw('')
      setNw2('')
      setBusy(false)
    }
  }, [open])

  if (!open) return null

  return jsx(Dialog, {
    open: true,
    onOpenChange: next => {
      if (!next && !busy) onClose()
    },
    children: jsx(DialogContent, {
      showCloseButton: false,
      children: jsxs('form', {
        className: 'grid gap-3',
        onSubmit: e => {
          e.preventDefault()
          if (nw.length < 8) {
            host.notify({ kind: 'error', message: 'New password must be at least 8 characters' })
            return
          }
          if (nw !== nw2) {
            host.notify({ kind: 'error', message: 'Passwords do not match' })
            return
          }
          setBusy(true)
          call('/change-password', {
            method: 'POST',
            body: { current_password: cur, new_password: nw }
          })
            .then(r => {
              host.notify({ kind: 'success', message: r.message || 'Password updated' })
              onClose()
            })
            .catch(err => {
              host.notifyError(err, detailMessage(err))
              setBusy(false)
            })
        },
        children: [
          jsxs(DialogHeader, {
            children: [
              jsx(DialogTitle, { children: 'Change vault password' }),
              jsx(DialogDescription, { children: 'Rotates the on-disk PBKDF2 hash only.' })
            ]
          }),
          jsx(Input, {
            autoFocus: true,
            type: 'password',
            disabled: busy,
            value: cur,
            placeholder: 'Current password',
            onChange: e => setCur(e.target.value)
          }),
          jsx(Input, {
            type: 'password',
            disabled: busy,
            value: nw,
            placeholder: 'New password (min 8)',
            onChange: e => setNw(e.target.value)
          }),
          jsx(Input, {
            type: 'password',
            disabled: busy,
            value: nw2,
            placeholder: 'Confirm new password',
            onChange: e => setNw2(e.target.value)
          }),
          jsxs(DialogFooter, {
            children: [
              jsx(Button, {
                type: 'button',
                variant: 'ghost',
                disabled: busy,
                onClick: onClose,
                children: 'Cancel'
              }),
              jsx(Button, {
                type: 'submit',
                disabled: busy || !cur || !nw || !nw2,
                children: busy ? '…' : 'Update'
              })
            ]
          })
        ]
      })
    })
  })
}

function StatusChip() {
  const { data } = useQuery({
    queryKey: [ID, 'status'],
    queryFn: () => call('/status'),
    refetchInterval: 30_000,
    retry: 1
  })

  const state = data?.state || '…'
  const label =
    state === 'hidden' ? 'personal: locked' : state === 'visible' ? 'personal: open' : 'personal: —'

  return jsx(Tip, {
    label: data?.setup_complete
      ? `Secure profile ${data.profile || ''} — ${state}`
      : 'Secure my profile — not set up',
    children: jsx('button', {
      type: 'button',
      className: cn(
        'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] transition-colors',
        'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground'
      ),
      onClick: () => {
        haptic('tap')
        const msg = data
          ? `profile=${data.profile || '—'} state=${data.state} setup=${data.setup_complete}`
          : 'status unavailable (is Python plugin enabled + dashboard up?)'
        host.notify({ kind: 'info', message: msg })
      },
      children: label
    })
  })
}

/** Root contribution that owns dialogs + palette actions via storage atoms. */
function Controller() {
  const [mode, setMode] = useState(/** @type {null | 'hide' | 'show' | 'setup' | 'passwd'} */ (null))
  const qc = useQueryClient()

  // Expose openers for palette (palette runs outside React tree)
  useEffect(() => {
    window.__secureMyProfileOpen = setMode
    return () => {
      delete window.__secureMyProfileOpen
    }
  }, [])

  const onHide = useCallback(
    async password => {
      const r = await call('/hide', { method: 'POST', body: { password } })
      host.notify({ kind: 'success', message: r.message || 'Profile hidden' })
      void qc.invalidateQueries({ queryKey: [ID, 'status'] })
    },
    [qc]
  )

  const onShow = useCallback(
    async password => {
      const r = await call('/show', { method: 'POST', body: { password } })
      host.notify({ kind: 'success', message: r.message || 'Profile restored' })
      void qc.invalidateQueries({ queryKey: [ID, 'status'] })
    },
    [qc]
  )

  return jsxs(Fragment, {
    children: [
      jsx(PasswordDialog, {
        open: mode === 'hide',
        title: 'Hide personal profile',
        description: 'Moves the profile out of the list. Password is not saved.',
        submitLabel: 'Hide',
        onClose: () => setMode(null),
        onSubmit: onHide
      }),
      jsx(PasswordDialog, {
        open: mode === 'show',
        title: 'Show personal profile',
        description: 'Restores the stashed profile after password check.',
        submitLabel: 'Show',
        onClose: () => setMode(null),
        onSubmit: onShow
      }),
      jsx(SetupDialog, {
        open: mode === 'setup',
        onClose: () => setMode(null)
      }),
      jsx(ChangePasswordDialog, {
        open: mode === 'passwd',
        onClose: () => setMode(null)
      })
    ]
  })
}

function openMode(mode) {
  const fn = window.__secureMyProfileOpen
  if (typeof fn === 'function') {
    fn(mode)
    return
  }
  host.notify({
    kind: 'error',
    message: 'Secure UI not mounted — reload desktop plugins'
  })
}

export default {
  id: ID,
  name: 'Secure My Profile',
  defaultEnabled: true,
  register(ctx) {
    restFn = (path, opts) => ctx.rest(path, opts)

    // Invisible mount point so dialogs have a React tree (status bar chip hosts Controller)
    ctx.register({
      id: 'chip',
      area: STATUSBAR_AREAS.right,
      order: 140,
      render: () =>
        jsxs(Fragment, {
          children: [jsx(Controller, {}), jsx(StatusChip, {})]
        })
    })

    ctx.registerMany([
      {
        id: 'palette-hide',
        area: PALETTE_AREA,
        data: {
          id: 'secure-my-profile.hide',
          label: 'Hide personal profile',
          keywords: ['secure', 'lock', 'vault', 'personal', 'hide'],
          run: () => {
            haptic('tap')
            openMode('hide')
          }
        }
      },
      {
        id: 'palette-show',
        area: PALETTE_AREA,
        data: {
          id: 'secure-my-profile.show',
          label: 'Show personal profile',
          keywords: ['secure', 'unlock', 'vault', 'personal', 'show'],
          run: () => {
            haptic('tap')
            openMode('show')
          }
        }
      },
      {
        id: 'palette-setup',
        area: PALETTE_AREA,
        data: {
          id: 'secure-my-profile.setup',
          label: 'Setup personal vault',
          keywords: ['secure', 'setup', 'vault', 'password'],
          run: () => {
            haptic('tap')
            openMode('setup')
          }
        }
      },
      {
        id: 'palette-passwd',
        area: PALETTE_AREA,
        data: {
          id: 'secure-my-profile.change-password',
          label: 'Change vault password',
          keywords: ['secure', 'password', 'change'],
          run: () => {
            haptic('tap')
            openMode('passwd')
          }
        }
      },
      {
        id: 'palette-status',
        area: PALETTE_AREA,
        data: {
          id: 'secure-my-profile.status',
          label: 'Secure profile status',
          keywords: ['secure', 'status', 'vault'],
          run: async () => {
            haptic('tap')
            try {
              const s = await call('/status')
              host.notify({
                kind: 'info',
                message: `profile=${s.profile || '—'} state=${s.state} setup=${s.setup_complete}`
              })
            } catch (err) {
              host.notifyError(err, detailMessage(err))
            }
          }
        }
      }
    ])
  }
}
