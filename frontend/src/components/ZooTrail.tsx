import { motion } from 'framer-motion'
import { useEffect, useRef } from 'react'
import type { ZooStep } from '../store'
import type { CaseFile, Modes, Sweep } from '../types'

const ICONS: Record<string, string> = {
  list_disputes: '📥',
  get_dispute: '📄',
  get_order: '🛒',
  get_customer_history: '🧾',
  get_support_thread: '✉️',
  get_billing_records: '💳',
  request_partner_evidence: '🚚',
  ask_merchant: '✋',
  pin_evidence: '📌',
  set_strategy: '🧭',
  check_packet: '🔐',
  submit_evidence: '📨',
  accept_dispute: '🤝',
  write: '✏️',
  edit: '✏️',
  read: '👀',
  exec: '⌘',
  artifact_publish: '📤',
  web_search: '🔎',
  web_fetch: '🌐',
}

function argSummary(step: ZooStep) {
  const a = step.args ?? {}
  if (typeof a.path === 'string') return a.path
  if (typeof a.command === 'string') return a.command
  if (typeof a.exhibit_id === 'string') return `${a.exhibit_id} → ${a.supports ?? ''}`
  if (typeof a.request === 'string') return a.request
  if (typeof a.question === 'string') return a.question
  if (typeof a.decision === 'string') return `${a.decision} · ${a.win_probability}%`
  if (Array.isArray(a.claims)) return `${a.claims.length} findings · ${a.packet_path ?? ''}`
  if (typeof a.dispute_id === 'string') return a.dispute_id
  return ''
}

export function ZooTrail({ c, steps, modes, sweep }: { c: CaseFile | null; steps: ZooStep[]; modes: Modes | null; sweep: Sweep }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: 'smooth' })
  }, [steps.length, steps[steps.length - 1]?.status, c?.id])
  const live = sweep.brain === 'zoowork'
  const tools = steps.filter((s) => s.kind === 'tool')
  return (
    <section className="panel">
      <div className="panel-head">
        <span>🧠 Agent trail</span>
        <span className={`pill ${live ? 'pill-zoo live' : modes?.zoowork === 'live' ? 'pill-zoo' : 'pill-off'}`} style={{ fontSize: 11 }}>
          <span className="dot" />
          {live ? 'ZooWork managed agent' : sweep.brain === 'scripted' ? 'scripted inspector' : 'ZooWork'}
        </span>
        <span className="sub grow" style={{ textAlign: 'right' }}>
          {c?.session_id ? <span className="mono">session {c.session_id.slice(0, 8)}…</span> : `${tools.length} tool calls`}
        </span>
      </div>
      <div className="trail scroll grow" ref={ref}>
        {steps.length === 0 && <div className="trail-empty">Every model decision, tool call and result lands here as a replayable trajectory.</div>}
        {steps.map((s) => {
          if (s.kind === 'run')
            return (
              <div key={s.id} className="step run">
                {s.run === 'started' ? '▶ run started' : `■ run ${s.outcome ?? 'finished'}`}
              </div>
            )
          if (s.kind === 'thought' || s.kind === 'assistant')
            return (
              <motion.div key={s.id} className={`step ${s.kind}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <span className="ico">{s.kind === 'thought' ? '💭' : '🍊'}</span>
                <span>{s.text}</span>
              </motion.div>
            )
          return (
            <motion.div
              key={s.id}
              className={`step tool ${s.custom ? 'custom' : 'builtin'}`}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              title={s.preview}
            >
              <span className="ico">{ICONS[s.tool ?? ''] ?? '🔧'}</span>
              <span style={{ minWidth: 0 }}>
                <span className="name">{s.tool}</span>
                <span className="arg">{argSummary(s)}</span>
              </span>
              <span className={`st ${s.status}`}>
                {s.status === 'running' ? (
                  <>
                    <span className="spinner" /> {s.tool === 'ask_merchant' || s.tool === 'submit_evidence' || s.tool === 'accept_dispute' ? 'waiting' : 'running'}
                  </>
                ) : s.status === 'error' ? (
                  '✖ fix'
                ) : (
                  <>✓ {s.ms != null ? `${(s.ms / 1000).toFixed(1)}s` : ''}</>
                )}
              </span>
            </motion.div>
          )
        })}
      </div>
    </section>
  )
}
