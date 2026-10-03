"""Narration for the demo video. 'capy' lines are Inspector Capy's own voice."""

LINES = {
    "title": ("narrator", "Meet Chargeback Capy, an AI detective that wins back the money online shops lose to chargebacks."),
    "problem": (
        "narrator",
        "A chargeback costs the sale, the goods and a fee. The evidence is scattered, the deadlines are short, "
        "and often the customer really did get their order. So most small shops never fight back.",
    ),
    "inbox": ("narrator", "Hot Spring Supply has five open disputes, eighteen hundred dollars at risk, and every deadline is ticking."),
    "capy_go": ("capy", "Right. Let's have a look, shall we?"),
    "zoowork": (
        "narrator",
        "Inspector Capy is a ZooWork managed agent. Every dispute gets its own session, running in parallel, and Capy "
        "reads the shop's records through custom tools, so no credentials ever enter its sandbox.",
    ),
    "band": (
        "narrator",
        "Some proof lives at another company. In a Band case room, Capy asks the ShipCo warehouse's agent for proof of "
        "delivery, and gets back the scan history and a GPS-stamped photo of the parcel on the porch.",
    ),
    "board": (
        "narrator",
        "Every fact becomes a vault exhibit, pinned to the board with the point it proves. The cardholder said it never "
        "arrived. Two days after delivery, they emailed the shop asking for the parka in another colour.",
    ),
    "vault": (
        "narrator",
        "Capy writes its argument as a PDF inside the ZooWork sandbox. The vault checks every finding: no source, no "
        "claim. Then it attaches the original exhibits, untouched, each sealed with a SHA-256 fingerprint.",
    ),
    "honest": (
        "narrator",
        "Capy is honest, too. This customer cancelled before the renewal, and our billing bug charged them anyway. "
        "So Capy recommends a refund instead of a losing fight.",
    ),
    "question": (
        "narrator",
        "Meanwhile, on the rain jacket case, Capy needs something only the merchant has, so it asks in the room. "
        "I share the lab report proving the jacket really is waterproof.",
    ),
    "approval": (
        "narrator",
        "And nothing moves money without me. ZooWork's approval gate pauses the agent until I review the packet: "
        "the argument up front, then the original evidence.",
    ),
    "submitted": (
        "narrator",
        "Approved. Capy submits the packet to the card issuer, simulated here so it rules in seconds instead of weeks.",
    ),
    "capy_won": ("capy", "Case closed."),
    "rest": ("narrator", "The other packets get the same review: one look, one click each."),
    "results": (
        "narrator",
        "The issuer rules for us. Four disputes won, one honest refund, and eighteen hundred and forty-two dollars "
        "recovered. Capy only earns when the merchant wins.",
    ),
    "architecture": (
        "narrator",
        "Under the hood, ZooWork runs the agent loop, the sandbox and the approval gate, and keeps every run as a "
        "replayable trajectory. Band connects Capy to partner agents and to the merchant, with consent and a full audit trail.",
    ),
    "closing": ("narrator", "Chargeback Capy. Fight every dispute worth fighting, and pay only when you win."),
}

SFX = {
    "stamp": ("a heavy rubber stamp slammed onto paper on a wooden desk, single firm thud", 1.2),
    "chaching": ("a cheerful cash register cha-ching with coins, short", 1.4),
    "whoosh": ("a soft airy page-turn whoosh transition, gentle", 0.9),
}

MUSIC = (
    "cozy playful detective theme for a cute capybara mystery, lo-fi jazz, pizzicato strings, soft brushed drums, "
    "warm upright bass, vibraphone accents, light and curious, steady and unobtrusive under narration, instrumental, no vocals"
)
