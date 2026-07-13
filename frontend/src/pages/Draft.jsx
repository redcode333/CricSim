import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ChevronLeft, Search } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { api } from '../api'
import TossModal from '../components/match/TossModal'
import styles from './Draft.module.css'

const ROLE_COLOR = {
  batter: 'gold', bowler: 'teal', all_rounder: 'green', wicket_keeper: 'red',
}

function XiList({ players, title, count }) {
  return (
    <div className={styles.xiCard}>
      <div className={styles.xiHeader}>
        <span>{title}</span>
        <span className={styles.xiCount}>{count}/11</span>
      </div>
      <ul className={styles.xiList}>
        {players.map(p => (
          <li key={p.id} className={styles.xiItem}>
            <span>{p.name}</span>
            <span className={[styles.rolePip, styles[`role_${ROLE_COLOR[p.role] || 'gold'}`]].join(' ')}>
              {p.role?.replace('_', ' ')}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function Draft() {
  const { user }  = useAuth()
  const navigate  = useNavigate()
  const { state } = useLocation()

  const [phase, setPhase]       = useState('draft')  // draft | setup-series | series
  const [sid, setSid]           = useState(null)
  const [draftData, setDraftData] = useState(null)
  const [pool, setPool]         = useState([])
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(false)
  const [err, setErr]           = useState('')

  const [stadiums, setStadiums] = useState([])
  const [seriesFormat, setSeriesFormat] = useState(1)
  const [seriesStadium, setSeriesStadium] = useState('')

  const [userWins, setUserWins] = useState(0)
  const [aiWins, setAiWins]     = useState(0)
  const [seriesDone, setSeriesDone] = useState(false)
  const [seriesWinner, setSeriesWinner] = useState(null)
  const [currentFormat, setCurrentFormat] = useState(null)
  const [seriesTossPending, setSeriesTossPending] = useState(null)  // fmt awaiting toss, or null

  useEffect(() => {
    if (state?.restorePhase === 'series') {
      setSid(state.sid)
      setUserWins(state.userWins ?? 0)
      setAiWins(state.aiWins ?? 0)
      setSeriesDone(state.seriesDone ?? false)
      setSeriesWinner(state.seriesWinner ?? null)
      setCurrentFormat(state.currentFormat ?? null)
      setPhase('series')
      return
    }
    if (state?.restorePhase === 'series-finishing') {
      setSid(state.sid)
      setCurrentFormat(state.currentFormat ?? null)
      setPhase('series-finishing')
      return
    }
    init()
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Handle return from an interactive series match ─────────────────
  useEffect(() => {
    if (phase === 'series-finishing') {
      finishSeriesMatch()
    }
  }, [phase])  // eslint-disable-line react-hooks/exhaustive-deps

  async function finishSeriesMatch() {
    try {
      const data = await api('POST', `/draft/${sid}/finish-match`)
      setUserWins(data.user_wins)
      setAiWins(data.ai_wins)
      setSeriesDone(data.series_done)
      setSeriesWinner(data.series_winner)
      setPhase('series')
    } catch(e) { setErr(e.message); setPhase('series') }
  }

  async function init() {
    const [s] = await Promise.all([
      api('GET', '/teams/stadiums'),
    ])
    setStadiums(s)
    if (s.length) setSeriesStadium(s[0].id)

    setLoading(true)
    try {
      const data = await api('POST', '/draft/new', {
        username: user?.username !== 'Guest' ? user?.username : null,
      })
      setSid(data.session_id)
      setDraftData(data)
      setPool(data.pool)
    } catch(e) { setErr(e.message) }
    setLoading(false)
  }

  async function pickPlayer(playerId) {
    if (!sid || draftData?.awaiting !== 'user') return
    setLoading(true)
    try {
      const data = await api('POST', `/draft/${sid}/pick`, { player_id: playerId })
      setDraftData({
        round: data.round, awaiting: data.awaiting, complete: data.complete,
        user_xi: data.user_xi, ai_xi: data.ai_xi,
      })
      setPool(data.pool)

      if (data.complete) {
        setTimeout(() => setPhase('setup-series'), 800)
      }
    } catch(e) { setErr(e.message) }
    setLoading(false)
  }

  async function startSeries() {
    const fmtMap = {
      1: { total: 1, to_win: 1, label: '1-off T20' },
      3: { total: 3, to_win: 2, label: 'Best of 3' },
      5: { total: 5, to_win: 3, label: 'Best of 5' },
    }
    const fmt = fmtMap[seriesFormat]
    setLoading(true)
    try {
      await api('POST', `/draft/${sid}/setup-series`, {
        stadium_id: parseInt(seriesStadium),
        total: fmt.total, to_win: fmt.to_win, label: fmt.label,
      })
      setCurrentFormat(fmt)
      setUserWins(0); setAiWins(0)
      setSeriesTossPending(fmt)
    } catch(e) { setErr(e.message) }
    setLoading(false)
  }

  function onSeriesTossResolved(batFirstTeam) {
    const fmt = seriesTossPending
    setSeriesTossPending(null)
    playMatch(fmt, batFirstTeam)
  }

  async function playMatch(fmt, batFirstTeam) {
    try {
      const data = await api('POST', `/draft/${sid}/play-match`, { bat_first_team: batFirstTeam })
      navigate('/match', {
        state: {
          interactive: true,
          sid: data.interactive_sid,
          returnTo: '/draft',
          returnLabel: 'Continue Series',
          returnState: {
            restorePhase: 'series-finishing',
            sid,
            currentFormat: fmt ?? currentFormat,
          },
        },
      })
    } catch(e) { setErr(e.message) }
  }

  const filteredPool = pool.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.team.toLowerCase().includes(search.toLowerCase())
  )

  // ── Draft phase ─────────────────────────────────────────────────────
  if (phase === 'draft') {
    const isYourTurn = draftData?.awaiting === 'user' && !draftData?.complete
    return (
      <div className={styles.root}>
        <header className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate('/')}>
            <ChevronLeft size={14} /> Menu
          </button>
          <span className={styles.title}>📋 Draft — Round {draftData?.round ?? 1}/11</span>
          <span />
        </header>

        {draftData && (
          <div className={[styles.turnBanner, isYourTurn ? styles.yourTurn : styles.aiTurn].join(' ')}>
            {draftData.complete ? '✅ Draft complete!' : isYourTurn ? '🟢 Your pick' : '🤖 AI picking…'}
          </div>
        )}

        <div className={styles.body}>
          {/* Pool */}
          <div className={styles.poolCol}>
            <div className={styles.searchWrap}>
              <Search size={13} className={styles.searchIcon} />
              <input
                className={styles.searchInput}
                placeholder="Search player or team…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <div className={styles.pool}>
              {loading && !pool.length ? (
                <div className={styles.poolEmpty}>Loading draft pool…</div>
              ) : filteredPool.map(p => (
                <motion.div
                  key={p.id}
                  className={[
                    styles.poolPlayer,
                    !isYourTurn ? styles.poolDisabled : '',
                  ].join(' ')}
                  whileHover={isYourTurn ? { backgroundColor: 'var(--surface-2)' } : {}}
                  onClick={() => isYourTurn && pickPlayer(p.id)}
                >
                  <div>
                    <div className={styles.pName}>{p.name}</div>
                    <div className={styles.pMeta}>
                      <span className={[styles.rolePip, styles[`role_${ROLE_COLOR[p.role] || 'gold'}`]].join(' ')}>
                        {p.role?.replace('_', ' ')}
                      </span>
                      <span className={styles.pTeam}>{p.team}</span>
                    </div>
                  </div>
                  <div className={styles.pStats}>
                    <span>Bat {Math.round(p.bat_power * 100)}</span>
                    <span>Wkt {Math.round(p.wicket_threat * 100)}</span>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* XIs */}
          <div className={styles.xiCol}>
            {draftData && (
              <>
                <XiList players={draftData.user_xi} title="Your XI" count={draftData.user_xi?.length ?? 0} />
                <XiList players={draftData.ai_xi} title="AI's XI" count={draftData.ai_xi?.length ?? 0} />
              </>
            )}
          </div>
        </div>

        {err && <div className={styles.errBar}>{err}</div>}
      </div>
    )
  }

  // ── Series setup phase ───────────────────────────────────────────────
  if (phase === 'setup-series') {
    return (
      <div className={styles.root}>
        <header className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate('/')}>
            <ChevronLeft size={14} /> Menu
          </button>
          <span className={styles.title}>📋 Series Setup</span>
          <span />
        </header>

        <div className={styles.setupBody}>
          <div className={styles.setupCard}>
            <div className={styles.setupTitle}>Your XI is ready! Set up the series.</div>

            <div className={styles.field}>
              <label>Series Format</label>
              <select value={seriesFormat} onChange={e => setSeriesFormat(parseInt(e.target.value))}>
                <option value={1}>1-off T20</option>
                <option value={3}>Best of 3</option>
                <option value={5}>Best of 5</option>
              </select>
            </div>
            <div className={styles.field}>
              <label>Stadium</label>
              <select value={seriesStadium} onChange={e => setSeriesStadium(e.target.value)}>
                {stadiums.map(s => <option key={s.id} value={s.id}>{s.name}, {s.city}</option>)}
              </select>
            </div>
            {err && <div className={styles.err}>{err}</div>}
            <button className={styles.btnGold} onClick={startSeries} disabled={loading} style={{ marginTop: '1.25rem' }}>
              {loading ? 'Starting…' : '▶ Start Series'}
            </button>
          </div>
        </div>

        {seriesTossPending && (
          <TossModal
            callerLabel="YOU"
            opponentLabel="AI"
            stadiumId={parseInt(seriesStadium)}
            onResolved={onSeriesTossResolved}
          />
        )}
      </div>
    )
  }

  if (phase === 'series-finishing') {
    return <div className={styles.setupBody}><div className={styles.setupCard}>Finishing match…</div></div>
  }

  // ── Series result phase (returned from match) ────────────────────────
  if (phase === 'series') {
    const fmt = currentFormat
    return (
      <div className={styles.root}>
        <header className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate('/')}>
            <ChevronLeft size={14} /> Menu
          </button>
          <span className={styles.title}>
            📋 Series · YOU {userWins} – AI {aiWins}
            {fmt ? ` · ${fmt.label}` : ''}
          </span>
          <span />
        </header>

        <div className={styles.setupBody}>
          <div className={styles.setupCard}>
            {seriesDone ? (
              <>
                <div className={styles.seriesResult}>
                  {seriesWinner === 'user' ? (
                    <span className={styles.win}>🏆 You win the series!</span>
                  ) : seriesWinner === 'ai' ? (
                    <span className={styles.loss}>💔 AI wins the series.</span>
                  ) : (
                    <span className={styles.tie}>🤝 Series level.</span>
                  )}
                </div>
                <div className={styles.seriesScore}>
                  YOU {userWins} — AI {aiWins}
                </div>
                <button className={styles.btnGold} onClick={() => navigate('/')} style={{ marginTop: '1.5rem' }}>
                  ← Main Menu
                </button>
              </>
            ) : (
              <>
                <div className={styles.seriesScore}>YOU {userWins} — AI {aiWins}</div>
                <button
                  className={styles.btnGold}
                  onClick={() => setSeriesTossPending(currentFormat)}
                  disabled={loading}
                  style={{ marginTop: '1rem' }}
                >
                  {loading ? 'Simulating…' : '▶ Next Match'}
                </button>
              </>
            )}
            {err && <div className={styles.err}>{err}</div>}
          </div>
        </div>

        {seriesTossPending && (
          <TossModal
            callerLabel="YOU"
            opponentLabel="AI"
            stadiumId={parseInt(seriesStadium)}
            onResolved={onSeriesTossResolved}
          />
        )}
      </div>
    )
  }

  return null
}
