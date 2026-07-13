import { motion } from 'framer-motion'
import styles from './Button.module.css'

export default function Button({
  children,
  variant = 'outline',   // outline | solid | ghost
  size = 'md',           // sm | md | lg
  accent = 'gold',       // gold | teal
  disabled = false,
  fullWidth = false,
  onClick,
  type = 'button',
  className = '',
}) {
  return (
    <motion.button
      type={type}
      onClick={onClick}
      disabled={disabled}
      whileHover={disabled ? {} : { scale: 1.01 }}
      whileTap={disabled ? {} : { scale: 0.98 }}
      transition={{ duration: 0.12 }}
      className={[
        styles.btn,
        styles[variant],
        styles[size],
        styles[accent],
        fullWidth ? styles.full : '',
        disabled ? styles.disabled : '',
        className,
      ].join(' ')}
    >
      {children}
    </motion.button>
  )
}
