import { motion, AnimatePresence } from 'framer-motion'
import styles from './BatsmenTable.module.css'

export default function BatsmenTable({ batsmen = [] }) {
  const active = batsmen.filter(b => b.status === 'batting')
  const out    = batsmen.filter(b => b.status === 'out')

  const rows = [...active, ...out]

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th className={styles.th}>Batsman</th>
          <th className={styles.th}>R</th>
          <th className={styles.th}>B</th>
          <th className={styles.th}>SR</th>
        </tr>
      </thead>
      <tbody>
        <AnimatePresence>
          {rows.map(b => (
            <motion.tr
              key={b.name}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className={[styles.row, b.status === 'batting' ? styles.active : styles.out].join(' ')}
            >
              <td className={styles.name}>
                {b.status === 'batting' && <span className={styles.indicator} />}
                {b.name}
              </td>
              <td className={styles.num}>{b.runs}{b.status === 'batting' ? '*' : ''}</td>
              <td className={styles.num}>{b.balls}</td>
              <td className={[styles.num, b.sr >= 150 ? styles.srHigh : ''].join(' ')}>
                {b.sr?.toFixed(1)}
              </td>
            </motion.tr>
          ))}
        </AnimatePresence>
      </tbody>
    </table>
  )
}
