import { createContext, useContext, useEffect, useState } from 'react'
import { authService } from '../services/auth'
import API_BASE from '../services/apiConfig'

const readOnly = { create: false, update: false, delete: false, isAdmin: false, loaded: false }
const PrivilegesContext = createContext(readOnly)
export const usePrivileges = () => useContext(PrivilegesContext)

export function PrivilegesProvider({ children }) {
  const [privileges, setPrivileges] = useState(readOnly)
  useEffect(() => {
    let active = true
    authService.apiCall(`${API_BASE}/auth/me/`)
      .then(async response => {
        if (!response.ok) { if (active) setPrivileges({ ...readOnly, loaded: true }); return }
        const user = await response.json()
        if (active) setPrivileges({ ...readOnly, ...user.privileges, isAdmin: user.is_admin === true, loaded: true })
      }).catch(() => { if (active) setPrivileges({ ...readOnly, loaded: true }) })
    return () => { active = false }
  }, [])
  return <PrivilegesContext.Provider value={privileges}>{children}</PrivilegesContext.Provider>
}
