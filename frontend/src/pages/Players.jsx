import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronLeft, Search } from 'lucide-react'
import SkillRadar from '../components/player/SkillRadar'
import { api } from '../api'
import styles from './Players.module.css'

const ROLE_COLOR = {
  batter: 'gold', bowler: 'teal', all_rounder: 'green', wicket_keeper: 'red',
}

function StatBar({ label, value }) {
  return (
    <div className={styles.statBar}>
      <span className={styles.statLabel}>{label}</span>
      <div className={styles.barTrack}>
        <motion.div
          className={styles.barFill}
          initial={{ width: 0 }}
          animate={{ width: `${Math.round(value * 100)}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
      <span className={styles.statVal}>{Math.round(value * 100)}</span>
    </div>
  )
}

function PlayerDetail({ player, onClose }) {
  if (!player) return null
  const roleColor = ROLE_COLOR[player.role] || 'gold'
  return (
    <motion.div
      className={styles.detail}
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.22 }}
    >
      <div className={styles.detailHeader}>
        <div>
          <div className={styles.detailName}>{player.name}</div>
          <div className={styles.detailMeta}>
            <span className={[styles.roleBadge, styles[`role_${roleColor}`]].join(' ')}>
              {player.role?.replace('_', ' ')}
            </span>
            <span className={styles.detailTeam}>{player.team}</span>
            <span className={styles.detailNat}>{player.nationality}</span>
          </div>
        </div>
        <button className={styles.closeBtn} onClick={onClose}>✕</button>
      </div>

      <SkillRadar player={player} color={roleColor === 'teal' ? '#00c9a7' : '#d4a017'} />

      <div className={styles.statsGroup}>
        <div className={styles.statsTitle}>Batting</div>
        <StatBar label="Power"     value={player.skills.bat_power} />
        <StatBar label="Control"   value={player.skills.bat_control} />
        <StatBar label="Aggression" value={player.skills.bat_aggression} />
        <StatBar label="vs Pace"   value={player.skills.vs_pace} />
        <StatBar label="vs Spin"   value={player.skills.vs_spin} />
      </div>

      <div className={styles.statsGroup}>
        <div className={styles.statsTitle}>Bowling</div>
        <StatBar label="Wicket Threat" value={player.bowling.wicket_threat} />
        <StatBar label="Economy"      value={player.bowling.economy_skill} />
        <StatBar label="Death Skill"  value={player.bowling.death_skill} />
      </div>

      <div className={styles.statsGroup}>
        <div className={styles.statsTitle}>Mental / Form</div>
        <StatBar label="Pressure"    value={player.mental.pressure_handling} />
        <StatBar label="Consistency" value={player.mental.consistency} />
        <StatBar label="Recent Form" value={player.form.recent_form} />
      </div>

      <div className={styles.statsGroup}>
        <div className={styles.statsTitle}>Fielding & Running</div>
        <StatBar label="Catching"       value={player.fielding.catching} />
        <StatBar label="Ground Fielding" value={player.fielding.ground_fielding} />
        <StatBar label="Speed"          value={player.running.speed} />
        <StatBar label="Quick Singles"  value={player.running.quick_singles} />
      </div>
    </motion.div>
  )
}

export default function Players() {
  const navigate = useNavigate()
  const [teams, setTeams]       = useState([])
  const [selectedTeam, setSelectedTeam] = useState('')
  const [players, setPlayers]   = useState([])
  const [selected, setSelected] = useState(null)
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    api('GET', '/teams/').then(t => {
      setTeams(t)
      if (t.length) { setSelectedTeam(t[0]); fetchPlayers(t[0]) }
    })
  }, [])

  async function fetchPlayers(team) {
    setLoading(true); setSelected(null)
    try {
      const data = await api('GET', `/teams/${team}/players`)
      setPlayers(data)
    } catch {}
    setLoading(false)
  }

  function selectTeam(t) {
    setSelectedTeam(t)
    setSearch('')
    fetchPlayers(t)
  }

  const filtered = players.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <button className={styles.backBtn} onClick={() => navigate('/')}>
            <ChevronLeft size={14} /> Menu
          </button>
          <span className={styles.title}>Player Hub</span>
          <span />
        </div>

        {/* Team selector */}
        <div className={styles.teamTabs}>
          {teams.map(t => (
            <button
              key={t}
              className={[styles.teamTab, selectedTeam === t ? styles.teamTabActive : ''].join(' ')}
              onClick={() => selectTeam(t)}
            >{t}</button>
          ))}
        </div>
      </header>

      <div className={styles.body}>
        {/* Player list */}
        <div className={[styles.list, selected ? styles.listNarrow : ''].join(' ')}>
          <div className={styles.searchWrap}>
            <Search size={13} className={styles.searchIcon} />
            <input
              className={styles.searchInput}
              placeholder="Search player…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          {loading ? (
            <div className={styles.emptyMsg}>Loading…</div>
          ) : filtered.map((p, i) => (
            <motion.div
              key={p.id}
              className={[styles.playerRow, selected?.id === p.id ? styles.playerRowActive : ''].join(' ')}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.012 }}
              onClick={() => setSelected(selected?.id === p.id ? null : p)}
            >
              <div className={styles.playerName}>{p.name}</div>
              <div className={styles.playerMeta}>
                <span className={[styles.rolePip, styles[`role_${ROLE_COLOR[p.role] || 'gold'}`]].join(' ')}>
                  {p.role?.replace('_', ' ')}
                </span>
                <span className={styles.playerStats}>
                  Bat {Math.round(p.bat_power * 100)} · Wkt {Math.round(p.wicket_threat * 100)}
                </span>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Detail panel */}
        <AnimatePresence>
          {selected && (
            <div className={styles.detailWrap}>
              <PlayerDetail player={selected} onClose={() => setSelected(null)} />
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
