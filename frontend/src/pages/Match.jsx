import { useState, useEffect, useRef, useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Cpu, ChevronRight } from 'lucide-react'
import LiveScoreboard from '../components/match/LiveScoreboard'
import CommentaryFeed from '../components/match/CommentaryFeed'
import BatsmenTable from '../components/match/BatsmenTable'
import OverDots from '../components/match/OverDots'
import RunRateGraph from '../components/match/RunRateGraph'
import WinProbability from '../components/match/WinProbability'
import { api } from '../api'
import styles from './Match.module.css'

// ── Interactive Match Component ──────────────────────────────────────────────
function InteractiveMatch({ sid, returnTo, returnLabel, returnState }) {
  const navigate = useNavigate()
  const [sess, setSess]           = useState(null)   // committed decision-point state
  const [liveBall, setLiveBall]   = useState(null)   // most recently revealed ball (cumulative score/wkts/crr)
  const [allBalls, setAllBalls]   = useState([])      // progressively revealed ball history
  const [overOutcomes, setOverOutcomes] = useState([])  // outcomes revealed so far for the current over
  const [busy, setBusy]           = useState(false)   // true from API call kickoff until animation finishes
  const [speed, setSpeed]         = useState(600)
  const [isPaused, setIsPaused]   = useState(false)
  const [suggestion, setSuggestion] = useState(null)
  const [suggLoading, setSuggLoading] = useState(false)
  const [selectedOpeners, setSelectedOpeners] = useState([])
  const [err, setErr]             = useState('')

  const speedRef  = useRef(600)
  const pausedRef = useRef(false)
  const timerRef  = useRef(null)

  useEffect(() => {
    api('GET', `/match/interactive/${sid}`).then(s => { setSess(s); setAllBalls(s.ball_log ?? []) })
  }, [sid])

  useEffect(() => () => clearInterval(timerRef.current), [])

  // Proactively surface the AI's recommendation whenever it's the user's decision to make.
  useEffect(() => {
    if (!sess) return
    const needsUserBowlerPick  = sess.pending === 'pick_bowler' && sess.user_picks_bowler
    const needsUserBatsmanPick = sess.pending === 'pick_batsman' && sess.user_picks_batsman
    if (needsUserBowlerPick || needsUserBatsmanPick) {
      getMcpSuggestion()
    } else {
      setSuggestion(null)
    }
  }, [sess?.pending, sess?.user_picks_bowler, sess?.user_picks_batsman])  // eslint-disable-line react-hooks/exhaustive-deps

  function changeSpeed(ms) {
    speedRef.current = ms
    setSpeed(ms)
  }

  function togglePause() {
    const next = !isPaused
    setIsPaused(next)
    pausedRef.current = next
  }

  // Reveal an over's balls one at a time (or instantly at speed 0), then commit the new session.
  function playOver(balls, newSess) {
    clearInterval(timerRef.current)
    setOverOutcomes([])
    if (!balls.length || speedRef.current === 0) {
      balls.forEach(b => {
        setLiveBall(b)
        setAllBalls(prev => [...prev, b])
        setOverOutcomes(prev => [...prev, b.outcome])
      })
      setSess(newSess)
      setBusy(false)
      return
    }
    let i = 0
    timerRef.current = setInterval(() => {
      if (pausedRef.current) return
      if (i >= balls.length) {
        clearInterval(timerRef.current)
        setSess(newSess)
        setBusy(false)
        return
      }
      const b = balls[i]
      setLiveBall(b)
      setAllBalls(prev => [...prev, b])
      setOverOutcomes(prev => [...prev, b.outcome])
      i++
    }, speedRef.current)
  }

  async function chooseBowler(bowlerId) {
    setBusy(true); setSuggestion(null); setErr('')
    try {
      const s = await api('POST', `/match/interactive/${sid}/over`, { bowler_id: bowlerId })
      playOver(s.last_over_balls ?? [], s)
    } catch(e) { setErr(e.message); setBusy(false) }
  }

  async function chooseBatsman(batsmanId) {
    setBusy(true); setSuggestion(null); setErr('')
    try {
      const s = await api('POST', `/match/interactive/${sid}/batsman`, { batsman_id: batsmanId })
      setSess(s)
    } catch(e) { setErr(e.message) }
    setBusy(false)
  }

  function toggleOpener(id) {
    setSelectedOpeners(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id)
      if (prev.length >= 2) return prev
      return [...prev, id]
    })
  }

  async function confirmOpeners() {
    if (selectedOpeners.length !== 2) return
    setBusy(true); setErr('')
    try {
      const s = await api('POST', `/match/interactive/${sid}/openers`, {
        striker_id: selectedOpeners[0], non_striker_id: selectedOpeners[1],
      })
      setSess(s)
      setSelectedOpeners([])
    } catch(e) { setErr(e.message) }
    setBusy(false)
  }

  async function goNextInnings() {
    setBusy(true)
    try {
      const s = await api('POST', `/match/interactive/${sid}/next-innings`)
      setAllBalls([]); setOverOutcomes([]); setLiveBall(null)
      setSess(s); setSuggestion(null)
    } catch(e) { setErr(e.message) }
    setBusy(false)
  }

  async function getMcpSuggestion() {
    setSuggLoading(true)
    try {
      const s = await api('GET', `/match/interactive/${sid}/suggest`)
      setSuggestion(s)
    } catch(e) { setErr(e.message) }
    setSuggLoading(false)
  }

  // AI-controlled side: use the same phase/situation-aware suggestion engine
  // instead of just grabbing whichever candidate happens to be listed first.
  async function autoPlayBowler() {
    setBusy(true); setErr('')
    try {
      const sugg = await api('GET', `/match/interactive/${sid}/suggest`)
      const bowlerId = sugg.suggestion || sess.available_bowlers?.[0]?.id
      if (!bowlerId) { setBusy(false); return }
      const s = await api('POST', `/match/interactive/${sid}/over`, { bowler_id: bowlerId })
      playOver(s.last_over_balls ?? [], s)
    } catch(e) { setErr(e.message); setBusy(false) }
  }

  async function autoPlayBatsman() {
    setBusy(true); setErr('')
    try {
      const sugg = await api('GET', `/match/interactive/${sid}/suggest`)
      const batsmanId = sugg.suggestion || sess.available_batsmen?.[0]?.id
      if (!batsmanId) { setBusy(false); return }
      const s = await api('POST', `/match/interactive/${sid}/batsman`, { batsman_id: batsmanId })
      setSess(s)
    } catch(e) { setErr(e.message) }
    setBusy(false)
  }

  async function goToScorecard() {
    try {
      const result = await api('GET', `/match/interactive/${sid}/result`)
      navigate('/scorecard', {
        state: { matchData: result, returnTo, returnLabel, returnState },
      })
    } catch(e) { setErr(e.message) }
  }

  if (!sess) return <div className={styles.loading}>Loading match…</div>

  const phase       = sess.phase_key ?? 'powerplay'
  const phaseLabel  = sess.phase ?? 'Powerplay'
  const userBowling = sess.user_picks_bowler
  const userBatting = sess.user_picks_batsman
  const isPending        = sess.pending === 'pick_bowler'
  const isPendingBatsman = sess.pending === 'pick_batsman'
  const isPendingOpeners = sess.pending === 'pick_openers'
  const isBreak          = sess.pending === 'innings_break'
  const isDone           = sess.pending === 'complete'

  // Live/cumulative figures: prefer the most recently revealed ball, fall back to committed state.
  const lb = liveBall
  const liveRuns       = lb ? lb.runs        : sess.runs
  const liveWkts       = lb ? lb.wickets     : sess.wickets
  const liveOverStr    = lb ? lb.over_str    : sess.over_str
  const liveCrr        = lb ? lb.crr         : sess.crr
  const liveRrr        = lb ? (lb.rrr ?? null) : sess.rrr
  const liveRunsNeeded = lb ? (lb.runs_needed ?? null) : sess.runs_needed

  const batsmen        = allBalls.length ? computeBatsmen(allBalls, allBalls.length - 1) : (sess.active_batsmen ?? [])
  const currentBowler  = allBalls.length ? computeBowler(allBalls, allBalls.length - 1) : sess.current_bowler
  const rrHistory      = buildRRHistory(allBalls)
  const targetRR       = sess.inning === 2 && sess.target ? +(sess.target / 20).toFixed(2) : null

  // Build display from session for LiveScoreboard
  const liveData = {
    score: liveRuns, wickets: liveWkts, overs: liveOverStr,
    crr: liveCrr, target: sess.target, runs_needed: liveRunsNeeded,
    rrr: liveRrr, batting_team: sess.bat_team, bowling_team: sess.fld_team,
    batsmen: batsmen.length ? batsmen : (sess.active_batsmen ?? []),
    currentBowler: currentBowler ?? sess.current_bowler,
    overBalls: overOutcomes,
    currentOver: parseInt((liveOverStr || '0.0').split('.')[0]),
    feed: allBalls
      .map((b, idx) => ({ over: b.over_str, outcome: b.outcome, text: b.commentary, seq: idx }))
      .slice(-300)
      .reverse(),
    rrHistory,
    winProb: sess.inning === 2 && sess.target
      ? Math.round(Math.min(95, Math.max(5, (liveRuns / sess.target) * 70 + ((10 - liveWkts) / 10) * 30)))
      : 50,
  }

  const SPEEDS = [
    { ms: 1200, label: '0.8x' },
    { ms: 600,  label: '1x' },
    { ms: 200,  label: '3x' },
    { ms: 0,    label: '⚡' },
  ]

  return (
    <div className={styles.root}>
      {/* Topbar */}
      <header className={styles.topbar}>
        <div className={styles.matchTitle}>
          {sess.bat_team} vs {sess.fld_team}
          <span className={styles.stadium}> · {sess.stadium?.name}</span>
        </div>
        <div className={styles.controls}>
          <span className={[styles.phaseBadge, styles[`phase_${phase}`]].join(' ')}>{phaseLabel}</span>
          {sess.user_team && (
            <span className={styles.managingBadge}>Managing: {sess.user_team}</span>
          )}
          {SPEEDS.map(({ ms, label }) => (
            <button
              key={ms}
              className={[styles.speedBtn, speed === ms ? styles.speedActive : ''].join(' ')}
              onClick={() => changeSpeed(ms)}
            >{label}</button>
          ))}
          <button className={styles.pauseBtn} onClick={togglePause} disabled={!busy}>
            {isPaused ? '▶' : '⏸'}
          </button>
        </div>
      </header>

      <LiveScoreboard data={liveData} />

      <div className={styles.body}>
        <div className={styles.left}>
          {/* Opener picker (user's team is batting first this innings) */}
          {isPendingOpeners && sess.user_picks_openers && !busy && (
            <motion.div
              className={styles.pickerPanel}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className={styles.pickerHeader}>
                <span>Pick Your Openers ({selectedOpeners.length}/2)</span>
                <button
                  className={styles.mcpBtn}
                  onClick={confirmOpeners}
                  disabled={selectedOpeners.length !== 2 || busy}
                >
                  Confirm
                </button>
              </div>

              <div className={styles.pickerList}>
                {(sess.available_openers ?? []).map(b => (
                  <motion.button
                    key={b.id}
                    className={[
                      styles.pickerItem,
                      selectedOpeners.includes(b.id) ? styles.pickerSuggested : '',
                    ].join(' ')}
                    whileHover={{ backgroundColor: 'var(--surface-2)' }}
                    onClick={() => toggleOpener(b.id)}
                    disabled={busy}
                  >
                    <div className={styles.pickerName}>
                      {selectedOpeners.includes(b.id) && <span className={styles.suggStar}>★ </span>}
                      {b.name}
                      <span className={styles.pickerMeta}>{b.role?.replace('_', ' ')}</span>
                    </div>
                    <div className={styles.pickerStats}>
                      <span className={styles.statChip} title="Bat power">Bat {Math.round(b.bat_power * 100)}</span>
                      <span className={styles.statChip} title="Bat control">Ctrl {Math.round(b.bat_control * 100)}</span>
                      <span className={styles.statChip} title="Aggression">Agg {Math.round(b.bat_aggression * 100)}</span>
                    </div>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Batsman picker (wicket fell, user's team is batting) */}
          {isPendingBatsman && userBatting && !busy && (
            <motion.div
              className={styles.pickerPanel}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className={styles.pickerHeader}>
                <span>Wicket! Send in next batsman</span>
                <button
                  className={styles.mcpBtn}
                  onClick={getMcpSuggestion}
                  disabled={suggLoading}
                >
                  <Cpu size={12} />
                  {suggLoading ? 'Thinking…' : 'Refresh'}
                </button>
              </div>

              {suggestion && (
                <motion.div className={styles.suggBox} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <div className={styles.suggTitle}>MCP Suggestion: <strong>{suggestion.player_name}</strong></div>
                  <div className={styles.suggReason}>{suggestion.reason}</div>
                </motion.div>
              )}

              <div className={styles.pickerList}>
                {(sess.available_batsmen ?? []).map(b => (
                  <motion.button
                    key={b.id}
                    className={[
                      styles.pickerItem,
                      suggestion?.suggestion === b.id ? styles.pickerSuggested : '',
                    ].join(' ')}
                    whileHover={{ backgroundColor: 'var(--surface-2)' }}
                    onClick={() => chooseBatsman(b.id)}
                    disabled={busy}
                  >
                    <div className={styles.pickerName}>
                      {suggestion?.suggestion === b.id && <span className={styles.suggStar}>★ </span>}
                      {b.name}
                      <span className={styles.pickerMeta}>{b.role?.replace('_', ' ')}</span>
                    </div>
                    <div className={styles.pickerStats}>
                      <span className={styles.statChip} title="Bat power">Bat {Math.round(b.bat_power * 100)}</span>
                      <span className={styles.statChip} title="Bat control">Ctrl {Math.round(b.bat_control * 100)}</span>
                      <span className={styles.statChip} title="Pressure handling">Prs {Math.round(b.pressure_handling * 100)}</span>
                    </div>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Bowler picker */}
          {isPending && userBowling && !busy && (
            <motion.div
              className={styles.pickerPanel}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className={styles.pickerHeader}>
                <span>Pick Bowler — Over {sess.over + 1}</span>
                <button
                  className={styles.mcpBtn}
                  onClick={getMcpSuggestion}
                  disabled={suggLoading}
                >
                  <Cpu size={12} />
                  {suggLoading ? 'Thinking…' : 'Refresh'}
                </button>
              </div>

              {suggestion && (
                <motion.div
                  className={styles.suggBox}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <div className={styles.suggTitle}>MCP Suggestion: <strong>{suggestion.player_name}</strong></div>
                  <div className={styles.suggReason}>{suggestion.reason}</div>
                </motion.div>
              )}

              <div className={styles.pickerList}>
                {(sess.available_bowlers ?? []).map(b => (
                  <motion.button
                    key={b.id}
                    className={[
                      styles.pickerItem,
                      suggestion?.suggestion === b.id ? styles.pickerSuggested : '',
                    ].join(' ')}
                    whileHover={{ backgroundColor: 'var(--surface-2)' }}
                    onClick={() => chooseBowler(b.id)}
                    disabled={busy}
                  >
                    <div className={styles.pickerName}>
                      {suggestion?.suggestion === b.id && <span className={styles.suggStar}>★ </span>}
                      {b.name}
                      <span className={styles.pickerMeta}>{b.bowling_type} · {b.overs_bowled}/4 ov</span>
                    </div>
                    <div className={styles.pickerStats}>
                      <span className={styles.statChip} title="Wicket threat">W {Math.round(b.wicket_threat * 100)}</span>
                      <span className={styles.statChip} title="Economy skill">E {Math.round(b.economy_skill * 100)}</span>
                      <span className={styles.statChip} title="Death skill">D {Math.round(b.death_skill * 100)}</span>
                    </div>
                    {b.overs_bowled > 0 && (
                      <div className={styles.pickerRecord}>
                        {b.runs_given}R · {b.wickets}W in match
                      </div>
                    )}
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Auto-play when user doesn't control bowling */}
          {isPending && !userBowling && !busy && (
            <div className={styles.autoPanel}>
              <div className={styles.autoPanelText}>AI managing {sess.fld_team} bowling</div>
              <button className={styles.autoBtn} onClick={autoPlayBowler}>
                <ChevronRight size={14} /> Simulate next over
              </button>
            </div>
          )}

          {/* Auto-play when user doesn't control batting (AI's team lost a wicket) */}
          {isPendingBatsman && !userBatting && !busy && (
            <div className={styles.autoPanel}>
              <div className={styles.autoPanelText}>AI managing {sess.bat_team} batting</div>
              <button className={styles.autoBtn} onClick={autoPlayBatsman}>
                <ChevronRight size={14} /> Send in next batsman
              </button>
            </div>
          )}

          {busy && (
            <div className={styles.simulatingMsg}>
              {isPaused ? 'Paused…' : 'Simulating…'}
            </div>
          )}

          {/* Batsmen + bowler panel */}
          {allBalls.length > 0 && (
            <div className={styles.panel}>
              <div className={styles.panelTitle}>Batting</div>
              <BatsmenTable batsmen={liveData.batsmen} />
              {liveData.currentBowler && (
                <>
                  <div className={styles.divider} />
                  <div className={styles.panelTitle}>Bowling</div>
                  <table className={styles.bowlerTable}>
                    <thead><tr><th>Bowler</th><th>O</th><th>R</th><th>W</th></tr></thead>
                    <tbody>
                      <tr>
                        <td>{liveData.currentBowler.name}</td>
                        <td>{liveData.currentBowler.overs}</td>
                        <td>{liveData.currentBowler.runs}</td>
                        <td>{liveData.currentBowler.wickets}</td>
                      </tr>
                    </tbody>
                  </table>
                </>
              )}
              <div className={styles.divider} />
              <OverDots balls={overOutcomes} overNum={liveData.currentOver} />
            </div>
          )}

          {rrHistory.length > 1 && (
            <div className={styles.panel} style={{ marginTop: '1px' }}>
              <div className={styles.panelTitle}>Run Rate</div>
              <RunRateGraph data={rrHistory} targetRR={targetRR} />
            </div>
          )}

          {sess.inning === 2 && allBalls.length > 0 && (
            <div className={styles.panel} style={{ marginTop: '1px' }}>
              <div className={styles.panelTitle}>Win Probability</div>
              <WinProbability prob={liveData.winProb} team1={sess.fld_team} team2={sess.bat_team} />
            </div>
          )}
        </div>

        {/* Commentary */}
        <div className={styles.right}>
          <div className={styles.feedWrap}>
            <div className={styles.panelTitle}>Live Commentary</div>
            <CommentaryFeed balls={liveData.feed} />
          </div>
        </div>
      </div>

      {/* Innings break overlay */}
      <AnimatePresence>
        {isBreak && (
          <motion.div
            className={styles.inningsDone}
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className={styles.doneMsg}>
              <strong>{sess.bat_team}</strong> finished: {sess.runs}/{sess.wickets} ({sess.over_str} ov)
            </div>
            <div className={styles.doneTarget}>
              {sess.fld_team} need <strong>{sess.runs + 1}</strong> to win
            </div>
            <button className={styles.doneBtn} onClick={goNextInnings} disabled={busy}>
              {busy ? 'Setting up…' : '▶ Start 2nd Innings'}
            </button>
          </motion.div>
        )}

        {isDone && (
          <motion.div
            className={styles.inningsDone}
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className={styles.doneMsg}>Match complete!</div>
            <button className={styles.doneBtn} onClick={goToScorecard}>→ View Scorecard</button>
          </motion.div>
        )}
      </AnimatePresence>

      {err && <div className={styles.errBar}>{err}</div>}
    </div>
  )
}

function buildRRHistory(balls) {
  const history = []; let lastOv = -1
  for (const b of balls) {
    const [ov] = b.over_str.split('.').map(Number)
    if (ov !== lastOv) { lastOv = ov; history.push({ over: ov + 1, crr: b.crr ?? 0 }) }
    else history[history.length - 1].crr = b.crr ?? 0
  }
  return history
}

// ── Shared helpers to compute batsmen/bowler state from a ball log ──────────
function computeBatsmen(balls, upTo) {
  const statMap = {}
  for (let i = 0; i <= upTo; i++) {
    const b = balls[i]
    if (!statMap[b.batsman]) {
      statMap[b.batsman] = { name: b.batsman, runs: 0, balls: 0, fours: 0, sixes: 0, status: 'batting' }
    }
    const s = statMap[b.batsman]
    if (!['Wd', 'Nb'].includes(b.outcome)) s.balls++
    if (!['W', 'Wd', 'Nb'].includes(b.outcome)) s.runs += parseInt(b.outcome) || 0
    if (b.outcome === '4') s.fours++
    if (b.outcome === '6') s.sixes++
    if (b.outcome === 'W') s.status = 'out'
  }
  // Only show 2 at a time (striker + non-striker = recent 2 active)
  const active = Object.values(statMap).filter(x => x.status === 'batting')
  const showing = active.slice(-2)
  return showing.map(s => ({ ...s, sr: s.balls > 0 ? +((s.runs / s.balls) * 100).toFixed(1) : 0 }))
}

function computeBowler(balls, upTo) {
  const b = balls[upTo]
  const name = b.bowler
  let legalBalls = 0, runs = 0, wickets = 0
  for (let i = 0; i <= upTo; i++) {
    const ball = balls[i]
    if (ball.bowler !== name) continue
    if (['Wd', 'Nb'].includes(ball.outcome)) { runs += 1; continue }
    legalBalls++
    if (ball.outcome === 'W') wickets++
    else runs += parseInt(ball.outcome) || 0
  }
  const ov = `${Math.floor(legalBalls / 6)}.${legalBalls % 6}`
  return { name, overs: ov, runs, wickets }
}

// ── Standard (pre-simulated) Match ──────────────────────────────────────────
function initDisplay(innings, inningsIdx) {
  return {
    score: 0, wickets: 0, overs: '0.0', crr: 0,
    target: inningsIdx === 1 ? (innings.prev_runs ?? 0) + 1 : null,
    runs_needed: null, rrr: null, balls_remaining: null,
    batting_team: innings.team,
    bowling_team: innings.bowling_team ?? '—',
    batsmen: [],
    currentBowler: null,
    overBalls: [],
    currentOver: -1,
    feed: [],
    rrHistory: [],
    winProb: 50,
  }
}

function ballsRemaining(overStr) {
  const [ov, bl] = overStr.split('.').map(Number)
  return (20 - ov) * 6 - bl
}

export default function Match() {
  const { state } = useLocation()
  const navigate  = useNavigate()

  // Interactive mode: route to dedicated component
  if (state?.interactive && state?.sid) {
    return (
      <InteractiveMatch
        sid={state.sid}
        returnTo={state.returnTo ?? '/'}
        returnLabel={state.returnLabel}
        returnState={state.returnState}
      />
    )
  }

  const matchData = state?.matchData
  const initSpeed = state?.speed ?? 600
  const returnTo  = state?.returnTo ?? '/'

  const [inningsIdx, setInningsIdx] = useState(0)
  const [speed, setSpeed]           = useState(initSpeed)
  const [isPaused, setIsPaused]     = useState(false)
  const [display, setDisplay]       = useState(null)
  const [inningsDone, setInningsDone] = useState(false)

  const ballIdxRef   = useRef(0)
  const timerRef     = useRef(null)
  const speedRef     = useRef(initSpeed)
  const pausedRef    = useRef(false)
  const displayRef   = useRef(null)

  const innings = inningsIdx === 0 ? matchData?.inn1 : matchData?.inn2

  function processRRHistory(balls, upTo) {
    const history = []
    let lastOv = -1
    for (let i = 0; i <= upTo; i++) {
      const b = balls[i]
      const [ov] = b.over_str.split('.').map(Number)
      if (ov !== lastOv) {
        lastOv = ov
        history.push({ over: ov + 1, crr: b.crr ?? 0 })
      } else {
        history[history.length - 1].crr = b.crr ?? 0
      }
    }
    return history
  }

  // ── Process a single ball into display state ───────────────────────
  const processball = useCallback((balls, idx, prev, inIdx) => {
    const b = balls[idx]
    const [ov] = b.over_str.split('.').map(Number)

    const overBalls = ov !== prev.currentOver
      ? [b.outcome]
      : [...prev.overBalls, b.outcome]

    const feedEntry = {
      over: b.over_str,
      outcome: b.outcome,
      text: b.commentary,
      seq: idx,
    }

    const batsmen     = computeBatsmen(balls, idx)
    const currentBowler = computeBowler(balls, idx)
    const rrHistory   = processRRHistory(balls, idx)

    const runsNeeded  = b.runs_needed ?? null
    const ballsLeft   = runsNeeded !== null ? ballsRemaining(b.over_str) : null

    // Simple win-prob: percentage of runs already scored vs target (2nd inn only)
    let winProb = 50
    if (inIdx === 1 && b.runs !== undefined) {
      const target = matchData.inn1.runs + 1
      const scored = b.runs
      const wkts   = b.wickets
      const ballsDone = (parseInt(b.over_str.split('.')[0]) * 6) + parseInt(b.over_str.split('.')[1])
      // crude: progress towards target * wickets factor
      const progress = scored / target
      const wktFactor = (10 - wkts) / 10
      winProb = Math.round(Math.min(95, Math.max(5, progress * 70 + wktFactor * 30)))
    }

    return {
      score: b.runs, wickets: b.wickets, overs: b.over_str, crr: b.crr ?? 0,
      target: inIdx === 1 ? matchData.inn1.runs + 1 : null,
      runs_needed: runsNeeded,
      balls_remaining: ballsLeft,
      rrr: b.rrr ?? null,
      batting_team: innings?.team ?? '—',
      bowling_team: inIdx === 0 ? matchData.fld_first : matchData.bat_first,
      batsmen,
      currentBowler,
      overBalls,
      currentOver: ov,
      feed: [feedEntry, ...prev.feed].slice(0, 300),
      rrHistory,
      winProb,
    }
  }, [innings, matchData])

  // ── Start a tick loop ───────────────────────────────────────────────
  const startLoop = useCallback((balls, spd) => {
    clearInterval(timerRef.current)
    if (spd === 0) {
      // Instant: process all balls
      let d = initDisplay(innings, inningsIdx)
      balls.forEach((_, i) => { d = processball(balls, i, d, inningsIdx) })
      setDisplay(d)
      displayRef.current = d
      setInningsDone(true)
      return
    }
    timerRef.current = setInterval(() => {
      if (pausedRef.current) return
      const idx = ballIdxRef.current
      if (idx >= balls.length) {
        clearInterval(timerRef.current)
        setInningsDone(true)
        return
      }
      setDisplay(prev => {
        const next = processball(balls, idx, prev, inningsIdx)
        displayRef.current = next
        return next
      })
      ballIdxRef.current++
    }, spd)
  }, [innings, inningsIdx, processball])

  // ── Init / re-init on innings change ────────────────────────────────
  useEffect(() => {
    if (!matchData) return
    const inn = inningsIdx === 0 ? matchData.inn1 : matchData.inn2
    const initial = initDisplay(inn, inningsIdx)
    setDisplay(initial)
    displayRef.current = initial
    ballIdxRef.current = 0
    setInningsDone(false)
    startLoop(inn.balls, speedRef.current)
    return () => clearInterval(timerRef.current)
  }, [inningsIdx, matchData])   // eslint-disable-line react-hooks/exhaustive-deps

  // ── Speed change ────────────────────────────────────────────────────
  function changeSpeed(ms) {
    speedRef.current = ms
    setSpeed(ms)
    const inn = inningsIdx === 0 ? matchData.inn1 : matchData.inn2
    clearInterval(timerRef.current)
    if (ms === 0) {
      // Instant from current position
      let d = displayRef.current || initDisplay(inn, inningsIdx)
      for (let i = ballIdxRef.current; i < inn.balls.length; i++) {
        d = processball(inn.balls, i, d, inningsIdx)
      }
      ballIdxRef.current = inn.balls.length
      setDisplay(d)
      displayRef.current = d
      setInningsDone(true)
    } else {
      timerRef.current = setInterval(() => {
        if (pausedRef.current) return
        const idx = ballIdxRef.current
        if (idx >= inn.balls.length) { clearInterval(timerRef.current); setInningsDone(true); return }
        setDisplay(prev => {
          const next = processball(inn.balls, idx, prev, inningsIdx)
          displayRef.current = next
          return next
        })
        ballIdxRef.current++
      }, ms)
    }
  }

  function togglePause() {
    const next = !isPaused
    setIsPaused(next)
    pausedRef.current = next
  }

  function goNextInnings() {
    setInningsIdx(1)
  }

  function goToScorecard() {
    navigate('/scorecard', {
      state: {
        matchData,
        returnTo,
        returnLabel: state?.returnLabel,
        returnState: state?.returnState,
      },
    })
  }

  if (!matchData) {
    return (
      <div style={{ padding: '2rem', color: 'var(--text-muted)', textAlign: 'center' }}>
        No match data. <a href="/" style={{ color: 'var(--gold)' }}>Go home</a>
      </div>
    )
  }

  const targetRR = inningsIdx === 1
    ? +((matchData.inn1.runs + 1) / 20).toFixed(2)
    : null

  const SPEEDS = [
    { ms: 1200, label: '0.8x' },
    { ms: 600,  label: '1x' },
    { ms: 200,  label: '3x' },
    { ms: 0,    label: '⚡' },
  ]

  return (
    <div className={styles.root}>
      {/* ── Topbar ── */}
      <header className={styles.topbar}>
        <div className={styles.matchTitle}>
          {matchData.bat_first} vs {matchData.fld_first}
          <span className={styles.stadium}> · {matchData.stadium.name}</span>
        </div>
        <div className={styles.controls}>
          {SPEEDS.map(({ ms, label }) => (
            <button
              key={ms}
              className={[styles.speedBtn, speed === ms ? styles.speedActive : ''].join(' ')}
              onClick={() => changeSpeed(ms)}
            >{label}</button>
          ))}
          <button className={styles.pauseBtn} onClick={togglePause}>
            {isPaused ? '▶' : '⏸'}
          </button>
        </div>
      </header>

      {/* ── Scoreboard ── */}
      {display && (
        <LiveScoreboard data={display} />
      )}

      {/* ── Main content ── */}
      <div className={styles.body}>
        {/* Left panel */}
        <div className={styles.left}>
          <div className={styles.panel}>
            <div className={styles.panelTitle}>Batting</div>
            <BatsmenTable batsmen={display?.batsmen ?? []} />

            {display?.currentBowler && (
              <>
                <div className={styles.divider} />
                <div className={styles.panelTitle}>Bowling</div>
                <table className={styles.bowlerTable}>
                  <thead><tr><th>Bowler</th><th>O</th><th>R</th><th>W</th></tr></thead>
                  <tbody>
                    <tr>
                      <td>{display.currentBowler.name}</td>
                      <td>{display.currentBowler.overs}</td>
                      <td>{display.currentBowler.runs}</td>
                      <td>{display.currentBowler.wickets}</td>
                    </tr>
                  </tbody>
                </table>
              </>
            )}

            {display && (
              <>
                <div className={styles.divider} />
                <OverDots balls={display.overBalls} overNum={display.currentOver + 1} />
              </>
            )}
          </div>

          {inningsIdx === 1 && display && (
            <div className={styles.panel} style={{ marginTop: '1px' }}>
              <div className={styles.panelTitle}>Win Probability</div>
              <WinProbability
                prob={display.winProb}
                team1={matchData.fld_first}
                team2={matchData.bat_first}
              />
            </div>
          )}

          {display?.rrHistory?.length > 1 && (
            <div className={styles.panel} style={{ marginTop: '1px' }}>
              <div className={styles.panelTitle}>Run Rate</div>
              <RunRateGraph data={display.rrHistory} targetRR={targetRR} />
            </div>
          )}
        </div>

        {/* Commentary */}
        <div className={styles.right}>
          <div className={styles.feedWrap}>
            <div className={styles.panelTitle}>Live Commentary</div>
            <CommentaryFeed balls={display?.feed ?? []} />
          </div>
        </div>
      </div>

      {/* ── Innings done overlay ── */}
      <AnimatePresence>
        {inningsDone && (
          <motion.div
            className={styles.inningsDone}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            {inningsIdx === 0 ? (
              <>
                <div className={styles.doneMsg}>
                  <strong>{matchData.inn1.team}</strong> finished:{' '}
                  {matchData.inn1.runs}/{matchData.inn1.wickets} ({matchData.inn1.overs} ov)
                </div>
                <div className={styles.doneTarget}>
                  {matchData.fld_first} need <strong>{matchData.inn1.runs + 1}</strong> to win
                </div>
                <button className={styles.doneBtn} onClick={goNextInnings}>
                  ▶ Start 2nd Innings
                </button>
              </>
            ) : (
              <>
                <div className={styles.doneMsg}>
                  Match complete!{' '}
                  {matchData.result.winner
                    ? <><strong>{matchData.result.winner}</strong> won by {matchData.result.margin}</>
                    : 'Match Tied!'}
                </div>
                <button className={styles.doneBtn} onClick={goToScorecard}>
                  → View Scorecard
                </button>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
