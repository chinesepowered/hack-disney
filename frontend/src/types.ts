export type CaseStatus =
  | 'new'
  | 'investigating'
  | 'waiting_partner'
  | 'waiting_merchant'
  | 'drafting'
  | 'awaiting_approval'
  | 'submitted'
  | 'won'
  | 'lost'
  | 'accepted'

export interface Exhibit {
  id: string
  case_id: string
  key: string
  kind: string
  title: string
  source: string
  summary: string
  rows: string[][]
  body: string
  image: string | null
  image_url: string | null
  sha256: string
}

export interface Pin {
  exhibit: Exhibit
  supports: string
  pinned_at: number
}

export interface Claim {
  text: string
  exhibit_ids: string[]
}

export interface Attention {
  id: string
  question: string
  options: string[]
  status: 'open' | 'answered'
  answer: string | null
}

export interface Packet {
  pdf_url: string
  pages: string[]
  page_count: number
  argument_pages: number
  exhibits: string[]
  sha256: string
}

export interface Decision {
  status: 'won' | 'lost' | 'accepted'
  amount: number
  reasons: string[]
  decided_at: number
}

export interface CaseFile {
  id: string
  order_id: string
  charge_id: string
  amount: number
  reason: string
  network_code: string
  reason_label: string
  customer_name: string
  customer_email: string
  item: string
  claim: string
  opened_at: string
  respond_by: string
  status: CaseStatus
  status_label: string
  strategy: 'fight' | 'accept' | null
  win_probability: number | null
  rationale: string
  activity: string
  pins: Pin[]
  claims: Claim[]
  attention: Attention[]
  room: { id: string | null; title: string; live: boolean; members: string[] } | null
  packet: Packet | null
  decision: Decision | null
  session_id: string | null
  updated_at: number
}

export interface Stats {
  total: number
  open: number
  at_risk: number
  recovered: number
  lost: number
  accepted: number
  won_count: number
  decided_count: number
  win_rate: number | null
  fee: number
  fee_rate: number
}

export interface ApprovalRequest {
  id: string
  case_id: string
  tool: 'submit_evidence' | 'accept_dispute'
  args: Record<string, unknown>
  preview: {
    amount: number
    case: CaseFile
    summary: string
    claims: Claim[]
    packet: Packet | null
    exhibits: Exhibit[]
    checks: { label: string; ok: boolean }[]
    win_probability: number | null
  }
  created_at: number
  status: string
}

export interface Modes {
  zoowork: 'live' | 'off'
  band: 'live' | 'off'
  band_error: string | null
  band_user: string | null
  model: string | null
  voices: boolean
}

export interface Sweep {
  id?: string
  status: 'idle' | 'running' | 'done'
  brain?: 'zoowork' | 'scripted'
  band?: boolean
  started_at?: number
  finished_at?: number
}

export interface BandItem {
  id: string
  case_id: string
  channel: 'band'
  sender: 'capy' | 'shipco' | 'merchant' | 'system'
  name: string
  text: string
  kind: string
  attachments: { name: string; url: string }[]
  live: boolean
  ts: number
  attention_id?: string
  options?: string[]
  exhibit_id?: string
}

export interface ZooItem {
  id: string
  case_id: string
  channel: 'zoo'
  kind: 'tool' | 'thought' | 'assistant' | 'run'
  ts: number
  call_id?: string
  tool?: string
  phase?: 'start' | 'end'
  custom?: boolean
  args?: Record<string, unknown>
  preview?: string
  error?: boolean
  ms?: number
  text?: string
  status?: string
  outcome?: string | null
}

export type FeedItem = BandItem | ZooItem

export interface Snapshot {
  cases: CaseFile[]
  stats: Stats
  approvals: ApprovalRequest[]
  sweep: Sweep
  modes: Modes
  merchant: { name: string }
}

export interface LogLine {
  level: 'info' | 'warn' | 'error'
  text: string
  ts: number
}
