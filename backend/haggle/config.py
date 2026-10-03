"""Runtime configuration.

Every sponsor integration is optional. With no keys at all the app runs a fully
simulated deal that emits the same events as the live integrations, so the
dashboard and the demo video never depend on the network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
RUNS_DIR = BACKEND_ROOT / "runs"
ARTIFACTS_DIR = BACKEND_ROOT / "artifacts"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

load_dotenv(REPO_ROOT / ".env")

SELLER_KEYS = ("mochi", "baron", "pickles")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _flag(name: str, default: bool = False) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BandAgentCreds:
    agent_id: str
    api_key: str

    @property
    def ok(self) -> bool:
        return bool(self.agent_id and self.api_key)


@dataclass(frozen=True)
class Settings:
    # Band: one external agent per capybara (create them in the Band web app).
    band_rest_url: str = field(default_factory=lambda: _env("BAND_REST_URL", "https://app.band.ai"))
    band_ws_url: str = field(
        default_factory=lambda: _env("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket")
    )
    band_agents: dict[str, BandAgentCreds] = field(
        default_factory=lambda: {
            key: BandAgentCreds(
                _env(f"BAND_{key.upper()}_AGENT_ID"), _env(f"BAND_{key.upper()}_API_KEY")
            )
            for key in ("yuzu", *SELLER_KEYS)
        }
    )
    # Run the three seller agents inside this process. Set to false when teammates
    # run their sellers on their own machines with scripts/run_seller.py.
    band_local_sellers: bool = field(default_factory=lambda: _flag("BAND_LOCAL_SELLERS", True))

    # ZooWork managed agents (Yuzu's back office: research, memory, checkout).
    zoowork_api_key: str = field(default_factory=lambda: _env("ZOOWORK_API_KEY"))
    zoowork_base_url: str = field(default_factory=lambda: _env("ZOOWORK_BASE_URL"))
    zoowork_agent_id: str = field(default_factory=lambda: _env("ZOOWORK_AGENT_ID"))
    zoowork_model: str = field(default_factory=lambda: _env("ZOOWORK_MODEL"))

    # Claude powers the negotiating brains when present; otherwise scripted brains.
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    claude_model: str = field(default_factory=lambda: _env("CLAUDE_MODEL", "claude-sonnet-5-5"))

    # ElevenLabs gives the capybaras their voices (dashboard + demo video).
    elevenlabs_api_key: str = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))

    # Feature switches. "auto" means: live if the keys are present.
    band_mode: str = field(default_factory=lambda: _env("HAGGLE_BAND", "auto"))
    zoowork_mode: str = field(default_factory=lambda: _env("HAGGLE_ZOOWORK", "auto"))
    brain_mode: str = field(default_factory=lambda: _env("HAGGLE_BRAIN", "auto"))

    # Seconds multiplier for simulated pauses (typing, thinking). 0 = instant.
    pace: float = field(default_factory=lambda: float(_env("HAGGLE_PACE", "1.0") or 1.0))

    @property
    def band_live(self) -> bool:
        if self.band_mode == "off":
            return False
        ready = self.band_agents["yuzu"].ok and (
            not self.band_local_sellers or all(self.band_agents[k].ok for k in SELLER_KEYS)
        )
        if self.band_mode == "on" and not ready:
            raise RuntimeError("HAGGLE_BAND=on but Band agent ids/keys are missing in .env")
        return ready

    @property
    def zoowork_live(self) -> bool:
        if self.zoowork_mode == "off":
            return False
        if self.zoowork_mode == "on" and not self.zoowork_api_key:
            raise RuntimeError("HAGGLE_ZOOWORK=on but ZOOWORK_API_KEY is missing in .env")
        return bool(self.zoowork_api_key)

    @property
    def claude_live(self) -> bool:
        if self.brain_mode == "scripted":
            return False
        return bool(self.anthropic_api_key)

    def public_status(self) -> dict[str, object]:
        return {
            "band": "live" if self.band_live else "sim",
            "zoowork": "live" if self.zoowork_live else "sim",
            "brain": "claude" if self.claude_live else "scripted",
            "voices": bool(self.elevenlabs_api_key),
            "band_local_sellers": self.band_local_sellers,
        }


def load_settings() -> Settings:
    return Settings()
