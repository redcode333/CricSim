import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { X, Sparkles } from 'lucide-react'
import { api } from '../../api'
import styles from './SquadPicker.module.css'

const MAX_OVERSEAS = 4

// Pick your playing XI before a match. When `suggestedIds`/`reasons`/`matchupNote`
// are supplied (tournament mode's AI suggestion), shows a banner with a
// one-click "Use AI XI" shortcut and per-player reason tags — manual toggling
// always remains available regardless. Quick Match doesn't pass these props,
// so the suggestion UI simply doesn't render there.
export default function SquadPicker({
  team, onConfirm, onCancel,
  suggestedIds, reasons, matchupNote, loadingSuggestion,
}) {
  const [squad, setSquad]     = useState([])
  const [selected, setSelected] = useState([])
  const [loading, setLoading] = useState(true)
  const [warn, setWarn]       = useState('')

  useEffect(() => {
    api('GET', `/teams/${team}/players`).then(s => { setSquad(s); setLoading(false) })
  }, [team])

  const byId = Object.fromEntries(squad.map(p => [p.id, p]))
  const isOverseas = p => (p?.nationality || 'IND') !== 'IND'
  const overseasCount = selected.filter(id => isOverseas(byId[id])).length
  const wkCount = selected.filter(id => byId[id]?.role === 'wicket_keeper').length

  function toggle(id) {
    setWarn('')
    setSelected(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id)
      if (prev.length >= 11) return prev
      if (isOverseas(byId[id]) && overseasCount >= MAX_OVERSEAS) {
        setWarn(`Max ${MAX_OVERSEAS} overseas players allowed in the XI.`)
        return prev
      }
      return [...prev, id]
    })
  }

  function useAiXi() {
    setWarn('')
    if (suggestedIds?.length === 11) setSelected(suggestedIds)
  }

  const canConfirm = selected.length === 11 && wkCount >= 1

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <motion.div
        className={styles.squadModal}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.22 }}
        onClick={e => e.stopPropagation()}
      >
        <div className={styles.modalHeader}>
          <span>Pick Your XI — {team} ({selected.length}/11)</span>
          <button className={styles.closeBtn} onClick={onCancel}><X size={16} /></button>
        </div>

        {(matchupNote || loadingSuggestion) && (
          <div className={styles.suggestBanner}>
            <div className={styles.suggestHeader}>
              <span className={styles.suggestTitle}><Sparkles size={11} /> AI Matchup Read</span>
              {suggestedIds?.length === 11 && (
                <button type="button" className={styles.useAiBtn} onClick={useAiXi}>Use AI XI</button>
              )}
            </div>
            {loadingSuggestion ? 'Analysing pitch and opponent…' : matchupNote}
          </div>
        )}

        <div className={styles.squadRules}>
          <span className={overseasCount > MAX_OVERSEAS ? styles.ruleBad : ''}>
            ✈️ Overseas: {overseasCount}/{MAX_OVERSEAS}
          </span>
          <span className={wkCount < 1 ? styles.ruleBad : ''}>
            🧤 Keeper: {wkCount >= 1 ? 'Yes' : 'Needed'}
          </span>
        </div>

        <div className={styles.squadList}>
          {loading ? (
            <div className={styles.poolEmpty}>Loading squad…</div>
          ) : squad.map(p => (
            <div
              key={p.id}
              className={[styles.squadPlayer, selected.includes(p.id) ? styles.squadPlayerSelected : ''].join(' ')}
              onClick={() => toggle(p.id)}
            >
              <div>
                <div className={styles.pName}>
                  {p.name}{isOverseas(p) ? ' ✈️' : ''}
                </div>
                <div className={styles.pMeta}>
                  <span className={styles.pTeam}>{p.role?.replace('_', ' ')}</span>
                </div>
                {reasons?.[p.id] && (
                  <div className={styles.reasonTag}>★ {reasons[p.id]}</div>
                )}
              </div>
              <div className={styles.pStats}>
                <span>Bat {Math.round(p.bat_power * 100)}</span>
                <span>Wkt {Math.round(p.wicket_threat * 100)}</span>
              </div>
            </div>
          ))}
        </div>

        <div className={styles.squadFooter}>
          {warn && <div className={styles.err}>{warn}</div>}
          <button
            className={styles.btnPlay}
            disabled={!canConfirm}
            onClick={() => onConfirm(selected)}
          >
            {selected.length === 11 && wkCount < 1
              ? 'Need a wicket-keeper'
              : `Confirm XI (${selected.length}/11)`}
          </button>
        </div>
      </motion.div>
    </div>
  )
}
