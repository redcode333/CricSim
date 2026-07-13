import { motion } from 'framer-motion'
import Navbar from './Navbar'
import styles from './PageLayout.module.css'

const pageVariants = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit:    { opacity: 0 },
}

export default function PageLayout({ children, user, onLogout, fullWidth = false }) {
  return (
    <div className={styles.root}>
      <Navbar user={user} onLogout={onLogout} />
      <motion.main
        variants={pageVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={{ duration: 0.22, ease: 'easeOut' }}
        className={[styles.main, fullWidth ? styles.full : ''].join(' ')}
      >
        {children}
      </motion.main>
    </div>
  )
}
