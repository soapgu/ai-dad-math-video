#!/usr/bin/env python3
"""生成最小开场样片的唯一 TTS 音频。"""

import asyncio
from pathlib import Path

import edge_tts


TEXT = "嗨，我是数字爸爸"
VOICE = "zh-CN-YunjianNeural"
RATE = "-15%"
OUTPUT_PATH = Path(__file__).parent / "tts" / "intro-tts-v1.mp3"


async def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    communicator = edge_tts.Communicate(TEXT, VOICE, rate=RATE)
    await communicator.save(str(OUTPUT_PATH))
    print(OUTPUT_PATH)


if __name__ == "__main__":
    asyncio.run(main())
