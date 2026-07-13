import { motion, AnimatePresence } from 'framer-motion'
import styles from './LiveScoreboard.module.css'

function CountUp({ value, suffix = '' }) {
  return (
    <motion.span
      key={value}
      initial={{ opacity: 0.4, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {value}{suffix}
    </motion.span>
  )
}

export default function LiveScoreboard({ data }) {
  const { batting_team, bowling_team, score, wickets, overs, crr, target, runs_needed, rrr } = data
  const second = target != null

  return (
    <div className={styles.board}>
      <div className={styles.teams}>
        <span className={styles.batting}>{batting_team}</span>
        <span className={styles.vs}>vs</span>
        <span className={styles.bowling}>{bowling_team}</span>
      </div>

      <div className={styles.scoreRow}>
        <div className={styles.scoreMain}>
          <span className={styles.runs}>
            <CountUp value={score} />
            <span className={styles.wkts}>/{wickets}</span>
          </span>
          <span className={styles.overs}>{overs} ov</span>
        </div>

        <div className={styles.rates}>
          <div className={styles.rate}>
            <span className={styles.rateLabel}>CRR</span>
            <span className={styles.rateVal}>{crr?.toFixed(2)}</span>
          </div>
          {second && (
            <>
              <div className={styles.rateDivider} />
              <div className={styles.rate}>
                <span className={styles.rateLabel}>NEED</span>
                <span className={[styles.rateVal, styles.teal].join(' ')}>
                  {runs_needed} off {data.balls_remaining}b
                </span>
              </div>
              <div className={styles.rateDivider} />
              <div className={styles.rate}>
                <span className={styles.rateLabel}>RRR</span>
                <span className={[styles.rateVal, rrr > crr + 2 ? styles.red : styles.teal].join(' ')}>
                  {rrr?.toFixed(2)}
                </span>
              </div>
            </>
          )}
          {second && (
            <div className={styles.target}>
              Target <span className={styles.targetNum}>{target}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
