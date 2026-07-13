// Real IPL franchise brand colors, used to render team badges.
export const TEAM_COLORS = {
  CSK:  { primary: '#FFCB05', secondary: '#0A3A5C', text: '#0A3A5C' },
  MI:   { primary: '#004C93', secondary: '#D1AB3E', text: '#FFFFFF' },
  KKR:  { primary: '#3A225D', secondary: '#B3A369', text: '#FFFFFF' },
  RCB:  { primary: '#EC1C24', secondary: '#D4AF37', text: '#FFFFFF' },
  DC:   { primary: '#17479E', secondary: '#EF1C25', text: '#FFFFFF' },
  SRH:  { primary: '#FF822A', secondary: '#000000', text: '#FFFFFF' },
  GT:   { primary: '#1B2133', secondary: '#B3A369', text: '#FFFFFF' },
  LSG:  { primary: '#00A99D', secondary: '#F4C430', text: '#FFFFFF' },
  PBKS: { primary: '#ED1B24', secondary: '#A7A9AC', text: '#FFFFFF' },
  RR:   { primary: '#EA1A85', secondary: '#1B2599', text: '#FFFFFF' },
}

export function teamColor(code) {
  return TEAM_COLORS[code] || { primary: '#666666', secondary: '#333333', text: '#FFFFFF' }
}
