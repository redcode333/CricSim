import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Button from '../ui/Button'
import { api } from '../../api'
import styles from './TossModal.module.css'

// Stage machine: 'call' -> 'flipping' -> 'result' -> (if user won) 'choose' -> done
export default function TossModal({ callerLabel, opponentLabel, stadiumId, onResolved }) {
  const [stage, setStage]   = useState('call')
  const [call, setCall]     = useState(null)
  const [toss, setToss]     = useState(null)
  const [err, setErr]       = useState('')

  async function makeCall(c) {
    setCall(c)
    setStage('flipping')
    setErr('')
    try {
      const data = await api('POST', '/match/toss', {
        caller_team: callerLabel,
        opponent_team: opponentLabel,
        stadium_id: stadiumId,
        call: c,
      })
      // Let the coin animation play a beat before revealing the result.
      setTimeout(() => {
        setToss(data)
        setStage('result')
        if (!data.user_won_toss) {
          setTimeout(() => onResolved(data.bat_first_team), 1400)
        }
      }, 900)
    } catch (e) {
      setErr(e.message)
      setStage('call')
    }
  }

  function choose(decision) {
    const batFirst = decision === 'bat' ? callerLabel : opponentLabel
    setStage('choose-done')
    setTimeout(() => onResolved(batFirst), 700)
  }

  return (
    <div className={styles.overlay}>
      <motion.div
        className={styles.card}
        initial={{ opacity: 0, y: 12, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.22 }}
      >
        <div className={styles.header}>Toss</div>
        <div className={styles.matchup}>{callerLabel} <span className={styles.vs}>vs</span> {opponentLabel}</div>

        <AnimatePresence mode="wait">
          {stage === 'call' && (
            <motion.div key="call" className={styles.stage} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <div className={styles.prompt}>Call it in the air</div>
              <div className={styles.callRow}>
                <Button accent="gold" onClick={() => makeCall('heads')}>Heads</Button>
                <Button accent="teal" onClick={() => makeCall('tails')}>Tails</Button>
              </div>
              {err && <div className={styles.err}>{err}</div>}
            </motion.div>
          )}

          {stage === 'flipping' && (
            <motion.div key="flipping" className={styles.stage} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <motion.div
                className={styles.coin}
                animate={{ rotateY: [0, 360, 720, 1080] }}
                transition={{ duration: 0.9, ease: 'linear' }}
              >🪙</motion.div>
              <div className={styles.prompt}>Flipping…</div>
            </motion.div>
          )}

          {stage === 'result' && toss && (
            <motion.div key="result" className={styles.stage} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <div className={styles.coinResult}>{toss.coin_result === 'heads' ? '🪙 Heads' : '🪙 Tails'}</div>
              {toss.user_won_toss ? (
                <>
                  <div className={styles.prompt}>You called {toss.user_call} — you won the toss!</div>
                  <div className={styles.callRow}>
                    <Button accent="gold" onClick={() => choose('bat')}>Bat First</Button>
                    <Button accent="teal" onClick={() => choose('field')}>Field First</Button>
                  </div>
                </>
              ) : (
                <div className={styles.prompt}>
                  You called {toss.user_call} — {opponentLabel} won the toss and chose to {toss.ai_decision} first.
                </div>
              )}
            </motion.div>
          )}

          {stage === 'choose-done' && (
            <motion.div key="done" className={styles.stage} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <div className={styles.prompt}>Let's play!</div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
