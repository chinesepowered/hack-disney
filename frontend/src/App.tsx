import confetti from 'canvas-confetti'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ApprovalModal } from './components/Approval'
import { StoryCard } from './components/Cards'
import { BandRoom } from './components/BandRoom'
import { CaseFileView } from './components/CaseFile'
import { Header } from './components/Header'
import { Inbox } from './components/Inbox'
import { ZooTrail } from './components/ZooTrail'
import { useCapyStore, type DecisionToast, type State } from './store'
import { money } from './util'

const DIRECTOR = new URLSearchParams(location.search).has('director')
const DWELL_MS = 6500

declare global {
  interface Window {
    __capy?: {
      select: (id: string) => void
      follow: (on: boolean) => void
      caption: (text: string | null) => void
      focus: (target: string | null, scale?: number, mode?: 'fit' | 'top') => void
      state: () => State
      card: (name: string | null) => void
      click: (selector: string) => Promise<boolean>
      showApproval: (caseId: string | null) => void
      modals: (on: boolean) => void
    }
  }
}

function pickFocus(state: State, current: string | null, lastSwitch: number): string | null {
  const cases = Object.values(state.cases)
  if (!cases.length) return null
  const stamp = state.decisions[0]?.case_id
  if (stamp) return stamp
  const approval = state.approvals[0]?.case_id
  if (approval) return approval
  const question = cases.find((c) => c.attention.some((a) => a.status === 'open'))
  if (question) return question.id
  const cur = current ? state.cases[current] : undefined
  const busy = (id?: string | null) =>
    !!id && ['investigating', 'waiting_partner', 'drafting'].includes(state.cases[id]?.status ?? '')
  if (cur && busy(cur.id) && Date.now() - lastSwitch < DWELL_MS * 2) return cur.id
  if (Date.now() - lastSwitch < DWELL_MS && cur && cur.status !== 'new') return cur.id
  if (busy(state.lastActive)) return state.lastActive
  return current ?? cases[0].id
}

function Stamp({ toast }: { toast: DecisionToast }) {
  const s = toast.decision.status
  return (
    <motion.div
      className="stamp-layer"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.5 } }}
    >
      <motion.div
        className={`stamp ${s}`}
        initial={{ scale: 2.6, rotate: -18, opacity: 0 }}
        animate={{ scale: 1, rotate: -8, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 380, damping: 16 }}
      >
        <div className="big">{s === 'won' ? 'WON' : s === 'lost' ? 'LOST' : 'ACCEPTED'}</div>
        <div className="small">
          {s === 'won' ? `+${money(toast.decision.amount, true)} recovered` : s === 'accepted' ? `refunded ${money(toast.decision.amount, true)}` : `−${money(toast.decision.amount, true)}`}
        </div>
      </motion.div>
    </motion.div>
  )
}

