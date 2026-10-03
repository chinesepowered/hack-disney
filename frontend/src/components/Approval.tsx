import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { api } from '../store'
import type { ApprovalRequest } from '../types'
import { money } from '../util'
import { InspectorCapy } from './Capys'

export function ApprovalModal({ approval, queued, live, onLater }: { approval: ApprovalRequest; queued: number; live: boolean; onLater: () => void }) {
  const p = approval.preview
  const pages = p.packet?.pages ?? []
  const [page, setPage] = useState(0)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    setPage(0)
    setBusy(false)
  }, [approval.id])
  const submit = approval.tool === 'submit_evidence'
  const decide = async (d: 'approve' | 'deny') => {
    setBusy(true)
    await api.decide(approval.id, d)
  }
  return (
    <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <motion.div
        className="modal"
        initial={{ y: 40, scale: 0.96, opacity: 0 }}
        animate={{ y: 0, scale: 1, opacity: 1 }}
        exit={{ y: 20, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 220, damping: 24 }}
      >
        <div className="modal-left">
          {submit && pages.length > 0 ? (
            <>
              <div className="big-page">
                <img src={pages[page]} alt={`Packet page ${page + 1}`} />
              </div>
              <div className="thumbs">
                {pages.map((src, i) => (
                  <button key={src} className={i === page ? 'on' : ''} onClick={() => setPage(i)}>
                    <img src={src} alt="" />
                  </button>
                ))}
              </div>
            </>
          ) : (
            <div className="big-page" style={{ textAlign: 'center' }}>
              <div>
                <InspectorCapy size={260} mood="idle" />
                <p style={{ fontFamily: 'var(--font-head)', fontSize: 22, color: 'var(--brown-dark)', margin: 0 }}>
                  Honest call: this one is on us.
                </p>
              </div>
            </div>
          )}
        </div>
        <div className="modal-right">
          <div className="modal-title">
            <InspectorCapy size={64} mood="wait" />
            <div>
              <h3>{submit ? 'Submit this evidence packet?' : 'Accept this dispute and refund?'}</h3>
              <p>
                {approval.case_id} · {p.case.network_code} {p.case.reason_label} · {p.case.customer_name}
                {queued > 1 ? ` · ${queued - 1} more waiting` : ''}
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
            <span className="money">{money(p.amount, true)}</span>
            <span style={{ fontWeight: 800, color: submit ? 'var(--teal-dark)' : 'var(--muted)' }}>
              {submit ? `to recover · ${p.win_probability ?? '?'}% win odds` : 'refunded to the cardholder'}
            </span>
          </div>
          {p.summary && <div style={{ fontSize: 14, lineHeight: 1.45, color: '#4a3d31' }}>{p.summary}</div>}
          {submit && (
            <div className="claims-list">
              {p.claims.map((cl, i) => (
                <div className="claim-row" key={i}>
                  <span className="n">{i + 1}</span>
                  <div>
                    {cl.text}
                    <div className="exchips">
                      {cl.exhibit_ids.map((id) => (
                        <span key={id} className="exchip">
                          {id}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="checks">
            {p.checks.map((ch) => (
              <div key={ch.label}>
                <span className={ch.ok ? 'check-ok' : ''}>{ch.ok ? '✅' : '⚠️'}</span> {ch.label}
              </div>
            ))}
          </div>
          <div className="modal-actions">
            <button className="later" onClick={onLater}>
              Later
            </button>
            <button className="hold" disabled={busy} onClick={() => decide('deny')}>
              {submit ? 'Hold' : 'Keep fighting'}
            </button>
            <button className="go" disabled={busy} onClick={() => decide('approve')}>
              {submit ? `Approve & submit ${money(p.amount, true)}` : `Approve refund of ${money(p.amount, true)}`}
            </button>
          </div>
          <div className="gatenote">
            🔒 {live ? `ZooWork always_ask approval gate · ${approval.id}` : 'Money moves only with your approval'}
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}
