/* RacePulse 132 — Live telemetry adapter.
   Polls /api/state (the StateManager snapshot) and maps it into the same
   `snap` / `events` shapes the simulator produces, so the existing widgets
   render real Carrera Control Unit data unchanged.

   Real telemetry is LAP-level, not sector-level: the Control Unit reports lap
   times, fuel, pit and connection state — but no sector splits, no continuous
   race-time, no driver metadata. So sector columns, precise gaps and intervals
   render as "—" in live mode; everything the hardware actually provides is
   shown faithfully. Exposed as window globals for app.jsx. */

const LIVE_TOTAL_LAPS = 30; // race length is not in state.json; display target.

// Map a StateManager RaceState string → the dashboard's race-state enum.
const RACE_STATE_MAP = {
  idle: 'IDLE',
  countdown: 'FORMATION',
  running: 'RUNNING',
  paused: 'PAUSED',
  finished: 'FINISHED',
};

// Connection states the StateManager considers "link healthy".
const CONN_OK = new Set(['connected', 'subscribing', 'ready']);
const CONN_WARN = new Set(['stale', 'degraded', 'reconnecting', 'scanning', 'connecting']);

function msToSecs(ms) {
  return ms == null || !isFinite(ms) ? null : ms / 1000;
}

// rssi (dBm, negative) → 1..4 signal bars. Unknown → 0 (no bars).
function rssiToBars(rssi) {
  if (rssi == null || !isFinite(rssi)) return 0;
  if (rssi >= -55) return 4;
  if (rssi >= -67) return 3;
  if (rssi >= -78) return 2;
  return 1;
}

// Build a per-car display row from a state.json car record, borrowing colors,
// flags and car/team labels from the static ROSTER (indexed by car_id) so the
// live view keeps the broadcast look. driver_name from telemetry wins if set.
function mapCar(car, idx) {
  const roster = ROSTER[(car.car_id - 1) % ROSTER.length] || ROSTER[idx % ROSTER.length];
  const name = car.driver_name || roster.last;
  return {
    ...roster,
    id: car.car_id,
    no: car.car_id,
    idx,
    last: name,
    first: car.driver_name ? '' : roster.first,
  };
}

// Translate the whole snapshot into { snap, events, raceState, leaderLap,
// totalLaps, connection }. Returns null when the snapshot has no cars yet
// (so app.jsx can fall back to the simulator / a "waiting" state).
function mapSnapshot(state) {
  if (!state || typeof state !== 'object') return null;
  const rawCars = (state.race_metrics && state.race_metrics.cars) || state.cars || [];
  if (!Array.isArray(rawCars) || rawCars.length === 0) return null;

  // Order by reported position when present, else by lap count desc.
  const ordered = [...rawCars].sort((a, b) => {
    const pa = a.position ?? 999, pb = b.position ?? 999;
    if (pa !== pb) return pa - pb;
    return (b.lap_count || 0) - (a.lap_count || 0);
  });

  const takenMono = state.taken_at_monotonic_ms ?? 0;
  const leaderLapCount = ordered.reduce((m, c) => Math.max(m, c.lap_count || 0), 0);

  let bestLap = Infinity;
  const items = ordered.map((car, i) => {
    const driver = mapCar(car, i);
    const lastLap = msToSecs(car.latest_lap_ms);
    const personalBest = msToSecs(car.best_lap_ms);
    if (personalBest != null && personalBest < bestLap) bestLap = personalBest;
    const lapsCompleted = car.lap_count || 0;
    const fuel = car.fuel_percent != null ? Math.max(0, Math.min(100, car.fuel_percent)) : null;
    const gapLapsDown = Math.max(0, leaderLapCount - lapsCompleted);

    // Rough track position: how far into the current lap we likely are, based
    // on time since this car's last event vs its average lap. Best-effort only.
    const avgMs = car.average_lap_ms;
    let lapProgress = 0;
    if (avgMs && car.last_event_at_ms != null && takenMono) {
      lapProgress = Math.max(0, Math.min(1, (takenMono - car.last_event_at_ms) / avgMs));
    }

    return {
      driver,
      lapsCompleted,
      onLap: lapsCompleted + 1,
      // No sector data from hardware — nulls render as "—" / dim bars.
      cur: { s1: null, s2: null, s3: null, lap: lastLap },
      lapElapsed: 0,
      curSec: 1,
      lastLap,
      personalBest,
      raceTime: 0,
      lapProgress,
      isPit: !!(car.in_pit || car.pit_active),
      position: car.position ?? i + 1,
      gapToLeader: null,
      interval: null,
      gapLapsDown,
      fuel: fuel == null ? 100 : fuel,
      pitCount: 0,
      lastStopLap: null,
    };
  });

  const raceState = RACE_STATE_MAP[state.race] || 'IDLE';
  const conn = state.connection || {};
  const connState = conn.state || 'disconnected';
  const connection = {
    state: connState,
    ok: CONN_OK.has(connState),
    warn: CONN_WARN.has(connState),
    rssi: typeof conn.rssi === 'number' ? conn.rssi : null,
    bars: rssiToBars(conn.rssi),
    deviceName: conn.device_name || null,
    mac: conn.mac_address || null,
    reconnects: conn.reconnect_attempts || 0,
  };

  return {
    snap: {
      items,
      bestLap,
      bestS1: Infinity, bestS2: Infinity, bestS3: Infinity,
      bestLapDrv: null, bestS1Drv: null, bestS2Drv: null, bestS3Drv: null,
      leaderLap: Math.min(leaderLapCount + 1, LIVE_TOTAL_LAPS),
      leaderLapsRemaining: Math.max(0, LIVE_TOTAL_LAPS - leaderLapCount),
    },
    events: mapEvents(state.recent_events || []),
    raceState,
    leaderLap: Math.min(leaderLapCount + 1, LIVE_TOTAL_LAPS),
    totalLaps: LIVE_TOTAL_LAPS,
    connection,
    takenAtIso: state.taken_at_iso || null,
  };
}

