import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { api } from '../store'
import type { BandItem, CaseFile } from '../types'
import { shortTime, stripMentions } from '../util'
import { CapyAvatar } from './Capys'

const MENTION_NAMES: Record<string, string> = {
  shipco: '@ShipCo Warehouse',
  merchant: '@You',
  capy: '@Inspector Capy',
}

function Message({ m }: { m: BandItem }) {
  if (m.sender === 'system') return <div className="sys">— {m.text} —</div>
  const mentions = ((m as unknown as { mentions?: string[] }).mentions ?? []).filter((r) => r !== 'merchant' || m.kind === 'attention')
  return (
    <motion.div className={`msg ${m.sender} kind-${m.kind}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <CapyAvatar who={m.sender} size={34} />
      <div className="body">
        <div className="who">
          {m.name}
          <time>{shortTime(m.ts)}</time>
        </div>
        <div className="text">
          {mentions.map((r) => (
            <span key={r} className="mention">
              {MENTION_NAMES[r] ?? `@${r}`}{' '}
            </span>
          ))}
          {stripMentions(m.text)}
          {m.attachments.map((a) => (
            <img key={a.url} className="attach" src={a.url} alt={a.name} />
          ))}
        </div>
      </div>
    </motion.div>
  )
}

function AttentionCard({ c, m }: { c: CaseFile; m: BandItem }) {
  const att = c.attention.find((a) => a.id === m.attention_id)
  const [sent, setSent] = useState(false)
  const open = att?.status === 'open' && !sent
  const reply = (text: string) => {
    setSent(true)
    const share = /lab|report|share|attach/i.test(text) ? 'lab_report' : undefined
    api.reply(c.id, text.replace(/^📎\s*/, ''), share)
  }
  return (
    <motion.div className="msg" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <CapyAvatar who="capy" size={34} />
      <div className="body">
        <div className="who">
          Inspector Capy <time>{shortTime(m.ts)}</time>
        </div>
        <div className="attention">
          <div className="tag">✋ Needs you · Band attention item</div>
          <div className="q">
            <span className="mention">@You</span> {m.text}
          </div>
          {open ? (
            <div className="quick">
              {(m.options?.length ? m.options : ['Yes', 'No']).map((o, i) => (
                <button key={o} className={i === 0 ? 'primary' : ''} onClick={() => reply(i === 0 && o.includes('lab') ? 'Yes! Here’s the ISO 811 lab report for batch SS-24.' : o)}>
                  {o}
                </button>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--green)' }}>✓ Answered{att?.answer ? `: ${att.answer}` : '…'}</div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export function BandRoom({ c, items }: { c: CaseFile | null; items: BandItem[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const [draft, setDraft] = useState('')
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: 'smooth' })
  }, [items.length, c?.id])
  const members = c?.room?.members ?? ['capy', 'merchant']
  const openQuestion = c?.attention.find((a) => a.status === 'open')
  return (
    <section className="panel">
      <div className="panel-head">
        <span>💬 Case room</span>
        <span className={`pill ${c?.room?.id ? 'pill-band live' : 'pill-off'}`} style={{ fontSize: 11 }}>
          <span className="dot" />
          {c?.room?.id ? 'live on Band' : 'local'}
        </span>
        <span className="room-head-title grow">{c?.room?.title ?? ''}</span>
        <span className="members">
          {members.map((m) => (
            <CapyAvatar key={m} who={m} size={28} />
          ))}
        </span>
      </div>
      <div className="messages scroll grow" ref={ref} key={c?.id ?? 'none'}>
        {items.length === 0 && <div className="room-empty">The case room opens when the sweep starts. Inspector Capy, partners and you meet here.</div>}
        <AnimatePresence initial={false}>
          {items.map((m) =>
            m.kind === 'attention' && c ? <AttentionCard key={m.id} c={c} m={m} /> : <Message key={m.id} m={m} />,
          )}
        </AnimatePresence>
      </div>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault()
          if (!c || !draft.trim()) return
          api.reply(c.id, draft.trim())
          setDraft('')
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={openQuestion ? 'Answer Inspector Capy…' : 'Message the case room as Hot Spring Supply…'}
        />
        <button type="submit">Send</button>
      </form>
    </section>
  )
}
