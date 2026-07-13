import { motion } from 'framer-motion'
import styles from './Card.module.css'

export default function Card({ children, accent, className = '', animate = true }) {
  const el = (
    <div className={[styles.card, accent ? styles[accent] : '', className].join(' ')}>
      {children}
    </div>
  )

  if (!animate) return el

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className={[styles.card, accent ? styles[accent] : '', className].join(' ')}
    >
      {children}
    </motion.div>
  )
}
