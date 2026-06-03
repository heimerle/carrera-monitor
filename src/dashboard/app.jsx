/* RacePulse 132 — App composition + race simulation hook. */

const { useState, useEffect, useMemo, useRef } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#e8c84a",
  "density": "regular",
  "lang": "de",
  "driverCount": 8,
  "layout": "broadcast",
  "dataSource": "live",
  "showTrackMap": true,
  "showEvents": true,
  "showBT": true
}/*EDITMODE-END*/;

// Small badge (top-right of the canvas) showing whether the dashboard is
// rendering live Control-Unit telemetry, the simulator, or waiting for data.
function SourceBadge({ source, error }) {
  const label = source === 'live' ? 'LIVE' : source === 'sim' ? 'SIM' : 'LIVE · WARTEN';
  const title = source === 'waiting'
    ? (error ? `Keine Live-Daten: ${error}` : 'Warte auf erste Telemetrie von /api/state')
    : (source === 'live' ? 'Live-Telemetrie der Control Unit' : 'Simulierte Demo-Daten');
  return (
    <div className={`src-badge src-${source}`} title={title}>
      <span className="src-led"></span>{label}
    </div>
  );
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [lang, setLang] = useState(t.lang || 'de');
  useEffect(() => { setLang(t.lang); }, [t.lang]);
  const strings = STRINGS[lang];

  // IDLE → FORMATION → RUNNING ⇄ PAUSED → FINISHED
  const [raceState, setRaceState] = useState('RUNNING');
  const [raceClock, setRaceClock] = useState(178.4);
  const [wallClock, setWallClock] = useState('14:32:08');
  const lastTickRef = useRef(performance.now());

  const sim = useMemo(() => makeSim(t.driverCount), [t.driverCount]);
  const precomp = useMemo(() => precomputeRace(sim), [sim]);

  useEffect(() => {
    let raf;
    const loop = () => {
      const now = performance.now();
      const dt = (now - lastTickRef.current) / 1000;
      lastTickRef.current = now;
      if (raceState === 'RUNNING') {
        setRaceClock((c) => {
          const next = c + dt;
          const totalRace = precomp[0].laps[sim.totalLaps - 1].cum;
          if (next >= totalRace) { setRaceState('FINISHED'); return totalRace; }
          return next;
        });
      }
      const d = new Date();
      const h = String(d.getHours()).padStart(2, '0');
      const m = String(d.getMinutes()).padStart(2, '0');
      const s = String(d.getSeconds()).padStart(2, '0');
      setWallClock(`${h}:${m}:${s}`);
      raf = requestAnimationFrame(loop);
    };
    lastTickRef.current = performance.now();
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [raceState, precomp, sim.totalLaps]);

  useEffect(() => {
    const r = document.documentElement;
    r.style.setProperty('--accent', t.accent);
  }, [t.accent]);

  const simSnap = useMemo(() => sampleRace(precomp, raceClock, sim), [precomp, raceClock, sim]);
  const simEvents = useMemo(() => buildEvents(precomp, raceClock, sim, strings), [precomp, raceClock, sim, strings]);

  // ── Live telemetry (polls /api/state) ─────────────────────────────────
  const wantLive = t.dataSource === 'live';
  const { live, error: liveError } = useLiveData(500, wantLive);
  const liveActive = wantLive && !!live;

  // Effective data feeding the widgets: real telemetry when available,
  // otherwise the simulator (also used as a populated placeholder while we
  // wait for the first live snapshot). The source badge makes the mode clear.
  const snap = liveActive ? live.snap : simSnap;
  const events = liveActive ? live.events : simEvents;
  const displayState = liveActive ? live.raceState : raceState;
  const leaderLap = liveActive ? live.leaderLap : Math.min(simSnap.leaderLap, sim.totalLaps);
  const totalLaps = liveActive ? live.totalLaps : sim.totalLaps;
  const source = !wantLive ? 'sim' : (liveActive ? 'live' : 'waiting');

  const onAction = (a) => {
    // Controls drive the simulator only; in live mode race state comes from
    // the Control Unit, so these are no-ops there (overwritten next poll).
    if (a === 'start')  { setRaceClock(0); setRaceState('RUNNING'); }
    if (a === 'pause')  setRaceState('PAUSED');
    if (a === 'resume') setRaceState('RUNNING');
    if (a === 'stop')   { setRaceState('FINISHED'); }
    if (a === 'safety') { /* visual only */ }
  };

  useStageScale();

  return (
    <div className="stage">
      <div className="canvas" data-density={t.density}>
        <SourceBadge source={source} error={liveError} />
        <div className="grid">
          <TopBar
            raceState={displayState}
            raceSnapshot={snap}
            leaderLap={leaderLap}
            totalLaps={totalLaps}
            clock={{ wall: wallClock, elapsedMs: raceClock * 1000 }}
            lang={lang}
            t={strings}
          />

          <div className="main">
            <div className="col-l">
              <PositionTable snap={snap} t={strings} density={t.density} />
              <FuelStrip snap={snap} t={strings} />
            </div>
            <div className="col-r">
              {t.showEvents    && <EventsFeed events={events} t={strings} />}
              {t.showTrackMap  && <TrackMap snap={snap} t={strings} />}
              {t.showBT        && <BluetoothPanel raceTime={raceClock} t={strings} live={liveActive ? live.connection : undefined} />}
            </div>
          </div>

          <ControlStrip
            raceState={displayState}
            onAction={onAction}
            leaderLap={leaderLap}
            totalLaps={totalLaps}
            t={strings}
            lang={lang}
            setLang={(l) => { setLang(l); setTweak('lang', l); }}
          />
        </div>
      </div>

      <TweaksPanel title="RacePulse · Tweaks">
        <TweakSection label="Race">
          <TweakRadio
            label="State"
            value={raceState}
            options={[
              { value: 'IDLE',      label: 'Idle' },
              { value: 'FORMATION', label: 'Form' },
              { value: 'RUNNING',   label: 'Live' },
              { value: 'PAUSED',    label: 'Pause' },
              { value: 'FINISHED',  label: 'End' },
            ]}
            onChange={(v) => { setRaceState(v); if (v === 'IDLE') setRaceClock(0); }}
          />
          <TweakSlider
            label="Race time"
            value={Math.round(raceClock)}
            min={0}
            max={Math.round(precomp[0].laps[sim.totalLaps - 1].cum)}
            unit="s"
            onChange={(v) => setRaceClock(v)}
          />
          <TweakSlider
            label="Drivers"
            value={t.driverCount}
            min={2}
            max={8}
            onChange={(v) => setTweak('driverCount', v)}
          />
        </TweakSection>

        <TweakSection label="Data">
          <TweakRadio
            label="Source"
            value={t.dataSource}
            options={[
              { value: 'live', label: 'Live' },
              { value: 'sim',  label: 'Sim' },
            ]}
            onChange={(v) => setTweak('dataSource', v)}
          />
        </TweakSection>

        <TweakSection label="Layout">
          <TweakRadio
            label="Density"
            value={t.density}
            options={[
              { value: 'compact',   label: 'Compact' },
              { value: 'regular',   label: 'Regular' },
              { value: 'broadcast', label: 'Broadcast' },
            ]}
            onChange={(v) => setTweak('density', v)}
          />
          <TweakRadio
            label="Language"
            value={lang}
            options={[
              { value: 'de', label: 'DE' },
              { value: 'en', label: 'EN' },
            ]}
            onChange={(v) => { setLang(v); setTweak('lang', v); }}
          />
        </TweakSection>

        <TweakSection label="Accent">
          <TweakColor
            label="Accent color"
            value={t.accent}
            options={['#e8c84a', '#ff5a3d', '#41d68a', '#5ab7ff', '#c878ff']}
            onChange={(v) => setTweak('accent', v)}
          />
        </TweakSection>

        <TweakSection label="Side rail">
          <TweakToggle label="Events feed"    value={t.showEvents}    onChange={(v) => setTweak('showEvents', v)} />
          <TweakToggle label="Track map"      value={t.showTrackMap}  onChange={(v) => setTweak('showTrackMap', v)} />
          <TweakToggle label="Bluetooth / CU" value={t.showBT}        onChange={(v) => setTweak('showBT', v)} />
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
