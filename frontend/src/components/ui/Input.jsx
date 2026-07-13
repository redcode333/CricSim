import styles from './Input.module.css'

export default function Input({ label, error, ...props }) {
  return (
    <div className={styles.group}>
      {label && <label className={styles.label}>{label}</label>}
      <input className={[styles.input, error ? styles.err : ''].join(' ')} {...props} />
      {error && <span className={styles.errMsg}>{error}</span>}
    </div>
  )
}
