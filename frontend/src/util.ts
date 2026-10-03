import { useEffect, useRef, useState } from 'react'
import type { CaseFile } from './types'

export const money = (n: number | null | undefined, cents = false) =>
  n == null
    ? '—'
    : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0 })

export const REASON_COLORS: Record<string, string> = {
  product_not_received: '#d9822b',
  fraudulent: '#c0473f',
  subscription_canceled: '#8a7a6b',
  product_unacceptable: '#3e8fb0',
  duplicate: '#7b62c9',
}

export function reasonColor(reason: string) {
  return REASON_COLORS[reason] ?? '#8d5d39'
}

export function statusTone(c: CaseFile): string {
  switch (c.status) {
    case 'won':
      return 'won'
    case 'lost':
      return 'lost'
    case 'accepted':
      return 'accepted'
    case 'waiting_merchant':
    case 'awaiting_approval':
      return 'needs'
    case 'submitted':
      return 'review'
    case 'new':
      return ''
    default:
      return 'active'
  }
}

export function isBusy(c: CaseFile) {
  return ['investigating', 'waiting_partner', 'drafting', 'submitted'].includes(c.status)
}

export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(t)
  }, [intervalMs])
  return now
}

export function countdown(iso: string, now: number) {
  const ms = new Date(iso).getTime() - now
  if (ms <= 0) return { label: 'overdue', urgent: true }
  const d = Math.floor(ms / 86_400_000)
  const h = Math.floor((ms % 86_400_000) / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  const label = d > 0 ? `${d}d ${h}h left` : `${h}h ${m}m left`
  return { label, urgent: ms < 5 * 86_400_000 }
}

export function shortTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' })
}

/** Smoothly animate a number toward its target (for KPI tickers). */
export function useAnimatedNumber(target: number, duration = 1200) {
  const [value, setValue] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    const start = performance.now()
    const begin = from.current
    let frame = 0
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      const v = begin + (target - begin) * eased
      setValue(v)
      if (p < 1) frame = requestAnimationFrame(tick)
      else from.current = target
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, duration])
  return value
}

export function stripMentions(text: string) {
  return text.replace(/@\[\[[0-9a-f-]+\]\]\s*/g, '')
}
