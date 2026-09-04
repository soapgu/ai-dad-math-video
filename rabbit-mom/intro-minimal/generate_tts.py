#!/usr/bin/env python3
"""生成兔子妈妈 8 秒样片的两个成熟女声候选版本。"""

import asyncio
import argparse
import json
import socket
import subprocess
import tempfile
from shutil import copyfile
from dataclasses import dataclass
from pathlib import Path

import edge_tts


SAMPLE_RATE = 24_000
BIT_RATE = "48k"
LEADING_SILENCE = 0.20
FIRST_PAUSE = 0.35
CONTRAST_PAUSE = 0.85
TRAILING_SILENCE = 0.90
OUTPUT_DIR = Path(__file__).parent / "tts"


@dataclass(frozen=True)
class Segment:
    label: str
    text: str
    rate: str


@dataclass(frozen=True)
class Variant:
    label: str
    voice: str
    output_stem: str
    pitch_semitones: float = 0.0
    rate_overrides: tuple[str, str, str] | None = None


SEGMENTS = (
    Segment("自我介绍", "嗨，我是兔子妈妈。", "-10%"),
    Segment("询问作业", "今天的作业做完了没有？", "-15%"),
    Segment("最后提醒", "你最好做完了。", "-25%"),
)

VARIANTS = (
    Variant(
        "晓晓标准普通话成熟版",
        "zh-CN-XiaoxiaoNeural",
        "rabbit-mom-intro-tts-v2-xiaoxiao-mature",
        -2.0,
    ),
    Variant(
        "晓臻台湾普通话版",
        "zh-TW-HsiaoChenNeural",
        "rabbit-mom-intro-tts-v2-hsiaochen",
        rate_overrides=("-5%", "-10%", "-20%"),
    ),
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


async def synthesize(segment: Segment, voice: str, output_path: Path) -> None:
    communicator = edge_tts.Communicate(
        segment.text,
        voice,
        rate=segment.rate,
    )
    await communicator.save(str(output_path))


def trim_edge_silence(input_path: Path, output_path: Path) -> None:
    trim_filter = (
        "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-45dB,"
        "areverse,"
        "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-45dB,"
        "areverse"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-af",
            trim_filter,
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def force_ipv4() -> None:
    """避免本机可解析但无法连接微软语音服务的 IPv6 地址。"""
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_getaddrinfo(
        host: str,
        port: int | str | None,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ) -> list[tuple[int, int, int, str, tuple[object, ...]]]:
        return original_getaddrinfo(
            host,
            port,
            socket.AF_INET,
            type,
            proto,
            flags,
        )

    socket.getaddrinfo = ipv4_getaddrinfo


def concatenate(segment_paths: list[Path], output_path: Path) -> None:
    silence_durations = (
        LEADING_SILENCE,
        FIRST_PAUSE,
        CONTRAST_PAUSE,
        TRAILING_SILENCE,
    )
    command = ["ffmpeg", "-y"]
    for path in segment_paths:
        command.extend(["-i", str(path)])

    filters = []
    for index, duration in enumerate(silence_durations):
        filters.append(
            f"anullsrc=r={SAMPLE_RATE}:cl=mono:d={duration:.3f}[silence{index}]"
        )
    filters.append(
        "[silence0][0:a][silence1][1:a][silence2][2:a][silence3]"
        "concat=n=7:v=0:a=1[out]"
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


def apply_pitch_shift(input_path: Path, output_path: Path, semitones: float) -> None:
    pitch_factor = 2 ** (semitones / 12)
    tempo_factor = 1 / pitch_factor
    pitch_filter = (
        f"asetrate={SAMPLE_RATE}*{pitch_factor:.9f},"
        f"aresample={SAMPLE_RATE},atempo={tempo_factor:.9f}"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-af",
            pitch_filter,
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-b:a",
            BIT_RATE,
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def segments_for_variant(variant: Variant) -> tuple[Segment, ...]:
    if variant.rate_overrides is None:
        return SEGMENTS
    return tuple(
        Segment(segment.label, segment.text, rate)
        for segment, rate in zip(SEGMENTS, variant.rate_overrides)
    )


def build_timing(
    variant: Variant,
    segments: tuple[Segment, ...],
    durations: list[float],
) -> dict[str, object]:
    cursor = LEADING_SILENCE
    items = []
    pauses_after = (FIRST_PAUSE, CONTRAST_PAUSE, TRAILING_SILENCE)
    for segment, duration, pause_after in zip(segments, durations, pauses_after):
        start = cursor
        end = start + duration
        items.append(
            {
                "label": segment.label,
                "text": segment.text,
                "rate": segment.rate,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
            }
        )
        cursor = end + pause_after

    return {
        "variant": variant.label,
        "voice": variant.voice,
        "pitch_shift_semitones": variant.pitch_semitones,
        "leading_silence_seconds": LEADING_SILENCE,
        "first_pause_seconds": FIRST_PAUSE,
        "contrast_pause_seconds": CONTRAST_PAUSE,
        "trailing_silence_seconds": TRAILING_SILENCE,
        "segments": items,
        "total_seconds": round(cursor, 3),
    }


async def main(selected_stem: str | None = None) -> None:
    force_ipv4()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rabbit-mom-tts-") as temp_dir:
        temp_root = Path(temp_dir)
        selected_variants = tuple(
            variant
            for variant in VARIANTS
            if selected_stem is None or variant.output_stem == selected_stem
        )
        if not selected_variants:
            raise ValueError(f"未知候选版本：{selected_stem}")

        for variant_index, variant in enumerate(selected_variants):
            segments = segments_for_variant(variant)
            temp_path = temp_root / str(variant_index)
            temp_path.mkdir()
            raw_paths = [temp_path / f"raw-{index}.mp3" for index in range(3)]
            segment_paths = [temp_path / f"segment-{index}.wav" for index in range(3)]
            for segment, path in zip(segments, raw_paths):
                await synthesize(segment, variant.voice, path)

            for raw_path, segment_path in zip(raw_paths, segment_paths):
                trim_edge_silence(raw_path, segment_path)

            durations = [probe_duration(path) for path in segment_paths]
            combined_path = temp_path / "combined.mp3"
            concatenate(segment_paths, combined_path)

            output_path = OUTPUT_DIR / f"{variant.output_stem}.mp3"
            if variant.pitch_semitones:
                apply_pitch_shift(
                    combined_path,
                    output_path,
                    variant.pitch_semitones,
                )
            else:
                copyfile(combined_path, output_path)

            timing = build_timing(variant, segments, durations)
            timing["encoded_total_seconds"] = round(probe_duration(output_path), 3)
            timing_path = OUTPUT_DIR / f"{variant.output_stem}-timing.json"
            timing_path.write_text(
                json.dumps(timing, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(timing, ensure_ascii=False, indent=2))
            print(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", help="只生成指定 output_stem 的候选版本")
    arguments = parser.parse_args()
    asyncio.run(main(arguments.variant))
