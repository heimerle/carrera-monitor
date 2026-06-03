/* RacePulse 132 — Driver roster, i18n strings, race simulation engine.
   Exposed as window globals for cross-file use. */

// ── Driver roster ──────────────────────────────────────────────────────────
const ROSTER = [
  { id: 1, no: 7,  first: 'Maximilian', last: 'KÖHLER',  team: 'RaceLab Boxenstop',  car: 'Audi R8 LMS Evo II',     country: 'DE', flag: ['#000','#dd0000','#ffce00'], color: '#c8102e', ink: '#fff' },
  { id: 2, no: 19, first: 'Tobias',     last: 'WEISS',   team: 'Heimkeller Racing',  car: 'Porsche 911 GT3 R',      country: 'DE', flag: ['#000','#dd0000','#ffce00'], color: '#1c1c1c', ink: '#fff' },
  { id: 3, no: 4,  first: 'Lukas',      last: 'RICHTER', team: 'Schwarzwald Motors', car: 'Mercedes-AMG GT3',       country: 'DE', flag: ['#000','#dd0000','#ffce00'], color: '#00a3a1', ink: '#fff' },
  { id: 4, no: 88, first: 'Sebastian',  last: 'BAUER',   team: 'M-Power Garage',     car: 'BMW M4 GT3',             country: 'DE', flag: ['#000','#dd0000','#ffce00'], color: '#0066b1', ink: '#fff' },
  { id: 5, no: 23, first: 'Jakub',      last: 'NOWAK',   team: 'Toro Carrera',       car: 'Lamborghini Huracán GT3',country: 'PL', flag: ['#fff','#fff','#dc143c'], color: '#28a745', ink: '#fff' },
  { id: 6, no: 55, first: 'Felix',      last: 'BERGER',  team: 'Alpenglow Racing',   car: 'Ford Mustang GT4',       country: 'AT', flag: ['#ed2939','#fff','#ed2939'], color: '#ff7a00', ink: '#1a1a1a' },
  { id: 7, no: '·', first: '',          last: 'GHOST',   team: 'AI Pace Ghost',      car: 'Phantom Ghost-Car',       country: '··', flag: ['#444','#222','#444'], color: '#5e6b7a', ink: '#fff', isGhost: true },
  { id: 8, no: 'P', first: '',          last: 'PACE',    team: 'Safety',             car: 'Carrera Pace Car',        country: '··', flag: ['#ffce00','#1a1a1a','#ffce00'], color: '#ffce00', ink: '#1a1a1a', isPace: true },
];

