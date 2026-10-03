import { useId } from 'react'

export type Mood = 'idle' | 'search' | 'wait' | 'happy' | 'sad' | 'sleep'
type Hat = 'deerstalker' | 'courier' | 'towel'

interface HeadProps {
  hat: Hat
  mood?: Mood
  uid: string
}

/** Capybara head in a 240x240 box (head occupies roughly y 20..200). */
function Head({ hat, mood = 'idle', uid }: HeadProps) {
  const fur = `fur-${uid}`
  const plaid = `plaid-${uid}`
  const eyes = (() => {
    if (mood === 'happy')
      return (
        <g stroke="#26170d" strokeWidth="5" strokeLinecap="round" fill="none">
          <path d="M77 118 Q86 106 95 118" />
          <path d="M145 118 Q154 106 163 118" />
        </g>
      )
    if (mood === 'sleep' || mood === 'wait')
      return (
        <g stroke="#26170d" strokeWidth="4.5" strokeLinecap="round" fill="none">
          <path d="M77 117 Q86 124 95 117" />
          <path d="M145 117 Q154 124 163 117" />
        </g>
      )
    return (
      <g>
        <ellipse className={mood === 'search' ? 'capy-eyes-look' : 'capy-blink'} cx="86" cy="116" rx="8.5" ry="9.5" fill="#26170d" />
        <ellipse className={mood === 'search' ? 'capy-eyes-look' : 'capy-blink'} cx="154" cy="116" rx="8.5" ry="9.5" fill="#26170d" />
        <circle cx="89.5" cy="112" r="3" fill="#fff" />
        <circle cx="157.5" cy="112" r="3" fill="#fff" />
        {mood === 'sad' && (
          <g stroke="#5b3a22" strokeWidth="3.5" strokeLinecap="round">
            <path d="M74 100 L94 105" />
            <path d="M166 100 L146 105" />
          </g>
        )}
      </g>
    )
  })()
  const mouth =
    mood === 'happy' ? (
      <path d="M104 164 Q120 186 136 164 Z" fill="#5b2f22" stroke="#3a2416" strokeWidth="3" strokeLinejoin="round" />
    ) : mood === 'sad' ? (
      <path d="M108 174 Q120 164 132 174" stroke="#3a2416" strokeWidth="3.2" fill="none" strokeLinecap="round" />
    ) : (
      <path d="M108 168 Q120 177 132 168" stroke="#3a2416" strokeWidth="3.2" fill="none" strokeLinecap="round" />
    )
  return (
    <g>
      <defs>
        <linearGradient id={fur} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#b9845a" />
          <stop offset="1" stopColor="#9a6a41" />
        </linearGradient>
        <pattern id={plaid} width="16" height="16" patternUnits="userSpaceOnUse">
          <rect width="16" height="16" fill="#c9a26b" />
          <rect width="16" height="5" y="5" fill="#a97e4a" opacity="0.7" />
          <rect width="5" height="16" x="5" fill="#a97e4a" opacity="0.7" />
          <rect width="16" height="1.5" y="12" fill="#7b5530" opacity="0.6" />
          <rect width="1.5" height="16" x="12" fill="#7b5530" opacity="0.6" />
        </pattern>
      </defs>
      <ellipse cx="62" cy="84" rx="15" ry="13" fill="#7f5434" />
      <ellipse cx="62" cy="86" rx="7" ry="6" fill="#e9a99a" />
      <ellipse cx="178" cy="84" rx="15" ry="13" fill="#7f5434" />
      <ellipse cx="178" cy="86" rx="7" ry="6" fill="#e9a99a" />
      <rect x="48" y="70" width="144" height="128" rx="62" fill={`url(#${fur})`} />
      <rect x="68" y="124" width="104" height="74" rx="36" fill="#8d5d39" />
      <ellipse cx="102" cy="146" rx="8" ry="4.5" fill="#3a2416" />
      <ellipse cx="138" cy="146" rx="8" ry="4.5" fill="#3a2416" />
      {mouth}
      {eyes}
      <ellipse cx="70" cy="140" rx="12" ry="7" fill="#f3998a" opacity={mood === 'happy' ? 0.85 : 0.55} />
      <ellipse cx="170" cy="140" rx="12" ry="7" fill="#f3998a" opacity={mood === 'happy' ? 0.85 : 0.55} />
      {hat === 'deerstalker' && (
        <g>
          <path d="M150 74 C176 70 200 78 206 88 C190 88 170 86 150 84 Z" fill="#9c7243" />
          <path d="M60 80 C60 40 92 22 120 22 C148 22 180 40 180 80 C150 72 90 72 60 80 Z" fill={`url(#${plaid})`} stroke="#6e4c28" strokeWidth="2.5" />
          <path d="M86 78 C70 80 46 86 34 96 C52 98 74 94 92 86 Z" fill="#9c7243" stroke="#6e4c28" strokeWidth="2" />
          <path d="M120 22 C122 40 122 60 120 76" stroke="#6e4c28" strokeWidth="2" fill="none" opacity="0.6" />
          <path d="M112 24 C104 14 98 12 96 16 C96 22 106 24 116 26 Z" fill="#9c7243" stroke="#6e4c28" strokeWidth="1.5" />
          <path d="M128 24 C136 14 142 12 144 16 C144 22 134 24 124 26 Z" fill="#9c7243" stroke="#6e4c28" strokeWidth="1.5" />
          <circle cx="120" cy="24" r="5" fill="#6e4c28" />
          <circle cx="160" cy="44" r="11" fill="#ffc531" />
          <circle cx="157" cy="41" r="3" fill="#fff1b0" opacity="0.8" />
          <path d="M160 33 C163 28 170 27 172 30 C168 33 164 34 160 33 Z" fill="#62b35a" />
        </g>
      )}
      {hat === 'courier' && (
        <g>
          <path d="M62 82 C60 44 90 30 120 30 C150 30 180 44 178 82 C150 74 90 74 62 82 Z" fill="#2f8f86" stroke="#1f6660" strokeWidth="2.5" />
          <path d="M150 76 C176 74 204 82 210 92 C188 94 166 90 146 84 Z" fill="#23736c" stroke="#1f6660" strokeWidth="2" />
          <circle cx="120" cy="54" r="13" fill="#ffc531" stroke="#1f6660" strokeWidth="2" />
          <text x="120" y="60" textAnchor="middle" fontFamily="Fredoka, sans-serif" fontWeight="700" fontSize="16" fill="#1f6660">S</text>
        </g>
      )}
      {hat === 'towel' && (
        <g>
          <path d="M70 66 C70 46 96 40 120 40 C146 40 172 46 170 66 C170 76 150 80 120 80 C92 80 70 76 70 66 Z" fill="#fdfaf3" stroke="#d9cdb8" strokeWidth="2.5" />
          <path d="M84 52 H156 M82 62 H158" stroke="#7ec8c0" strokeWidth="4" strokeLinecap="round" />
        </g>
      )}
    </g>
  )
}

