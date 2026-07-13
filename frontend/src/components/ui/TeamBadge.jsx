import { motion } from 'framer-motion'
import { teamColor } from '../../data/teamColors'
import styles from './TeamBadge.module.css'

export default function TeamBadge({ team, size = 40, selected = false, onClick }) {
  const c = teamColor(team)
  const fontSize = size * (team && team.length > 3 ? 0.24 : 0.32)

  return (
    <motion.div
      className={[styles.badge, selected ? styles.badgeSelected : '', onClick ? styles.clickable : ''].join(' ')}
      style={{
        width: size,
        height: size,
        background: `radial-gradient(circle at 32% 28%, ${c.secondary}, ${c.primary})`,
        color: c.text,
        fontSize,
        boxShadow: selected ? `0 0 0 2px ${c.secondary}, 0 0 12px ${c.primary}99` : 'none',
      }}
      whileHover={onClick ? { scale: 1.1 } : {}}
      whileTap={onClick ? { scale: 0.94 } : {}}
      onClick={onClick}
      title={team}
    >
      {team}
    </motion.div>
  )
}