// ── i18n strings ───────────────────────────────────────────────────────────
const STRINGS = {
  de: {
    sessionLabel: 'Session',
    trackLabel: 'Strecke',
    raceLabel: 'Rennen',
    raceState: { IDLE: 'BEREIT', FORMATION: 'FORMATION', RUNNING: 'RENNEN LÄUFT', PAUSED: 'PAUSE', FINISHED: 'BEENDET' },
    lap: 'Runde',
    laps: 'Runden',
    of: 'von',
    pos: 'Pos',
    driver: 'Fahrer / Fahrzeug',
    lastLap: 'Letzte',
    bestLap: 'Beste',
    sectors: 'Sektoren',
    gap: 'Abstand',
    int: 'Intervall',
    fuel: 'Tank',
    status: 'Status',
    statusRun: 'Strecke',
    statusPit: 'Box',
    statusOut: 'Out-Lap',
    statusGhost: 'Ghost',
    statusPace: 'Pace',
    statusFin: 'Beendet',
    events: 'Renn-Geschehen',
    eventsLive: 'live',
    bt: 'AppConnect · Control Unit',
    btConn: 'Verbunden',
    signal: 'Signal',
    latency: 'Latenz',
    rx: 'RX',
    tx: 'TX',
    cuFw: 'CU Firmware',
    heartbeat: 'Heartbeat',
    track: 'Streckenkarte',
    trackLen: 'Länge',
    sector: 'Sektor',
    start: 'Start',
    pause: 'Pause',
    resume: 'Fortsetzen',
    stop: 'Abbrechen',
    safetyCar: 'Pace Car',
    progress: 'Fortschritt',
    elapsed: 'Renndauer',
    remaining: 'Verbleibend',
    fuelPanel: 'Tankstand & Box',
    pitCount: 'Stops',
    lastStop: 'Letzter',
    leader: 'Führender',
    fastest: 'Schnellste',
    avgLap: 'Schnitt',
    cars: 'Fahrer',
    overtakeMsg: (a, b, s) => <React.Fragment>Überholmanöver · <b>{a}</b> überholt <b>{b}</b> <span>in Sektor {s}</span></React.Fragment>,
    fastestLapMsg: (a, t) => <React.Fragment>Schnellste Runde · <b>{a}</b> <span>· {t}</span></React.Fragment>,
    pitInMsg:     (a) => <React.Fragment>Box-Eingang · <b>{a}</b> <span>fährt zum Boxenstopp</span></React.Fragment>,
    pitOutMsg:    (a, t) => <React.Fragment>Box-Ausgang · <b>{a}</b> <span>· Stop {t}</span></React.Fragment>,
    lapMsg:       (a, l) => <React.Fragment>Rundensieg · <b>{a}</b> <span>schließt Runde {l}</span></React.Fragment>,
    safetyMsg:    () => <React.Fragment><b>Pace Car</b> <span>auf der Strecke</span></React.Fragment>,
    fuelMsg:      (a) => <React.Fragment>Tankwarnung · <b>{a}</b> <span>unter 12 %</span></React.Fragment>,
    startMsg:     () => <React.Fragment><b>Grünes Licht</b> <span>· Rennen freigegeben</span></React.Fragment>,
  },
  en: {
    sessionLabel: 'Session',
    trackLabel: 'Track',
    raceLabel: 'Race',
    raceState: { IDLE: 'READY', FORMATION: 'FORMATION', RUNNING: 'RACE LIVE', PAUSED: 'PAUSED', FINISHED: 'FINISHED' },
    lap: 'Lap',
    laps: 'Laps',
    of: 'of',
    pos: 'Pos',
    driver: 'Driver / Car',
    lastLap: 'Last Lap',
    bestLap: 'Best Lap',
    sectors: 'Sectors',
    gap: 'Gap',
    int: 'Interval',
    fuel: 'Fuel',
    status: 'Status',
    statusRun: 'On Track',
    statusPit: 'In Pit',
    statusOut: 'Out Lap',
    statusGhost: 'Ghost',
    statusPace: 'Pace',
    statusFin: 'Finished',
    events: 'Race Events',
    eventsLive: 'live',
    bt: 'AppConnect · Control Unit',
    btConn: 'Connected',
    signal: 'Signal',
    latency: 'Latency',
    rx: 'RX',
    tx: 'TX',
    cuFw: 'CU Firmware',
    heartbeat: 'Heartbeat',
    track: 'Track Map',
    trackLen: 'Length',
    sector: 'Sector',
    start: 'Start',
    pause: 'Pause',
    resume: 'Resume',
    stop: 'Abort',
    safetyCar: 'Pace Car',
    progress: 'Progress',
    elapsed: 'Elapsed',
    remaining: 'Remaining',
    fuelPanel: 'Fuel & Pit',
    pitCount: 'Stops',
    lastStop: 'Last',
    leader: 'Leader',
    fastest: 'Fastest',
    avgLap: 'Avg Lap',
    cars: 'Cars',
    overtakeMsg: (a, b, s) => <React.Fragment>Overtake · <b>{a}</b> passes <b>{b}</b> <span>in sector {s}</span></React.Fragment>,
    fastestLapMsg: (a, t) => <React.Fragment>Fastest lap · <b>{a}</b> <span>· {t}</span></React.Fragment>,
    pitInMsg:     (a) => <React.Fragment>Pit entry · <b>{a}</b> <span>entering box</span></React.Fragment>,
    pitOutMsg:    (a, t) => <React.Fragment>Pit exit · <b>{a}</b> <span>· stop {t}</span></React.Fragment>,
    lapMsg:       (a, l) => <React.Fragment>Lap complete · <b>{a}</b> <span>finishes lap {l}</span></React.Fragment>,
    safetyMsg:    () => <React.Fragment><b>Pace car</b> <span>deployed</span></React.Fragment>,
    fuelMsg:      (a) => <React.Fragment>Fuel warning · <b>{a}</b> <span>below 12 %</span></React.Fragment>,
    startMsg:     () => <React.Fragment><b>Green light</b> <span>· race underway</span></React.Fragment>,
  },
};

