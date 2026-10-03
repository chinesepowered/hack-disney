import { useEffect, useReducer } from 'react'
import type {
  ApprovalRequest,
  BandItem,
  CaseFile,
  Decision,
  LogLine,
  Modes,
  Snapshot,
  Stats,
  Sweep,
  ZooItem,
} from './types'

export interface ZooStep {
  id: string
  kind: 'tool' | 'thought' | 'assistant' | 'run'
  ts: number
  tool?: string
  custom?: boolean
  args?: Record<string, unknown>
  status?: 'running' | 'ok' | 'error'
  preview?: string
  ms?: number
  text?: string
  outcome?: string | null
  run?: string
}

export interface DecisionToast {
  key: number
  case_id: string
  decision: Decision
}

export interface State {
  connected: boolean
  cases: Record<string, CaseFile>
  order: string[]
  stats: Stats | null
  approvals: ApprovalRequest[]
  sweep: Sweep
  modes: Modes | null
  merchant: string
  band: Record<string, BandItem[]>
  zoo: Record<string, ZooStep[]>
  logs: LogLine[]
  decisions: DecisionToast[]
  lastActive: string | null
}

const initial: State = {
  connected: false,
  cases: {},
  order: [],
  stats: null,
  approvals: [],
  sweep: { status: 'idle' },
  modes: null,
  merchant: 'Hot Spring Supply Co.',
  band: {},
  zoo: {},
  logs: [],
  decisions: [],
  lastActive: null,
}

type Action =
  | { type: 'connected'; value: boolean }
  | { type: 'event'; event: Record<string, any> }
  | { type: 'dismissDecision'; key: number }

let decisionKey = 0

function fromSnapshot(state: State, snap: Snapshot, clearFeeds: boolean): State {
  const cases: Record<string, CaseFile> = {}
  for (const c of snap.cases) cases[c.id] = c
  return {
    ...state,
    cases,
    order: snap.cases.map((c) => c.id),
    stats: snap.stats,
    approvals: snap.approvals ?? [],
    sweep: snap.sweep ?? state.sweep,
    modes: snap.modes ?? state.modes,
    merchant: snap.merchant?.name ?? state.merchant,
    band: clearFeeds ? {} : state.band,
    zoo: clearFeeds ? {} : state.zoo,
    decisions: clearFeeds ? [] : state.decisions,
    lastActive: clearFeeds ? null : state.lastActive,
  }
}

function addZoo(steps: ZooStep[], item: ZooItem): ZooStep[] {
  if (item.kind === 'tool' && item.call_id) {
    const idx = steps.findIndex((s) => s.id === item.call_id)
    if (item.phase === 'end') {
      const done: Partial<ZooStep> = {
        status: item.error ? 'error' : 'ok',
        preview: item.preview,
        ms: item.ms,
      }
      if (idx >= 0) {
        const next = steps.slice()
        next[idx] = { ...next[idx], ...done, args: next[idx].args ?? item.args }
        return next
      }
      return [...steps, { id: item.call_id, kind: 'tool', ts: item.ts, tool: item.tool, custom: item.custom, args: item.args, ...done }]
    }
    if (idx >= 0) return steps
    return [...steps, { id: item.call_id, kind: 'tool', ts: item.ts, tool: item.tool, custom: item.custom, args: item.args, status: 'running' }]
  }
  if (steps.some((s) => s.id === item.id)) return steps
  return [...steps, { id: item.id, kind: item.kind, ts: item.ts, text: item.text, run: item.status, outcome: item.outcome }]
}

function reducer(state: State, action: Action): State {
  if (action.type === 'connected') return { ...state, connected: action.value }
  if (action.type === 'dismissDecision') {
    return { ...state, decisions: state.decisions.filter((d) => d.key !== action.key) }
  }
  const e = action.event
  switch (e.type) {
    case 'snapshot':
      return fromSnapshot(state, e as unknown as Snapshot, false)
    case 'reset':
      return fromSnapshot(state, e as unknown as Snapshot, true)
    case 'case': {
      const c = e.case as CaseFile
      const order = state.order.includes(c.id) ? state.order : [...state.order, c.id].sort()
      return { ...state, cases: { ...state.cases, [c.id]: c }, order }
    }
    case 'stats':
      return { ...state, stats: e.stats }
    case 'sweep':
      return { ...state, sweep: e.sweep }
    case 'approval':
      return { ...state, approvals: [...state.approvals.filter((a) => a.id !== e.approval.id), e.approval] }
    case 'approval_resolved':
      return { ...state, approvals: state.approvals.filter((a) => a.id !== e.approval_id) }
    case 'decision': {
      const { case_id, status, amount, reasons, decided_at } = e
      decisionKey += 1
      return {
        ...state,
        decisions: [...state.decisions, { key: decisionKey, case_id, decision: { status, amount, reasons, decided_at } }],
      }
    }
    case 'log':
      return { ...state, logs: [...state.logs.slice(-6), { level: e.level, text: e.text, ts: e.ts }] }
    case 'feed': {
      const item = e.item as BandItem | ZooItem
      const caseId = item.case_id
      if (!caseId) return state
      if (item.channel === 'band') {
        const list = state.band[caseId] ?? []
        if (list.some((m) => m.id === item.id)) return state
        return { ...state, band: { ...state.band, [caseId]: [...list, item] }, lastActive: caseId }
      }
      const steps = addZoo(state.zoo[caseId] ?? [], item)
      return { ...state, zoo: { ...state.zoo, [caseId]: steps }, lastActive: caseId }
    }
    default:
      return state
  }
}

export function useCapyStore() {
  const [state, dispatch] = useReducer(reducer, initial)

  useEffect(() => {
    let socket: WebSocket | null = null
    let closed = false
    let retry = 500
    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      socket = new WebSocket(`${proto}://${location.host}/ws`)
      socket.onopen = () => {
        retry = 500
        dispatch({ type: 'connected', value: true })
      }
      socket.onmessage = (msg) => dispatch({ type: 'event', event: JSON.parse(msg.data) })
      socket.onclose = () => {
        dispatch({ type: 'connected', value: false })
        if (!closed) setTimeout(connect, (retry = Math.min(retry * 2, 5000)))
      }
    }
    connect()
    return () => {
      closed = true
      socket?.close()
    }
  }, [])

  return { state, dismissDecision: (key: number) => dispatch({ type: 'dismissDecision', key }) }
}

export const api = {
  async sweep(body: { brain?: string; band?: boolean; cases?: string[] } = {}) {
    const r = await fetch('/api/sweep', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
    if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText)
    return r.json()
  },
  async decide(id: string, decision: 'approve' | 'deny') {
    await fetch(`/api/approvals/${id}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ decision }) })
  },
  async reply(caseId: string, text: string, share?: string) {
    await fetch(`/api/cases/${caseId}/reply`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text, share }) })
  },
  async runs(): Promise<{ id: string; events: number; duration: number }[]> {
    return (await fetch('/api/runs')).json()
  },
  async replay(run_id: string, speed = 1) {
    await fetch('/api/replay', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ run_id, speed }) })
  },
}
