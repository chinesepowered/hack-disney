"""ElevenLabs helpers: narration (TTS), sound effects and a music bed, cached on disk."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import httpx

API = "https://api.elevenlabs.io/v1"
VOICES = {
    # narrator: bright and warm; Inspector Capy: a British storyteller, very detective
    "narrator": os.getenv("ELEVEN_NARRATOR_VOICE", "cgSgspJ2msm6clMCkdW9"),  # Jessica
    "capy": os.getenv("ELEVEN_CAPY_VOICE", "JBFqnCBsd6RMkjVDRZzb"),  # George
}
MODEL = os.getenv("ELEVEN_MODEL", "eleven_multilingual_v2")
SETTINGS = {
    "narrator": {"stability": 0.42, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True},
    "capy": {"stability": 0.38, "similarity_boost": 0.8, "style": 0.55, "use_speaker_boost": True},
}


def _key() -> str:
    key = os.getenv("ELEVENLABS_API_KEY", "")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    return key


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def _cached(out_dir: Path, kind: str, payload: dict) -> Path:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    return out_dir / f"{kind}-{digest}.mp3"


def speak(text: str, voice: str, out_dir: Path) -> Path:
    payload = {"text": text, "model_id": MODEL, "voice_settings": SETTINGS[voice], "voice": VOICES[voice]}
    target = _cached(out_dir, f"tts-{voice}", payload)
    if target.exists():
        return target
    response = httpx.post(
        f"{API}/text-to-speech/{VOICES[voice]}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": _key()},
        json={"text": text, "model_id": MODEL, "voice_settings": SETTINGS[voice]},
        timeout=120,
    )
    response.raise_for_status()
    target.write_bytes(response.content)
    return target


def sound(prompt: str, seconds: float, out_dir: Path) -> Path:
    payload = {"text": prompt, "duration_seconds": seconds, "prompt_influence": 0.6}
    target = _cached(out_dir, "sfx", payload)
    if target.exists():
        return target
    response = httpx.post(f"{API}/sound-generation", headers={"xi-api-key": _key()}, json=payload, timeout=120)
    response.raise_for_status()
    target.write_bytes(response.content)
    return target


def music(prompt: str, seconds: float, out_dir: Path) -> Path:
    payload = {"prompt": prompt, "music_length_ms": int(seconds * 1000)}
    target = _cached(out_dir, "music", payload)
    if target.exists():
        return target
    response = httpx.post(f"{API}/music", headers={"xi-api-key": _key()}, json=payload, timeout=600)
    response.raise_for_status()
    target.write_bytes(response.content)
    return target


def align(audio: Path, text: str) -> list[dict]:
    """Word timings for a narration clip (ElevenLabs forced alignment), cached next to the clip."""
    target = audio.with_suffix(".words.json")
    if target.exists():
        return json.loads(target.read_text())
    with audio.open("rb") as fh:
        response = httpx.post(
            f"{API}/forced-alignment",
            headers={"xi-api-key": _key()},
            files={"file": (audio.name, fh, "audio/mpeg")},
            data={"text": text},
            timeout=120,
        )
    response.raise_for_status()
    words = [{"text": w["text"], "start": w["start"], "end": w["end"]} for w in response.json()["words"] if w["text"].strip()]
    target.write_text(json.dumps(words))
    return words
