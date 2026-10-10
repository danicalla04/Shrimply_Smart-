import { useEffect, useState } from 'react'
import { authService } from '../services/auth'
import API_BASE from '../services/apiConfig'

const emptyForm = { username: '', email: '', first_name: '', last_name: '', password: '', password2: '', privileges: { create: false, update: false, delete: false } }

export default function AccountManagement() {
  const [isAdmin, setIsAdmin] = useState(false)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ ...emptyForm })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    let active = true
    authService.apiCall(`${API_BASE}/auth/me/`)
      .then(async response => {
        if (!response.ok) return
        const user = await response.json()
        if (active) setIsAdmin(user.is_admin === true)
      })
      .catch(() => {})
    return () => { active = false }
  }, [])

  const submit = async event => {
    event.preventDefault()
    setError('')
    setSuccess('')
    if (form.password !== form.password2) {
      setError('Passwords do not match.')
      return
    }
    setSaving(true)
    try {
      const response = await authService.apiCall(`${API_BASE}/auth/register/`, {
        method: 'POST',
        body: JSON.stringify(form),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(Object.values(data).flat().join(' ') || 'Could not create account.')
      setSuccess(`Account "${data.username}" created. Give this user their username and password to sign in.`)
      setForm({ ...emptyForm })
      setOpen(false)
    } catch (err) {
      setError(err.message || 'Could not create account.')
    } finally {
      setSaving(false)
    }
  }

  if (!isAdmin) return null

  return (
    <section className="card p-5 mb-8">
      <h2 className="text-xl font-semibold text-gray-800 mb-2">Account Management</h2>
      <p className="text-sm text-gray-600 mb-4">Create accounts for people you want to give access to the website.</p>
      {success && <p className="alert-modern alert-success-modern mb-4" role="status">{success}</p>}
      {!open ? (
        <button type="button" className="btn-modern" onClick={() => { setOpen(true); setError(''); setSuccess('') }}>
          Create another account
        </button>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              ['first_name', 'First name', 'text', false],
              ['last_name', 'Last name', 'text', false],
              ['username', 'Username', 'text', true],
              ['email', 'Email (optional)', 'email', false],
              ['password', 'Password', 'password', true],
              ['password2', 'Confirm password', 'password', true],
            ].map(([name, label, type, required]) => (
              <div key={name}>
                <label htmlFor={`account-${name}`} className="block text-sm font-medium text-gray-600 mb-1">{label}</label>
                <input id={`account-${name}`} name={name} type={type} required={required}
                  className="input-modern w-full" value={form[name]} disabled={saving}
                  autoComplete={type === 'password' ? 'new-password' : 'off'}
                  minLength={type === 'password' ? 8 : undefined}
                  maxLength={name === 'username' || name === 'first_name' || name === 'last_name' ? 150 : undefined}
                  onChange={event => setForm(current => ({ ...current, [name]: event.target.value }))} />
              </div>
            ))}
          </div>
          <fieldset className="rounded-xl border border-slate-500/30 p-4" disabled={saving}>
            <legend className="px-2 font-semibold">Account privileges</legend>
            <label className="flex items-center gap-2 mb-3">
              <input type="checkbox" checked={!Object.values(form.privileges).some(Boolean)}
                onChange={() => setForm(current => ({ ...current, privileges: { create: false, update: false, delete: false } }))} />
              Read only ? view information without making changes
            </label>
            <div className="flex flex-wrap gap-6">
              {['create', 'update', 'delete'].map(privilege => (
                <label key={privilege} className="flex items-center gap-2">
                  <input type="checkbox" checked={form.privileges[privilege]}
                    onChange={event => setForm(current => ({ ...current, privileges: { ...current.privileges, [privilege]: event.target.checked } }))} />
                  {privilege.charAt(0).toUpperCase() + privilege.slice(1)}
                </label>
              ))}
            </div>
            <p className="text-xs text-gray-600 mt-3">Create adds seasons, harvests and reports. Update changes records, settings and feeder controls. Delete removes records. Account management stays admin-only.</p>
          </fieldset>
          <p className="text-xs text-gray-600">Use at least 8 characters for the password.</p>
          {error && <p className="alert-modern alert-critical-modern" role="alert">{error}</p>}
          <div className="flex gap-3">
            <button type="submit" className="btn-modern" disabled={saving}>{saving ? 'Creating account...' : 'Create account'}</button>
            <button type="button" className="btn-secondary" disabled={saving}
              onClick={() => { setOpen(false); setForm({ ...emptyForm }); setError('') }}>Cancel</button>
          </div>
        </form>
      )}
    </section>
  )
}
