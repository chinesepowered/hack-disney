import { motion } from 'framer-motion'
import { InspectorCapy, MerchantCapy, ShipCoCapy } from './Capys'

const fade = { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0.7 } }
const rise = (delay: number) => ({
  initial: { opacity: 0, y: 28 },
  animate: { opacity: 1, y: 0 },
  transition: { delay, duration: 0.7, ease: [0.22, 1, 0.36, 1] as const },
})

function Steam() {
  return (
    <div className="card-steam">
      {Array.from({ length: 9 }).map((_, i) => (
        <span key={i} style={{ left: `${8 + i * 10.5}%`, animationDelay: `${(i % 4) * 0.9}s` }} />
      ))}
    </div>
  )
}

function Sponsors() {
  return (
    <div className="card-sponsors">
      <span className="pill pill-zoo live">
        <span className="dot" /> ZooWork managed agents
      </span>
      <span className="pill pill-band live">
        <span className="dot" /> Band agent rooms
      </span>
    </div>
  )
}

function Title() {
  return (
    <div className="card card-title">
      <Steam />
      <motion.div {...rise(0.1)} className="card-hero-capy">
        <InspectorCapy size={470} mood="search" />
      </motion.div>
      <div className="card-copy">
        <motion.div {...rise(0.3)} className="card-kicker">
          Capybara Investigations presents
        </motion.div>
        <motion.h1 {...rise(0.45)}>Chargeback Capy</motion.h1>
        <motion.p {...rise(0.7)}>The AI detective that wins back the money merchants lose to chargebacks.</motion.p>
        <motion.div {...rise(1)}>
          <Sponsors />
        </motion.div>
      </div>
    </div>
  )
}

function Problem() {
  const items = [
    { icon: '🧩', title: 'Evidence is scattered', text: 'Orders, carrier scans, support inboxes, lab reports: five systems, two companies.' },
    { icon: '⏳', title: 'Deadlines are short', text: 'Days to respond, a different rulebook for every reason code.' },
    { icon: '🎭', title: 'Friendly fraud', text: 'The customer got the item, then told their bank it never came.' },
  ]
  return (
    <div className="card card-problem">
      <motion.h2 {...rise(0.1)}>Chargebacks quietly drain small shops</motion.h2>
      <motion.p {...rise(0.25)} className="card-sub">
        Each one costs the sale, the goods and a fee. Most small merchants never fight back.
      </motion.p>
      <div className="problem-grid">
        {items.map((it, i) => (
          <motion.div key={it.title} className="problem-item" {...rise(0.45 + i * 0.2)}>
            <div className="problem-icon">{it.icon}</div>
            <h3>{it.title}</h3>
            <p>{it.text}</p>
          </motion.div>
        ))}
      </div>
      <motion.div {...rise(1.2)} className="problem-capy">
        <InspectorCapy size={200} mood="sad" />
      </motion.div>
    </div>
  )
}

function Box({ title, children, tone, delay }: { title: string; children: React.ReactNode; tone: string; delay: number }) {
  return (
    <motion.div className={`arch-box ${tone}`} {...rise(delay)}>
      <h4>{title}</h4>
      {children}
    </motion.div>
  )
}

function Architecture() {
  return (
    <div className="card card-arch">
      <motion.h2 {...rise(0.05)}>How Chargeback Capy works</motion.h2>
      <div className="arch-grid">
        <Box title="🏪 Merchant systems" tone="cream" delay={0.2}>
          <ul>
            <li>Orders & payments</li>
            <li>Support inbox</li>
            <li>Billing & refunds</li>
          </ul>
          <div className="arch-note">Credentials stay in the merchant's backend</div>
        </Box>
        <motion.div className="arch-arrow" {...rise(0.35)}>
          custom tools ⇄
        </motion.div>
        <Box title="🧠 ZooWork managed agent" tone="zoo" delay={0.45}>
          <div className="arch-capy">
            <InspectorCapy size={110} mood="search" />
          </div>
          <ul>
            <li>One session per dispute, in parallel</li>
            <li>13 custom tools, sandbox builds the PDF</li>
            <li>always_ask approval before money moves</li>
            <li>Every run kept as a replayable trajectory</li>
          </ul>
        </Box>
        <motion.div className="arch-arrow" {...rise(0.6)}>
          ⇄ @mentions
        </motion.div>
        <Box title="💬 Band case rooms" tone="band" delay={0.7}>
          <div className="arch-capys">
            <ShipCoCapy size={84} />
            <MerchantCapy size={84} />
          </div>
          <ul>
            <li>ShipCo warehouse agent shares proof</li>
            <li>Merchant answers attention items</li>
            <li>Consent between companies, full audit trail</li>
          </ul>
        </Box>
      </div>
      <motion.div className="arch-bottom" {...rise(0.95)}>
        <div className="arch-pill">🔐 Evidence vault: originals sealed with SHA-256 · no source, no claim</div>
        <div className="arch-pill">📨 Card processor: packet submitted, issuer rules</div>
        <div className="arch-pill">💸 Capy earns 20% of recovered dollars only</div>
      </motion.div>
    </div>
  )
}

function Closing() {
  return (
    <div className="card card-title card-closing">
      <Steam />
      <motion.div {...rise(0.1)} className="card-hero-capy">
        <InspectorCapy size={430} mood="happy" />
      </motion.div>
      <div className="card-copy">
        <motion.div {...rise(0.3)} className="card-kicker">
          Case closed
        </motion.div>
        <motion.h1 {...rise(0.45)}>Chargeback Capy</motion.h1>
        <motion.p {...rise(0.7)}>Fight every dispute worth fighting. Pay only when you win.</motion.p>
        <motion.div {...rise(1)}>
          <Sponsors />
        </motion.div>
      </div>
    </div>
  )
}

const CARDS: Record<string, () => JSX.Element> = { title: Title, problem: Problem, architecture: Architecture, closing: Closing }

export function StoryCard({ name }: { name: string }) {
  const Card = CARDS[name]
  if (!Card) return null
  return (
    <motion.div className="card-layer" {...fade}>
      <Card />
    </motion.div>
  )
}