export function InspectorCapy({ mood = 'idle', size = 160, className }: { mood?: Mood; size?: number; className?: string }) {
  const uid = useId().replace(/:/g, '')
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 240 240" role="img" aria-label="Inspector Capy">
      <defs>
        <linearGradient id={`lens-${uid}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#e9fbff" />
          <stop offset="1" stopColor="#9fd8e6" />
        </linearGradient>
      </defs>
      <path d="M28 240 C34 196 76 182 120 182 C164 182 206 196 212 240 Z" fill="#c8995f" />
      <path d="M28 240 C40 205 70 196 96 196 L120 240 Z" fill="#b3864f" />
      <path d="M212 240 C200 205 170 196 144 196 L120 240 Z" fill="#b3864f" />
      <path d="M96 196 L120 226 L144 196 C136 190 104 190 96 196 Z" fill="#f4ead8" />
      <Head hat="deerstalker" mood={mood} uid={uid} />
      <g className={mood === 'search' ? 'capy-magnifier-search' : mood === 'happy' ? 'capy-magnifier-up' : undefined}>
        <g transform="rotate(-24 196 170)">
          <rect x="190" y="182" width="12" height="46" rx="6" fill="#6e4c28" />
          <circle cx="196" cy="160" r="27" fill={`url(#lens-${uid})`} opacity="0.92" />
          <circle cx="196" cy="160" r="27" fill="none" stroke="#e1a83a" strokeWidth="7" />
          <path d="M182 150 C186 142 194 138 202 139" stroke="#fff" strokeWidth="4" fill="none" strokeLinecap="round" opacity="0.9" />
        </g>
        <ellipse cx="190" cy="214" rx="15" ry="11" fill="#9a6a41" />
      </g>
    </svg>
  )
}

export function ShipCoCapy({ size = 40, mood = 'idle' }: { size?: number; mood?: Mood }) {
  const uid = useId().replace(/:/g, '')
  return (
    <svg width={size} height={size} viewBox="0 0 240 240" role="img" aria-label="ShipCo courier capybara">
      <path d="M36 240 C42 200 80 186 120 186 C160 186 198 200 204 240 Z" fill="#2f8f86" />
      <Head hat="courier" mood={mood} uid={uid} />
      <g transform="translate(150 178)">
        <rect width="62" height="50" rx="4" fill="#d29a5c" stroke="#9c6a35" strokeWidth="3" />
        <rect x="26" width="10" height="50" fill="#ecd3a6" />
      </g>
    </svg>
  )
}

export function MerchantCapy({ size = 40, mood = 'idle' }: { size?: number; mood?: Mood }) {
  const uid = useId().replace(/:/g, '')
  return (
    <svg width={size} height={size} viewBox="0 0 240 240" role="img" aria-label="You, the shopkeeper">
      <path d="M36 240 C42 200 80 186 120 186 C160 186 198 200 204 240 Z" fill="#6aa86b" />
      <path d="M92 192 H148 V240 H92 Z" fill="#fdfaf3" opacity="0.9" />
      <Head hat="towel" mood={mood} uid={uid} />
    </svg>
  )
}

export function CapyAvatar({ who, size = 36 }: { who: string; size?: number }) {
  const inner =
    who === 'shipco' ? (
      <ShipCoCapy size={size * 1.25} />
    ) : who === 'merchant' ? (
      <MerchantCapy size={size * 1.25} />
    ) : (
      <InspectorCapy size={size * 1.25} />
    )
  return (
    <span className={`avatar avatar-${who}`} style={{ width: size, height: size }}>
      {inner}
    </span>
  )
}
