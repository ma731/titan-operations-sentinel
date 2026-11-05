"""Pre-record Titan's lines with a free neural voice (Microsoft Edge TTS).

    pip install edge-tts
    python scripts/build_titan_voice.py

Reads every line Titan can say (written answers + action replies) from the frontend,
renders the ones not yet recorded to webapp/frontend/public/voice/<hash>.mp3, and writes
webapp/frontend/src/voiceManifest.json (text -> file). Re-run after editing any line.
"""
import asyncio
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "webapp" / "frontend"
OUT = FRONT / "public" / "voice"
MANIFEST = FRONT / "src" / "voiceManifest.json"
VOICE = "en-US-AvaNeural"   # warm, natural; slowed a little so it sounds calm
RATE, PITCH = "-6%", "-2Hz"


def spoken(text: str) -> str:
    # "€3,200" reads as "3,200 euros", "€870k" as "870 thousand euros"; quote marks dropped.
    text = re.sub(r"€([\d,.]+)k\b", r"\1 thousand euros", text)
    text = re.sub(r"€([\d,.]+)", r"\1 euros", text)
    return text.replace('"', "")


async def render(text: str, path: Path) -> None:
    await edge_tts.Communicate(spoken(text), VOICE, rate=RATE, pitch=PITCH).save(str(path))


async def main() -> None:
    texts = json.loads(subprocess.run(["node", str(FRONT / "scripts" / "voice-texts.mjs")],
                                      capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, todo = {}, []
    for t in texts:
        name = hashlib.sha1(f"{VOICE}|{RATE}|{PITCH}|{spoken(t)}".encode()).hexdigest()[:12] + ".mp3"
        manifest[t] = name
        if not (OUT / name).exists():
            todo.append((t, OUT / name))
    for i in range(0, len(todo), 6):
        await asyncio.gather(*(render(t, p) for t, p in todo[i:i + 6]))
    keep = set(manifest.values())
    for f in OUT.glob("*.mp3"):
        if f.name not in keep:
            f.unlink()
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(texts)} lines, {len(todo)} recorded now, voice {VOICE}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
