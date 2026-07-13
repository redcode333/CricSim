import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import styles from './Navbar.module.css'

const NAV = [
  { path: '/',           label: 'Home' },
  { path: '/match',      label: 'Match' },
  { path: '/players',    label: 'Players' },
  { path: '/tournament', label: 'Tournament' },
]

export default function Navbar({ user, onLogout }) {
  const { pathname } = useLocation()

  return (
    <nav className={styles.nav}>
      <Link to="/" className={styles.logo}>
        <img src="/logo.png" alt="CricSim" className={styles.logoImg} />
      </Link>

      <ul className={styles.links}>
        {NAV.map(({ path, label }) => (
          <li key={path}>
            <Link to={path} className={[styles.link, pathname === path ? styles.active : ''].join(' ')}>
              {label}
              {pathname === path && (
                <motion.div
                  layoutId="nav-indicator"
                  className={styles.indicator}
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
            </Link>
          </li>
        ))}
      </ul>

      <div className={styles.right}>
        {user ? (
          <>
            <span className={styles.username}>{user.username}</span>
            <button className={styles.logoutBtn} onClick={onLogout}>Logout</button>
          </>
        ) : (
          <Link to="/login" className={styles.loginBtn}>Login</Link>
        )}
      </div>
    </nav>
  )
}
