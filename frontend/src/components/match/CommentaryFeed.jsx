import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import styles from './CommentaryFeed.module.css'

const OUTCOME_COLOR = {
  '6': 'six', '4': 'four', 'W': 'wicket', 'Wd': 'extra', 'Nb': 'extra',
}

function BallPip({ outcome }) {
  const cls = OUTCOME_COLOR[outcome] || 'normal'
  return (
    <span className={[styles.pip, styles[cls]].join(' ')}>
      {outcome === 'W' ? 'W' : outcome === '0' ? '·' : outcome}
    </span>
  )
}

export default function CommentaryFeed({ balls = [] }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [balls.length])

  return (
    <div className={styles.feed}>
      <AnimatePresence initial={false}>
        {[...balls].reverse().map((ball) => (
          <motion.div
            key={ball.seq}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className={[styles.row, OUTCOME_COLOR[ball.outcome] ? styles[`row_${OUTCOME_COLOR[ball.outcome]}`] : ''].join(' ')}
          >
            <span className={styles.over}>{ball.over}</span>
            <BallPip outcome={ball.outcome} />
            <span className={styles.text}>{ball.text}</span>
          </motion.div>
        ))}
      </AnimatePresence>
      <div ref={bottomRef} />
    </div>
  )
}
