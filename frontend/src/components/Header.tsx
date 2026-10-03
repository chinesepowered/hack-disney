import { useEffect, useState, type ReactNode } from 'react'
import type { Modes, Stats, Sweep } from '../types'
import { api, OFFLINE, REPLAY_INFO } from '../store'
import { money, useAnimatedNumber } from '../util'
import { InspectorCapy } from './Capys'

function Kpi({ label, value, tone, format = money }: { label: ReactNode; value: number | null; tone?: string; format?: (n: number) => string }) {
  const animated = useAnimatedNumber(value ?? 0)
  return (
    <div className={`kpi ${tone ?? ''}`}>
      <label>{label}</label>
      <strong>{value == null ? '—' : format(animated)}</strong>
    </div>
  )
}

export function Header({ stats, modes, sweep }: { stats: Stats | null; modes: Modes | null; sweep: Sweep }) {
  const [menu, setMenu] = useState(false)
  const [brain, setBrain] = useState<'auto' | 'zoowork' | 'scripted'>('auto')
  const [useBand, setUseBand] = useState(true)
  const [runs, setRuns] = useState<{ id: string; events: number; duration: number }[]>([])
  const [error, setError] = useState<string | null>(null)
  const running = sweep.status === 'running'

  useEffect(() => {
    if (menu) api.runs().then(setRuns).catch(() => setRuns([]))
  }, [menu])

  const start = async () => {
    setError(null)
    try {
      await api.sweep({ brain, band: useBand })
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const winRate = stats?.win_rate == null ? null : stats.win_rate * 100
  // Spans with these classes collapse on smaller screens (see responsive.css):
  // brand-sub, kpi-extra, pill-detail, run-long.
  return (
    <header className="header">
      <div className="brand">
        <div className="brand-badge">
          <span className="steam" />
          <span className="steam" />
          <span className="steam" />
          <InspectorCapy size={78} mood={running ? 'search' : 'idle'} />
        </div>
        <div>
          <h1>Chargeback Capy</h1>
          <p>
            {OFFLINE ? (
              <span className="replay-tag">▶ offline replay of a live run · {REPLAY_INFO?.recorded_at}</span>
            ) : (
              <span className="brand-sub">Capybara Investigations · defending Hot Spring Supply Co.</span>
            )}
          </p>
        </div>
      </div>

      <div className="kpis" data-focus="kpis">
        <Kpi label="At risk" value={stats?.at_risk ?? null} tone="risk" />
        <Kpi label="Recovered" value={stats?.recovered ?? null} tone="good" />
        <Kpi label="Win rate" value={winRate} format={(n) => `${Math.round(n)}%`} />
        <Kpi
          label={
            <>
              Capy's fee<span className="kpi-extra"> ({Math.round((stats?.fee_rate ?? 0.2) * 100)}% of wins)</span>
            </>
          }
          value={stats?.fee ?? null}
        />
      </div>

      <div className="sponsors">
        <span className={`pill ${modes?.zoowork === 'live' ? 'pill-zoo live' : 'pill-off'}`}>
          <span className="dot" />
          ZooWork managed agent
          <span className="pill-detail">{modes?.zoowork === 'live' ? ` · ${modes.model?.replace('litellm/', '')}` : ' · offline'}</span>
        </span>
        <span className={`pill ${modes?.band === 'live' ? 'pill-band live' : 'pill-off'}`}>
          <span className="dot" />
          Band case rooms
          <span className="pill-detail">{modes?.band === 'live' ? ` · @${modes.band_user}` : ' · offline'}</span>
        </span>
      </div>

      <div className="header-actions">
        <button className="run-btn" onClick={start} disabled={running}>
          {running ? (
            <>
              <span className="spinner" /> Sweeping<span className="run-long"> disputes</span>…
            </>
          ) : (
            <>
              🔍 Run <span className="run-long">dispute </span>sweep
            </>
          )}
        </button>
        <button className="icon-btn" aria-label="Sweep settings" onClick={() => setMenu((m) => !m)}>
          ⚙︎
        </button>
        {menu && (
          <div className="menu">
            <h4>Who investigates?</h4>
            <label>
              <input type="radio" checked={brain === 'auto'} onChange={() => setBrain('auto')} /> Auto (ZooWork if connected)
            </label>
            <label>
              <input type="radio" checked={brain === 'zoowork'} disabled={modes?.zoowork !== 'live'} onChange={() => setBrain('zoowork')} /> ZooWork
              managed agent
            </label>
            <label>
              <input type="radio" checked={brain === 'scripted'} onChange={() => setBrain('scripted')} /> Scripted inspector (offline demo)
            </label>
            <h4>Case rooms</h4>
            <label>
              <input type="checkbox" checked={useBand} disabled={modes?.band !== 'live'} onChange={(e) => setUseBand(e.target.checked)} /> Post to Band
            </label>
            {runs.length > 0 && (
              <>
                <h4>Recorded sweeps</h4>
                {runs.slice(0, 5).map((r) => (
                  <div className="run-row" key={r.id}>
                    <span className="mono" style={{ fontSize: 11 }}>
                      {r.id} · {Math.round(r.duration)}s
                    </span>
                    <button className="link" onClick={() => api.replay(r.id)}>
                      Replay
                    </button>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
        {error && (
          <div className="menu" style={{ top: 56 }}>
            {error}
          </div>
        )}
      </div>
    </header>
  )
}
