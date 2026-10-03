import { AnimatePresence, motion } from 'framer-motion'
import { useLayoutEffect, useState } from 'react'
import type { CaseFile, Pin } from '../types'
import { countdown, money, reasonColor, useNow } from '../util'
import { InspectorCapy, type Mood } from './Capys'

type Slot = { x: number; y: number; rot: number }

// Where notes go, as percentages of the board (x, y = the note's center at full size).
const SLOTS: Slot[] = [
  { x: 19, y: 24, rot: -4 },
  { x: 81, y: 24, rot: 3 },
  { x: 82, y: 73, rot: -3 },
  { x: 54, y: 83, rot: 2 },
  { x: 50, y: 15, rot: -2 },
  { x: 36, y: 70, rot: 3 },
]

// The corkboard is designed for a 1000x620 board; on smaller boards its contents scale down
// (never below MIN_SCALE) via the --k variable used in responsive.css.
const BOARD_W = 1000
const BOARD_H = 620
const MIN_SCALE = 0.62
const COMPACT_HEIGHT = 440 // shorter boards trim each note (see .board.compact in responsive.css)

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

const clamp = (lo: number, v: number, hi: number) => Math.max(lo, Math.min(v, hi))

/** An element's size, kept current with a ResizeObserver. Pass the returned setter as its ref. */
function useElementSize() {
  const [el, setEl] = useState<HTMLDivElement | null>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  useLayoutEffect(() => {
    if (!el) return
    const update = () => setSize({ w: el.clientWidth, h: el.clientHeight })
    update()
    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => observer.disconnect()
  }, [el])
  return [setEl, size] as const
}

/** Worst-case note height: its text is line-clamped in responsive.css and has minimum sizes. */
function noteHeight(width: number, k: number, photo: boolean, compact: boolean) {
  const sourceLine = Math.max(9.5, 10.5 * k) * 1.35
  const title = 2 * 1.15 * Math.max(11.5, 14 * k) + 7
  const handwriting = (compact ? 2 : 3) * Math.max(15, 19 * k) * 1.05 + 7
  if (photo) return 21 * k + (width - 18 * k) * (compact ? 0.625 : 0.75) + 7 + sourceLine + title + handwriting
  const summary = compact ? 0 : 3 * 1.35 * Math.max(11, 12.5 * k)
  return 22 * k + sourceLine + title + summary + handwriting
}

interface Placement {
  x: number // horizontal center, and where the pin is
  top: number // top edge, where the pin and the red string meet the note
  width: number
}

/** A note's slot on a w x h board, pulled inward so the whole note stays on the board. */
function place(slot: Slot, photo: boolean, w: number, h: number, k: number, compact: boolean): Placement {
  const width = (photo && !compact ? 256 : 236) * k
  const height = noteHeight(width, k, photo, compact)
  const x = clamp(width / 2 + 10, (slot.x / 100) * w, w - width / 2 - 10)
  const top = clamp(14, (slot.y / 100) * h - height / 2, h - height - 10)
  return { x, top, width }
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
  if (c.status === 'new') return sweeping ? 'Queued, I’ll get to this one soon.' : 'Ready when you are. Start a sweep up top.'
  return c.activity || 'On it…'
}

function Note({ pin, slot, placement, index }: { pin: Pin; slot: Slot; placement: Placement; index: number }) {
  const ex = pin.exhibit
  const photo = !!ex.image_url
  return (
    <div
      className="note-anchor"
      style={{
        left: placement.x,
        top: placement.top,
        zIndex: 4 + index,
        ['--rot' as string]: `${slot.rot}deg`,
        ['--nw' as string]: `${placement.width}px`,
      }}
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
  const [boardRef, board] = useElementSize()
  if (!c) return <section className="panel" />
  const dl = countdown(c.respond_by, now)
  const pins = c.pins.slice(0, SLOTS.length)
  const pageCount = c.packet?.page_count ?? 0
  const argumentPages = c.packet?.argument_pages ?? 1
  const w = board.w || BOARD_W
  const h = board.h || BOARD_H
  const k = clamp(MIN_SCALE, Math.min(w / BOARD_W, h / BOARD_H), 1)
  const compact = h < COMPACT_HEIGHT
  const placements = pins.map((p, i) => place(SLOTS[i], !!p.exhibit.image_url, w, h, k, compact))
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

      <div className="board-wrap" style={{ ['--k' as string]: k }}>
        <div className={`board ${compact ? 'compact' : ''}`} ref={boardRef}>
          <svg className="strings" viewBox={`0 0 ${w} ${h}`}>
            <AnimatePresence>
              {pins.map((p, i) => (
                <motion.line
                  key={p.exhibit.id}
                  x1={w / 2}
                  y1={h / 2}
                  x2={placements[i].x}
                  y2={placements[i].top}
                  stroke="#c0392b"
                  strokeWidth={2.6}
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
            <Note key={p.exhibit.id} pin={p} slot={SLOTS[i]} placement={placements[i]} index={i} />
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
            <img src={page} alt="Packet page" style={{ maxHeight: '90vh', maxWidth: '94vw', borderRadius: 8, boxShadow: '0 30px 80px rgba(0,0,0,.5)' }} />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
