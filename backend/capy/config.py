"""Runtime configuration.

Each sponsor integration switches on when its key is present. With no keys the
whole sweep still runs: a scripted inspector drives the same tools, Band
messages stay local, and the dashboard receives identical events.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
PACKAGE_ROOT = BACKEND_ROOT / "capy"
ASSETS = PACKAGE_ROOT / "assets"
FONTS = ASSETS / "fonts"
STATE_DIR = BACKEND_ROOT / ".state"  # provisioned agent ids/keys (gitignored)
RUNS_DIR = BACKEND_ROOT / "runs"  # recorded sweeps for replay (gitignored)
OUTPUT_DIR = BACKEND_ROOT / "output"  # packets, previews (gitignored)
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _mode(name: str) -> str:
    value = _env(name, "auto").lower()
    return value if value in {"auto", "on", "off"} else "auto"


@dataclass(frozen=True)
class Settings:
    zoowork_api_key: str = field(default_factory=lambda: _env("ZOOWORK_API_KEY"))
    zoowork_base_url: str = field(default_factory=lambda: _env("ZOOWORK_BASE_URL"))
    zoowork_model: str = field(
        default_factory=lambda: _env("ZOOWORK_MODEL", "litellm/claude-sonnet-5")
    )
    band_api_key: str = field(default_factory=lambda: _env("BAND_API_KEY"))
    band_rest_url: str = field(default_factory=lambda: _env("BAND_REST_URL", "https://app.band.ai"))
    band_ws_url: str = field(
        default_factory=lambda: _env("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket")
    )
    elevenlabs_api_key: str = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))

    zoowork_mode: str = field(default_factory=lambda: _mode("CAPY_ZOOWORK"))
    band_mode: str = field(default_factory=lambda: _mode("CAPY_BAND"))

    # Multiplier for the scripted inspector's pauses; 0 makes simulated sweeps instant.
    pace: float = field(default_factory=lambda: float(_env("CAPY_PACE", "1") or 1))
    # Seconds the simulated issuer "reviews" a packet before ruling.
    issuer_delay: float = field(default_factory=lambda: float(_env("CAPY_ISSUER_DELAY", "4") or 4))

    @property
    def zoowork_live(self) -> bool:
        if self.zoowork_mode == "off":
            return False
        if self.zoowork_mode == "on" and not self.zoowork_api_key:
            raise RuntimeError("CAPY_ZOOWORK=on but ZOOWORK_API_KEY is not set")
        return bool(self.zoowork_api_key)

    @property
    def band_live(self) -> bool:
        if self.band_mode == "off":
            return False
        if self.band_mode == "on" and not self.band_api_key:
            raise RuntimeError("CAPY_BAND=on but BAND_API_KEY is not set")
        return bool(self.band_api_key)


def load_settings() -> Settings:
    return Settings()
