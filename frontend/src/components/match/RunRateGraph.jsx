import { AreaChart, Area, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: '#111', border: '1px solid #222',
      padding: '8px 12px', fontSize: 11, fontFamily: 'monospace',
    }}>
      <div style={{ color: '#666', marginBottom: 4 }}>Over {label}</div>
      <div style={{ color: '#00c9a7' }}>CRR: {payload[0]?.value}</div>
      {payload[1] && <div style={{ color: '#d4a017' }}>Target RR: {payload[1]?.value}</div>}
    </div>
  )
}

export default function RunRateGraph({ data = [], targetRR }) {
  return (
    <ResponsiveContainer width="100%" height={110}>
      <AreaChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: -20 }}>
        <defs>
          <linearGradient id="crr" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#00c9a7" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#00c9a7" stopOpacity={0}   />
          </linearGradient>
        </defs>
        <XAxis dataKey="over" tick={{ fill: '#555', fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: '#555', fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip content={<CustomTooltip />} />
        {targetRR && (
          <ReferenceLine y={targetRR} stroke="#d4a017" strokeDasharray="4 3" strokeWidth={1} />
        )}
        <Area
          type="monotone"
          dataKey="crr"
          stroke="#00c9a7"
          strokeWidth={1.5}
          fill="url(#crr)"
          dot={false}
          activeDot={{ r: 3, fill: '#00c9a7', strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
