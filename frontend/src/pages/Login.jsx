import { useState, useEffect } from 'react'
import { useNavigate, Navigate, useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../hooks/useAuth'
import { api } from '../api'
import styles from './Login.module.css'

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [tab, setTab] = useState('login')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  // Handle Google OAuth callback redirect
  useEffect(() => {
    const googleUser = searchParams.get('google_user')
    const display    = searchParams.get('display')
    const oauthErr   = searchParams.get('error')
    if (googleUser) {
      login(decodeURIComponent(display || googleUser))
      navigate('/')
    } else if (oauthErr) {
      setErr(`Google sign-in failed: ${oauthErr.replace(/_/g, ' ')}`)
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  function googleSignIn() {
    window.location.href = '/api/auth/google'
  }

  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const [regForm, setRegForm]   = useState({ username: '', password: '', confirm: '' })

  if (user) return <Navigate to="/" replace />

  async function doLogin(e) {
    e.preventDefault()
    setErr(''); setLoading(true)
    try {
      const data = await api('POST', '/auth/login', loginForm)
      login(data.username)
      navigate('/')
    } catch(e) {
      setErr(e.message)
    } finally { setLoading(false) }
  }

  async function doRegister(e) {
    e.preventDefault()
    if (regForm.password !== regForm.confirm) { setErr("Passwords don't match"); return }
    setErr(''); setLoading(true)
    try {
      const data = await api('POST', '/auth/register', {
        username: regForm.username, password: regForm.password,
      })
      login(data.username)
      navigate('/')
    } catch(e) {
      setErr(e.message)
    } finally { setLoading(false) }
  }

  function guestMode() {
    login('Guest')
    navigate('/')
  }

  return (
    <div className={styles.root}>
      <div className={styles.box}>
        <div className={styles.logo}>
          <img src="/logo.png" alt="CricSim" className={styles.logoImg} />
          <p className={styles.sub}>IPL 2026 · Ball-by-Ball AI Simulator</p>
        </div>

        <div className={styles.card}>
          <div className={styles.tabs}>
            {['login','register'].map(t => (
              <button
                key={t}
                className={[styles.tab, tab === t ? styles.tabActive : ''].join(' ')}
                onClick={() => { setTab(t); setErr('') }}
              >
                {t === 'login' ? 'Login' : 'Register'}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            {tab === 'login' ? (
              <motion.form
                key="login"
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 8 }}
                transition={{ duration: 0.18 }}
                onSubmit={doLogin}
                className={styles.form}
              >
                <div className={styles.field}>
                  <label>Username</label>
                  <input
                    autoComplete="username"
                    value={loginForm.username}
                    onChange={e => setLoginForm(f => ({ ...f, username: e.target.value }))}
                    disabled={loading}
                  />
                </div>
                <div className={styles.field}>
                  <label>Password</label>
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={loginForm.password}
                    onChange={e => setLoginForm(f => ({ ...f, password: e.target.value }))}
                    disabled={loading}
                  />
                </div>
                {err && <div className={styles.err}>{err}</div>}
                <button className={styles.btnPrimary} type="submit" disabled={loading}>
                  {loading ? 'Logging in…' : 'Login'}
                </button>
              </motion.form>
            ) : (
              <motion.form
                key="register"
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.18 }}
                onSubmit={doRegister}
                className={styles.form}
              >
                <div className={styles.field}>
                  <label>Username <span className={styles.hint}>(min 3 chars)</span></label>
                  <input
                    autoComplete="username"
                    value={regForm.username}
                    onChange={e => setRegForm(f => ({ ...f, username: e.target.value }))}
                    disabled={loading}
                  />
                </div>
                <div className={styles.field}>
                  <label>Password</label>
                  <input
                    type="password"
                    autoComplete="new-password"
                    value={regForm.password}
                    onChange={e => setRegForm(f => ({ ...f, password: e.target.value }))}
                    disabled={loading}
                  />
                </div>
                <div className={styles.field}>
                  <label>Confirm Password</label>
                  <input
                    type="password"
                    value={regForm.confirm}
                    onChange={e => setRegForm(f => ({ ...f, confirm: e.target.value }))}
                    disabled={loading}
                  />
                </div>
                {err && <div className={styles.err}>{err}</div>}
                <button className={styles.btnPrimary} type="submit" disabled={loading}>
                  {loading ? 'Creating account…' : 'Create Account'}
                </button>
              </motion.form>
            )}
          </AnimatePresence>

          <div className={styles.divider}><span>or</span></div>
          <button className={styles.btnGoogle} onClick={googleSignIn} type="button">
            <svg width="16" height="16" viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continue with Google
          </button>
          <button className={styles.btnGuest} onClick={guestMode} type="button">
            Continue as Guest
            <span className={styles.guestNote}> — saves disabled</span>
          </button>
        </div>
      </div>
    </div>
  )
}
