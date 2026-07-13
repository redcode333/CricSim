export default function TrophyIcon({ size = 96 }) {
  const gradId = 'trophyGold'
  return (
    <svg width={size} height={size * 1.2} viewBox="0 0 100 120" fill="none">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#FFE585" />
          <stop offset="50%" stopColor="#D4AF37" />
          <stop offset="100%" stopColor="#8A6D1E" />
        </linearGradient>
      </defs>
      {/* Handles */}
      <path d="M30 18 C10 18 10 45 30 45" stroke={`url(#${gradId})`} strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d="M70 18 C90 18 90 45 70 45" stroke={`url(#${gradId})`} strokeWidth="5" fill="none" strokeLinecap="round" />
      {/* Cup */}
      <path d="M30 10 H70 V45 C70 65 55 72 50 72 C45 72 30 65 30 45 Z" fill={`url(#${gradId})`} />
      {/* Star accent */}
      <path
        d="M50 24 L52.5 30.5 L59.5 31 L54 35.3 L55.8 42 L50 38.2 L44.2 42 L46 35.3 L40.5 31 L47.5 30.5 Z"
        fill="#8A6D1E" opacity="0.55"
      />
      {/* Stem */}
      <rect x="45" y="72" width="10" height="16" fill={`url(#${gradId})`} />
      {/* Base */}
      <rect x="32" y="88" width="36" height="8" rx="2" fill={`url(#${gradId})`} />
      <rect x="26" y="96" width="48" height="10" rx="2" fill={`url(#${gradId})`} />
    </svg>
  )
}
