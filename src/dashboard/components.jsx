/* RacePulse 132 — Widget components. */

const { useMemo, useEffect, useState, useRef } = React;

// ── Brand logo ─────────────────────────────────────────────────────────────
function BrandMark() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <defs>
        <linearGradient id="bm-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--accent)" />
          <stop offset="100%" stopColor="oklch(0.65 0.18 60)" />
        </linearGradient>
      </defs>
      <rect x="3" y="3" width="42" height="42" rx="3" fill="none" stroke="var(--line-2)" strokeWidth="1.5" />
      <path d="M10 30 L18 12 L26 30 L34 12 L42 30" fill="none" stroke="url(#bm-g)" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx="14" cy="36" r="1.6" fill="var(--accent)" />
      <circle cx="22" cy="36" r="1.6" fill="var(--accent)" />
      <circle cx="30" cy="36" r="1.6" fill="var(--accent)" />
      <circle cx="38" cy="36" r="1.6" fill="var(--accent)" />
    </svg>
  );
}

// ── Top Bar ────────────────────────────────────────────────────────────────
function TopBar({ raceState, raceSnapshot, leaderLap, totalLaps, clock, lang, t }) {
  return (
    <div className="topbar">
      <div className="tb-brand">
        <div className="tb-logo"><BrandMark /></div>
        <div className="tb-name">
          <b>RACE<i>PULSE</i> 132</b>
          <span>Race Control · v0.9</span>
        </div>
      </div>

      <div className="tb-session">
        <div className="kv">
          <div className="kv-k">{t.sessionLabel}</div>
          <div className="kv-v">SPRINT · 30 {t.laps.toUpperCase()}</div>
        </div>
        <div className="kv">
          <div className="kv-k">{t.trackLabel}</div>
          <div className="kv-v">Heimkeller GP · B</div>
        </div>
        <div className="kv">
          <div className="kv-k">{t.trackLen}</div>
          <div className="kv-v mono">24.62 m</div>
        </div>
      </div>

      <div className="tb-state">
        <div className="state-pill" data-state={raceState}>
          <span className="led"></span>
          <span className="lbl">{t.raceState[raceState]}</span>
        </div>
      </div>

      <div className="tb-clock">
        <div className="kv">
          <div className="kv-k">{t.elapsed}</div>
          <div className="kv-v mono" style={{ fontSize: 15 }}>{formatClock(clock.elapsedMs)}</div>
        </div>
        <div className="clock">
          <div className="clock-time">{clock.wall}</div>
          <div className="clock-date">22 MAY 2026</div>
        </div>
      </div>

      <div className="tb-lap">
        <div className="tb-lap-row">
          <span className="lap-cur">{String(leaderLap).padStart(2, '0')}</span>
          <span className="lap-sep">/</span>
          <span>{totalLaps}</span>
          <span style={{ fontSize: 13, marginLeft: 'auto', color: 'var(--text-3)', letterSpacing: '.18em' }}>
            {t.lap.toUpperCase()}
          </span>
        </div>
        <div className="tb-lap-meta">
          <span>{t.remaining}</span>
          <span>{totalLaps - leaderLap + 1} {t.laps.toLowerCase()}</span>
        </div>
      </div>
    </div>
  );
}

// ── Position Table ─────────────────────────────────────────────────────────
function classifyTime(time, best, personalBest) {
  if (time == null) return 'slower';
  if (best != null && Math.abs(time - best) < 0.001) return 'best-overall';
  if (personalBest != null && Math.abs(time - personalBest) < 0.001) return 'best-personal';
  return 'slower';
}

