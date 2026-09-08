#!/usr/bin/env python3
"""生成《父子讲题》第一段的唯一混合 TTS 与实测时间轴。"""

from __future__ import annotations

import asyncio
import json
import re
import socket
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from shutil import copyfile

import edge_tts


SAMPLE_RATE = 24_000
BIT_RATE = "48k"
LEADING_SILENCE = 0.60
PAUSES_AFTER = (0.45, 0.65, 0.40, 0.40, 0.90)
TARGET_MIN_SECONDS = 10.5
TARGET_MAX_SECONDS = 11.0
MOM_PITCH_SEMITONES = -2.0
OUTPUT_DIR = Path(__file__).parent / "tts"
OUTPUT_STEM = "segment-01-dialogue-v2"
TIMING_FILENAME = "segment-01-timing-v2.json"


@dataclass(frozen=True)
class Track:
    role: str
    voice: str
    text: str
    rate: str
    pitch_shift_semitones: float = 0.0


@dataclass(frozen=True)
class Event:
    label: str
    tracks: tuple[Track, ...]


BASE_EVENTS = (
    Event(
        "妈妈讲题三遍",
        (
            Track(
                "兔子妈妈",
                "zh-CN-XiaoxiaoNeural",
                "这道题我已经讲三遍了！",
                "-5%",
                MOM_PITCH_SEMITONES,
            ),
        ),
    ),
    Event(
        "儿子仍未听懂",
        (
            Track(
                "儿子",
                "zh-CN-YunxiaNeural",
                "可我还是听不懂嘛！",
                "+5%",
            ),
        ),
    ),
    Event(
        "爸爸主动接棒",
        (
            Track(
                "数字爸爸",
                "zh-CN-YunjianNeural",
                "别急，讲题这事，还得看我。",
                "-5%",
            ),
        ),
    ),
    Event(
        "母子齐声",
        (
            Track(
                "兔子妈妈",
                "zh-CN-XiaoxiaoNeural",
                "你行你上啊！",
                "-5%",
                MOM_PITCH_SEMITONES,
            ),
            Track(
                "儿子",
                "zh-CN-YunxiaNeural",
                "你行你上啊！",
                "+5%",
            ),
        ),
    ),
    Event(
        "爸爸应战",
        (
            Track(
                "数字爸爸",
                "zh-CN-YunjianNeural",
                "我上就我上。",
                "+0%",
            ),
        ),
    ),
)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def force_ipv4() -> None:
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return original_getaddrinfo(
            host,
            port,
            socket.AF_INET,
            type,
            proto,
            flags,
        )

    socket.getaddrinfo = ipv4_getaddrinfo


def probe_duration(path: Path) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return float(result.stdout.strip())


def probe_audio(path: Path) -> dict[str, object]:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ]
    )
    stream = json.loads(result.stdout)["streams"][0]
    return {
        "codec": stream["codec_name"],
        "sample_rate_hz": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
    }


def probe_max_volume(path: Path) -> float:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"max_volume:\s*(-?[0-9.]+) dB", result.stderr)
    if not match:
        raise RuntimeError("无法从 FFmpeg 输出中读取峰值")
    return float(match.group(1))


async def synthesize(track: Track, output_path: Path) -> None:
    for attempt in range(3):
        try:
            output_path.unlink(missing_ok=True)
            await edge_tts.Communicate(
                track.text,
                track.voice,
                rate=track.rate,
            ).save(str(output_path))
            return
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(1.5)


def trim_to_wav(input_path: Path, output_path: Path) -> None:
    trim_filter = (
        "silenceremove=start_periods=1:start_duration=0.05:"
        "start_threshold=-45dB,areverse,"
        "silenceremove=start_periods=1:start_duration=0.05:"
        "start_threshold=-45dB,areverse"
    )
    run(
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
        ]
    )


def apply_pitch_shift(input_path: Path, output_path: Path, semitones: float) -> None:
    pitch_factor = 2 ** (semitones / 12)
    tempo_factor = 1 / pitch_factor
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-af",
            (
                f"asetrate={SAMPLE_RATE}*{pitch_factor:.9f},"
                f"aresample={SAMPLE_RATE},atempo={tempo_factor:.9f}"
            ),
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            str(output_path),
        ]
    )


