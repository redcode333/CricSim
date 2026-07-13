import { motion } from 'framer-motion'
import styles from './OverDots.module.css'

const DOT_COLOR = { '6': 'six', '4': 'four', 'W': 'wicket', 'Wd': 'extra', 'Nb': 'extra', '0': 'dot' }

export default function OverDots({ balls = [], overNum }) {
  return (
    <div className={styles.wrap}>
      <span className={styles.label}>Over {overNum}</span>
      <div className={styles.dots}>
        {balls.map((b, i) => (
          <motion.span
            key={i}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 400, damping: 20, delay: i * 0.04 }}
            className={[styles.dot, styles[DOT_COLOR[b] || 'run']].join(' ')}
          >
            {b === '0' ? '·' : b === 'Wd' ? 'w' : b === 'Nb' ? 'nb' : b}
          </motion.span>
        ))}
        {Array.from({ length: Math.max(0, 6 - balls.length) }).map((_, i) => (
          <span key={`e${i}`} className={[styles.dot, styles.empty].join(' ')} />
        ))}
      </div>
    </div>
  )
}