function PositionTable({ snap, t, density }) {
  const { items, bestLap, bestS1, bestS2, bestS3, bestLapDrv } = snap;
  return (
    <div className="panel" style={{ overflow: 'hidden' }}>
      <div className="panel-hd">
        <h2>{t.pos.toUpperCase()} · LIVE TIMING</h2>
        <div className="hd-meta">
          <span className="tag" data-tone="ok"><span className="led-mini"></span> {t.fastest} {bestLap < Infinity ? formatLapTime(bestLap) : '—'}</span>
          <span className="tag">{items.length} {t.cars}</span>
        </div>
      </div>
      <div className="panel-body" style={{ overflow: 'auto' }}>
        <table className="ptable">
          <colgroup>
            <col style={{ width: 56 }} />
            <col style={{ width: 56 }} />
            <col />
            <col style={{ width: 140 }} />
            <col style={{ width: 130 }} />
            <col style={{ width: 200 }} />
            <col style={{ width: 110 }} />
            <col style={{ width: 110 }} />
          </colgroup>
          <thead>
            <tr>
              <th>{t.pos}</th>
              <th>±</th>
              <th>{t.driver}</th>
              <th className="r">{t.lastLap}</th>
              <th className="r">{t.bestLap}</th>
              <th className="r">{t.sectors}</th>
              <th className="r">{t.gap}</th>
              <th className="c">{t.status}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => {
              const d = it.driver;
              const isLeader = it.position === 1 && !d.isPace && !d.isGhost;
              const lastClass = classifyTime(it.lastLap, bestLap, it.personalBest);
              const bestClass = it.personalBest != null && Math.abs(it.personalBest - bestLap) < 0.001 ? 'best-overall' : (it.personalBest != null ? 'best-personal' : 'slower');
              return (
                <tr key={d.id}
                    className={[
                      isLeader && 'is-leader',
                      it.isPit && 'is-pit',
                      d.isGhost && 'is-ghost',
                    ].filter(Boolean).join(' ')}>
                  <td className="pos">
                    {String(it.position).padStart(2, '0')}
                  </td>
                  <td>
                    <span className="t-delta" data-d={d.idx % 3 === 0 ? 'up' : (d.idx % 3 === 1 ? 'down' : '')}>
                      {d.idx % 3 === 0 ? '▲1' : d.idx % 3 === 1 ? '▼1' : '—'}
                    </span>
                  </td>
                  <td>
                    <div className="driver-cell">
                      <div className="car-no" style={{
                        '--car-color': d.color, '--car-ink': d.ink,
                      }}>{d.no}</div>
                      <div className="driver-info">
                        <div className="driver-name">
                          <span className="first">{d.first ? d.first[0] + '.' : ''}</span>{d.last}
                        </div>
                        <div className="driver-meta">
                          <span className="flag" style={{
                            '--f1': d.flag[0], '--f2': d.flag[1], '--f3': d.flag[2],
                          }}></span>
                          <span>{d.country}</span>
                          <span style={{ color: 'var(--text-4)' }}>·</span>
                          <span>{d.car}</span>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="r">
                    <span className="t-time" data-t={lastClass}>{formatLapTime(it.lastLap)}</span>
                    <span className="t-delta" data-d={it.lastLap && it.personalBest && it.lastLap > it.personalBest ? 'down' : (it.lastLap && it.personalBest && Math.abs(it.lastLap - it.personalBest) < 0.001 ? 'up' : '')}>
                      {it.lastLap && it.personalBest
                        ? (Math.abs(it.lastLap - it.personalBest) < 0.001
                          ? '— PB'
                          : `${it.lastLap > it.personalBest ? '+' : ''}${(it.lastLap - it.personalBest).toFixed(3)}`)
                        : '—'}
                    </span>
                  </td>
                  <td className="r">
                    <span className="t-time" data-t={bestClass}>{formatLapTime(it.personalBest)}</span>
                    <span className="t-delta">
                      L{it.lapsCompleted > 0 ? Math.max(1, it.lapsCompleted) : '—'}
                    </span>
                  </td>
                  <td>
                    <div className="sectors">
                      {[1,2,3].map((s) => {
                        const time = it.lapsCompleted > 0 ? (s===1?it.cur.s1:s===2?it.cur.s2:it.cur.s3) : null;
                        const sessionBest = s===1?bestS1:s===2?bestS2:bestS3;
                        const isBestO = time != null && Math.abs(time - sessionBest) < 0.001;
                        const tone = it.curSec === s && !it.lapsCompleted ? 'improving' : (isBestO ? 'best-overall' : (time ? 'best-personal' : 'slower'));
                        return (
                          <div key={s} className="sector">
                            <div className="sector-bar" data-t={tone}></div>
                            <div className="sector-time" data-t={tone}>{time ? time.toFixed(3) : '—'}</div>
                          </div>
                        );
                      })}
                    </div>
                  </td>
                  <td className="r">
                    <div className="gap-cell">
                      {it.position === 1
                        ? <><span style={{ color: 'var(--accent)', fontWeight: 600 }}>LEADER</span><span className="gap-int">—</span></>
                        : it.gapLapsDown > 0
                          ? <><span>{formatGapLaps(it.gapLapsDown)}</span><span className="gap-int">{formatGap(it.interval)} {t.int}</span></>
                          : <><span>{formatGap(it.gapToLeader)}</span><span className="gap-int">{formatGap(it.interval)} {t.int}</span></>
                      }
                    </div>
                  </td>
                  <td className="c">
                    {d.isGhost ? <span className="status-tag" data-s="ghost"><span className="dot"></span>{t.statusGhost}</span>
                      : d.isPace ? <span className="status-tag" data-s="pace"><span className="dot"></span>{t.statusPace}</span>
                      : it.isPit ? <span className="status-tag" data-s="pit"><span className="dot"></span>{t.statusPit}</span>
                      : <span className="status-tag" data-s="run"><span className="dot"></span>{t.statusRun}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Fuel & Pit Strip ───────────────────────────────────────────────────────
function FuelStrip({ snap, t }) {
  const { items } = snap;
  return (
    <div className="panel">
      <div className="panel-hd">
        <h2>{t.fuelPanel}</h2>
        <div className="hd-meta">
          <span>Σ {items.reduce((sum, it) => sum + it.pitCount, 0)} {t.pitCount.toLowerCase()}</span>
        </div>
      </div>
      <div className="panel-body fuel-strip">
        {items.map((it) => {
          const d = it.driver;
          const fuel = it.fuel;
          const lvl = fuel < 12 ? 'critical' : fuel < 25 ? 'low' : 'ok';
          return (
            <div key={d.id} className={`fuel-card ${it.isPit ? 'is-pit' : ''}`}
                 style={{ '--car-color': d.color }}>
              <div className="fuel-card-top">
                <div className="fuel-card-pos">
                  <span className="pos-mark">P</span>{String(it.position).padStart(2, '0')}
                </div>
                <div className="fuel-card-no">#{d.no}</div>
              </div>
              <div className="fuel-card-name">{d.last}</div>
              <div className="fuel-tank">
                <div className="fuel-tank-fill" data-lvl={lvl} style={{ width: `${fuel}%` }}></div>
                <div className="fuel-tank-marks">
                  <span></span><span></span><span></span><span></span>
                </div>
              </div>
              <div className="fuel-card-foot">
                <span className="pct">{fuel.toFixed(0)}%</span>
                <span>{t.pitCount.toUpperCase()} <b>{it.pitCount}</b>{it.lastStopLap ? ` · L${it.lastStopLap}` : ''}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Events Feed ────────────────────────────────────────────────────────────
function EventsFeed({ events, t }) {
  const visible = events.slice(0, 12);
  return (
    <div className="panel">
      <div className="panel-hd">
        <h2>{t.events}</h2>
        <div className="hd-meta">
          <span className="tag" data-tone="ok"><span className="led-mini"></span>{t.eventsLive}</span>
        </div>
      </div>
      <div className="panel-body">
        <div className="events scroll-hide">
          {visible.map(e => (
            <div className="event" key={e.id} data-kind={e.kind}>
              <span className="event-lap">L{String(e.lap).padStart(2, '0')}</span>
              <span className="event-icon">{
                e.kind === 'OT' ? '↔'
                : e.kind === 'FL' ? '⚡'
                : e.kind === 'PIT' ? 'P'
                : e.kind === 'OUT' ? '→'
                : e.kind === 'LAP' ? '◇'
                : e.kind === 'SAFE' ? '⚠'
                : e.kind === 'FUEL' ? '⛽'
                : e.kind === 'START' ? '▶'
                : '•'
              }</span>
              <span className="event-msg">{e.msg}</span>
              <span className="event-time">{
                e.iso
                  ? new Date(e.iso).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                  : formatClock(Math.max(0, e.tAbs * 1000))
              }</span>
            </div>
          ))}
          {visible.length === 0 && (
            <div style={{ padding: '24px 14px', color: 'var(--text-3)', font: '500 12px/1 JetBrains Mono, monospace', letterSpacing: '.1em' }}>
              — NO EVENTS YET —
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Track Map ──────────────────────────────────────────────────────────────
function TrackMap({ snap, t }) {
  const pathRef = useRef(null);
  const [pathLen, setPathLen] = useState(0);
  useEffect(() => {
    if (pathRef.current) setPathLen(pathRef.current.getTotalLength());
  }, []);

  const d = "M 60 80 C 60 30, 200 30, 240 70 L 380 70 C 460 70, 470 150, 380 170 L 220 170 C 130 170, 120 220, 200 230 L 380 230 C 470 230, 470 320, 380 320 L 80 320 C 20 320, 20 230, 60 200 Z";

  return (
    <div className="panel" style={{ position: 'relative' }}>
      <div className="panel-hd">
        <h2>{t.track}</h2>
        <div className="hd-meta">
          <span>HEIMKELLER GP · B</span>
          <span>24.62 m</span>
        </div>
      </div>
      <div className="panel-body" style={{ position: 'relative', padding: '4px 12px 12px' }}>
        <svg className="track-svg" viewBox="0 0 500 360" preserveAspectRatio="xMidYMid meet">
          <path ref={pathRef} className="track-bg" d={d} />
          <path className="track-line" d={d} />
          {pathLen > 0 && (() => {
            const p = pathRef.current.getPointAtLength(0);
            const p2 = pathRef.current.getPointAtLength(8);
            const dx = p2.x - p.x, dy = p2.y - p.y;
            const len = Math.hypot(dx, dy) || 1;
            const nx = -dy / len * 14, ny = dx / len * 14;
            return <line className="start-mark" x1={p.x - nx} y1={p.y - ny} x2={p.x + nx} y2={p.y + ny} />;
          })()}
          {pathLen > 0 && snap.items.map((it) => {
            const pos = it.lapProgress * pathLen;
            const p = pathRef.current.getPointAtLength(Math.min(pos, pathLen - 0.01));
            return (
              <g key={it.driver.id} className="car-dot" transform={`translate(${p.x},${p.y})`}>
                <circle className="bg" r="11" fill={it.driver.color} />
                <text>{String(it.driver.no)}</text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

// ── BT / Control Unit Status ───────────────────────────────────────────────
// In sim mode (`live` undefined) the panel shows synthetic demo telemetry.
// In live mode it renders the real connection record from state.json: rssi,
// link state, device, and reconnect count. Values the Control Unit does not
// report (latency, RX/TX packet counts) render as "—".
function BluetoothPanel({ raceTime, t, live }) {
  if (live) {
    const tone = live.ok ? 'ok' : (live.warn ? 'warn' : 'warn');
    const connLabel = (live.deviceName || live.state || '').toString().toUpperCase();
    return (
      <div className="panel">
        <div className="panel-hd">
          <h2>{t.bt}</h2>
          <div className="hd-meta">
            <span className="tag" data-tone={live.ok ? 'ok' : 'warn'}>
              <span className="led-mini"></span>{(live.ok ? t.btConn : live.state).toString().toUpperCase()}
            </span>
          </div>
        </div>
        <div className="panel-body bt-grid">
          <div className="bt-cell">
            <div className="k">{t.signal}</div>
            <div className="v" data-state={tone}>
              {live.rssi != null ? `${live.rssi} dBm` : '—'}
              <span className={`signal-bars s-${live.bars}`}><i></i><i></i><i></i><i></i></span>
            </div>
          </div>
          <div className="bt-cell">
            <div className="k">{t.latency}</div>
            <div className="v">—</div>
          </div>
          <div className="bt-cell">
            <div className="k">{t.cuFw}</div>
            <div className="v mono">{live.mac || '—'}</div>
          </div>
          <div className="bt-cell">
            <div className="k">{t.heartbeat}</div>
            <div className="v" data-state={tone}>{live.state.toString().toUpperCase()}</div>
          </div>
          <div className="bt-cell bt-cell-wide">
            <div className="bt-packets">
              <div className="bt-packet">
                <div className="k">RECONNECTS</div>
                <div className="v mono">{live.reconnects}</div>
              </div>
              <div className="bt-packet">
                <div className="k">DEVICE</div>
                <div className="v mono">{connLabel || '—'}</div>
              </div>
            </div>
            <div className="bt-tags">
              <span className="tag" data-tone="info">APPCONNECT</span>
              <span className="tag">BLE · 2.4 GHz</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const rx = 8420 + Math.floor(raceTime * 47);
  const tx = 312 + Math.floor(raceTime * 1.8);
  const latency = 16 + Math.round(Math.sin(raceTime * 0.7) * 4);
  return (
    <div className="panel">
      <div className="panel-hd">
        <h2>{t.bt}</h2>
        <div className="hd-meta">
          <span className="tag" data-tone="ok"><span className="led-mini"></span>{t.btConn.toUpperCase()}</span>
        </div>
      </div>
      <div className="panel-body bt-grid">
        <div className="bt-cell">
          <div className="k">{t.signal}</div>
          <div className="v" data-state="ok">
            -42 dBm
            <span className="signal-bars s-4"><i></i><i></i><i></i><i></i></span>
          </div>
        </div>
        <div className="bt-cell">
          <div className="k">{t.latency}</div>
          <div className="v">{latency} ms</div>
        </div>
        <div className="bt-cell">
          <div className="k">{t.cuFw}</div>
          <div className="v mono">CU 5.41 · BT 1.07</div>
        </div>
        <div className="bt-cell">
          <div className="k">{t.heartbeat}</div>
          <div className="v" data-state="ok">{(latency / 1000 + 0.05).toFixed(3)} s</div>
        </div>
        <div className="bt-cell bt-cell-wide">
          <div className="bt-packets">
            <div className="bt-packet">
              <div className="k">{t.rx}</div>
              <div className="v mono">{rx.toLocaleString()}</div>
            </div>
            <div className="bt-packet">
              <div className="k">{t.tx}</div>
              <div className="v mono">{tx.toLocaleString()}</div>
            </div>
          </div>
          <div className="bt-tags">
            <span className="tag" data-tone="info">APPCONNECT</span>
            <span className="tag">BLE 4.2 · 2.4 GHz</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Control Strip (bottom bar) ─────────────────────────────────────────────
function ControlStrip({ raceState, onAction, leaderLap, totalLaps, t, lang, setLang }) {
  const pct = ((leaderLap - 1) / totalLaps) * 100;
  return (
    <div className="bottombar">
      <div className="progress-block">
        <div className="progress-row">
          <span>{t.progress.toUpperCase()} · {t.leader.toUpperCase()}</span>
          <span><b>{leaderLap - 1}</b> / {totalLaps} {t.laps.toLowerCase()} · <b>{pct.toFixed(1)}%</b></span>
        </div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${pct}%` }}></div>
        </div>
        <div className="progress-row">
          <span>L01</span>
          <span>L08</span>
          <span>L15</span>
          <span>L22</span>
          <span>L30 · CHEQUERED</span>
        </div>
      </div>

      <div className="controls">
        {(raceState === 'IDLE' || raceState === 'FINISHED') && (
          <button className="ctl-btn" data-variant="primary" onClick={() => onAction('start')}>
            <Triangle /> {t.start}
          </button>
        )}
        {raceState === 'RUNNING' && (
          <button className="ctl-btn" data-variant="warn" onClick={() => onAction('pause')}>
            <PauseIcon /> {t.pause}
          </button>
        )}
        {raceState === 'PAUSED' && (
          <button className="ctl-btn" data-variant="primary" onClick={() => onAction('resume')}>
            <Triangle /> {t.resume}
          </button>
        )}
        <button className="ctl-btn" data-variant="danger" onClick={() => onAction('stop')}
                disabled={raceState === 'IDLE'}>
          <SquareIcon /> {t.stop}
        </button>
        <div className="divider-v"></div>
        <button className="ctl-btn" onClick={() => onAction('safety')}>
          <DiamondIcon /> {t.safetyCar}
        </button>
      </div>

      <div className="lang-toggle">
        <button aria-pressed={lang === 'de'} onClick={() => setLang('de')}>DE</button>
        <button aria-pressed={lang === 'en'} onClick={() => setLang('en')}>EN</button>
      </div>
    </div>
  );
}

function Triangle()   { return <svg className="icon" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 1.5v9l8-4.5z" fill="currentColor"/></svg>; }
function PauseIcon()  { return <svg className="icon" viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="2" width="3" height="8" fill="currentColor"/><rect x="7" y="2" width="3" height="8" fill="currentColor"/></svg>; }
function SquareIcon() { return <svg className="icon" viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="2" width="8" height="8" fill="currentColor"/></svg>; }
function DiamondIcon(){ return <svg className="icon" viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1 L11 6 L6 11 L1 6 Z" fill="currentColor"/></svg>; }

// ── Stage scaler ───────────────────────────────────────────────────────────
function useStageScale() {
  useEffect(() => {
    const fit = () => {
      const canvas = document.querySelector('.canvas');
      if (!canvas) return;
      const sx = window.innerWidth / 1920;
      const sy = window.innerHeight / 1080;
      const s = Math.min(sx, sy);
      canvas.style.transform = `scale(${s})`;
    };
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
}

Object.assign(window, {
  TopBar, PositionTable, FuelStrip, EventsFeed, TrackMap,
  BluetoothPanel, ControlStrip, BrandMark, useStageScale,
});