export default function App() {
  const { state, dismissDecision } = useCapyStore()
  const [selected, setSelected] = useState<string | null>(null)
  const [follow, setFollow] = useState(true)
  const [caption, setCaption] = useState<string | null>(null)
  const [focus, setFocus] = useState<{ x: number; y: number; scale: number } | null>(null)
  const [snoozed, setSnoozed] = useState<string[]>([])
  const [card, setCard] = useState<string | null>(null)
  const [cursor, setCursor] = useState({ x: 960, y: 1180, clicking: false, visible: false })
  const [forced, setForced] = useState<string | null>(null)
  const [modalsOn, setModalsOn] = useState(true)
  const lastSwitch = useRef(0)
  const cases = useMemo(() => state.order.map((id) => state.cases[id]).filter(Boolean), [state.order, state.cases])

  // follow the action, but dwell long enough for viewers to read
  useEffect(() => {
    if (!follow) return
    const next = pickFocus(state, selected, lastSwitch.current)
    if (next && next !== selected) {
      setSelected(next)
      lastSwitch.current = Date.now()
    }
  }, [state, follow, selected])

  useEffect(() => {
    if (!selected && cases.length) setSelected(cases[0].id)
  }, [cases, selected])

  // decisions: jump to the case, stamp it, celebrate wins
  const stamp = state.decisions.find((d) => d.case_id === selected) ?? null
  useEffect(() => {
    const d = state.decisions[0]
    if (!d) return
    if (follow && d.case_id !== selected) return // the follow camera is on its way to this case
    if (d.case_id === selected && d.decision.status === 'won') {
      const colors = ['#ffc531', '#f08c2b', '#2b8c83', '#8d5d39', '#ffffff']
      confetti({ particleCount: 140, spread: 80, origin: { x: 0.5, y: 0.45 }, colors, scalar: 1.1 })
      setTimeout(() => confetti({ particleCount: 90, angle: 60, spread: 60, origin: { x: 0.25, y: 0.6 }, colors }), 250)
      setTimeout(() => confetti({ particleCount: 90, angle: 120, spread: 60, origin: { x: 0.75, y: 0.6 }, colors }), 400)
    }
    const t = setTimeout(() => dismissDecision(d.key), d.case_id === selected ? 3200 : 600)
    return () => clearTimeout(t)
  }, [state.decisions, selected, follow, dismissDecision])

  // director hooks for the demo video recorder
  const stateRef = useRef(state)
  stateRef.current = state
  useEffect(() => {
    window.__capy = {
      select: (id: string) => {
        setFollow(false)
        setSelected(id)
      },
      follow: (on) => setFollow(on),
      caption: (text) => setCaption(text),
      focus: (target, scale = 1.6, mode = 'fit') => {
        if (!target) return setFocus(null)
        const el = document.querySelector(`[data-focus="${target}"]`) as HTMLElement | null
        if (!el) return
        // measure without the current zoom, then center the element and fit it on screen
        const app = document.querySelector('.app') as HTMLElement
        const prev = app.style.transform
        app.style.transition = 'none'
        app.style.transform = 'none'
        const r = el.getBoundingClientRect()
        app.style.transform = prev
        void app.offsetWidth
        app.style.transition = ''
        const W = window.innerWidth
        const H = window.innerHeight
        if (mode === 'top') {
          const s = Math.min(scale, (0.92 * W) / r.width)
          setFocus({ x: W / 2 - s * (r.left + r.width / 2), y: 40 - s * r.top, scale: s })
          return
        }
        const s = Math.min(scale, (0.92 * W) / r.width, (0.86 * H) / r.height)
        setFocus({ x: W / 2 - s * (r.left + r.width / 2), y: H / 2 - s * (r.top + r.height / 2) - 20, scale: s })
      },
      state: () => stateRef.current,
      card: (name) => setCard(name),
      showApproval: (caseId) => setForced(caseId),
      modals: (on) => setModalsOn(on),
      click: async (selector) => {
        const el = document.querySelector(selector) as HTMLElement | null
        if (!el) return false
        const r = el.getBoundingClientRect()
        setCursor((c) => ({ ...c, visible: true }))
        await new Promise((ok) => setTimeout(ok, 30))
        setCursor({ x: r.left + r.width / 2, y: r.top + r.height / 2, clicking: false, visible: true })
        await new Promise((ok) => setTimeout(ok, 950))
        setCursor((c) => ({ ...c, clicking: true }))
        await new Promise((ok) => setTimeout(ok, 200))
        el.click()
        await new Promise((ok) => setTimeout(ok, 350))
        setCursor((c) => ({ ...c, clicking: false }))
        setTimeout(() => setCursor((c) => ({ ...c, visible: false })), 1400)
        return true
      },
    }
    if (DIRECTOR) document.body.classList.add('director-cursor-hidden')
  }, [])

  const current = selected ? state.cases[selected] ?? null : null
  const approval = !modalsOn
    ? undefined
    : forced
      ? state.approvals.find((a) => a.case_id === forced)
      : state.approvals.find((a) => !snoozed.includes(a.id))
  const waiting = DIRECTOR ? 0 : state.approvals.length
  const toasts = state.logs.filter((l) => l.level !== 'info' && Date.now() / 1000 - l.ts < 9)

  return (
    <>
      <div
        className="app"
        style={focus ? { transform: `translate(${focus.x}px, ${focus.y}px) scale(${focus.scale})`, transformOrigin: '0 0' } : { transformOrigin: '0 0' }}
      >
        <Header stats={state.stats} modes={state.modes} sweep={state.sweep} />
        <main className="main">
          <div data-focus="inbox" style={{ minHeight: 0, display: 'grid' }}>
            <Inbox
              cases={cases}
              selected={selected}
              stats={state.stats}
              onSelect={(id) => {
                setFollow(false)
                setSelected(id)
              }}
            />
          </div>
          <div data-focus="casefile" style={{ minHeight: 0, display: 'grid' }}>
            <CaseFileView
              c={current}
              sweeping={state.sweep.status === 'running'}
              stamp={<AnimatePresence>{stamp && <Stamp key={stamp.key} toast={stamp} />}</AnimatePresence>}
            />
          </div>
          <div className="right">
            <div data-focus="band" style={{ minHeight: 0, display: 'grid' }}>
              <BandRoom c={current} items={selected ? state.band[selected] ?? [] : []} />
            </div>
            <div data-focus="zoo" style={{ minHeight: 0, display: 'grid' }}>
              <ZooTrail c={current} steps={selected ? state.zoo[selected] ?? [] : []} modes={state.modes} sweep={state.sweep} />
            </div>
          </div>
        </main>
      </div>

      {!follow && !DIRECTOR && (
        <button
          className="pill pill-band"
          style={{ position: 'fixed', right: 22, bottom: 20, zIndex: 30, border: 0, padding: '9px 14px' }}
          onClick={() => setFollow(true)}
        >
          🔍 Follow Inspector Capy
        </button>
      )}

      <AnimatePresence>
        {approval && (
          <ApprovalModal
            key={approval.id}
            approval={approval}
            queued={state.approvals.length}
            live={state.sweep.brain === 'zoowork'}
            onLater={() => setSnoozed((s) => [...s, ...state.approvals.map((a) => a.id)])}
          />
        )}
      </AnimatePresence>

      {!approval && waiting > 0 && (
        <button className="approval-dock" onClick={() => setSnoozed([])}>
          ✋ {waiting} approval{waiting > 1 ? 's' : ''} waiting for you
        </button>
      )}

      <div className="toasts">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div key={t.ts} className={`toast ${t.level}`} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
              {t.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {caption && (
          <motion.div key={caption} className="caption" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}>
            {caption}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>{card && <StoryCard key={card} name={card} />}</AnimatePresence>

      {DIRECTOR && (
        <div
          className={`fake-cursor ${cursor.clicking ? 'clicking' : ''}`}
          style={{ transform: `translate(${cursor.x}px, ${cursor.y}px)`, opacity: cursor.visible ? 1 : 0 }}
        >
          <svg width="34" height="40" viewBox="0 0 34 40">
            <path d="M3 2 L3 32 L11 25 L17 38 L23 35 L17 22 L28 22 Z" fill="#2b2118" stroke="#fff" strokeWidth="2.5" strokeLinejoin="round" />
          </svg>
          <span className="ripple" />
        </div>
      )}

      {!state.connected && <div className="disconnected">Reconnecting to the Capy backend…</div>}
    </>
  )
}
