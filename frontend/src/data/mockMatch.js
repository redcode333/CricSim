export const MOCK_INNINGS = {
  batting_team: 'Mumbai Indians',
  bowling_team: 'Royal Challengers Bengaluru',
  score: 178,
  wickets: 6,
  overs: '18.4',
  crr: 9.57,
  target: null,
  batsmen: [
    { name: 'Rohit Sharma',      runs: 44,  balls: 29, fours: 5, sixes: 3, sr: 151.7, status: 'out' },
    { name: 'Ishan Kishan',      runs: 31,  balls: 22, fours: 3, sixes: 2, sr: 140.9, status: 'out' },
    { name: 'Suryakumar Yadav',  runs: 71,  balls: 41, fours: 6, sixes: 5, sr: 173.2, status: 'batting' },
    { name: 'Tilak Varma',       runs: 18,  balls: 14, fours: 2, sixes: 0, sr: 128.6, status: 'batting' },
    { name: 'Hardik Pandya',     runs: 14,  balls: 8,  fours: 1, sixes: 1, sr: 175.0, status: 'out' },
  ],
  bowlers: [
    { name: 'Jasprit Bumrah',    overs: '4.0', runs: 28, wickets: 2, economy: 7.00 },
    { name: 'Mohammed Siraj',    overs: '3.0', runs: 34, wickets: 1, economy: 11.33 },
    { name: 'Josh Hazlewood',    overs: '3.4', runs: 41, wickets: 1, economy: 11.18 },
    { name: 'Virat Kohli',       overs: '1.0', runs: 12, wickets: 0, economy: 12.00 },
    { name: 'Krunal Pandya',     overs: '4.0', runs: 39, wickets: 2, economy: 9.75 },
    { name: 'Jacob Bethell',     overs: '3.0', runs: 24, wickets: 0, economy: 8.00 },
  ],
  current_over_balls: ['0', '4', '1', 'W', '6'],
}

export const MOCK_FEED = [
  { over: '18.4', outcome: 'Wd',  text: 'Wide down the leg side from Hazlewood.' },
  { over: '18.4', outcome: '1',   text: 'SKY nudges it to midwicket for a single.' },
  { over: '18.3', outcome: '6',   text: 'MASSIVE SIX! Suryakumar clears long-on with ease.' },
  { over: '18.2', outcome: 'W',   text: 'OUT! Tilak holes out to long-off. Hazlewood strikes.' },
  { over: '18.1', outcome: '4',   text: 'FOUR! SKY flicks it fine, races to the boundary.' },
  { over: '18.0', outcome: '0',   text: 'Good length delivery, SKY defends solidly.' },
  { over: '17.6', outcome: '1',   text: 'Pushed to covers for one.' },
  { over: '17.5', outcome: '4',   text: 'FOUR! Tilak Varma drives through extra cover.' },
  { over: '17.4', outcome: '0',   text: 'Dot ball. Bethell ties Tilak down outside off.' },
  { over: '17.3', outcome: '6',   text: 'SIX! SKY goes inside-out over covers. Stunning.' },
]

export const MOCK_RUN_RATE = Array.from({ length: 19 }, (_, i) => ({
  over: i + 1,
  crr: +(5.5 + (i / 18) * 4.2 + (Math.random() - 0.5) * 1.2).toFixed(2),
  target_rr: 8.5,
}))

export const MOCK_WIN_PROB = 62   // MI win probability %

export const MOCK_PLAYERS = [
  {
    id: 'MI_002', name: 'Suryakumar Yadav', team: 'MI', role: 'batter', age: 34, nationality: 'IND',
    skills: { bat_power: 0.735, bat_control: 0.68, bat_aggression: 0.71, vs_pace: 0.66, vs_spin: 0.64 },
    bowling: { type: 'pace', economy_skill: 0.15, wicket_threat: 0.05, death_skill: 0.12 },
    mental: { pressure_handling: 0.90, consistency: 0.88 },
    fielding: { catching: 0.85, ground_fielding: 0.82, throwing: 0.80 },
    running: { speed: 0.80, quick_singles: 0.82 },
    form: { recent_form: 0.78 },
  },
  {
    id: 'MI_017', name: 'Jasprit Bumrah', team: 'MI', role: 'bowler', age: 30, nationality: 'IND',
    skills: { bat_power: 0.05, bat_control: 0.05, bat_aggression: 0.05, vs_pace: 0.05, vs_spin: 0.05 },
    bowling: { type: 'pace', economy_skill: 0.88, wicket_threat: 0.92, death_skill: 0.95 },
    mental: { pressure_handling: 0.97, consistency: 0.95 },
    fielding: { catching: 0.75, ground_fielding: 0.72, throwing: 0.70 },
    running: { speed: 0.62, quick_singles: 0.60 },
    form: { recent_form: 0.85 },
  },
  {
    id: 'RCB_001', name: 'Virat Kohli', team: 'RCB', role: 'batter', age: 37, nationality: 'IND',
    skills: { bat_power: 0.546, bat_control: 0.71, bat_aggression: 0.499, vs_pace: 0.658, vs_spin: 0.728 },
    bowling: { type: 'pace', economy_skill: 0.573, wicket_threat: 0.05, death_skill: 0.277 },
    mental: { pressure_handling: 0.97, consistency: 0.95 },
    fielding: { catching: 0.92, ground_fielding: 0.91, throwing: 0.90 },
    running: { speed: 0.92, quick_singles: 0.94 },
    form: { recent_form: 0.643 },
  },
]
