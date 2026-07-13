import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { api } from '../api'
import TossModal from '../components/match/TossModal'
import SquadPicker from '../components/match/SquadPicker'
import TeamBadge from '../components/ui/TeamBadge'
import Confetti from '../components/ui/Confetti'
import TrophyIcon from '../components/ui/TrophyIcon'
import styles from './Tournament.module.css'

// ── Standings table ──────────────────────────────────────────────────────────
function Standings({ standings, playerTeam }) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th>#</th><th>Team</th>
          <th className={styles.numCell}>P</th>
          <th className={styles.numCell}>W</th>
          <th className={styles.numCell}>L</th>
          <th className={styles.numCell}>Pts</th>
          <th className={styles.numCell}>NRR</th>
        </tr>
      </thead>
      <tbody>
        {standings.map((s, i) => (
          <tr
            key={s.team}
            className={[
              s.team === playerTeam ? styles.myTeam : '',
              i < 4 ? styles.playoffRow : '',
            ].join(' ')}
          >
            <td>{i + 1}</td>
            <td className={styles.teamCell}>
              <span className={styles.teamCellInner}>
                {s.team === playerTeam
                  ? <ChevronRight size={13} className={styles.myTeamPointer} />
                  : <span className={styles.pointerSlot} />}
                <TeamBadge team={s.team} size={18} />
                {s.team}
              </span>
            </td>
            <td className={styles.numCell}>{s.played}</td>
            <td className={[styles.win, styles.numCell].join(' ')}>{s.won}</td>
            <td className={[styles.loss, styles.numCell].join(' ')}>{s.lost}</td>
            <td className={[styles.pts, styles.numCell].join(' ')}>{s.points}</td>
            <td className={[styles.nrr, styles.numCell, s.nrr >= 0 ? styles.pos : styles.neg].join(' ')}>
              {s.nrr >= 0 ? '+' : ''}{s.nrr?.toFixed ? s.nrr.toFixed(3) : s.nrr}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ── Playoff bracket ──────────────────────────────────────────────────────────
function PlayoffBracket({ bracket, currentIdx }) {
  return (
    <div className={styles.bracket}>
      {bracket.map((m, i) => (
        <div
          key={i}
          className={[styles.bracketMatch, i === currentIdx ? styles.bracketActive : m.winner ? styles.bracketDone : styles.bracketPending].join(' ')}
        >
          <div className={styles.bracketName}>{m.name}</div>
          <div className={styles.bracketTeams}>
            <span className={m.winner === m.team1 ? styles.bracketWinner : ''}>{m.team1 || '?'}</span>
            <span className={styles.vs}>vs</span>
            <span className={m.winner === m.team2 ? styles.bracketWinner : ''}>{m.team2 || '?'}</span>
          </div>
          {m.winner && (
            <div className={styles.bracketResult}>→ {m.winner}</div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────
export default function Tournament() {
  const { user }   = useAuth()
  const navigate   = useNavigate()
  const { state }  = useLocation()

  const [phase, setPhase]         = useState('loading')   // loading | setup | round | playoffs | done
  const [teams, setTeams]         = useState([])
  const [stadiums, setStadiums]   = useState([])
  const [saveHint, setSaveHint]   = useState(null)

  const [sid, setSid]             = useState(null)
  const [playerTeam, setPlayerTeam] = useState('')
  const [standings, setStandings] = useState([])
  const [roundIdx, setRoundIdx]   = useState(0)
  const [totalRounds, setTotalRounds] = useState(0)
  const [aiResults, setAiResults] = useState([])
  const [speed, setSpeed]         = useState(600)
  const [stadiumId, setStadiumId] = useState('')
  const [nextOpponent, setNextOpponent] = useState(null)
  const [tossStep, setTossStep]   = useState(null)  // null | 'round' | 'playoff'
  const [squadStep, setSquadStep] = useState(null)  // null | 'round' | 'playoff'
  const [userXiIds, setUserXiIds] = useState(null)
  const [xiSuggestion, setXiSuggestion] = useState(null)
  const [loadingSuggestion, setLoadingSuggestion] = useState(false)
  const [loading, setLoading]     = useState(false)
  const [err, setErr]             = useState('')

  const [bracket, setBracket]     = useState([])
  const [playoffIdx, setPlayoffIdx] = useState(0)
  const [champion, setChampion]   = useState(null)
  const [playerQualified, setPlayerQualified] = useState(false)
  const [playoffStadiumId, setPlayoffStadiumId] = useState('')

  // ── On mount: restore from navigation state (returning from match) ──
  useEffect(() => {
    if (state?.restorePhase) {
      const s = state
      setSid(s.sid)
      setPlayerTeam(s.playerTeam)
      setStandings(s.standings)
      setRoundIdx(s.roundIdx)
      setTotalRounds(s.totalRounds)
      setAiResults(s.aiResults ?? [])
      setSpeed(s.speed ?? 600)
      if (s.restorePhase === 'playoffs' || s.restorePhase === 'finishing-playoff') {
        setBracket(s.bracket ?? [])
        setPlayoffIdx(s.playoffIdx ?? 0)
        setPlayerQualified(s.playerQualified ?? false)
      }
      if (s.restorePhase === 'done') {
        setChampion(s.champion)
      }
      if (s.restorePhase === 'round') {
        // Refresh authoritative next-opponent for the new round.
        api('GET', `/tournament/${s.sid}`).then(d => setNextOpponent(d.next_opponent)).catch(() => {})
      }
      setPhase(s.restorePhase)
      return
    }
    loadInitial()
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  // ── Handle return from an interactive user match ───────────────────
  useEffect(() => {
    if (phase === 'finishing') {
      finishUserMatch()
    }
  }, [phase])  // eslint-disable-line react-hooks/exhaustive-deps

  async function loadInitial() {
    const [t, s] = await Promise.all([
      api('GET', '/teams/'),
      api('GET', '/teams/stadiums'),
    ])
    setTeams(t)
    setStadiums(s)
    if (s.length) { setStadiumId(s[0].id); setPlayoffStadiumId(s[0].id) }

    // Check for saved game
    if (user?.username && user.username !== 'Guest') {
      try {
        const hints = await api('POST', '/saves/hints', { username: user.username })
        if (hints.tournament) setSaveHint(hints.tournament)
      } catch {}
    }
    setPhase('setup')
  }

  async function startNew(team) {
    setErr(''); setLoading(true)
    try {
      const data = await api('POST', '/tournament/new', {
        player_team: team,
        username: user?.username !== 'Guest' ? user?.username : null,
      })
      setSid(data.session_id)
      setPlayerTeam(data.player_team)
      setStandings(data.standings)
      setRoundIdx(data.round_idx)
      setTotalRounds(data.total_rounds)
      setNextOpponent(data.next_opponent)
      setPhase('round')
    } catch(e) { setErr(e.message) }
    setLoading(false)
  }

  async function loadSaved() {
    setErr(''); setLoading(true)
    try {
      const data = await api('POST', '/tournament/load', { username: user.username })
      setSid(data.session_id)
      setPlayerTeam(data.player_team)
      setStandings(data.standings)
      setRoundIdx(data.round_idx)
      setTotalRounds(data.total_rounds)
      setNextOpponent(data.next_opponent)
      if (data.playoff_state) {
        setBracket(data.playoff_state.bracket ?? [])
        setPlayoffIdx(data.playoff_state.next_playoff_idx ?? 0)
        setPhase('playoffs')
      } else {
        setPhase('round')
      }
    } catch(e) { setErr(e.message) }
    setLoading(false)
  }

  async function openRoundToss() {
    setErr('')
    if (!nextOpponent) { playRound(null); return }
    setUserXiIds(null)
    setXiSuggestion(null)
    setSquadStep('round')
    setLoadingSuggestion(true)
    try {
      const qs = new URLSearchParams({ opponent: nextOpponent, stadium_id: parseInt(stadiumId) })
      const s = await api('GET', `/tournament/${sid}/suggest-xi?${qs}`)
      setXiSuggestion(s)
    } catch (e) { /* suggestion is best-effort; picking still works without it */ }
    setLoadingSuggestion(false)
  }

  function onRoundSquadConfirm(ids) {
    setUserXiIds(ids)
    setSquadStep(null)
    setTossStep('round')
  }

  function onRoundTossResolved(batFirstTeam) {
    setTossStep(null)
    playRound(batFirstTeam)
  }

  async function playRound(batFirstTeam) {
    setErr(''); setLoading(true)
    try {
      const data = await api('POST', `/tournament/${sid}/play-round`, {
        round_idx: roundIdx, stadium_id: parseInt(stadiumId), bat_first_team: batFirstTeam,
        user_xi_ids: userXiIds,
      })
      setUserXiIds(null)
      setAiResults(data.ai_results)
      setStandings(data.standings)

      if (data.interactive_sid) {
        // Play the user's match ball-by-ball, then come back to reconcile.
        navigate('/match', {
          state: {
            interactive: true,
            sid: data.interactive_sid,
            returnTo: '/tournament',
            returnLabel: 'Continue Tournament',
            returnState: {
              restorePhase: 'finishing',
              sid, playerTeam, standings: data.standings,
              roundIdx, totalRounds,
              aiResults: data.ai_results, speed,
            },
          },
        })
        return
      }

      // Bye week — no match for the player this round.
      if (data.group_complete) {
        await enterPlayoffs(data.standings)
      } else {
        setRoundIdx(data.next_round_idx)
        api('GET', `/tournament/${sid}`).then(d => setNextOpponent(d.next_opponent)).catch(() => {})
      }
    } catch(e) { setErr(e.message) }
    setLoading(false)
  }

  async function finishUserMatch() {
    try {
      const data = await api('POST', `/tournament/${sid}/finish-user-match`)
      setStandings(data.standings)
      setRoundIdx(data.next_round_idx)
      if (data.group_complete) {
        await enterPlayoffs(data.standings)
      } else {
        const d = await api('GET', `/tournament/${sid}`)
        setNextOpponent(d.next_opponent)
        setPhase('round')
      }
    } catch(e) { setErr(e.message); setPhase('round') }
  }

  async function enterPlayoffs(currentStandings) {
    try {
      const data = await api('GET', `/tournament/${sid}/top4`)
      setBracket(data.bracket)
      setPlayoffIdx(0)
      setPlayerQualified(data.player_qualified)
      setPhase('playoffs')
    } catch(e) { setErr(e.message) }
  }

  async function openPlayoffToss() {
    setErr('')
    const curMatch = bracket[playoffIdx]
    if (!(curMatch && playerTeam && (curMatch.team1 === playerTeam || curMatch.team2 === playerTeam))) {
      playPlayoff(null)
      return
    }
    const opp = curMatch.team1 === playerTeam ? curMatch.team2 : curMatch.team1
    setUserXiIds(null)
    setXiSuggestion(null)
    setSquadStep('playoff')
    setLoadingSuggestion(true)
    try {
      const qs = new URLSearchParams({ opponent: opp, stadium_id: parseInt(playoffStadiumId) || 1 })
      const s = await api('GET', `/tournament/${sid}/suggest-xi?${qs}`)
      setXiSuggestion(s)
    } catch (e) { /* suggestion is best-effort; picking still works without it */ }
    setLoadingSuggestion(false)
  }

  function onPlayoffSquadConfirm(ids) {
    setUserXiIds(ids)
    setSquadStep(null)
    setTossStep('playoff')
  }

  function onPlayoffTossResolved(batFirstTeam) {
    setTossStep(null)
    playPlayoff(batFirstTeam)
  }

  async function playPlayoff(batFirstTeam) {
    setErr(''); setLoading(true)
    try {
      const data = await api('POST', `/tournament/${sid}/play-playoff`, {
        match_idx: playoffIdx,
        stadium_id: parseInt(playoffStadiumId) || 1,
        bat_first_team: batFirstTeam,
        user_xi_ids: userXiIds,
      })
      setUserXiIds(null)
      setBracket(data.bracket)

      if (data.interactive_sid) {
        // Play the user's playoff match ball-by-ball, then come back to reconcile.
        navigate('/match', {
          state: {
            interactive: true,
            sid: data.interactive_sid,
            returnTo: '/tournament',
            returnLabel: 'Continue Tournament',
            returnState: {
              restorePhase: 'finishing-playoff',
              sid, playerTeam, standings,
              roundIdx, totalRounds, speed,
              bracket: data.bracket,
              playoffIdx,
              playerQualified,
            },
          },
        })
        return
      }

      navigate('/match', {
        state: {
          matchData: data.match_data,
          speed,
          returnTo: '/tournament',
          returnLabel: 'Continue Tournament',
          returnState: {
            restorePhase: data.complete ? 'done' : 'playoffs',
            sid, playerTeam, standings,
            roundIdx, totalRounds, speed,
            bracket: data.bracket,
            playoffIdx: playoffIdx + 1,
            playerQualified,
            champion: data.champion,
          },
        },
      })
    } catch(e) { setErr(e.message) }
    setLoading(false)
  }

  async function finishPlayoffMatch() {
    try {
      const data = await api('POST', `/tournament/${sid}/finish-playoff`)
      setBracket(data.bracket)
      if (data.complete) {
        setChampion(data.champion)
        setPhase('done')
      } else {
        setPlayoffIdx(playoffIdx + 1)
        setPhase('playoffs')
      }
    } catch(e) { setErr(e.message); setPhase('playoffs') }
  }

  // ── Handle return from match when group is complete ───────────────
  useEffect(() => {
    if (phase === 'playoffs-pending') {
      enterPlayoffs(standings)
    }
    if (phase === 'finishing-playoff') {
      finishPlayoffMatch()
    }
  }, [phase])  // eslint-disable-line react-hooks/exhaustive-deps

  // ─────────────────────────────── Render ──────────────────────────────────

  if (phase === 'loading' || phase === 'finishing' || phase === 'finishing-playoff') {
    return <div className={styles.loading}>{phase === 'loading' ? 'Loading…' : 'Finishing match…'}</div>
  }

  if (phase === 'setup') {
    return (
      <div className={styles.root}>
        <header className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate('/')}>
            <ChevronLeft size={14} /> Menu
          </button>
          <span className={styles.title}>🏆 Tournament</span>
          <span />
        </header>
        <div className={styles.setupBody}>
          {saveHint && (
            <div className={styles.saveBox}>
              <div className={styles.saveTitle}>Saved Tournament</div>
              <div className={styles.saveDesc}>{saveHint}</div>
              <div className={styles.saveButtons}>
                <button className={styles.btnGold} onClick={loadSaved} disabled={loading}>
                  ▶ Continue
                </button>
                <button className={styles.btnGhost} onClick={() => setSaveHint(null)}>
                  + New Game
                </button>
              </div>
            </div>
          )}

          {!saveHint && (
            <div className={styles.setupCard}>
              <div className={styles.setupTitle}>Select Your Team</div>
              <div className={styles.teamGrid}>
                {teams.map(t => (
                  <button
                    key={t}
                    className={styles.teamPickBtn}
                    onClick={() => startNew(t)}
                    disabled={loading}
                  >
                    <TeamBadge team={t} size={40} />
                    <span>{t}</span>
                  </button>
                ))}
              </div>

              <div className={styles.fieldRow}>
                <div className={styles.field}>
                  <label>Playback Speed</label>
                  <select value={speed} onChange={e => setSpeed(parseInt(e.target.value))}>
                    <option value={1200}>Slow</option>
                    <option value={600}>Normal</option>
                    <option value={200}>Fast</option>
                    <option value={0}>Instant</option>
                  </select>
                </div>
              </div>

              {err && <div className={styles.err}>{err}</div>}
            </div>
          )}
        </div>
      </div>
    )
  }

  if (phase === 'round') {
    return (
      <div className={styles.root}>
        <header className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate('/')}>
            <ChevronLeft size={14} /> Menu
          </button>
          <span className={styles.title}>
            Round {roundIdx + 1} / {totalRounds} · <span className={styles.myTeamLabel}>{playerTeam}</span>
          </span>
          <span />
        </header>

        <div className={styles.roundBody}>
          <div className={styles.roundLeft}>
            {/* Play your match */}
            <div className={styles.panel}>
              <div className={styles.panelTitle}>Your Match</div>
              {nextOpponent && (
                <div className={styles.matchupLine}>{playerTeam} vs {nextOpponent}</div>
              )}
              <div className={styles.field}>
                <label>Venue</label>
                <select value={stadiumId} onChange={e => setStadiumId(e.target.value)}>
                  {stadiums.map(s => <option key={s.id} value={s.id}>{s.name}, {s.city}</option>)}
                </select>
              </div>
              <div className={styles.field}>
                <label>Speed</label>
                <select value={speed} onChange={e => setSpeed(parseInt(e.target.value))}>
                  <option value={1200}>Slow</option>
                  <option value={600}>Normal</option>
                  <option value={200}>Fast</option>
                  <option value={0}>Instant</option>
                </select>
              </div>
              {err && <div className={styles.err}>{err}</div>}
              <button className={styles.btnGold} onClick={openRoundToss} disabled={loading} style={{ marginTop: '1rem' }}>
                {loading ? 'Simulating…' : '▶ Toss & Play Round'}
              </button>
            </div>

            {/* AI results */}
            {aiResults.length > 0 && (
              <div className={styles.panel} style={{ marginTop: '1px' }}>
                <div className={styles.panelTitle}>AI Results</div>
                <div className={styles.aiResults}>
                  {aiResults.map(r => (
                    <div key={r.match_num} className={styles.aiResult}>
                      <span className={styles.aiTeams}>{r.team1} vs {r.team2}</span>
                      <span className={styles.aiScores}>{r.t1_score} / {r.t2_score}</span>
                      <span className={styles.aiWinner}>{r.winner || 'Tied'} {r.margin ? `by ${r.margin}` : ''}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className={styles.roundRight}>
            <div className={styles.panel}>
              <div className={styles.panelHeaderRow}>
                <div className={styles.panelTitle}>Points Table</div>
                <button
                  className={styles.statsLinkBtn}
                  onClick={() => navigate('/tournament/stats', { state: { sid } })}
                >
                  🧢 Orange/Purple Cap & Stats <ChevronRight size={13} />
                </button>
              </div>
              <Standings standings={standings} playerTeam={playerTeam} />
              <div className={styles.playoffNote}>Top 4 qualify for playoffs</div>
            </div>
          </div>
        </div>

        {squadStep === 'round' && nextOpponent && (
          <SquadPicker
            team={playerTeam}
            suggestedIds={xiSuggestion?.suggested_ids}
            reasons={xiSuggestion?.reasons}
            matchupNote={xiSuggestion?.matchup_note}
            loadingSuggestion={loadingSuggestion}
            onConfirm={onRoundSquadConfirm}
            onCancel={() => setSquadStep(null)}
          />
        )}

        {tossStep === 'round' && nextOpponent && (
          <TossModal
            callerLabel={playerTeam}
            opponentLabel={nextOpponent}
            stadiumId={parseInt(stadiumId)}
            onResolved={onRoundTossResolved}
          />
        )}
      </div>
    )
  }

  if (phase === 'playoffs') {
    const curMatch = bracket[playoffIdx]
    return (
      <div className={styles.root}>
        <header className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate('/')}>
            <ChevronLeft size={14} /> Menu
          </button>
          <span className={styles.title}>🏆 Playoffs · {playerTeam}</span>
          <span />
        </header>

        <div className={styles.playoffBody}>
          <div className={styles.panel} style={{ marginBottom: '1px' }}>
            <div className={styles.panelTitle}>Bracket</div>
            <PlayoffBracket bracket={bracket} currentIdx={playoffIdx} />
          </div>

          {playoffIdx < 4 && curMatch && (
            <div className={styles.panel}>
              <div className={styles.panelTitle}>{curMatch.name}</div>
              <div className={styles.playoffMatchup}>
                {curMatch.team1} <span className={styles.vs}>vs</span> {curMatch.team2}
              </div>
              <div className={styles.field} style={{ marginTop: '0.75rem' }}>
                <label>Venue</label>
                <select value={playoffStadiumId} onChange={e => setPlayoffStadiumId(e.target.value)}>
                  {stadiums.map(s => <option key={s.id} value={s.id}>{s.name}, {s.city}</option>)}
                </select>
              </div>
              {err && <div className={styles.err}>{err}</div>}
              <button className={styles.btnGold} onClick={openPlayoffToss} disabled={loading} style={{ marginTop: '0.75rem' }}>
                {loading ? 'Simulating…' : '▶ Toss & Play Match'}
              </button>
            </div>
          )}
        </div>

        {squadStep === 'playoff' && curMatch && (
          <SquadPicker
            team={playerTeam}
            suggestedIds={xiSuggestion?.suggested_ids}
            reasons={xiSuggestion?.reasons}
            matchupNote={xiSuggestion?.matchup_note}
            loadingSuggestion={loadingSuggestion}
            onConfirm={onPlayoffSquadConfirm}
            onCancel={() => setSquadStep(null)}
          />
        )}

        {tossStep === 'playoff' && curMatch && (
          <TossModal
            callerLabel={curMatch.team1 === playerTeam ? curMatch.team1 : curMatch.team2}
            opponentLabel={curMatch.team1 === playerTeam ? curMatch.team2 : curMatch.team1}
            stadiumId={parseInt(playoffStadiumId) || 1}
            onResolved={onPlayoffTossResolved}
          />
        )}
      </div>
    )
  }

  if (phase === 'done') {
    return (
      <div className={styles.root}>
        <Confetti />
        <header className={styles.header}>
          <button className={styles.backBtn} onClick={() => navigate('/')}>
            <ChevronLeft size={14} /> Menu
          </button>
          <span className={styles.title}>🏆 Tournament Complete</span>
          <span />
        </header>
        <div className={styles.doneBody}>
          <motion.div
            className={styles.champBanner}
            initial={{ scale: 0.85, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 18 }}
          >
            <motion.div
              className={styles.champTrophy}
              initial={{ y: -20, rotate: -8, opacity: 0 }}
              animate={{ y: 0, rotate: 0, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 160, damping: 12, delay: 0.15 }}
            >
              <TrophyIcon size={100} />
            </motion.div>
            <div className={styles.champBadgeRow}>
              <TeamBadge team={champion} size={48} />
              <div className={styles.champName}>{champion}</div>
            </div>
            <div className={styles.champSub}>IPL 2026 Champions!</div>
            {champion === playerTeam && (
              <div className={styles.champYou}>You won it! Congratulations!</div>
            )}
          </motion.div>
          <button className={styles.btnGold} onClick={() => navigate('/')} style={{ marginTop: '2rem' }}>
            ← Main Menu
          </button>
        </div>
      </div>
    )
  }

  return null
}
