#!/usr/bin/env python3
"""生成第三段父子互动 TTS，并自动调整语速以适配 15 秒视频。"""

import asyncio
import json
import socket
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from shutil import copyfile

import edge_tts


SAMPLE_RATE = 24_000
BIT_RATE = "48k"
MAX_DURATION = 14.50
LEADING_SILENCE = 1.20
OUTPUT_DIR = Path(__file__).parent / "tts"
OUTPUT_STEM = "segment-03-tts-v1"
RATE_STEPS = (-5, 0, 5, 10, 15)


@dataclass(frozen=True)
class Line:
    label: str
    role: str
    voice: str
    text: str
    base_rate: int
    adjustable: bool
    pause_after: float
    rate: int = 0


BASE_LINES = (
    Line(
        "提出练习",
        "数字爸爸",
        "zh-CN-YunjianNeural",
        "试一试：几减四等于六？",
        -5,
        True,
        0.30,
    ),
    Line(
        "倒过来思考",
        "数字爸爸",
        "zh-CN-YunjianNeural",
        "倒过来想，六加四等于几？",
        -5,
        True,
        0.70,
    ),
    Line(
        "儿子回答",
        "儿子",
        "zh-CN-YunxiaNeural",
        "六加四等于十，所以答案是十！",
        0,
        True,
        0.50,
    ),
    Line(
        "表扬",
        "数字爸爸",
        "zh-CN-YunjianNeural",
        "真棒！",
        -5,
        False,
        0.30,
    ),
    Line(
        "总结",
        "数字爸爸",
        "zh-CN-YunjianNeural",
        "遇到问题，换个方向，多想一步！",
        -5,
        True,
        0.80,
    ),
)


def force_ipv4() -> None:
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = ipv4_getaddrinfo


def rate_text(rate: int) -> str:
    return f"{rate:+d}%"


def lines_for_step(step_index: int) -> tuple[Line, ...]:
    increment = step_index * 5
    return tuple(
        replace(
            line,
            rate=min(15, line.base_rate + increment)
            if line.adjustable
            else line.base_rate,
        )
        for line in BASE_LINES
    )


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
                line.text,
                line.voice,
                rate=rate_text(line.rate),
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


def concatenate(lines: tuple[Line, ...], paths: list[Path], output_path: Path) -> None:
    command = ["ffmpeg", "-y"]
    for path in paths:
        command.extend(["-i", str(path)])
    filters = [f"anullsrc=r={SAMPLE_RATE}:cl=mono:d={LEADING_SILENCE}[lead]"]
    concat_inputs = ["[lead]"]
    for index, line in enumerate(lines):
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


def build_timing(
    lines: tuple[Line, ...], durations: list[float], encoded_duration: float
) -> dict:
    cursor = LEADING_SILENCE
    items = []
    for line, duration in zip(lines, durations):
        start = cursor
        end = start + duration
        items.append(
            {
                "label": line.label,
                "role": line.role,
                "voice": line.voice,
                "text": line.text,
                "rate": rate_text(line.rate),
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
        "maximum_duration_seconds": MAX_DURATION,
        "leading_silence_seconds": LEADING_SILENCE,
        "lines": items,
        "timeline_total_seconds": round(cursor, 3),
        "encoded_total_seconds": round(encoded_duration, 3),
    }


async def render_attempt(
    lines: tuple[Line, ...], attempt_root: Path
) -> tuple[Path, list[float], float]:
    raw_paths = [attempt_root / f"raw-{i}.mp3" for i in range(len(lines))]
    line_paths = [attempt_root / f"line-{i}.wav" for i in range(len(lines))]
    for line, raw_path in zip(lines, raw_paths):
        await synthesize(line, raw_path)
    for raw_path, line_path in zip(raw_paths, line_paths):
        trim_silence(raw_path, line_path)
    durations = [probe_duration(path) for path in line_paths]
    combined_path = attempt_root / "combined.mp3"
    concatenate(lines, line_paths, combined_path)
    return combined_path, durations, probe_duration(combined_path)


async def main() -> None:
    force_ipv4()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="segment-03-tts-") as temp_dir:
        temp_root = Path(temp_dir)
        selected = None
        for step_index, _ in enumerate(RATE_STEPS):
            lines = lines_for_step(step_index)
            attempt_root = temp_root / f"attempt-{step_index}"
            attempt_root.mkdir()
            combined_path, durations, encoded_duration = await render_attempt(
                lines, attempt_root
            )
            print(
                f"attempt={step_index + 1} duration={encoded_duration:.3f}s "
                f"rates={[rate_text(line.rate) for line in lines]}"
            )
            if encoded_duration <= MAX_DURATION:
                selected = (lines, combined_path, durations, encoded_duration)
                break
        if selected is None:
            raise RuntimeError("语速达到 +15% 后总时长仍超过 14.5 秒")

        lines, combined_path, durations, encoded_duration = selected
        output_path = OUTPUT_DIR / f"{OUTPUT_STEM}.mp3"
        copyfile(combined_path, output_path)
        timing = build_timing(lines, durations, encoded_duration)
        timing_path = OUTPUT_DIR / f"{OUTPUT_STEM}-timing.json"
        timing_path.write_text(
            json.dumps(timing, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(timing, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
