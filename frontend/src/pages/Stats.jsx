import { useState, useEffect, useRef, useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ChevronDown, Search, ChevronLeft } from 'lucide-react'
import { api } from '../api'
import { teamColor } from '../data/teamColors'
import styles from './Stats.module.css'

const TEAMS = ['CSK', 'DC', 'GT', 'KKR', 'LSG', 'MI', 'PBKS', 'RCB', 'RR', 'SRH']

const BATTER_AWARDS = [
  { key: 'orange_cap',    label: 'Orange Cap',                               sortKey: 'runs',       highlight: 'runs' },
  { key: 'fours_season',  label: 'RuPay On-The-Go 4s Of The Season',         sortKey: 'fours',      highlight: 'fours' },
  { key: 'fours_innings', label: 'Most Fours (Innings)',                     sortKey: 'best_fours', highlight: 'fours' },
  { key: 'sixes_season',  label: 'Angel One Super Sixes Of The Season',      sortKey: 'sixes',      highlight: 'sixes' },
  { key: 'sixes_innings', label: 'Most Sixes (Innings)',                     sortKey: 'best_sixes', highlight: 'sixes' },
]

const BOWLER_AWARDS = [
  { key: 'purple_cap',   label: 'Purple Cap',              sortKey: 'wickets',  highlight: 'wickets' },
  { key: 'maidens',      label: 'Most Maidens',             sortKey: 'maidens',  highlight: 'maidens' },
  { key: 'dots_season',  label: 'TATA IPL Green Dot Balls', sortKey: 'dots',     highlight: 'dots' },
  { key: 'dots_innings', label: 'Most Dot Balls (Innings)', sortKey: 'best_dots', highlight: 'dots' },
  { key: 'best_avg',     label: 'Best Bowling Average',     sortKey: 'avg',      highlight: 'avg', ascending: true, requiresValue: true },
  { key: 'best_econ',    label: 'Best Bowling Economy',     sortKey: 'econ',     highlight: 'econ', ascending: true },
]

