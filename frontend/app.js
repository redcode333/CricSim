/* ============================================================
   app.js  —  Cricket Sim frontend
   ============================================================ */

// ── Global state ──────────────────────────────────────────
const S = {
  username:    null,
  display:     null,
  matchData:   null,   // current match {inn1, inn2, result, bat_first, fld_first, stadium}
  inningsIdx:  0,      // 0 = first innings, 1 = second
  ballIdx:     0,
  isPaused:    false,
  speed:       600,
  timer:       null,
  // Tournament
  tournSid:    null,
  tournRound:  0,
  tournTotal:  0,
  tournTeam:   null,
  tournSpeed:  600,
  playoffBracket: null,
  playoffIdx:  0,
  // Draft / Series
  draftSid:    null,
  draftPool:   [],     // full pool for filtering
  seriesState: null,   // {user_wins, ai_wins, format}
  // Current over tracker
  overBalls:   [],
  currentOver: -1,
};

// ── API helper ─────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch('/api' + path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'API error');
  return data;
}

// ── Page navigation ─────────────────────────────────────────
function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

// ── Auth ────────────────────────────────────────────────────
document.querySelectorAll('.auth-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const which = tab.dataset.tab;
    document.getElementById('auth-login-form').classList.toggle('hidden', which !== 'login');
    document.getElementById('auth-register-form').classList.toggle('hidden', which !== 'register');
  });
});

async function doLogin() {
  const u = document.getElementById('login-user').value.trim();
  const p = document.getElementById('login-pass').value;
  const err = document.getElementById('login-err');
  err.classList.remove('show');
  try {
    const data = await api('POST', '/auth/login', { username: u, password: p });
    S.username = data.username;
    S.display  = data.display;
    await enterGame();
  } catch(e) {
    err.textContent = e.message;
    err.classList.add('show');
  }
}

async function doRegister() {
  const u  = document.getElementById('reg-user').value.trim();
  const p  = document.getElementById('reg-pass').value;
  const p2 = document.getElementById('reg-pass2').value;
  const err = document.getElementById('reg-err');
  err.classList.remove('show');
  if (p !== p2) { err.textContent = "Passwords don't match."; err.classList.add('show'); return; }
  try {
    const data = await api('POST', '/auth/register', { username: u, password: p });
    S.username = data.username;
    S.display  = data.display;
    await enterGame();
  } catch(e) {
    err.textContent = e.message;
    err.classList.add('show');
  }
}

function guestMode() {
  S.username = null;
  S.display  = 'Guest';
  enterGame();
}

function doLogout() {
  S.username = null; S.display = null;
  showPage('page-auth');
}

async function enterGame() {
  document.getElementById('header-user').textContent =
    S.username ? `Logged in as ${S.display}` : 'Playing as Guest';
  showPage('page-menu');

  // Load save hints
  if (S.username) {
    try {
      const hints = await api('POST', '/saves/hints', { username: S.username });
      if (hints.tournament) {
        const el = document.getElementById('hint-tournament');
        el.textContent = '💾 ' + hints.tournament;
        el.classList.remove('hidden');
      }
      if (hints.duo_ai) {
        const el = document.getElementById('hint-draft');
        el.textContent = '💾 ' + hints.duo_ai;
        el.classList.remove('hidden');
      }
    } catch(_) {}
  }

  // Populate team / stadium dropdowns
  await populateDropdowns();
}

// ── Dropdown population ─────────────────────────────────────
let _teams    = [];
let _stadiums = [];

async function populateDropdowns() {
  if (_teams.length) return;
  [_teams, _stadiums] = await Promise.all([
    api('GET', '/teams/'),
    api('GET', '/teams/stadiums'),
  ]);
  const teamSels  = ['qm-team1','qm-team2','tourn-team'];
  const stadSels  = ['qm-stadium','round-stadium','series-stadium','playoff-stadium'];

  teamSels.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    _teams.forEach(t => { const o = document.createElement('option'); o.value = t; o.textContent = t; el.appendChild(o); });
  });
  if (document.getElementById('qm-team2'))
    document.getElementById('qm-team2').selectedIndex = 1;

  stadSels.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    _stadiums.forEach(s => { const o = document.createElement('option'); o.value = s.id; o.textContent = `${s.name}, ${s.city}`; el.appendChild(o); });
  });
}

