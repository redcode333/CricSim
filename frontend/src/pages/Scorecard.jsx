import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import styles from './Scorecard.module.css'

function InningsCard({ inn }) {
  return (
    <div className={styles.inningsBlock}>
      <div className={styles.inningsHeader}>
        <span className={styles.inningsTeam}>{inn.team}</span>
        <span className={styles.inningsScore}>
          {inn.runs}/{inn.wickets}
          <span className={styles.inningsOvers}> ({inn.overs} ov)</span>
        </span>
      </div>

      {/* Batting */}
      <div className={styles.tableLabel}>Batting</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Batsman</th>
            <th>R</th><th>B</th><th>4s</th><th>6s</th><th>SR</th>
          </tr>
        </thead>
        <tbody>
          {inn.bat_stats.map(b => (
            <tr key={b.name} className={b.dismissed ? styles.out : styles.notOut}>
              <td className={styles.nameCell}>{b.name}</td>
              <td className={styles.mono}>{b.runs}</td>
              <td className={styles.mono}>{b.balls}</td>
              <td className={styles.mono}>{b.fours}</td>
              <td className={styles.mono}>{b.sixes}</td>
              <td className={[styles.mono, b.sr >= 150 ? styles.srHigh : ''].join(' ')}>
                {b.sr?.toFixed ? b.sr.toFixed(1) : b.sr}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Fall of wickets */}
      {inn.fow?.length > 0 && (
        <div className={styles.fow}>
          <span className={styles.fowLabel}>FoW: </span>
          {inn.fow.map((f, i) => (
            <span key={i} className={styles.fowItem}>
              {f.n}-{f.score} ({f.batsman}, {f.over}){i < inn.fow.length - 1 ? ' · ' : ''}
            </span>
          ))}
        </div>
      )}

      {/* Bowling */}
      <div className={styles.tableLabel} style={{ marginTop: '1rem' }}>Bowling</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Bowler</th>
            <th>O</th><th>R</th><th>W</th><th>Eco</th>
          </tr>
        </thead>
        <tbody>
          {inn.bowl_stats.map(b => (
            <tr key={b.name}>
              <td className={styles.nameCell}>{b.name}</td>
              <td className={styles.mono}>{b.overs}</td>
              <td className={styles.mono}>{b.runs}</td>
              <td className={[styles.mono, b.wickets > 0 ? styles.wktCell : ''].join(' ')}>{b.wickets}</td>
              <td className={styles.mono}>{b.economy?.toFixed ? b.economy.toFixed(2) : b.economy}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Scorecard() {
  const { state } = useLocation()
  const navigate  = useNavigate()
  const [tab, setTab] = useState(0)

  const matchData   = state?.matchData
  const returnTo    = state?.returnTo ?? '/'
  const returnLabel = state?.returnLabel ?? '← Menu'
  const returnState = state?.returnState ?? null

  if (!matchData) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        No scorecard data. <a href="/" style={{ color: 'var(--gold)' }}>Go home</a>
      </div>
    )
  }

  const { inn1, inn2, result } = matchData

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div>
            <div className={styles.title}>Scorecard</div>
            <div className={styles.subtitle}>{matchData.bat_first} vs {matchData.fld_first}</div>
          </div>
          <button
            className={styles.backBtn}
            onClick={() => navigate(returnTo, returnState ? { state: returnState } : {})}
          >
            {returnLabel}
          </button>
        </div>
      </header>

      {/* Result banner */}
      <motion.div
        className={styles.resultBanner}
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        {result.winner
          ? <><span className={styles.winner}>{result.winner}</span> won by {result.margin}</>
          : 'Match Tied!'}
      </motion.div>

      {/* Innings tabs */}
      <div className={styles.tabs}>
        <button
          className={[styles.tabBtn, tab === 0 ? styles.tabActive : ''].join(' ')}
          onClick={() => setTab(0)}
        >
          1st Innings — {inn1.team}
        </button>
        <button
          className={[styles.tabBtn, tab === 1 ? styles.tabActive : ''].join(' ')}
          onClick={() => setTab(1)}
        >
          2nd Innings — {inn2.team}
        </button>
      </div>

      <div className={styles.content}>
        {tab === 0 && <InningsCard inn={inn1} />}
        {tab === 1 && <InningsCard inn={inn2} />}
      </div>
    </div>
  )
}