// Recent telemetry events → the dashboard's event-feed entries.
function mapEvents(recent) {
  const out = [];
  recent.forEach((ev, i) => {
    const carLabel = ev.car_id != null ? `#${ev.car_id}` : '';
    const lap = (ev.payload && ev.payload.lap_number) || 0;
    let kind = null, msg = null;
    if (ev.event_type === 'lap') {
      kind = 'LAP';
      const txt = formatLapTime(msToSecs(ev.payload && ev.payload.lap_time_ms));
      msg = <React.Fragment>Runde · <b>{carLabel}</b> <span>· {txt}</span></React.Fragment>;
    } else if (ev.event_type === 'fuel') {
      kind = 'FUEL';
      const lvl = ev.payload && ev.payload.level_percent;
      msg = <React.Fragment>Tank · <b>{carLabel}</b> <span>· {lvl != null ? `${Math.round(lvl)} %` : '—'}</span></React.Fragment>;
    } else if (ev.event_type === 'pitlane') {
      const inPit = ev.payload && ev.payload.in_pit;
      kind = inPit ? 'PIT' : 'OUT';
      msg = <React.Fragment>{inPit ? 'Box-Eingang' : 'Box-Ausgang'} · <b>{carLabel}</b></React.Fragment>;
    } else if (ev.event_type === 'race_state') {
      kind = 'START';
      const s = ev.payload && ev.payload.state;
      msg = <React.Fragment><b>Rennstatus</b> <span>· {String(s || '').toUpperCase()}</span></React.Fragment>;
    } else if (ev.event_type === 'connection_state') {
      kind = 'SAFE';
      const s = ev.payload && ev.payload.state;
      msg = <React.Fragment><b>Verbindung</b> <span>· {String(s || '').toUpperCase()}</span></React.Fragment>;
    } else {
      return; // skip raw/speed/controller noise in the feed
    }
    out.push({
      id: `live-${i}-${ev.timestamp_monotonic_ms ?? i}`,
      kind,
      lap,
      tAbs: 0,
      iso: ev.timestamp_iso || null,
      msg,
    });
  });
  return out;
}

// ── React hook: poll /api/state ──────────────────────────────────────────────
// Returns { live, error, lastOkIso }. `live` is the mapped snapshot or null
// when telemetry is absent/unreachable. Polls every `pollMs` (default 500)
// while `enabled`; when disabled it stops fetching and clears live state.
function useLiveData(pollMs, enabled) {
  const interval = pollMs || 500;
  const on = enabled !== false;
  const [state, setState] = React.useState({ live: null, error: null, lastOkIso: null });
  React.useEffect(() => {
    if (!on) { setState({ live: null, error: null, lastOkIso: null }); return undefined; }
    let cancelled = false;
    let timer = null;
    const tick = async () => {
      try {
        const res = await fetch('/api/state', { cache: 'no-store' });
        const json = await res.json();
        if (cancelled) return;
        const live = mapSnapshot(json);
        setState({ live, error: null, lastOkIso: live ? live.takenAtIso : null });
      } catch (e) {
        if (cancelled) return;
        setState((prev) => ({ ...prev, live: null, error: String(e && e.message || e) }));
      } finally {
        if (!cancelled) timer = setTimeout(tick, interval);
      }
    };
    tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [interval, on]);
  return state;
}

Object.assign(window, { mapSnapshot, mapEvents, useLiveData });