// ── Helpers ────────────────────────────────────────────────────────────────
function formatLapTime(secs) {
  if (secs == null || !isFinite(secs)) return '—';
  const m = Math.floor(secs / 60);
  const s = secs - m * 60;
  return m > 0
    ? `${m}:${s.toFixed(3).padStart(6, '0')}`
    : `${s.toFixed(3)}`;
}
function formatGap(secs) {
  if (secs == null) return '—';
  if (secs < 0.001) return '—';
  return `+${secs.toFixed(3)}`;
}
function formatGapLaps(laps) {
  return `+${laps} L`;
}
function formatClock(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
    : `${m}:${String(ss).padStart(2, '0')}`;
}

// ── Race Simulator ─────────────────────────────────────────────────────────
function makeSim(driverCount) {
  const drivers = ROSTER.slice(0, driverCount).map((d, i) => ({
    ...d,
    idx: i,
    basePace:  11.20 + i * 0.15 + (d.isGhost ? 0.40 : 0) + (d.isPace ? 0.60 : 0),
    paceNoise: 0.08,
  }));
  const sectorShare = [0.32, 0.33, 0.35];
  return { drivers, sectorShare, totalLaps: 30, trackLength: 24.6 };
}

function rng(seed) {
  let s = seed | 0;
  return () => {
    s = (s * 1664525 + 1013904223) | 0;
    return ((s >>> 0) % 100000) / 100000;
  };
}

function precomputeRace(sim) {
  const { drivers, sectorShare, totalLaps } = sim;
  return drivers.map((d, di) => {
    const r = rng(1000 + di * 31);
    const laps = [];
    let cum = 0;
    for (let L = 1; L <= totalLaps; L++) {
      let lap = d.basePace + (r() - 0.5) * d.paceNoise * 2;
      lap += L > 20 ? (L - 20) * 0.018 : -L * 0.004;
      if (di === 0 && L === 14) lap -= 0.18;
      if (di === 0 && L === 8)  lap -= 0.10;
      if (di === 1 && L === 9)  lap += 0.42;
      if (di === 2 && L === 23) lap += 0.55;
      if (di === 3 && L === 17) lap += 6.5;
      if (di === 4 && L === 19) lap += 6.2;
      if (di === 5 && L === 22) lap += 6.8;
      if (d.isGhost) lap += 0.05 * Math.sin(L * 0.4);

      const s1 = lap * sectorShare[0] + (r() - 0.5) * 0.04;
      const s2 = lap * sectorShare[1] + (r() - 0.5) * 0.04;
      const s3 = lap - s1 - s2;
      cum += lap;
      laps.push({ s1, s2, s3, lap, cum, pit: (di === 3 && L === 17) || (di === 4 && L === 19) || (di === 5 && L === 22) });
    }
    return { driver: d, laps };
  });
}

