import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from 'recharts'

export default function SkillRadar({ player, color = '#d4a017' }) {
  const s = player.skills
  const b = player.bowling
  const m = player.mental

  const data = [
    { label: 'Bat Control',  value: Math.round(s.bat_control  * 100) },
    { label: 'Bat Power',    value: Math.round(s.bat_power    * 100) },
    { label: 'Aggression',   value: Math.round(s.bat_aggression * 100) },
    { label: 'Wicket Threat',value: Math.round(b.wicket_threat * 100) },
    { label: 'Economy',      value: Math.round(b.economy_skill * 100) },
    { label: 'Pressure',     value: Math.round(m.pressure_handling * 100) },
  ]

  return (
    <ResponsiveContainer width="100%" height={220}>
      <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
        <PolarGrid stroke="#222" />
        <PolarAngleAxis
          dataKey="label"
          tick={{ fill: '#666', fontSize: 10, fontFamily: 'monospace' }}
        />
        <Radar
          name={player.name}
          dataKey="value"
          stroke={color}
          fill={color}
          fillOpacity={0.12}
          strokeWidth={1.5}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}