function initials(name) {
  return (name || '')
    .split(' ')
    .filter(Boolean)
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function PlayerAvatar({ name, team, size = 30 }) {
  const c = teamColor(team)
  return (
    <div
      className={styles.avatar}
      style={{
        width: size, height: size,
        background: `linear-gradient(135deg, ${c.primary}, ${c.secondary})`,
        color: c.text, fontSize: size * 0.38,
      }}
    >
      {initials(name)}
    </div>
  )
}

function AwardDropdown({ category, setCategory, award, setAward }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function onDocClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  const list = category === 'BATTERS' ? BATTER_AWARDS : BOWLER_AWARDS

  return (
    <div className={styles.dropdownWrap} ref={ref}>
      <button type="button" className={styles.awardTrigger} onClick={() => setOpen(o => !o)}>
        <span>{award.label}</span>
        <ChevronDown size={14} className={open ? styles.chevOpen : ''} />
      </button>

      {open && (
        <div className={styles.awardPanel}>
          <div className={styles.categoryTabs}>
            <button
              type="button"
              className={[styles.categoryTab, category === 'BATTERS' ? styles.categoryTabActive : ''].join(' ')}
              onClick={() => {
                setCategory('BATTERS')
                setAward(BATTER_AWARDS[0])
              }}
            >
              BATTERS
            </button>
            <button
              type="button"
              className={[styles.categoryTab, category === 'BOWLERS' ? styles.categoryTabActive : ''].join(' ')}
              onClick={() => {
                setCategory('BOWLERS')
                setAward(BOWLER_AWARDS[0])
              }}
            >
              BOWLERS
            </button>
          </div>
          <div className={styles.awardList}>
            {list.map(a => (
              <div
                key={a.key}
                className={[styles.awardItem, award.key === a.key ? styles.awardItemActive : ''].join(' ')}
                onClick={() => { setAward(a); setOpen(false) }}
              >
                {a.label}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function Stats() {
  const { state } = useLocation()
  const navigate  = useNavigate()
  const sid = state?.sid

  const [category, setCategory] = useState('BATTERS')
  const [award, setAward]     = useState(BATTER_AWARDS[0])
  const [team, setTeam]       = useState('ALL')
  const [player, setPlayer]   = useState('ALL')
  const [search, setSearch]   = useState('')

  const [batters, setBatters] = useState([])
  const [bowlers, setBowlers] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr]         = useState('')

  useEffect(() => {
    if (!sid) return
    api('GET', `/tournament/${sid}/stats`)
      .then(d => { setBatters(d.batters ?? []); setBowlers(d.bowlers ?? []) })
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false))
  }, [sid])

  const rawList = category === 'BATTERS' ? batters : bowlers

  const playerOptions = useMemo(() => {
    const names = [...new Set(rawList.map(p => p.name))].sort()
    return names
  }, [rawList])

  const filtered = useMemo(() => {
    let rows = rawList
    if (team !== 'ALL')   rows = rows.filter(p => p.team === team)
    if (player !== 'ALL') rows = rows.filter(p => p.name === player)
    if (search.trim())    rows = rows.filter(p => p.name.toLowerCase().includes(search.trim().toLowerCase()))
    if (award.requiresValue) rows = rows.filter(p => p[award.sortKey] != null)

    const sorted = [...rows].sort((a, b) => {
      const av = a[award.sortKey], bv = b[award.sortKey]
      if (av == null) return 1
      if (bv == null) return -1
      return award.ascending ? av - bv : bv - av
    })
    return sorted
  }, [rawList, team, player, search, award])

  if (!sid) {
    return (
      <div className={styles.root}>
        <div className={styles.notice}>
          No tournament session. <button className={styles.linkBtn} onClick={() => navigate('/tournament')}>Go to Tournament</button>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.root}>
      <div className={styles.topBar}>
        <button className={styles.backBtn} onClick={() => navigate('/tournament', { state: { sid } })}>
          <ChevronLeft size={16} /> Back to Tournament
        </button>
      </div>

      <>
          <div className={styles.filterRow}>
            <AwardDropdown category={category} setCategory={setCategory} award={award} setAward={setAward} />

            <select className={styles.simpleSelect} value={team} onChange={e => { setTeam(e.target.value); setPlayer('ALL') }}>
              <option value="ALL">All Teams</option>
              {TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>

            <select className={styles.simpleSelect} value={player} onChange={e => setPlayer(e.target.value)}>
              <option value="ALL">All Players</option>
              {playerOptions.map(n => <option key={n} value={n}>{n}</option>)}
            </select>

            <div className={styles.searchWrap}>
              <Search size={14} className={styles.searchIcon} />
              <input
                className={styles.searchInput}
                placeholder="Search By Player Name"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>

          {loading ? (
            <div className={styles.notice}>Loading stats…</div>
          ) : err ? (
            <div className={styles.notice}>{err}</div>
          ) : filtered.length === 0 ? (
            <div className={styles.notice}>No matches played yet — stats will appear as the season progresses.</div>
          ) : category === 'BATTERS' ? (
            <BattingTable rows={filtered} highlight={award.highlight} />
          ) : (
            <BowlingTable rows={filtered} highlight={award.highlight} />
          )}
      </>
    </div>
  )
}

function hl(col, highlight) {
  return col === highlight ? styles.highlightCol : ''
}

function BattingTable({ rows, highlight }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>POS</th><th className={styles.playerHeadCell}>PLAYER</th>
            <th className={hl('runs', highlight)}>RUNS</th>
            <th>MAT</th><th>INNS</th><th>NO</th><th>HS</th>
            <th className={hl('avg', highlight)}>AVG</th>
            <th>BF</th><th>SR</th><th>100</th><th>50</th>
            <th className={hl('fours', highlight)}>4S</th>
            <th className={hl('sixes', highlight)}>6S</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p, i) => (
            <tr key={p.id}>
              <td>{i + 1}</td>
              <td className={styles.playerCell}>
                <PlayerAvatar name={p.name} team={p.team} />
                <div className={styles.playerNameCol}>
                  <div className={styles.playerName}>{p.name}</div>
                  <div className={styles.playerTeam}>{p.team}</div>
                </div>
              </td>
              <td className={[styles.numCell, hl('runs', highlight)].join(' ')}>{p.runs}</td>
              <td className={styles.numCell}>{p.matches}</td>
              <td className={styles.numCell}>{p.innings}</td>
              <td className={styles.numCell}>{p.not_outs}</td>
              <td className={styles.numCell}>{p.highest_score}</td>
              <td className={[styles.numCell, hl('avg', highlight)].join(' ')}>{p.avg}</td>
              <td className={styles.numCell}>{p.balls_faced}</td>
              <td className={styles.numCell}>{p.sr}</td>
              <td className={styles.numCell}>{p.hundreds}</td>
              <td className={styles.numCell}>{p.fifties}</td>
              <td className={[styles.numCell, hl('fours', highlight)].join(' ')}>{p.fours}</td>
              <td className={[styles.numCell, hl('sixes', highlight)].join(' ')}>{p.sixes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function BowlingTable({ rows, highlight }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>POS</th><th className={styles.playerHeadCell}>PLAYER</th>
            <th className={hl('wickets', highlight)}>WKTS</th>
            <th>MAT</th><th>INNS</th><th>OV</th><th>RUNS</th>
            <th className={hl('avg', highlight)}>AVG</th>
            <th className={hl('econ', highlight)}>ECON</th>
            <th className={hl('maidens', highlight)}>MDNS</th>
            <th className={hl('dots', highlight)}>DOTS</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p, i) => (
            <tr key={p.id}>
              <td>{i + 1}</td>
              <td className={styles.playerCell}>
                <PlayerAvatar name={p.name} team={p.team} />
                <div className={styles.playerNameCol}>
                  <div className={styles.playerName}>{p.name}</div>
                  <div className={styles.playerTeam}>{p.team}</div>
                </div>
              </td>
              <td className={[styles.numCell, hl('wickets', highlight)].join(' ')}>{p.wickets}</td>
              <td className={styles.numCell}>{p.matches}</td>
              <td className={styles.numCell}>{p.innings}</td>
              <td className={styles.numCell}>{p.overs}</td>
              <td className={styles.numCell}>{p.runs_conceded}</td>
              <td className={[styles.numCell, hl('avg', highlight)].join(' ')}>{p.avg ?? '-'}</td>
              <td className={[styles.numCell, hl('econ', highlight)].join(' ')}>{p.econ}</td>
              <td className={[styles.numCell, hl('maidens', highlight)].join(' ')}>{p.maidens}</td>
              <td className={[styles.numCell, hl('dots', highlight)].join(' ')}>{p.dots}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