// ── Quick Match ─────────────────────────────────────────────
async function startQuickMatch() {
  const t1  = document.getElementById('qm-team1').value;
  const t2  = document.getElementById('qm-team2').value;
  const sid = parseInt(document.getElementById('qm-stadium').value);
  const bf  = document.getElementById('qm-batfirst').value;
  S.speed   = parseInt(document.getElementById('qm-speed').value);

  if (t1 === t2) { alert('Pick two different teams.'); return; }

  let bat_first = null;
  if (bf === 'team1') bat_first = t1;
  if (bf === 'team2') bat_first = t2;

  showPage('page-match');
  document.getElementById('match-header').textContent = `${t1} vs ${t2}`;

  try {
    const data = await api('POST', '/match/quick', { team1: t1, team2: t2, stadium_id: sid, bat_first });
    S.matchData   = data;
    S.inningsIdx  = 0;
    S.afterMatch  = () => showScorecardFull();
    playInnings(0);
  } catch(e) { alert(e.message); showPage('page-quick-setup'); }
}

// ── Match playback engine ────────────────────────────────────
function playInnings(idx) {
  clearInterval(S.timer);
  const inn  = idx === 0 ? S.matchData.inn1 : S.matchData.inn2;
  const balls = inn.balls;
  S.ballIdx   = 0;
  S.isPaused  = false;
  S.overBalls = [];
  S.currentOver = -1;
  document.getElementById('pause-btn').textContent = '⏸';

  // Header
  document.getElementById('sb-teams').textContent =
    `${S.matchData.bat_first} vs ${S.matchData.fld_first} · ${S.matchData.stadium.name}`;

  // Target line
  const targetEl = document.getElementById('sb-target');
  if (idx === 1) {
    const target = S.matchData.inn1.runs + 1;
    targetEl.textContent = `Target: ${target}`;
    targetEl.classList.remove('hidden');
  } else {
    targetEl.classList.add('hidden');
  }

  // Clear feed
  document.getElementById('commentary-feed').innerHTML = '';
  document.getElementById('batsmen-table').querySelector('tbody').innerHTML = '';
  document.getElementById('bowler-table').querySelector('tbody').innerHTML = '';
  document.getElementById('over-tracker').innerHTML = '';
  document.getElementById('match-innings-done').classList.add('hidden');
  document.getElementById('sb-runs').textContent  = '0/0';
  document.getElementById('sb-overs').textContent = '0.0 overs';
  document.getElementById('sb-crr').textContent   = 'CRR: 0.00';

  if (S.speed === 0) {
    // Instant: dump all balls at once
    balls.forEach(b => renderBall(b, inn));
    finishInnings(idx, inn);
  } else {
    S.timer = setInterval(() => {
      if (S.isPaused) return;
      if (S.ballIdx >= balls.length) {
        clearInterval(S.timer);
        finishInnings(idx, inn);
        return;
      }
      renderBall(balls[S.ballIdx], inn);
      S.ballIdx++;
    }, S.speed);
  }
}

function renderBall(b, inn) {
  // Score
  document.getElementById('sb-runs').textContent  = `${b.runs}/${b.wickets}`;
  document.getElementById('sb-overs').textContent = `${b.over_str} overs`;
  document.getElementById('sb-crr').textContent   = `CRR: ${b.crr}`;
  if (b.runs_needed !== null && b.runs_needed !== undefined) {
    const tEl = document.getElementById('sb-target');
    tEl.textContent = `Need ${b.runs_needed} off ${ballsRemaining(b.over_str)} balls · RRR: ${b.rrr}`;
    tEl.classList.remove('hidden');
  }

  // Scoreboard flash
  const sb = document.getElementById('match-scoreboard');
  sb.className = 'scoreboard mt2';
  if (b.outcome === '4') sb.classList.add('flash-four');
  else if (b.outcome === '6') sb.classList.add('flash-six');
  else if (b.outcome === 'W') sb.classList.add('flash-wkt');
  else if (['1','2','3'].includes(b.outcome)) sb.classList.add('flash-run');

  // Current batsmen
  updateBatsmenTable(b, inn);
  updateBowlerTable(b, inn);

  // Over tracker
  updateOverTracker(b);

  // Commentary
  addCommentaryBall(b);
}

function ballsRemaining(overStr) {
  const [ov, bl] = overStr.split('.').map(Number);
  return (20 - ov) * 6 - bl;
}

