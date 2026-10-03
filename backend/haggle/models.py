"""Plain data types shared by the engine, brains and transports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class Brief:
    item: str
    budget: float
    prefs: list[str] = field(default_factory=list)
    notes: str = ""
    deadline: str = "this week"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Research:
    low: float
    high: float
    typical: float
    sources: list[dict[str, Any]] = field(default_factory=list)
    prefs: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Extra:
    name: str
    value: float

    def to_list(self) -> list[Any]:
        return [self.name, self.value]


@dataclass
class Listing:
    seller: str
    title: str
    condition: str
    defects: list[str]
    ask: float
    floor: float  # secret: the seller never goes below this
    included: list[Extra] = field(default_factory=list)
    extras_pool: list[Extra] = field(default_factory=list)  # sweeteners a bundler can add


@dataclass
class Offer:
    seller: str
    price: float
    condition: str
    extras: list[Extra] = field(default_factory=list)
    defects: list[str] = field(default_factory=list)
    final: bool = False
    deal: bool = False
    walked: bool = False
    round: int = 0

    @property
    def extras_value(self) -> float:
        return sum(extra.value for extra in self.extras)

    @property
    def effective(self) -> float:
        """Price minus the value of the extras thrown in."""
        return self.price - self.extras_value

    def to_dict(self) -> dict[str, Any]:
        return {
            "seller": self.seller,
            "price": self.price,
            "condition": self.condition,
            "extras": [extra.to_list() for extra in self.extras],
            "extras_value": self.extras_value,
            "effective": self.effective,
            "defects": list(self.defects),
            "final": self.final,
            "deal": self.deal,
            "walked": self.walked,
            "round": self.round,
        }


BuyerKind = Literal["inquiry", "counter", "accept", "decline"]


@dataclass
class BuyerMove:
    """What Yuzu says to one seller."""

    seller: str
    kind: BuyerKind
    text: str
    price: float | None = None
    round: int = 0


@dataclass
class SellerReply:
    seller: str
    text: str
    offer: Offer


@dataclass
class Decision:
    winner: str | None
    price: float | None
    reason: str
    ranking: list[dict[str, Any]] = field(default_factory=list)
