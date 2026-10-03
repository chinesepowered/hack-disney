import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import type { CaseFile, Pin } from '../types'
import { countdown, money, reasonColor, useNow } from '../util'
import { InspectorCapy, type Mood } from './Capys'

const SLOTS = [
  { x: 19, y: 24, rot: -4 },
  { x: 81, y: 24, rot: 3 },
  { x: 82, y: 73, rot: -3 },
  { x: 54, y: 83, rot: 2 },
  { x: 50, y: 15, rot: -2 },
  { x: 36, y: 70, rot: 3 },
]

const QUOTES: Record<string, string> = {
  product_not_received: 'It never arrived.',
  fraudulent: "I didn't make this purchase.",
  subscription_canceled: 'I already cancelled!',
  product_unacceptable: 'It leaked. Not waterproof!',
  duplicate: 'You charged me twice.',
}

const KIND_ICON: Record<string, string> = {
  photo: '📸',
  tracking: '🚚',
  email: '✉️',
  payment: '💳',
  history: '🧾',
  refund: '↩️',
  policy: '📜',
  document: '🧪',
  subscription: '🔁',
  product: '🏷️',
}

function moodFor(c: CaseFile): Mood {
  switch (c.status) {
    case 'investigating':
    case 'waiting_partner':
    case 'drafting':
      return 'search'
    case 'waiting_merchant':
    case 'awaiting_approval':
    case 'submitted':
      return 'wait'
    case 'won':
      return 'happy'
    case 'lost':
      return 'sad'
    default:
      return 'idle'
  }
}

function bubbleFor(c: CaseFile, sweeping: boolean) {
  if (c.status === 'won') return `We won! ${money(c.amount, true)} is back 🍊`
  if (c.status === 'lost') return 'The issuer sided with the cardholder.'
  if (c.status === 'accepted') return 'Refunded. Fair is fair. I flagged the bug 🍊'
  if (c.status === 'new') return sweeping ? 'Queued, I’ll get to this one soon.' : 'Ready when you are. Hit “Run dispute sweep”.'
  return c.activity || 'On it…'
}

function Note({ pin, slot, index }: { pin: Pin; slot: (typeof SLOTS)[number]; index: number }) {
  const ex = pin.exhibit
  const photo = !!ex.image_url
  return (
    <div
      className="note-anchor"
      style={{ left: `${slot.x}%`, top: `${slot.y}%`, zIndex: 4 + index, ['--rot' as string]: `${slot.rot}deg` }}
    >
      <motion.div
        className={`note kind-${ex.kind} ${photo ? 'photo' : ''}`}
        initial={{ opacity: 0, scale: 1.6, y: -40 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 260, damping: 18 }}
      >
        <span className="pin" />
        {photo ? <img src={ex.image_url!} alt={ex.title} /> : null}
        <div className="ex-id" style={{ marginTop: photo ? 7 : 0 }}>
          <span>
            {KIND_ICON[ex.kind] ?? '📎'} {ex.id}
          </span>
          <span>{ex.source.split(' (')[0]}</span>
        </div>
        <h5>{ex.title}</h5>
        {!photo && <p>{ex.summary}</p>}
        <div className="supports">{pin.supports}</div>
      </motion.div>
    </div>
  )
}