function updateBatsmenTable(b, inn) {
  const tbody = document.getElementById('batsmen-table').querySelector('tbody');
  tbody.innerHTML = '';
  // Find striker (last batsman mentioned + non-striker)
  const batsmenSeen = new Set();
  const recent = [...inn.balls].slice(0, inn.balls.indexOf(b) + 1).reverse();
  const active = [];
  for (const ball of recent) {
    if (!batsmenSeen.has(ball.batsman) && ball.outcome !== 'W') {
      batsmenSeen.add(ball.batsman);
      active.push(ball.batsman);
      if (active.length === 2) break;
    }
  }
  active.forEach((name, i) => {
    const runs = sumRunsForBatsman(name, inn.balls, inn.balls.indexOf(b));
    const balls = countBallsForBatsman(name, inn.balls, inn.balls.indexOf(b));
    const sr = balls > 0 ? ((runs / balls) * 100).toFixed(1) : '0.0';
    const tr = document.createElement('tr');
    if (i === 0) tr.classList.add('on-strike');
    tr.innerHTML = `<td>${name}</td><td>${runs}</td><td>${balls}</td><td>${sr}</td>`;
    tbody.appendChild(tr);
  });
}

function sumRunsForBatsman(name, balls, upTo) {
  let r = 0;
  for (let i = 0; i <= upTo; i++) {
    const b = balls[i];
    if (b.batsman === name && !['W','Wd','Nb'].includes(b.outcome)) r += parseInt(b.outcome) || 0;
  }
  return r;
}

function countBallsForBatsman(name, balls, upTo) {
  let c = 0;
  for (let i = 0; i <= upTo; i++) {
    const b = balls[i];
    if (b.batsman === name && !['Wd','Nb'].includes(b.outcome)) c++;
  }
  return c;
}

function updateBowlerTable(b, inn) {
  const tbody = document.getElementById('bowler-table').querySelector('tbody');
  tbody.innerHTML = '';
  // Current bowler = this ball's bowler
  const name = b.bowler;
  const overs = countOversForBowler(name, inn.balls, inn.balls.indexOf(b));
  const runs  = sumRunsForBowler(name, inn.balls, inn.balls.indexOf(b));
  const wkts  = countWicketsForBowler(name, inn.balls, inn.balls.indexOf(b));
  const tr = document.createElement('tr');
  tr.classList.add('active-bowler');
  tr.innerHTML = `<td>${name}</td><td>${overs}</td><td>${runs}</td><td>${wkts}</td>`;
  tbody.appendChild(tr);
}

function countOversForBowler(name, balls, upTo) {
  let legal = 0;
  for (let i = 0; i <= upTo; i++) {
    const b = balls[i];
    if (b.bowler === name && !['Wd','Nb'].includes(b.outcome)) legal++;
  }
  return `${Math.floor(legal/6)}.${legal%6}`;
}

function sumRunsForBowler(name, balls, upTo) {
  let r = 0;
  for (let i = 0; i <= upTo; i++) {
    const b = balls[i];
    if (b.bowler === name) {
      if (['Wd','Nb'].includes(b.outcome)) r += 1;
      else if (!['W'].includes(b.outcome)) r += parseInt(b.outcome) || 0;
    }
  }
  return r;
}

function countWicketsForBowler(name, balls, upTo) {
  return balls.slice(0, upTo+1).filter(b => b.bowler === name && b.outcome === 'W').length;
}

function updateOverTracker(b) {
  const [ov] = b.over_str.split('.').map(Number);
  if (ov !== S.currentOver) {
    S.currentOver = ov;
    S.overBalls = [];
  }
  if (!['Wd','Nb'].includes(b.outcome)) {
    S.overBalls.push(b.outcome);
  } else {
    S.overBalls.push(b.outcome); // still show extras
  }
  const el = document.getElementById('over-tracker');
  el.innerHTML = '';
  S.overBalls.forEach(o => {
    const dot = document.createElement('div');
    dot.className = 'over-dot ' + outcomeClass(o);
    dot.textContent = o === 'Wd' ? 'w' : o === 'Nb' ? 'n' : o === 'W' ? 'W' : o === '0' ? '·' : o;
    el.appendChild(dot);
  });
}

