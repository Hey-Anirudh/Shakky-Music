# shakky/utils/effects.py
# Per-chat live audio effect presets. Each preset expands to an ffmpeg -af
# filter chain that build_stream() appends so playback applies EQ / speed /
# nightcore / echo etc. without re-downloading anything.

import logging

LOGGER = logging.getLogger(__name__)

# chat_id -> effect name ("" = none)
_in_chat = {}
# chat_id -> bool: smooth fade-in on each new track
_crossfade = {}
CROSSFADE_SEC = 1.5

EFFECTS = {
    "": "",
    "boost": "bass=g=12:f=110:w=0.4,treble=g=6",
    "lows": "bass=g=16:f=60",
    "vibes": "bass=g=8:f=100:v=0.6,treble=g=4,apulsator=hz=0.5",
    "nightcore": "atempo=1.3,asetrate=44100*1.1,aresample=44100",
    "speed": "atempo=1.3",
    "slow": "atempo=0.85",
    "dvd": "atempo=2.0",
    "echo": "aecho=0.8:0.9:500|1000:0.3|0.25",
    "karaoke": "lowpass=f=700,highpass=f=200,volume=0.9",
    "3d": "apulsator=hz=0.9",
    "muff": "lowpass=f=1800",
    "mute": "volume=0.0",
}

PRESET_NAMES = {
    "": "Off",
    "boost": "Bass Boost",
    "lows": "Deep Bass",
    "vibes": "Cafe Vibes",
    "nightcore": "Nightcore",
    "speed": "Fast (1.3x)",
    "slow": "Slow (0.85x)",
    "dvd": "DVD Mode (2x)",
    "echo": "Echo Hall",
    "karaoke": "Karaoke",
    "3d": "3D Panned",
    "muff": "Muffled",
    "mute": "Mute",
}


def current(chat_id):
    return _in_chat.get(chat_id, "")


def set_effect(chat_id: int, name: str):
    name = name or ""
    if name not in EFFECTS:
        return False
    _in_chat[chat_id] = name
    return True


def set_speed(chat_id: int, speed: float):
    """Apply an arbitrary atempo (0.5x-2.0x). Returns the filter string."""
    speed = max(0.5, min(2.0, float(speed)))
    if abs(speed - 1.0) < 0.05:
        clear(chat_id)
        return ""
    _in_chat[chat_id] = f"atempo={speed:.2f}"
    return _in_chat[chat_id]


def clear(chat_id: int):
    _in_chat.pop(chat_id, None)


def get_filter(chat_id: int) -> str:
    """Return the ffmpeg -af chain for this chat ('' = no effect)."""
    name = _in_chat.get(chat_id, "")
    return EFFECTS.get(name, "")


def crossfade_enabled(chat_id) -> bool:
    return bool(_crossfade.get(chat_id, False))


def set_crossfade(chat_id: int, enabled: bool):
    _crossfade[chat_id] = bool(enabled)


def build_af(chat_id: int, ss: float = 0) -> str:
    """Full -af chain for a stream: chat effect + optional crossfade fade-in.

    Fade-in is only applied at the true start of a track (ss == 0).
    """
    parts = [p for p in [get_filter(chat_id)] if p]
    if crossfade_enabled(chat_id) and not ss:
        parts.append(f"afade=t=in:d={CROSSFADE_SEC}")
    return ",".join(parts)