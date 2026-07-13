import { motion } from 'framer-motion'
import styles from './WinProbability.module.css'

export default function WinProbability({ prob = 50, team1, team2 }) {
  const p = Math.max(0, Math.min(100, prob))

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <span className={styles.teamLabel}>{team1}</span>
        <span className={styles.probLabel}>Win Probability</span>
        <span className={styles.teamLabel}>{team2}</span>
      </div>
      <div className={styles.bar}>
        <motion.div
          className={styles.fill}
          initial={{ width: '50%' }}
          animate={{ width: `${p}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
        <div className={styles.divider} style={{ left: `${p}%` }} />
      </div>
      <div className={styles.footer}>
        <span className={styles.pct} style={{ color: 'var(--teal)' }}>{p}%</span>
        <span className={styles.pct} style={{ color: 'var(--text-muted)' }}>{100 - p}%</span>
      </div>
    </div>
  )
}