function sampleRace(precomp, t, sim) {
  const { totalLaps } = sim;
  const items = precomp.map((row) => {
    const { driver, laps } = row;
    let lapIdx = 0;
    let inLapStart = 0;
    while (lapIdx < laps.length && laps[lapIdx].cum <= t) {
      inLapStart = laps[lapIdx].cum;
      lapIdx++;
    }
    const onLap = Math.min(lapIdx + 1, totalLaps);
    const lapsCompleted = lapIdx;
    const cur = laps[Math.min(lapIdx, laps.length - 1)];
    const lapElapsed = Math.max(0, t - inLapStart);
    let curSec = 1; let secElapsed = lapElapsed;
    if (lapElapsed >= cur.s1) { curSec = 2; secElapsed = lapElapsed - cur.s1; }
    if (lapElapsed >= cur.s1 + cur.s2) { curSec = 3; secElapsed = lapElapsed - cur.s1 - cur.s2; }

    const lastFinished = lapIdx > 0 ? laps[lapIdx - 1] : null;
    const personalBest = laps.slice(0, lapIdx).reduce((min, l) => (min == null || l.lap < min ? l.lap : min), null);
    const lapProgress = Math.min(1, lapElapsed / cur.lap);

    return {
      driver,
      lapsCompleted,
      onLap,
      cur,
      lapElapsed,
      curSec,
      lastLap: lastFinished?.lap ?? null,
      personalBest,
      cumAtEndOfLastLap: lastFinished ? lapIdx ? row.laps[lapIdx - 1].cum : 0 : 0,
      raceTime: lapIdx > 0 ? row.laps[lapIdx - 1].cum : 0,
      lapProgress,
      isPit: cur.pit && curSec === 1 && lapElapsed < 6.5,
    };
  });

  const sorted = [...items].map((it, i) => ({ ...it, _idx: i })).sort((a, b) => {
    if (a.lapsCompleted !== b.lapsCompleted) return b.lapsCompleted - a.lapsCompleted;
    return b.lapProgress - a.lapProgress;
  });

  const leader = sorted[0];
  const leaderRaceTime = leader.raceTime + leader.lapProgress * leader.cur.lap;
  sorted.forEach((it, rank) => {
    it.position = rank + 1;
    if (rank === 0) {
      it.gapToLeader = 0;
      it.interval = 0;
      it.gapLapsDown = 0;
    } else {
      it.gapLapsDown = leader.lapsCompleted - it.lapsCompleted;
      const myRaceTime = it.raceTime + it.lapProgress * it.cur.lap;
      it.gapToLeader = Math.max(0, leaderRaceTime - myRaceTime);
      const ahead = sorted[rank - 1];
      const aheadRaceTime = ahead.raceTime + ahead.lapProgress * ahead.cur.lap;
      it.interval = Math.max(0, aheadRaceTime - myRaceTime);
    }
    let fuel = 100 - it.lapsCompleted * 3.6;
    if (it.driver.isPace || it.driver.isGhost) fuel = 100;
    if (it.driver.idx === 3 && it.lapsCompleted >= 17) fuel = 100 - (it.lapsCompleted - 17) * 3.6;
    if (it.driver.idx === 4 && it.lapsCompleted >= 19) fuel = 100 - (it.lapsCompleted - 19) * 3.6;
    if (it.driver.idx === 5 && it.lapsCompleted >= 22) fuel = 100 - (it.lapsCompleted - 22) * 3.6;
    it.fuel = Math.max(0, fuel);
    it.pitCount = (it.driver.idx === 3 && it.lapsCompleted >= 17 ? 1 : 0)
                + (it.driver.idx === 4 && it.lapsCompleted >= 19 ? 1 : 0)
                + (it.driver.idx === 5 && it.lapsCompleted >= 22 ? 1 : 0);
    it.lastStopLap = it.pitCount > 0
      ? (it.driver.idx === 3 ? 17 : it.driver.idx === 4 ? 19 : it.driver.idx === 5 ? 22 : null)
      : null;
  });

  let bestS1 = Infinity, bestS2 = Infinity, bestS3 = Infinity, bestLap = Infinity;
  let bestS1Drv, bestS2Drv, bestS3Drv, bestLapDrv;
  sorted.forEach(it => {
    const drvLaps = precomp.find(p => p.driver.id === it.driver.id).laps.slice(0, it.lapsCompleted);
    drvLaps.forEach((l) => {
      if (l.s1 < bestS1) { bestS1 = l.s1; bestS1Drv = it.driver.id; }
      if (l.s2 < bestS2) { bestS2 = l.s2; bestS2Drv = it.driver.id; }
      if (l.s3 < bestS3) { bestS3 = l.s3; bestS3Drv = it.driver.id; }
      if (l.lap < bestLap) { bestLap = l.lap; bestLapDrv = it.driver.id; }
    });
  });

  return {
    items: sorted,
    bestS1, bestS2, bestS3, bestLap,
    bestS1Drv, bestS2Drv, bestS3Drv, bestLapDrv,
    leaderLap: leader.lapsCompleted + 1,
    leaderLapsRemaining: totalLaps - leader.lapsCompleted,
  };
}