function outcomeClass(o) {
  if (o === '0') return 'dot';
  if (o === 'W') return 'wkt';
  if (o === '4') return 'four';
  if (o === '6') return 'six';
  if (o === 'Wd' || o === 'Nb') return 'wide';
  return 'run';
}

function addCommentaryBall(b) {
  const feed = document.getElementById('commentary-feed');
  const entry = document.createElement('div');
  entry.className = 'ball-entry';

  const badge = document.createElement('div');
  badge.className = 'ball-badge ' + badgeClass(b.outcome);
  badge.textContent = b.outcome === 'Wd' ? 'WD' : b.outcome === 'Nb' ? 'NB' : b.outcome === 'W' ? 'OUT' : b.outcome === '0' ? '·' : b.outcome;
  entry.appendChild(badge);

  const text = document.createElement('div');
  text.textContent = `${b.over_str}  ${b.commentary}`;
  entry.appendChild(text);

  feed.insertBefore(entry, feed.firstChild);
}

function badgeClass(o) {
  if (o === '0') return 'dot';
  if (o === '1') return 'one';
  if (o === '2') return 'two';
  if (o === '3') return 'three';
  if (o === '4') return 'four';
  if (o === '6') return 'six';
  if (o === 'W') return 'wkt';
  if (o === 'Wd') return 'wide';
  if (o === 'Nb') return 'nb';
  return 'dot';
}

function finishInnings(idx, inn) {
  const doneDiv = document.getElementById('match-innings-done');
  const nextBtn = document.getElementById('innings-next-btn');
  if (idx === 0) {
    const target = S.matchData.inn1.runs + 1;
    document.getElementById('innings-done-msg').textContent =
      `${inn.team} finished: ${inn.runs}/${inn.wickets} (${inn.overs} ov) — ${S.matchData.fld_first} need ${target} to win`;
    nextBtn.classList.remove('hidden');
    doneDiv.classList.remove('hidden');
  } else {
    // Match over — go to scorecard
    if (S.afterMatch) S.afterMatch();
  }
}

function startNextInnings() {
  S.inningsIdx = 1;
  document.getElementById('match-innings-done').classList.add('hidden');
  playInnings(1);
}

function togglePause() {
  S.isPaused = !S.isPaused;
  document.getElementById('pause-btn').textContent = S.isPaused ? '▶' : '⏸';
}

function setSpeed(ms) {
  S.speed = ms;
  document.querySelectorAll('.speed-btn[data-ms]').forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.ms) === ms);
  });
  if (S.timer) {
    clearInterval(S.timer);
    if (ms > 0 && S.ballIdx < (S.matchData?.inn1?.balls?.length || 0)) {
      const inn = S.inningsIdx === 0 ? S.matchData.inn1 : S.matchData.inn2;
      S.timer = setInterval(() => {
        if (S.isPaused) return;
        if (S.ballIdx >= inn.balls.length) { clearInterval(S.timer); finishInnings(S.inningsIdx, inn); return; }
        renderBall(inn.balls[S.ballIdx], inn);
        S.ballIdx++;
      }, S.speed);
    }
  }
}

// ── Scorecard ────────────────────────────────────────────────
function showScorecardFull() {
  // Show inn1 scorecard first
  showScorecard(0, () => showScorecard(1, () => showMatchResult()));
}

