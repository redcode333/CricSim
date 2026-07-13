import { useMemo } from 'react'
import { motion } from 'framer-motion'
import styles from './Confetti.module.css'

const COLORS = ['#FFCB05', '#004C93', '#EC1C24', '#3A225D', '#FF822A', '#EA1A85', '#00A99D', '#D4AF37']

export default function Confetti({ count = 70 }) {
  const pieces = useMemo(() => Array.from({ length: count }, (_, i) => ({
    id: i,
    left: Math.random() * 100,
    delay: Math.random() * 0.7,
    duration: 2.4 + Math.random() * 1.6,
    color: COLORS[i % COLORS.length],
    rotate: 180 + Math.random() * 360,
    drift: (Math.random() - 0.5) * 140,
    w: 5 + Math.random() * 5,
    h: 8 + Math.random() * 8,
  })), [count])

  return (
    <div className={styles.confettiLayer}>
      {pieces.map(p => (
        <motion.span
          key={p.id}
          className={styles.piece}
          style={{ left: `${p.left}%`, width: p.w, height: p.h, background: p.color }}
          initial={{ y: -24, x: 0, opacity: 1, rotate: 0 }}
          animate={{ y: '110vh', x: p.drift, opacity: [1, 1, 0], rotate: p.rotate }}
          transition={{ duration: p.duration, delay: p.delay, ease: 'easeIn' }}
        />
      ))}
    </div>
  )
}
