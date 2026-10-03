# 🔍 Chargeback Capy

- **What it does:** Chargeback Capy is an AI detective that wins back the money online merchants lose to chargebacks.
- **The problem:** every chargeback costs a shop the sale, the goods and a fee, and the evidence to fight it is scattered across systems and companies with deadlines in days, so most small merchants never respond.
- **Our solution:** Inspector Capy, a ZooWork managed agent, investigates every dispute in parallel, gathers proof from partner agents and the merchant in Band case rooms, writes an evidence packet where every claim must cite a fingerprinted exhibit, and submits only after the merchant approves.
- **Results:** in a live run it handled 5 disputes in about 90 seconds: 4 won ($1,842 recovered) and 1 honest refund where the shop was at fault. Merchants pay 20% of recovered dollars, nothing when Capy loses.

### ▶ [Watch the 3-minute demo on YouTube](https://www.youtube.com/watch?v=vCJSlZiHoYU)

[![Chargeback Capy dashboard during a live run. Click to watch the demo video.](docs/dashboard.jpg)](https://www.youtube.com/watch?v=vCJSlZiHoYU)

**Try it:** [`offline.html`](offline.html) (replay of a live run; download and open in any browser, no network needed) ·
[`slide.html`](slide.html) (4-slide pitch) · [`docs/SETUP.md`](docs/SETUP.md) (run it live) ·
[`docs/chargeback-capy-demo.mp4`](docs/chargeback-capy-demo.mp4) (offline copy of the video)

## Sponsor summary

| Sponsor | What it does in Chargeback Capy | Where |
|---|---|---|
| **ZooWork** | Runs Inspector Capy as a managed agent: one session per dispute in parallel, 13 custom tools, sandbox-built PDF via `artifact_publish`, `always_ask` approval before money moves, streamed trajectories | `backend/capy/zoo.py`, `tools.py`, `persona/` |
| **Band** | Cross-company case rooms: Capy and the ShipCo Warehouse partner agent talk by @mention, the merchant answers attention items, every step lands in the room's audit trail | `backend/capy/band.py`, `rooms.py` |

## Sponsor details

### ZooWork: the agent runtime
- **Managed agent `inspector-capy`** (Claude Sonnet 5 through ZooWork) with persona docs: an operating manual
  with a playbook per Visa reason code, identity and values (`backend/capy/persona/`).
- **One ZooWork session per dispute**, all five running in parallel. Every model message, tool call and result is
  streamed from the session's event stream into the dashboard's *Agent trail*.
- **13 application-executed custom tools**: dispute, order, customer-history, support and billing lookups; partner
  and merchant requests; evidence pins; strategy; the vault check; submit and accept. Our backend executes them, so
  merchant data and credentials never enter the agent's sandbox.
- **Sandbox work**: Capy writes a reportlab script, runs it with `exec`, and publishes `argument.pdf` with
  `artifact_publish`; the backend downloads the artifact, checks every citation and seals the packet.
- **`always_ask` permission** on `submit_evidence` and `accept_dispute`: the agent pauses on ZooWork's approval gate
  (`agent.approval`) until the merchant clicks Approve, which resolves it through the approvals API.
- **Outcome-labelled trajectories**: each dispute ends won, lost or accepted, which is exactly the signal ZooWork's
  trajectory and evaluation story needs. Sweeps are also recorded for replay.

### Band: the collaboration network
- **Two external agents registered with the merchant's Band key**: Inspector Capy and the **ShipCo Warehouse** partner.
  Both connect to Band's WebSocket through the Band SDK.
- **One Band room per dispute** with a room goal. Capy adds ShipCo to the room only when it needs delivery evidence,
  asks by @mention, and ShipCo answers with scans, GPS and the driver photo.
- **The merchant is a human participant.** Capy's questions are Band *attention* items; the merchant answers in the
  Band app or the dashboard, and the answer is posted to Band as the merchant.
- **Audit trail**: pins, strategy, vault checks, submissions and issuer rulings are all posted to the room.

---
The merchant, orders and disputes are fictional, and the card issuer is simulated so it rules in seconds instead of
weeks. Details and setup: [`docs/SETUP.md`](docs/SETUP.md).