function buildEvents(precomp, t, sim, strings) {
  const events = [];
  const sStart = strings;
  events.push({ id: 'start', kind: 'START', tAbs: 0, lap: 1, msg: sStart.startMsg() });

  let fastestSoFar = Infinity;
  for (let L = 1; L <= sim.totalLaps; L++) {
    precomp.forEach((p) => {
      const lap = p.laps[L - 1];
      const endT = lap.cum;
      if (endT > t) return;
      if (lap.lap < fastestSoFar - 0.001 && !p.driver.isGhost && !p.driver.isPace) {
        fastestSoFar = lap.lap;
        events.push({
          id: `fl-${p.driver.id}-${L}`,
          kind: 'FL', tAbs: endT, lap: L,
          msg: sStart.fastestLapMsg(p.driver.last, formatLapTime(lap.lap)),
        });
      }
      if (lap.pit) {
        events.push({ id: `pit-${p.driver.id}-${L}`, kind: 'PIT', tAbs: endT - lap.lap + 0.5, lap: L, msg: sStart.pitInMsg(p.driver.last) });
        events.push({ id: `out-${p.driver.id}-${L}`, kind: 'OUT', tAbs: endT - lap.lap + 6, lap: L, msg: sStart.pitOutMsg(p.driver.last, '6.20s') });
      }
    });
  }

  const overtakes = [
    { lap: 4,  a: 'WEISS',   b: 'KÖHLER',  s: 2 },
    { lap: 7,  a: 'KÖHLER',  b: 'WEISS',   s: 1 },
    { lap: 11, a: 'RICHTER', b: 'BAUER',   s: 3 },
    { lap: 16, a: 'NOWAK',   b: 'BERGER',  s: 2 },
    { lap: 18, a: 'BAUER',   b: 'RICHTER', s: 1 },
    { lap: 25, a: 'WEISS',   b: 'KÖHLER',  s: 2 },
  ];
  overtakes.forEach(o => {
    const leaderLapTime = precomp[0].laps[o.lap - 1].cum;
    if (leaderLapTime <= t) {
      events.push({
        id: `ot-${o.lap}-${o.a}`, kind: 'OT', tAbs: leaderLapTime - 1,
        lap: o.lap, msg: sStart.overtakeMsg(o.a, o.b, o.s),
      });
    }
  });

  precomp.forEach(p => {
    const warnLap = 18;
    if (p.driver.idx === 0 && precomp[0].laps[warnLap - 1].cum <= t) {
      events.push({ id: `fuel-${p.driver.id}-${warnLap}`, kind: 'FUEL', tAbs: precomp[0].laps[warnLap - 1].cum - 0.2, lap: warnLap, msg: sStart.fuelMsg('KÖHLER') });
    }
  });

  events.sort((a, b) => b.tAbs - a.tAbs);
  return events;
}

Object.assign(window, {
  ROSTER, STRINGS,
  makeSim, precomputeRace, sampleRace, buildEvents,
  formatLapTime, formatGap, formatGapLaps, formatClock,
});