function showScorecard(idx, next) {
  const inn  = idx === 0 ? S.matchData.inn1 : S.matchData.inn2;
  document.getElementById('sc-header').textContent = `${inn.team} — ${inn.runs}/${inn.wickets} (${inn.overs} ov)`;
  document.getElementById('sc-bat-title').textContent = `${inn.team} Batting`;
  document.getElementById('sc-bowl-title').textContent = 'Bowling';
  document.getElementById('sc-result-banner').classList.add('hidden');

  // Batting
  const batBody = document.getElementById('sc-bat-body');
  batBody.innerHTML = '';
  inn.bat_stats.forEach(b => {
    const tr = document.createElement('tr');
    if (b.dismissed) tr.classList.add('dismissed');
    tr.innerHTML = `<td>${b.name}</td><td>${b.runs}</td><td>${b.balls}</td><td>${b.fours}</td><td>${b.sixes}</td><td>${b.sr}</td>`;
    batBody.appendChild(tr);
  });

  // Bowling
  const bowlBody = document.getElementById('sc-bowl-body');
  bowlBody.innerHTML = '';
  inn.bowl_stats.forEach(b => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${b.name}</td><td>${b.overs}</td><td>${b.runs}</td><td>${b.wickets}</td><td>${b.economy}</td>`;
    bowlBody.appendChild(tr);
  });

  // FoW
  document.getElementById('sc-fow').textContent =
    inn.fow.map(f => `${f.n}-${f.score} (${f.batsman}, ${f.over} ov)`).join(' | ') || 'No wickets fell';

  const nextBtn = document.getElementById('sc-next-btn');
  nextBtn.textContent = idx === 0 ? '→ 2nd Innings Scorecard' : '→ Match Result';
  nextBtn.onclick = next;
  showPage('page-scorecard');
}

function showMatchResult() {
  const r     = S.matchData.result;
  const inn1  = S.matchData.inn1;
  const inn2  = S.matchData.inn2;
  const banner = document.getElementById('sc-result-banner');
  banner.classList.remove('hidden');
  banner.innerHTML = `
    <div class="winner-label">${r.winner ? r.winner + ' won!' : 'Match Tied!'}</div>
    <div class="margin-label">${r.winner ? 'by ' + r.margin : ''}</div>
    <div class="score-summary mt2">
      ${inn1.team}: ${inn1.runs}/${inn1.wickets} (${inn1.overs} ov)<br>
      ${inn2.team}: ${inn2.runs}/${inn2.wickets} (${inn2.overs} ov)
    </div>
  `;
  document.getElementById('sc-next-btn').textContent = '← Menu';
  document.getElementById('sc-next-btn').onclick = () => {
    if (S.returnPage) showPage(S.returnPage);
    else showPage('page-menu');
  };
  showPage('page-scorecard');
}

// ── Tournament ───────────────────────────────────────────────
async function startTournament() {
  await populateDropdowns();
  // Check for save
  const saveHintEl = document.getElementById('hint-tournament');
  if (S.username && !saveHintEl.classList.contains('hidden')) {
    document.getElementById('tourn-save-box').classList.remove('hidden');
    document.getElementById('tourn-save-desc').textContent = saveHintEl.textContent;
  } else {
    document.getElementById('tourn-save-box').classList.add('hidden');
  }
  showPage('page-tourn-setup');
}

async function loadTournament() {
  try {
    const data = await api('POST', '/tournament/load', { username: S.username });
    S.tournSid   = data.session_id;
    S.tournRound = data.round_idx;
    S.tournTotal = data.total_rounds;
    S.tournTeam  = data.player_team;
    S.tournSpeed = 600;
    if (data.playoff_state) {
      S.playoffBracket = data.playoff_state.bracket;
      S.playoffIdx     = data.playoff_state.next_playoff_idx;
      showPlayoffs();
    } else {
      showTournamentRound(data.standings);
    }
  } catch(e) { alert(e.message); }
}

async function newTournament() {
  document.getElementById('tourn-save-box').classList.add('hidden');
}

async function beginTournament() {
  const team = document.getElementById('tourn-team').value;
  S.tournSpeed = parseInt(document.getElementById('tourn-speed').value);
  try {
    const data = await api('POST', '/tournament/new', { player_team: team, username: S.username });
    S.tournSid   = data.session_id;
    S.tournRound = data.round_idx;
    S.tournTotal = data.total_rounds;
    S.tournTeam  = team;
    showTournamentRound(data.standings);
  } catch(e) { alert(e.message); }
}

function showTournamentRound(standings) {
  const rnd = S.tournRound;
  if (rnd >= S.tournTotal) {
    showPlayoffsSetup();
    return;
  }
  document.getElementById('round-header').textContent = `Round ${rnd + 1} / ${S.tournTotal}`;
  document.getElementById('round-sub').textContent = `Managing: ${S.tournTeam}`;
  document.getElementById('ai-results-list').innerHTML = '<span class="text-muted" style="font-size:.8rem">AI results will appear here after you play your match.</span>';
  document.getElementById('your-match-info').textContent = '';
  renderStandings(standings, S.tournTeam);
  showPage('page-tourn-round');
}

async function playRound() {
  const stadId   = parseInt(document.getElementById('round-stadium').value);
  const batChoice = document.getElementById('round-bat-choice').value;
  let batFirst = null;
  if (batChoice === 'bat')   batFirst = true;
  if (batChoice === 'field') batFirst = false;

  try {
    const data = await api('POST', `/tournament/${S.tournSid}/play-round`, {
      round_idx: S.tournRound, stadium_id: stadId, bat_first: batFirst,
    });

    // Show AI results
    const aiEl = document.getElementById('ai-results-list');
    aiEl.innerHTML = data.ai_results.map(r =>
      `<div style="padding:.3rem 0;border-bottom:1px solid var(--border)">
        <span class="text-muted">#${r.match_num}</span>
        ${r.team1} <b>${r.t1_score}</b> vs ${r.team2} <b>${r.t2_score}</b>
        — <span class="text-accent">${r.winner || 'Tied'}</span>
        ${r.winner ? `by ${r.margin}` : ''}
      </div>`
    ).join('');

    renderStandings(data.standings, S.tournTeam);
    S.tournRound = data.next_round_idx;

    if (data.user_match) {
      // Play the match
      S.matchData  = data.user_match;
      S.inningsIdx = 0;
      S.speed      = S.tournSpeed;
      document.getElementById('match-header').textContent =
        `Match — ${data.user_match.bat_first} vs ${data.user_match.fld_first}`;
      S.afterMatch = () => {
        // After scorecard show match result, then back to round view
        showScorecardAfterTournament(data.standings);
      };
      showPage('page-match');
      playInnings(0);
    } else if (data.group_complete) {
      showPlayoffsSetup();
    } else {
      showTournamentRound(data.standings);
    }
  } catch(e) { alert(e.message); }
}

function showScorecardAfterTournament(standings) {
  S.returnPage = null;
  showScorecard(0, () => showScorecard(1, () => {
    // Show result then back to round
    const r    = S.matchData.result;
    const inn1 = S.matchData.inn1;
    const inn2 = S.matchData.inn2;
    const banner = document.getElementById('sc-result-banner');
    banner.classList.remove('hidden');
    banner.innerHTML = `
      <div class="winner-label">${r.winner ? r.winner + ' won!' : 'Match Tied!'}</div>
      <div class="margin-label">${r.winner ? 'by ' + r.margin : ''}</div>
      <div class="score-summary mt2">
        ${inn1.team}: ${inn1.runs}/${inn1.wickets} (${inn1.overs} ov)<br>
        ${inn2.team}: ${inn2.runs}/${inn2.wickets} (${inn2.overs} ov)
      </div>
    `;
    document.getElementById('sc-next-btn').textContent = '→ Continue Tournament';
    document.getElementById('sc-next-btn').onclick = () => {
      if (S.tournRound >= S.tournTotal) showPlayoffsSetup();
      else showTournamentRound(standings);
    };
    showPage('page-scorecard');
  }));
}

async function showPlayoffsSetup() {
  try {
    const data = await api('GET', `/tournament/${S.tournSid}/top4`);
    S.playoffBracket = data.bracket;
    S.playoffIdx     = 0;
    sessions_update_bracket(data.bracket);
    showPlayoffs();
  } catch(e) { alert(e.message); }
}

function sessions_update_bracket(bracket) {
  S.playoffBracket = bracket;
}

function showPlayoffs() {
  const bracket = S.playoffBracket;
  const idx     = S.playoffIdx;

  document.getElementById('playoff-sub').textContent = `Managing: ${S.tournTeam}`;

  const bracketEl = document.getElementById('playoff-bracket-view');
  bracketEl.innerHTML = '<div class="card-title">Bracket</div>' +
    bracket.map((m, i) => `
      <div style="padding:.4rem 0;border-bottom:1px solid var(--border);font-size:.85rem;
                  ${i === idx ? 'color:var(--gold)' : 'color:var(--muted)'}">
        <b>${m.name}</b>: ${m.team1 || '?'} vs ${m.team2 || '?'}
        ${m.winner ? `<span class="badge badge-green">${m.winner} won</span>` : ''}
      </div>
    `).join('');

  if (idx < 4) {
    const cur = bracket[idx];
    document.getElementById('playoff-match-title').textContent =
      `${cur.name}: ${cur.team1} vs ${cur.team2}`;
    document.getElementById('playoff-match-setup').classList.remove('hidden');
  } else {
    document.getElementById('playoff-match-setup').classList.add('hidden');
  }

  showPage('page-playoffs');
}

async function playPlayoffMatch() {
  const stadId = parseInt(document.getElementById('playoff-stadium').value);
  const idx    = S.playoffIdx;
  try {
    const data = await api('POST', `/tournament/${S.tournSid}/play-playoff`, {
      match_idx: idx, stadium_id: stadId,
    });

    S.playoffBracket = data.bracket;
    S.matchData      = data.match_data;
    S.inningsIdx     = 0;
    S.speed          = S.tournSpeed;

    const m = S.matchData;
    document.getElementById('match-header').textContent =
      `${S.playoffBracket[idx].name} — ${m.bat_first} vs ${m.fld_first}`;

    S.afterMatch = () => {
      showScorecard(0, () => showScorecard(1, () => {
        if (data.complete) {
          // Tournament over
          const banner = document.getElementById('sc-result-banner');
          banner.classList.remove('hidden');
          banner.innerHTML = `
            <div class="winner-label">🏆 ${data.champion} are IPL 2026 Champions!</div>
            <div class="margin-label mt1">${data.champion === S.tournTeam ? 'Congratulations! You won!' : ''}</div>
          `;
          document.getElementById('sc-next-btn').textContent = '← Main Menu';
          document.getElementById('sc-next-btn').onclick = () => showPage('page-menu');
          showPage('page-scorecard');
        } else {
          S.playoffIdx++;
          showPlayoffs();
        }
      }));
    };

    showPage('page-match');
    playInnings(0);
  } catch(e) { alert(e.message); }
}

function renderStandings(standings, highlightTeam) {
  const tbody = document.getElementById('standings-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  standings.forEach((s, i) => {
    const tr = document.createElement('tr');
    if (s.team === highlightTeam) tr.classList.add('player-row');
    if (i < 4) tr.classList.add('playoff-row');
    const nrr = s.nrr >= 0 ? `+${s.nrr}` : `${s.nrr}`;
    tr.innerHTML = `<td>${i+1}</td><td>${s.team}</td><td>${s.played}</td><td>${s.won}</td><td>${s.lost}</td><td>${s.points}</td><td>${nrr}</td>`;
    tbody.appendChild(tr);
  });
}

// ── Draft ─────────────────────────────────────────────────────
async function startDraft() {
  await populateDropdowns();
  try {
    const data = await api('POST', '/draft/new', { username: S.username });
    S.draftSid  = data.session_id;
    S.draftPool = data.pool;
    renderDraft(data);
    showPage('page-draft');
  } catch(e) { alert(e.message); }
}

function renderDraft(data) {
  document.getElementById('draft-round-label').textContent =
    `Round ${data.round}/11`;

  const banner = document.getElementById('draft-turn-banner');
  banner.textContent = data.complete ? 'Draft complete!' : (data.awaiting === 'user' ? '🟢 Your pick' : '🤖 AI picking…');
  banner.className = 'draft-turn-banner ' + (data.awaiting === 'user' ? 'your-turn' : 'ai-turn');

  // Pool
  renderPool(data.pool);

  // XIs
  renderXI('user-xi-list', 'user-xi-count', data.user_xi);
  renderXI('ai-xi-list',   'ai-xi-count',   data.ai_xi);

  if (data.complete) {
    document.getElementById('draft-pool').innerHTML =
      '<div class="text-muted" style="padding:1rem;text-align:center">Draft complete! Set up your series below.</div>';
    setTimeout(() => showPage('page-series-setup'), 1200);
  }
}

function renderPool(pool) {
  S.draftPool = pool;
  filterPool();
}

function filterPool() {
  const q   = (document.getElementById('draft-search')?.value || '').toLowerCase();
  const el  = document.getElementById('draft-pool');
  el.innerHTML = '';
  const filtered = S.draftPool.filter(p =>
    p.name.toLowerCase().includes(q) || p.team.toLowerCase().includes(q)
  );
  filtered.slice(0, 40).forEach(p => {
    const div = document.createElement('div');
    div.className = 'pool-player';
    div.innerHTML = `
      <div>
        <div class="pname">${p.name}</div>
        <div class="pteam">${p.team} · ${p.role}</div>
      </div>
      <div class="pstats">${p.bowling_type ? p.bowling_type + '<br>' : ''}Bat ${p.bat_power} | Wkt ${p.wicket_threat}</div>
    `;
    div.onclick = () => draftPick(p.id);
    el.appendChild(div);
  });
}

function renderXI(listId, countId, xi) {
  const list = document.getElementById(listId);
  list.innerHTML = '';
  xi.forEach(p => {
    const li = document.createElement('li');
    li.innerHTML = `<span>${p.name}</span><span class="role-badge">${p.role}</span>`;
    list.appendChild(li);
  });
  document.getElementById(countId).textContent = xi.length;
}

async function draftPick(playerId) {
  if (!S.draftSid) return;
  try {
    const data = await api('POST', `/draft/${S.draftSid}/pick`, { player_id: playerId });
    // Show AI picks briefly
    const msgs = data.ai_picks.map(p => `AI picked: ${p.name} (${p.team})`).join('\n');
    if (msgs) setTimeout(() => alert(msgs), 100);
    renderDraft({
      round: data.round, awaiting: data.awaiting, complete: data.complete,
      pool: data.pool, user_xi: data.user_xi, ai_xi: data.ai_xi,
    });
  } catch(e) { alert(e.message); }
}

async function startSeries() {
  const fmtVal = parseInt(document.getElementById('series-format').value);
  const stadId = parseInt(document.getElementById('series-stadium').value);
  const spd    = parseInt(document.getElementById('series-speed').value);
  const fmtMap = { 1: {total:1, to_win:1, label:'1-off T20'}, 3: {total:3, to_win:2, label:'Best of 3'}, 5: {total:5, to_win:3, label:'Best of 5'} };
  const fmt    = fmtMap[fmtVal];
  S.tournSpeed = spd;
  S.seriesState = { user_wins: 0, ai_wins: 0, format: fmt };

  try {
    await api('POST', `/draft/${S.draftSid}/setup-series`, {
      stadium_id: stadId, total: fmt.total, to_win: fmt.to_win, label: fmt.label,
    });
    playSeriesMatch();
  } catch(e) { alert(e.message); }
}

async function playSeriesMatch() {
  try {
    const data = await api('POST', `/draft/${S.draftSid}/play-match`);
    S.matchData  = data.match_data;
    S.inningsIdx = 0;
    S.speed      = S.tournSpeed;

    const m = S.matchData;
    const fmt = data.format;
    document.getElementById('match-header').textContent =
      `${fmt.label} — ${m.bat_first} vs ${m.fld_first}`;
    document.getElementById('series-score-header').textContent =
      `YOU ${data.user_wins}  AI ${data.ai_wins}`;

    S.afterMatch = () => {
      showScorecard(0, () => showScorecard(1, () => {
        showSeriesResult(data);
      }));
    };
    showPage('page-match');
    playInnings(0);
  } catch(e) { alert(e.message); }
}

function showSeriesResult(data) {
  const r = data.match_data.result;
  const resEl = document.getElementById('series-result-text');
  resEl.innerHTML = `
    <div style="font-size:1.2rem;font-weight:700;color:${data.match_winner==='user'?'var(--accent)':'var(--red)'}">
      ${data.match_winner === 'user' ? '✅ You won this match!' : data.match_winner === 'ai' ? '❌ AI won this match.' : '🤝 Match tied.'}
    </div>
    <div class="text-muted mt1">${r.winner ? r.winner + ' by ' + r.margin : 'Tied'}</div>
  `;
  document.getElementById('series-score-display').textContent =
    `Series: YOU ${data.user_wins} — AI ${data.ai_wins}  (${data.format.label})`;

  const nextBtn = document.getElementById('series-next-btn');
  if (data.series_done) {
    nextBtn.textContent = '← Main Menu';
    const winner = data.series_winner;
    resEl.innerHTML += `<div class="mt2" style="font-size:1.1rem;font-weight:700;color:var(--gold)">
      ${winner === 'user' ? '🏆 You win the series!' : '💔 AI wins the series.'}</div>`;
    nextBtn.onclick = () => showPage('page-menu');
  } else {
    nextBtn.textContent = '▶ Next Match';
    nextBtn.onclick = () => playSeriesMatch();
  }

  document.getElementById('series-match-result').classList.remove('hidden');
  showPage('page-series-match');
}

// ── Enter key on auth forms ───────────────────────────────────
document.getElementById('login-pass').addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
document.getElementById('reg-pass2').addEventListener('keydown', e => { if (e.key === 'Enter') doRegister(); });
