import { useState, useEffect, createContext, useContext } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('cs_user')) } catch { return null }
  })

  function login(username) {
    const u = { username }
    localStorage.setItem('cs_user', JSON.stringify(u))
    setUser(u)
  }

  function logout() {
    localStorage.removeItem('cs_user')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext) ?? { user: null, login: () => {}, logout: () => {} }
}