export function CaseFileView({ c, sweeping, stamp }: { c: CaseFile | null; sweeping: boolean; stamp: React.ReactNode }) {
  const now = useNow(30_000)
  const [page, setPage] = useState<string | null>(null)
  if (!c) return <section className="panel" />
  const dl = countdown(c.respond_by, now)
  const pins = c.pins.slice(0, SLOTS.length)
  const pageCount = c.packet?.page_count ?? 0
  const argumentPages = c.packet?.argument_pages ?? 1
  return (
    <section className="panel casefile">
      <div className="case-head">
        <div>
          <h2>
            {c.id}
            <span className="reason-tag" style={{ ['--reason' as string]: reasonColor(c.reason) }}>
              {c.network_code} · {c.reason_label}
            </span>
          </h2>
          <div className="meta">
            {money(c.amount, true)} · {c.customer_name} · {c.item} · order {c.order_id} ·{' '}
            <span style={{ color: dl.urgent && !c.decision ? 'var(--red)' : undefined }}>⏳ {c.decision ? 'responded' : dl.label}</span>
          </div>
        </div>
        <div className="strategy">
          {c.strategy && <span className={`verdict-chip ${c.strategy}`}>{c.strategy === 'fight' ? '⚔️ Fight' : '🤝 Accept'}</span>}
          <div className="gauge" title="Inspector Capy's estimated win chance">
            <svg viewBox="0 0 64 64" width="64" height="64">
              <circle cx="32" cy="32" r="26" fill="none" stroke="#f0e6d6" strokeWidth="7" />
              <motion.circle
                cx="32"
                cy="32"
                r="26"
                fill="none"
                stroke={c.strategy === 'accept' ? '#a89886' : '#f0a12b'}
                strokeWidth="7"
                strokeLinecap="round"
                transform="rotate(-90 32 32)"
                initial={false}
                animate={{ pathLength: (c.win_probability ?? 0) / 100 }}
                transition={{ duration: 0.9 }}
              />
            </svg>
            <span>{c.win_probability == null ? '?' : `${c.win_probability}%`}</span>
            <small>win odds</small>
          </div>
        </div>
      </div>

      <div className="claim-strip">
        <b>Cardholder says</b>
        <span>“{c.claim}”</span>
        {c.rationale && <span className="rationale">🧭 {c.rationale}</span>}
      </div>

      <div className="board-wrap">
        <div className="board">
          <svg className="strings" viewBox="0 0 100 100" preserveAspectRatio="none">
            <AnimatePresence>
              {pins.map((p, i) => (
                <motion.line
                  key={p.exhibit.id}
                  x1={50}
                  y1={50}
                  x2={SLOTS[i].x}
                  y2={SLOTS[i].y - 9}
                  stroke="#c0392b"
                  strokeWidth={2.6}
                  vectorEffect="non-scaling-stroke"
                  strokeLinecap="round"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 0.9 }}
                  transition={{ duration: 0.7, delay: 0.25 }}
                  style={{ filter: 'drop-shadow(0 1px 1px rgba(0,0,0,.35))' }}
                />
              ))}
            </AnimatePresence>
          </svg>

          <div className="claim-card">
            <div className="label">Exhibit zero · the claim</div>
            <div className="quote">“{QUOTES[c.reason] ?? c.claim}”</div>
            <div className="by">
              {c.customer_name} · {money(c.amount, true)} · {c.network_code}
            </div>
          </div>

          {pins.map((p, i) => (
            <Note key={p.exhibit.id} pin={p} slot={SLOTS[i]} index={i} />
          ))}

          {pins.length === 0 && c.status !== 'accepted' && (
            <div className="board-empty">{c.status === 'new' ? 'No evidence pinned yet' : 'Gathering evidence…'}</div>
          )}

          <div className={`inspector ${c.status === 'won' ? 'happy' : ''}`}>
            <InspectorCapy size={150} mood={moodFor(c)} />
            <AnimatePresence mode="wait">
              <motion.div
                key={bubbleFor(c, sweeping)}
                className="bubble"
                initial={{ opacity: 0, y: 8, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.25 }}
              >
                {bubbleFor(c, sweeping)}
                {['investigating', 'waiting_partner', 'drafting'].includes(c.status) && (
                  <span className="typing">
                    <i />
                    <i />
                    <i />
                  </span>
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
        {stamp}
      </div>

      <div className="packet-strip">
        <div className="label">
          <b>Evidence packet</b>
          {c.packet ? `${pageCount} pages · ${c.claims.length} findings` : c.strategy === 'accept' ? 'Not needed: accepting' : 'Not built yet'}
        </div>
        <div className="pages">
          {c.packet?.pages.map((src, i) => (
            <motion.button
              key={src}
              className={`page-thumb ${i >= argumentPages ? 'vault' : ''}`}
              onClick={() => setPage(src)}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              style={{ padding: 0 }}
            >
              <img src={src.startsWith('data:') ? src : `${src}?v=${c.packet?.sha256.slice(0, 8)}`} alt={`Packet page ${i + 1}`} />
            </motion.button>
          ))}
        </div>
        {c.packet && (
          <div className="vault-badge" title={c.packet.sha256}>
            🔐 Vault-sealed · {c.packet.exhibits.length} originals · sha256 {c.packet.sha256.slice(0, 10)}…
          </div>
        )}
      </div>

      <AnimatePresence>
        {page && (
          <motion.div className="overlay" onClick={() => setPage(null)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <img src={page} alt="Packet page" style={{ maxHeight: '90vh', borderRadius: 8, boxShadow: '0 30px 80px rgba(0,0,0,.5)' }} />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