def mix_chorus(track_paths: list[Path], output_path: Path) -> None:
    command = ["ffmpeg", "-y"]
    for path in track_paths:
        command.extend(["-i", str(path)])
    command.extend(
        [
            "-filter_complex",
            (
                "[0:a][1:a]amix=inputs=2:duration=longest:"
                "dropout_transition=0:normalize=0,"
                "volume=0.72,alimiter=limit=0.95[out]"
            ),
            "-map",
            "[out]",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            str(output_path),
        ]
    )
    run(command)


def concatenate_events(
    event_paths: list[Path],
    trailing_silence: float,
    output_path: Path,
) -> None:
    command = ["ffmpeg", "-y"]
    for path in event_paths:
        command.extend(["-i", str(path)])
    filters = [
        f"anullsrc=r={SAMPLE_RATE}:cl=mono:d={LEADING_SILENCE:.3f}[lead]"
    ]
    concat_inputs = ["[lead]"]
    for index in range(len(event_paths)):
        pause = trailing_silence if index == len(event_paths) - 1 else PAUSES_AFTER[index]
        filters.append(
            f"anullsrc=r={SAMPLE_RATE}:cl=mono:d={pause:.3f}[pause{index}]"
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
    run(command)


def faster_fallback(events: tuple[Event, ...]) -> tuple[Event, ...]:
    adjusted = list(events)
    for event_index in (0, 2):
        track = adjusted[event_index].tracks[0]
        adjusted[event_index] = replace(
            adjusted[event_index],
            tracks=(replace(track, rate="+0%"),),
        )
    return tuple(adjusted)


async def build_event_audio(
    events: tuple[Event, ...],
    temp_root: Path,
) -> tuple[list[Path], list[list[float]]]:
    event_paths: list[Path] = []
    track_durations: list[list[float]] = []
    for event_index, event in enumerate(events):
        processed_paths: list[Path] = []
        durations: list[float] = []
        for track_index, track in enumerate(event.tracks):
            raw_path = temp_root / f"raw-{event_index}-{track_index}.mp3"
            trimmed_path = temp_root / f"trimmed-{event_index}-{track_index}.wav"
            processed_path = temp_root / f"track-{event_index}-{track_index}.wav"
            await synthesize(track, raw_path)
            trim_to_wav(raw_path, trimmed_path)
            if track.pitch_shift_semitones:
                apply_pitch_shift(
                    trimmed_path,
                    processed_path,
                    track.pitch_shift_semitones,
                )
            else:
                copyfile(trimmed_path, processed_path)
            processed_paths.append(processed_path)
            durations.append(probe_duration(processed_path))
        event_path = temp_root / f"event-{event_index}.wav"
        if len(processed_paths) == 1:
            copyfile(processed_paths[0], event_path)
        else:
            mix_chorus(processed_paths, event_path)
        event_paths.append(event_path)
        track_durations.append(durations)
    return event_paths, track_durations


def build_timing(
    events: tuple[Event, ...],
    event_paths: list[Path],
    track_durations: list[list[float]],
    trailing_silence: float,
    requested_trailing_silence: float,
    mp3_container_padding: float,
    encoded_duration: float,
    max_volume_db: float,
    fallback_applied: bool,
) -> dict[str, object]:
    cursor = LEADING_SILENCE
    items: list[dict[str, object]] = []
    for index, (event, event_path, durations) in enumerate(
        zip(events, event_paths, track_durations)
    ):
        event_duration = probe_duration(event_path)
        start = cursor
        end = start + event_duration
        item: dict[str, object] = {
            "label": event.label,
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "pause_after_seconds": round(
                trailing_silence if index == len(events) - 1 else PAUSES_AFTER[index],
                3,
            ),
            "tracks": [],
        }
        for track, duration in zip(event.tracks, durations):
            item["tracks"].append(
                {
                    "role": track.role,
                    "voice": track.voice,
                    "text": track.text,
                    "rate": track.rate,
                    "pitch_shift_semitones": track.pitch_shift_semitones,
                    "start_seconds": round(start, 3),
                    "end_seconds": round(start + duration, 3),
                }
            )
        items.append(item)
        cursor = end + item["pause_after_seconds"]
    return {
        "output": f"{OUTPUT_STEM}.mp3",
        "codec": "mp3",
        "sample_rate_hz": SAMPLE_RATE,
        "channels": 1,
        "bit_rate": BIT_RATE,
        "leading_silence_seconds": LEADING_SILENCE,
        "trailing_silence_seconds": round(trailing_silence, 3),
        "requested_trailing_silence_seconds": round(
            requested_trailing_silence,
            3,
        ),
        "mp3_container_padding_seconds": round(mp3_container_padding, 3),
        "target_duration_seconds": [TARGET_MIN_SECONDS, TARGET_MAX_SECONDS],
        "duration_fallback_applied": fallback_applied,
        "events": items,
        "timeline_total_seconds": round(cursor, 3),
        "encoded_total_seconds": round(encoded_duration, 3),
        "max_volume_db": max_volume_db,
        "mixing_note": "仅母子齐声事件包含两条并行音轨；其余事件为单一说话人。",
    }


async def render_once(
    events: tuple[Event, ...],
    temp_root: Path,
    fallback_applied: bool,
) -> tuple[dict[str, object], Path]:
    event_paths, track_durations = await build_event_audio(events, temp_root)
    trailing_silence = PAUSES_AFTER[-1]
    estimated = (
        LEADING_SILENCE
        + sum(probe_duration(path) for path in event_paths)
        + sum(PAUSES_AFTER[:-1])
        + trailing_silence
    )
    if estimated < TARGET_MIN_SECONDS:
        trailing_silence += TARGET_MIN_SECONDS - estimated
        estimated = TARGET_MIN_SECONDS
    output_path = OUTPUT_DIR / f"{OUTPUT_STEM}.mp3"
    concatenate_events(event_paths, trailing_silence, output_path)
    encoded_duration = probe_duration(output_path)
    mp3_container_padding = encoded_duration - estimated
    effective_trailing_silence = trailing_silence + mp3_container_padding
    timing = build_timing(
        events,
        event_paths,
        track_durations,
        effective_trailing_silence,
        trailing_silence,
        mp3_container_padding,
        encoded_duration,
        probe_max_volume(output_path),
        fallback_applied,
    )
    return timing, output_path


async def main() -> None:
    force_ipv4()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="homework-comedy-tts-") as temp_dir:
        temp_root = Path(temp_dir)
        timing, output_path = await render_once(BASE_EVENTS, temp_root, False)
        if float(timing["encoded_total_seconds"]) > TARGET_MAX_SECONDS:
            for path in temp_root.iterdir():
                path.unlink()
            timing, output_path = await render_once(
                faster_fallback(BASE_EVENTS),
                temp_root,
                True,
            )
        if not TARGET_MIN_SECONDS <= float(timing["encoded_total_seconds"]) <= TARGET_MAX_SECONDS:
            raise RuntimeError(
                f"输出时长不在 {TARGET_MIN_SECONDS}～{TARGET_MAX_SECONDS} 秒："
                f"{timing['encoded_total_seconds']} 秒"
            )
        audio = probe_audio(output_path)
        if audio != {"codec": "mp3", "sample_rate_hz": SAMPLE_RATE, "channels": 1}:
            raise RuntimeError(f"音频格式不符合要求：{audio}")
        if float(timing["max_volume_db"]) > -0.1:
            raise RuntimeError(f"音频峰值过高：{timing['max_volume_db']} dB")
        if abs(
            float(timing["timeline_total_seconds"])
            - float(timing["encoded_total_seconds"])
        ) > 0.05:
            raise RuntimeError("时间轴总长与编码时长误差超过 0.05 秒")
        timing_path = OUTPUT_DIR / TIMING_FILENAME
        timing_path.write_text(
            json.dumps(timing, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(timing, ensure_ascii=False, indent=2))
        print(output_path)
        print(timing_path)


if __name__ == "__main__":
    asyncio.run(main())
