#!/usr/bin/env python3
"""生成第二段父子互动的唯一混合 TTS。"""

import asyncio
import json
import socket
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import edge_tts


SAMPLE_RATE = 24_000
BIT_RATE = "48k"
LEADING_SILENCE = 1.20
OUTPUT_DIR = Path(__file__).parent / "tts"
OUTPUT_STEM = "segment-02-tts-v1"


@dataclass(frozen=True)
class Line:
    label: str
    role: str
    voice: str
    text: str
    rate: str
    pause_after: float


LINES = (
    Line(
        "回顾问题",
        "数字爸爸",
        "zh-CN-YunjianNeural",
        "原来有几个呢？",
        "-15%",
        0.55,
    ),
    Line(
        "放回苹果",
        "数字爸爸",
        "zh-CN-YunjianNeural",
        "把拿走的三个放回来，",
        "-15%",
        0.35,
    ),
    Line(
        "合并苹果",
        "数字爸爸",
        "zh-CN-YunjianNeural",
        "再和剩下的五个合起来。",
        "-15%",
        0.80,
    ),
    Line(
        "儿子回答",
        "儿子",
        "zh-CN-YunxiaNeural",
        "一共是八个！",
        "-5%",
        0.55,
    ),
    Line(
        "确认规律",
        "数字爸爸",
        "zh-CN-YunjianNeural",
        "对，所以被减数等于差加减数。",
        "-15%",
        0.80,
    ),
)


def force_ipv4() -> None:
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = ipv4_getaddrinfo


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


async def synthesize(line: Line, output_path: Path) -> None:
    for attempt in range(3):
        try:
            output_path.unlink(missing_ok=True)
            await edge_tts.Communicate(
                line.text, line.voice, rate=line.rate
            ).save(str(output_path))
            return
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(1.5)


def trim_silence(input_path: Path, output_path: Path) -> None:
    audio_filter = (
        "silenceremove=start_periods=1:start_duration=0.05:"
        "start_threshold=-45dB,areverse,"
        "silenceremove=start_periods=1:start_duration=0.05:"
        "start_threshold=-45dB,areverse"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-af",
            audio_filter,
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def concatenate(line_paths: list[Path], output_path: Path) -> None:
    command = ["ffmpeg", "-y"]
    for path in line_paths:
        command.extend(["-i", str(path)])
    filters = [f"anullsrc=r={SAMPLE_RATE}:cl=mono:d={LEADING_SILENCE}[lead]"]
    concat_inputs = ["[lead]"]
    for index, line in enumerate(LINES):
        filters.append(
            f"anullsrc=r={SAMPLE_RATE}:cl=mono:d={line.pause_after}[pause{index}]"
        )
        concat_inputs.extend([f"[{index}:a]", f"[pause{index}]"])
    filters.append(
        "".join(concat_inputs)
        + f"concat=n={len(concat_inputs)}:v=0:a=1[out]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-b:a",
            BIT_RATE,
            str(output_path),
        ]
    )
    subprocess.run(command, check=True, capture_output=True)


def build_timing(durations: list[float], encoded_duration: float) -> dict:
    cursor = LEADING_SILENCE
    items = []
    for line, duration in zip(LINES, durations):
        start = cursor
        end = start + duration
        items.append(
            {
                "label": line.label,
                "role": line.role,
                "voice": line.voice,
                "text": line.text,
                "rate": line.rate,
                "pause_after_seconds": line.pause_after,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
            }
        )
        cursor = end + line.pause_after
    return {
        "output": f"{OUTPUT_STEM}.mp3",
        "sample_rate_hz": SAMPLE_RATE,
        "channels": 1,
        "leading_silence_seconds": LEADING_SILENCE,
        "lines": items,
        "timeline_total_seconds": round(cursor, 3),
        "encoded_total_seconds": round(encoded_duration, 3),
    }


async def main() -> None:
    force_ipv4()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="segment-02-tts-") as temp_dir:
        temp_root = Path(temp_dir)
        raw_paths = [temp_root / f"raw-{i}.mp3" for i in range(len(LINES))]
        line_paths = [temp_root / f"line-{i}.wav" for i in range(len(LINES))]
        for line, raw_path in zip(LINES, raw_paths):
            await synthesize(line, raw_path)
        for raw_path, line_path in zip(raw_paths, line_paths):
            trim_silence(raw_path, line_path)
        durations = [probe_duration(path) for path in line_paths]
        output_path = OUTPUT_DIR / f"{OUTPUT_STEM}.mp3"
        concatenate(line_paths, output_path)
        timing = build_timing(durations, probe_duration(output_path))
        timing_path = OUTPUT_DIR / f"{OUTPUT_STEM}-timing.json"
        timing_path.write_text(
            json.dumps(timing, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(timing, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
