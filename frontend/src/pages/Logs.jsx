import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { usePrivileges } from '../context/PrivilegesContext'
import { authService } from '../services/auth'
import API_BASE from '../services/apiConfig'

const privilegeText = (privileges, admin = false) => admin ? 'Admin | Full access'
  : ['create', 'update', 'delete'].filter(key => privileges?.[key]).map(key => key.charAt(0).toUpperCase() + key.slice(1)).join(', ') || 'Read only'
const valueText = value => value == null ? 'Not recorded' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const fieldText = field => field.replace(/_/g, ' ').replace(/^./, letter => letter.toUpperCase())
const timeText = value => new Date(value).toLocaleString('en-PH', { timeZone: 'Asia/Manila', dateStyle: 'medium', timeStyle: 'short' })

export default function Logs() {
  const { isAdmin, loaded } = usePrivileges()
  const [accounts, setAccounts] = useState([])
  const [logs, setLogs] = useState([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)
  const [action, setAction] = useState('')
  const [username, setUsername] = useState('')
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [saving, setSaving] = useState(false)
  const [accountError, setAccountError] = useState('')
  const [accountSuccess, setAccountSuccess] = useState('')

  const openEdit = user => {
    setAccountError('')
    setAccountSuccess('')
    setEditing({ ...user, privileges: { ...user.privileges } })
  }
  const formatError = value => typeof value === 'object' && value !== null
    ? Object.values(value).map(formatError).join(' ') : String(value)
  const saveAccount = async event => {
    event.preventDefault()
    setSaving(true)
    setAccountError('')
    try {
      const payload = { username: editing.username, first_name: editing.first_name, last_name: editing.last_name, email: editing.email, is_active: editing.is_active }
      if (!editing.is_admin) payload.privileges = editing.privileges
      const response = await authService.apiCall(`${API_BASE}/accounts/${editing.id}/`, { method: 'PATCH', body: JSON.stringify(payload) })
      if (!response.ok) throw new Error(formatError(await response.json()))
      setAccountSuccess(`Account "${editing.username}" updated.`)
      setEditing(null)
      setPage(1)
      setRefresh(value => value + 1)
    } catch (err) { setAccountError(err.message || 'Could not update account.') }
    finally { setSaving(false) }
  }
  const deleteAccount = async () => {
    setSaving(true)
    setAccountError('')
    try {
      const response = await authService.apiCall(`${API_BASE}/accounts/${deleting.id}/`, { method: 'DELETE' })
      if (!response.ok) throw new Error(formatError(await response.json()))
      setAccountSuccess(`Account "${deleting.username}" deleted. Shared pond records and activity history were preserved.`)
      setDeleting(null)
      setPage(1)
      setRefresh(value => value + 1)
    } catch (err) { setAccountError(err.message || 'Could not delete account.') }
    finally { setSaving(false) }
  }

  useEffect(() => {
    if (!isAdmin) return
    const controller = new AbortController()
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const params = new URLSearchParams({ page: String(page), action, username, search })
        const responses = await Promise.all([
          authService.apiCall(`${API_BASE}/account-access/`, { signal: controller.signal }),
          authService.apiCall(`${API_BASE}/activity-logs/?${params}`, { signal: controller.signal }),
        ])
        if (responses.some(response => !response.ok)) throw new Error('Unable to load logs. Administrator access is required.')
        const [users, activity] = await Promise.all(responses.map(response => response.json()))
        if (controller.signal.aborted) return
        setAccounts(users)
        setLogs(activity.results)
        setCount(activity.count)
      } catch (err) {
        if (!controller.signal.aborted) { setError(err.message); setLogs([]); setCount(0) }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    load()
    return () => controller.abort()
  }, [isAdmin, page, action, username, search, refresh])

  if (!loaded) return <p className="p-6" role="status">Checking administrator access...</p>
  if (!isAdmin) return <Navigate to="/dashboard" replace />

  const pages = Math.max(1, Math.ceil(count / 20))
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-wrap justify-between items-center gap-4">
        <div><h1 className="text-3xl font-bold">Logs</h1><p className="text-sm text-slate-400 mt-2">Account privileges and activity history. Visible only to administrators.</p></div>
        <button type="button" className="btn-secondary" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Refresh</button>
      </div>
      {error && <p className="alert-modern alert-critical-modern" role="alert">{error}</p>}
      <section className="card p-5">
        <h2 className="text-xl font-semibold mb-4">Accounts and privileges</h2>
        {accountSuccess && <p className="alert-modern alert-success-modern mb-4" role="status">{accountSuccess}</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead><tr className="border-b border-slate-500/30">{['User', 'Email', 'Role', 'Read', 'Create', 'Update', 'Delete', 'Status', 'Actions'].map(title => <th key={title} className="p-3">{title}</th>)}</tr></thead>
            <tbody>{accounts.map(user => (
              <tr key={user.id} className="border-b border-slate-500/20">
                <td className="p-3 font-medium">{user.username}{user.name && <span className="block text-xs text-slate-400">{user.name}</span>}</td>
                <td className="p-3">{user.email || 'Not set'}</td>
                <td className="p-3">{user.is_admin ? 'Admin' : !Object.values(user.privileges).some(Boolean) ? 'Read only' : 'User'}</td>
                <td className="p-3">Yes</td>
                {['create', 'update', 'delete'].map(key => <td key={key} className="p-3">{user.privileges[key] ? 'Yes' : 'No'}</td>)}
                <td className="p-3">{user.is_active ? 'Active' : 'Inactive'}</td>
                <td className="p-3"><div className="flex gap-2">
                  <button type="button" className="btn-secondary text-xs" onClick={() => openEdit(user)}>Edit</button>
                  <button type="button" className="btn-secondary text-xs" disabled={user.is_current_user}
                    title={user.is_current_user ? 'You cannot delete your own account' : `Delete ${user.username}`}
                    onClick={() => { setDeleting(user); setAccountError(''); setAccountSuccess('') }}>Delete</button>
                </div></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </section>
      <section className="card p-5">
        <h2 className="text-xl font-semibold mb-2">Activity history</h2>
        <p className="text-xs text-slate-400 mb-4">New changes are recorded from the time logging was enabled. Times are shown in Philippine time.</p>
        <form className="flex flex-wrap gap-3 mb-5" onSubmit={event => { event.preventDefault(); setSearch(query.trim()); setPage(1) }}>
          <select aria-label="Filter by action" className="input-modern" style={{ width: 'auto' }} value={action} onChange={event => { setAction(event.target.value); setPage(1) }}>
            <option value="">All actions</option><option value="create">Create</option><option value="update">Update</option><option value="delete">Delete</option>
          </select>
          <select aria-label="Filter by user" className="input-modern" style={{ width: 'auto' }} value={username} onChange={event => { setUsername(event.target.value); setPage(1) }}>
            <option value="">All users</option>
            {[...new Set([...accounts.map(user => user.username), ...logs.map(log => log.username)])].sort().map(name => <option key={name} value={name}>{name}</option>)}
          </select>
          <input aria-label="Search activity" className="input-modern flex-1" style={{ minWidth: 180 }} placeholder="Search user or record..." value={query} onChange={event => setQuery(event.target.value)} />
          <button type="submit" className="btn-secondary">Search</button>
        </form>
        {loading ? <p role="status" className="py-8 text-center">Loading logs...</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead><tr className="border-b border-slate-500/30">{['Date and time', 'User', 'Privileges at time', 'Action', 'Record', 'What changed'].map(title => <th key={title} className="p-3 whitespace-nowrap">{title}</th>)}</tr></thead>
              <tbody>{logs.map(log => (
                <tr key={log.id} className="border-b border-slate-500/20 align-top">
                  <td className="p-3 whitespace-nowrap">{timeText(log.occurred_at)}</td>
                  <td className="p-3 font-medium">{log.username}</td>
                  <td className="p-3">{privilegeText(log.privileges)}</td>
                  <td className="p-3"><span className={`rounded-lg px-2 py-1 text-xs font-semibold ${log.action === 'create' ? 'bg-emerald-500/20 text-emerald-400' : log.action === 'delete' ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'}`}>{fieldText(log.action)}</span></td>
                  <td className="p-3">{log.record_label}<span className="block text-xs text-slate-400">{fieldText(log.resource)} | #{log.record_id}</span></td>
                  <td className="p-3 min-w-64">
                    <details><summary className="cursor-pointer">{log.changes.length} field{log.changes.length === 1 ? '' : 's'} | View details</summary>
                      <div className="mt-3 space-y-3">{log.changes.map(change => (
                        <div key={change.field} className="rounded-lg border border-slate-500/20 p-2">
                          <strong className="block mb-1">{fieldText(change.field)}</strong>
                          {log.action !== 'create' && <div className="break-words whitespace-pre-wrap"><span className="text-slate-400">Before: </span>{valueText(change.before)}</div>}
                          {log.action !== 'delete' && <div className="break-words whitespace-pre-wrap"><span className="text-slate-400">{log.action === 'create' ? 'Value: ' : 'After: '}</span>{valueText(change.after)}</div>}
                        </div>
                      ))}</div>
                    </details>
                  </td>
                </tr>
              ))}</tbody>
            </table>
            {!logs.length && <p className="py-8 text-center text-slate-400">No activity matches these filters.</p>}
          </div>
        )}
        <div className="flex justify-between items-center mt-5 gap-3">
          <span className="text-xs text-slate-400">{count} records | Page {page} of {pages}</span>
          <div className="flex gap-2"><button className="btn-secondary" disabled={loading || page <= 1} onClick={() => setPage(value => value - 1)}>Previous</button><button className="btn-secondary" disabled={loading || page >= pages} onClick={() => setPage(value => value + 1)}>Next</button></div>
        </div>
      </section>
      {editing && (
        <div className="aq-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="edit-account-title">
          <div className="card aq-modal" style={{ width: 'min(640px, 95vw)', maxHeight: '90vh', overflowY: 'auto' }}>
            <h2 id="edit-account-title" className="text-xl font-semibold mb-4">Edit account</h2>
            <form onSubmit={saveAccount} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  ['username', 'Username', 'text'], ['email', 'Email', 'email'],
                  ['first_name', 'First name', 'text'], ['last_name', 'Last name', 'text'],
                ].map(([key, title, type]) => (
                  <div key={key}><label htmlFor={`edit-account-${key}`} className="block text-sm mb-1">{title}</label>
                    <input id={`edit-account-${key}`} className="input-modern w-full" type={type} required={key === 'username'}
                      maxLength={key === 'email' ? 254 : 150} disabled={saving} value={editing[key] || ''}
                      onChange={event => setEditing(current => ({ ...current, [key]: event.target.value }))} />
                  </div>
                ))}
              </div>
              <fieldset disabled={saving || editing.is_admin} className="border border-slate-500/30 rounded-xl p-4">
                <legend className="px-2">Privileges</legend>
                <label className="flex gap-2 items-center mb-3"><input type="checkbox" checked={!Object.values(editing.privileges).some(Boolean)}
                  onChange={() => setEditing(current => ({ ...current, privileges: { create: false, update: false, delete: false } }))} />Read only</label>
                <div className="flex flex-wrap gap-5">{['create', 'update', 'delete'].map(key => (
                  <label key={key} className="flex gap-2 items-center"><input type="checkbox" checked={editing.privileges[key]}
                    onChange={event => setEditing(current => ({ ...current, privileges: { ...current.privileges, [key]: event.target.checked } }))} />{fieldText(key)}</label>
                ))}</div>
              </fieldset>
              {editing.is_admin && <p className="text-xs text-slate-400">Administrator accounts retain full access.</p>}
              <label className="flex gap-2 items-center"><input type="checkbox" disabled={saving || editing.is_current_user} checked={editing.is_active}
                onChange={event => setEditing(current => ({ ...current, is_active: event.target.checked }))} />Account active</label>
              {accountError && <p className="alert-modern alert-critical-modern" role="alert">{accountError}</p>}
              <div className="flex justify-end gap-3">
                <button type="button" className="btn-secondary" disabled={saving} onClick={() => setEditing(null)}>Cancel</button>
                <button type="submit" className="btn-modern" disabled={saving}>{saving ? 'Saving...' : 'Save changes'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
      {deleting && (
        <div className="aq-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="delete-account-title">
          <div className="card aq-modal">
            <h2 id="delete-account-title" className="text-xl font-semibold mb-3">Delete account</h2>
            <p className="mb-3">Delete account <strong>{deleting.username}</strong>? This user will lose access to the website.</p>
            <p className="text-sm text-slate-400 mb-4">Shared pond records and activity history will be preserved. This action cannot be undone.</p>
            {accountError && <p className="alert-modern alert-critical-modern mb-4" role="alert">{accountError}</p>}
            <div className="flex justify-end gap-3">
              <button type="button" className="btn-secondary" disabled={saving} onClick={() => setDeleting(null)}>Cancel</button>
              <button type="button" className="btn-modern" disabled={saving} onClick={deleteAccount}>{saving ? 'Deleting...' : 'Delete account'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
