import { motion } from 'framer-motion'
import type { CaseFile, Stats } from '../types'
import { countdown, isBusy, money, reasonColor, statusTone, useNow } from '../util'

function StatusChip({ c }: { c: CaseFile }) {
  const tone = statusTone(c)
  const icon =
    c.status === 'won' ? '🏆' : c.status === 'lost' ? '✖' : c.status === 'accepted' ? '🤝' : tone === 'needs' ? '✋' : null
  return (
    <span className={`status-chip ${tone}`}>
      {isBusy(c) && <span className="spinner" />}
      {icon}
      {c.status === 'won' ? `Won ${money(c.amount)}` : c.status_label}
    </span>
  )
}

export function Inbox({
  cases,
  selected,
  onSelect,
  stats,
}: {
  cases: CaseFile[]
  selected: string | null
  onSelect: (id: string) => void
  stats: Stats | null
}) {
  const now = useNow(30_000)
  return (
    <section className="panel">
      <div className="panel-head">
        📥 Dispute inbox
        <span className="sub grow" style={{ textAlign: 'right' }}>
          {stats ? `${stats.open} open · ${stats.total} total` : ''}
        </span>
      </div>
      <div className="inbox-list scroll">
        {cases.map((c) => {
          const dl = countdown(c.respond_by, now)
          const done = ['won', 'lost', 'accepted'].includes(c.status)
          return (
            <motion.button
              layout
              key={c.id}
              className={`case-card ${selected === c.id ? 'selected' : ''}`}
              style={{ ['--reason' as string]: reasonColor(c.reason) }}
              onClick={() => onSelect(c.id)}
            >
              <div>
                <div className="cid">
                  {c.id} · {c.network_code}
                </div>
                <div className="reason">{c.reason_label}</div>
              </div>
              <div className="amount">{money(c.amount, true)}</div>
              <div className="who">
                {c.customer_name} · {c.item}
              </div>
              {c.win_probability != null && !done && (
                <div className="winbar" title={`${c.win_probability}% win chance`}>
                  <div style={{ width: `${c.win_probability}%` }} />
                </div>
              )}
              <div className="foot">
                <StatusChip c={c} />
                {!done && <span className={`deadline ${dl.urgent ? 'urgent' : ''}`}>⏳ {dl.label}</span>}
              </div>
            </motion.button>
          )
        })}
      </div>
      {stats && (
        <div className="inbox-summary">
          <div>
            Decided <b>{stats.decided_count}</b> · won <b>{stats.won_count}</b> · accepted <b>{money(stats.accepted)}</b>
          </div>
          <div>
            Capy only earns on wins: <b>{money(stats.fee, true)}</b> so far
          </div>
        </div>
      )}
    </section>
  )
}
