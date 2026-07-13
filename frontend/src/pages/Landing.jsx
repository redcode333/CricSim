import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Trophy, Users, UserCircle, X } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { api } from '../api'
import TossModal from '../components/match/TossModal'
import SquadPicker from '../components/match/SquadPicker'
import TeamBadge from '../components/ui/TeamBadge'
import styles from './Landing.module.css'

const MENU_CARDS = [
  { id: 'quick',      icon: Zap,        title: 'Quick Match',   desc: 'Pick two teams and play now',        gold: true },
  { id: 'tournament', icon: Trophy,      title: 'Tournament',    desc: 'Full IPL 2026 season',               gold: false },
  { id: 'draft',      icon: Users,       title: 'Draft vs AI',  desc: 'Build your XI, play a series',       gold: false },
  { id: 'players',    icon: UserCircle,  title: 'Player Hub',    desc: 'Browse all 250 IPL 2026 players',   gold: false },
]

export default function Landing() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [teams, setTeams]       = useState([])
  const [stadiums, setStadiums] = useState([])
  const [modal, setModal]       = useState(null)  // null | 'quick'
  const [qmStep, setQmStep]     = useState('form') // 'form' | 'squad' | 'toss'
  const [userXiIds, setUserXiIds] = useState(null)
  const [loading, setLoading]   = useState(false)
  const [err, setErr]           = useState('')
  const [saveHints, setSaveHints] = useState({})

  const [qm, setQm] = useState({
    team1: '', team2: '', stadium_id: '', speed: 600,
    mode: 'watch',  // 'watch' | 'manage1' | 'manage2'
  })

  useEffect(() => {
    api('GET', '/teams/').then(t => {
      setTeams(t)
      setQm(q => ({ ...q, team1: t[0] || '', team2: t[1] || '' }))
    })
    api('GET', '/teams/stadiums').then(s => {
      setStadiums(s)
      setQm(q => ({ ...q, stadium_id: s[0]?.id ?? '' }))
    })
    if (user && user.username !== 'Guest') {
      api('POST', '/saves/hints', { username: user.username })
        .then(setSaveHints)
        .catch(() => {})
    }
  }, [user])

  // Default the venue to Team 1's home ground whenever it changes.
  useEffect(() => {
    if (!qm.team1 || !stadiums.length) return
    const home = stadiums.find(s => s.home_team === qm.team1)
    if (home) setQm(q => (q.stadium_id === home.id ? q : { ...q, stadium_id: home.id }))
  }, [qm.team1, stadiums])

  function handleCard(id) {
    if (id === 'quick')      setModal('quick')
    if (id === 'tournament') navigate('/tournament')
    if (id === 'draft')      navigate('/draft')
    if (id === 'players')    navigate('/players')
  }

  function submitQuickForm(e) {
    e.preventDefault()
    if (qm.team1 === qm.team2) { setErr('Pick two different teams.'); return }
    setErr('')
    setUserXiIds(null)
    // AI vs Me: let the user build their own XI before the toss.
    setQmStep(qm.mode !== 'watch' ? 'squad' : 'toss')
  }

  function onSquadConfirm(ids) {
    setUserXiIds(ids)
    setQmStep('toss')
  }

  async function onTossResolved(batFirstTeam) {
    setQmStep('form')
    setLoading(true)
    try {
      // Interactive mode: user manages a team
      if (qm.mode !== 'watch') {
        const user_team = qm.mode === 'manage1' ? qm.team1 : qm.team2
        const sess = await api('POST', '/match/interactive/start', {
          team1: qm.team1, team2: qm.team2,
          stadium_id: parseInt(qm.stadium_id),
          bat_first: batFirstTeam, user_team,
          user_xi_ids: userXiIds,
        })
        navigate('/match', { state: { interactive: true, sid: sess.session_id, returnTo: '/' } })
        return
      }

      const data = await api('POST', '/match/quick', {
        team1: qm.team1, team2: qm.team2,
        stadium_id: parseInt(qm.stadium_id),
        bat_first: batFirstTeam,
      })
      navigate('/match', { state: { matchData: data, speed: qm.speed, returnTo: '/' } })
    } catch(e) {
      setErr(e.message)
    } finally { setLoading(false) }
  }

  const tossCaller   = qm.mode === 'manage2' ? qm.team2 : qm.team1
  const tossOpponent = qm.mode === 'manage2' ? qm.team1 : qm.team2
  const userManagedTeam = qm.mode === 'manage2' ? qm.team2 : qm.team1

  return (
    <div className={styles.root}>
      {/* ── Header ── */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.brand}>
            <img src="/logo.png" alt="CricSim" className={styles.logoImg} />
          </div>
          <div className={styles.headerRight}>
            <span className={styles.userLabel}>
              {user?.username === 'Guest' ? 'Guest mode' : user?.username}
            </span>
            <button className={styles.logoutBtn} onClick={() => { logout(); navigate('/login') }}>
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* ── Menu grid ── */}
      <main className={styles.main}>
        {saveHints.tournament && (
          <div className={styles.saveHint}>
            💾 Saved tournament found — go to <strong>Tournament</strong> to continue
          </div>
        )}

        <div className={styles.grid}>
          {MENU_CARDS.map((card, i) => {
            const Icon = card.icon
            return (
              <motion.div
                key={card.id}
                className={[styles.card, card.gold ? styles.cardGold : ''].join(' ')}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.28, delay: i * 0.07, ease: 'easeOut' }}
                onClick={() => handleCard(card.id)}
              >
                <Icon size={28} className={styles.cardIcon} strokeWidth={1.5} />
                <div className={styles.cardTitle}>{card.title}</div>
                <div className={styles.cardDesc}>{card.desc}</div>
                {card.id === 'tournament' && saveHints.tournament && (
                  <div className={styles.saveChip}>💾 Saved</div>
                )}
                {card.id === 'draft' && saveHints.duo_ai && (
                  <div className={styles.saveChip}>💾 Saved</div>
                )}
              </motion.div>
            )
          })}
        </div>
      </main>

      {/* ── Footer ── */}
      <footer className={styles.footer}>
        <span>Made with ❤️ by Abhinav</span>
        <a href="mailto:crypto51121@gmail.com" className={styles.footerContact}>
          crypto51121@gmail.com
        </a>
      </footer>

      {/* ── Quick Match Modal ── */}
      <AnimatePresence>
        {modal === 'quick' && (
          <motion.div
            className={styles.overlay}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setModal(null)}
          >
            <motion.div
              className={styles.modal}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              transition={{ duration: 0.22 }}
              onClick={e => e.stopPropagation()}
            >
              <div className={styles.modalHeader}>
                <span>⚡ Quick Match</span>
                <button className={styles.closeBtn} onClick={() => setModal(null)}><X size={16} /></button>
              </div>

              <form onSubmit={submitQuickForm} className={styles.modalForm}>
                <div className={styles.field}>
                  <label>Team 1{qm.team1 && <span className={styles.teamLabelTag}>{qm.team1}</span>}</label>
                  <div className={styles.teamBadgeRow}>
                    {teams.map(t => (
                      <TeamBadge
                        key={t}
                        team={t}
                        size={34}
                        selected={qm.team1 === t}
                        onClick={() => setQm(q => ({ ...q, team1: t }))}
                      />
                    ))}
                  </div>
                </div>
                <div className={styles.field}>
                  <label>Team 2{qm.team2 && <span className={styles.teamLabelTag}>{qm.team2}</span>}</label>
                  <div className={styles.teamBadgeRow}>
                    {teams.map(t => (
                      <TeamBadge
                        key={t}
                        team={t}
                        size={34}
                        selected={qm.team2 === t}
                        onClick={() => setQm(q => ({ ...q, team2: t }))}
                      />
                    ))}
                  </div>
                </div>

                <div className={styles.field}>
                  <label>Stadium</label>
                  <select value={qm.stadium_id} onChange={e => setQm(q => ({ ...q, stadium_id: e.target.value }))}>
                    {stadiums.map(s => (
                      <option key={s.id} value={s.id}>
                        {s.name}, {s.city}{s.home_team ? ` — 🏠 ${s.home_team} Home` : ''}
                      </option>
                    ))}
                  </select>
                </div>

                <div className={styles.field}>
                  <label>Speed {qm.mode !== 'watch' ? '(interactive)' : ''}</label>
                  <select value={qm.speed} onChange={e => setQm(q => ({ ...q, speed: parseInt(e.target.value) }))} disabled={qm.mode !== 'watch'}>
                    <option value={1200}>Slow (1.2s/ball)</option>
                    <option value={600}>Normal (0.6s/ball)</option>
                    <option value={200}>Fast (0.2s/ball)</option>
                    <option value={0}>Instant</option>
                  </select>
                </div>

                <div className={styles.field}>
                  <label>Your role</label>
                  <div className={styles.modeRow}>
                    {[
                      { val: 'watch',   label: 'Watch only' },
                      { val: 'manage1', label: `Manage ${qm.team1 || 'Team 1'}` },
                      { val: 'manage2', label: `Manage ${qm.team2 || 'Team 2'}` },
                    ].map(opt => (
                      <button
                        key={opt.val}
                        type="button"
                        className={[styles.modeBtn, qm.mode === opt.val ? styles.modeBtnActive : ''].join(' ')}
                        onClick={() => setQm(q => ({ ...q, mode: opt.val }))}
                      >{opt.label}</button>
                    ))}
                  </div>
                  {qm.mode !== 'watch' && (
                    <p className={styles.modeHint}>
                      You'll pick bowlers every over and send batsmen after wickets. MCP suggests optimal choices.
                    </p>
                  )}
                </div>

                {err && <div className={styles.err}>{err}</div>}

                <button className={styles.btnPlay} type="submit" disabled={loading || !teams.length}>
                  {loading ? 'Simulating match…' : qm.mode !== 'watch' ? '▶ Pick Your XI' : '▶ Toss & Play'}
                </button>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {qmStep === 'squad' && (
        <SquadPicker
          team={userManagedTeam}
          onConfirm={onSquadConfirm}
          onCancel={() => setQmStep('form')}
        />
      )}

      {qmStep === 'toss' && (
        <TossModal
          callerLabel={tossCaller}
          opponentLabel={tossOpponent}
          stadiumId={parseInt(qm.stadium_id)}
          onResolved={onTossResolved}
        />
      )}
    </div>
  )
}
