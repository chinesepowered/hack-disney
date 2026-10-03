# 🔍 Chargeback Capy

**Chargeback Capy is an AI agent that fights card chargebacks for online merchants and wins back money they would otherwise lose.** Inspector Capy, a capybara detective, investigates every open dispute, gathers proof from the shop's own systems and from partner companies, and files an evidence packet once the merchant approves. Merchants pay only a share of what it recovers.

[![Watch the Chargeback Capy demo on YouTube](https://img.youtube.com/vi/hy5D2LYdi30/maxresdefault.jpg)](https://www.youtube.com/watch?v=hy5D2LYdi30)

**▶ [Watch the 3-minute demo on YouTube](https://www.youtube.com/watch?v=hy5D2LYdi30)**

**Try it:** [`offline.html`](offline.html) (download and open in any browser: replays a live run, no network needed) ·
[`slide.html`](slide.html) (4-slide pitch) · [`docs/SETUP.md`](docs/SETUP.md) (run it live)

## The problem

- **Every chargeback costs real money.** The merchant loses the sale, the goods and a dispute fee, often to "friendly fraud": the customer received the order, then told their bank it never arrived.
- **Fighting back is slow, manual work.** The evidence is spread across orders, payments, support inboxes and carrier systems, some of it at other companies, and every card-network reason code demands different proof on a tight deadline.
- **So small merchants rarely fight.** Without a disputes team, most chargebacks go unanswered and the money is simply gone.

## Our solution

Inspector Capy is a ZooWork managed agent that works every open dispute in parallel:

- **Investigates like a specialist.** It reads the order, payment checks, customer history, support emails and billing records through the merchant's own tools, and matches them to what each Visa reason code requires, such as Compelling Evidence 3.0 when a cardholder says "I didn't make this purchase".
- **Gathers proof across companies.** Each dispute gets a Band case room, where Capy asks the ShipCo warehouse's agent for delivery scans and a GPS-stamped photo, and asks the merchant when only they have the answer, like a lab report.
- **No source, no claim.** Capy writes its argument as a PDF in its sandbox. Every finding must cite a fingerprinted exhibit, and the vault attaches the untouched originals with SHA-256 hashes.
- **The merchant stays in control.** Nothing that moves money happens without the merchant's approval, and Capy recommends a refund when the shop is in the wrong.

![Chargeback Capy dashboard during a live run](docs/dashboard.jpg)

## Results

From a live run with the ZooWork agent and real Band rooms (Oct 3, 2026):

- **5 disputes** investigated in parallel in **about 90 seconds**.
- **4 fought and won** against the simulated issuer, recovering **$1,842**.
- **1 honest refund:** the customer had cancelled before renewal and a billing sync bug charged them anyway, so Capy recommended accepting the dispute.
- **Every finding** in every packet cited a fingerprinted exhibit.
- **Pay on win:** Capy's fee is 20% of recovered dollars ($368 in this run) and nothing when it loses.

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
