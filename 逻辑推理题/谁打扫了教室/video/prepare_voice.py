"""按实测语音长度生成试片时间轴、外挂字幕和混音。"""
import asyncio
import json
import math
from pathlib import Path
import subprocess
import sys

import edge_tts


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / '.render-assets'
OUT = ROOT / 'out'
STEM = '谁打扫了教室_有声试片'
FPS = 30
LINES = [
    ('rule', 'Yunjian', '谁说真话，就给谁戴小天使。', 6),
    ('question', 'Yunxia', '那小天使该给谁呢？', 90),
    ('assign', 'Yunjian', '轮流给三个人试试。每次一人说真话，另外两人说假话。', 6),
    ('method', 'Yunjian', '真话照着听，假话反过来想。', 8),
    ('first', 'Yunjian', '先假设小华说真话。', 5),
    ('huan', 'Yunjian', '欢欢说，也不是我做的。这句是假的，所以欢欢打扫了。', 6),
    ('le', 'Yunjian', '乐乐说，是欢欢做的。这句也是假的，所以欢欢没打扫。', 6),
    ('judge', 'Yunjian', '两条能同时成立吗？', 60),
    ('no', 'Yunjian', '不能。', 4),
    ('reject', 'Yunjian', '第一种排除。', 30),
]


INTRO = [
    ('intro', 'Xiaoxiao', '放学后，三个人里只有一人打扫了教室。', 5),
    ('quoteX', 'Xiaoxiao', '小华说，不是我做的。', 3),
    ('quoteH', 'Xiaoxiao', '欢欢说，也不是我做的。', 3),
    ('quoteL', 'Xiaoxiao', '乐乐说，是欢欢做的。', 3),
    ('mystery', 'Xiaoxiao', '三句话里，只有一句是真的。谁打扫了教室？', 30),
]
ENDING = [
    ('second', 'Yunjian', '再假设欢欢说真话，那她没打扫。', 4),
    ('secondX', 'Yunjian', '小华说不是我做的，反过来，就是小华打扫了。', 4),
    ('secondL', 'Yunjian', '乐乐的话反过来，也是欢欢没打扫。', 4),
    ('keep', 'Yunjian', '三句话对得上，先留下这一种。', 15),
    ('third', 'Yunjian', '最后假设乐乐说真话，那欢欢打扫了。', 4),
    ('thirdX', 'Yunjian', '小华说的是假话，所以小华也打扫了。', 4),
    ('thirdAsk', 'Yunjian', '可题目允许两个人都打扫吗？', 60),
    ('thirdReject', 'Yunjian', '只有一人打扫，第三种也排除。', 15),
    ('answer', 'Yunjian', '只剩第二种。打扫教室的是小华！', 8),
    ('checkX', 'Yunjian', '验算一下，小华说自己没打扫，是假话。', 4),
    ('checkH', 'Yunjian', '欢欢说自己没打扫，是真话。', 4),
    ('checkL', 'Yunjian', '乐乐说是欢欢做的，是假话。', 4),
    ('checkDone', 'Yunjian', '只有一人打扫，也只有一句真话。', 20),
    ('shortcut', 'Yunxia', '爸，我发现还能更快！', 4),
    ('opposites', 'Yunxia', '欢欢说自己没打扫，乐乐说欢欢打扫了。', 4),
    ('oneTruth', 'Yunxia', '这两句正好相反，一定一真一假。', 4),
    ('shortcutWhy', 'Yunxia', '唯一的真话已经在这里了，所以小华说不是我做的一定是假话。', 4),
    ('shortcutAnswer', 'Yunxia', '就是小华打扫的！', 8),
    ('praise', 'Yunjian', '漂亮！你找到两句正好相反的话，一下就推出来了！', 45),
]


def run(*args):
    subprocess.run(args, check=True)


def audio_duration(path):
    return float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'csv=p=0', path,
    ]))


def stamp(frame):
    ms = round(frame * 1000 / FPS)
    seconds, ms = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'


async def main():
    ASSETS.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    full = "--full" in sys.argv
    lines = INTRO + LINES + ENDING if full else LINES
    stem = "谁打扫了教室_成片" if full else STEM
    tag = "full" if full else "voice"
    props_file = ASSETS / f'{tag}-props.json'
    reuse = '--reuse' in sys.argv
    previous = json.loads(props_file.read_text(encoding='utf-8'))['timeline'] if reuse else {}
    trial_keys = {entry[0] for entry in LINES}
    timeline = {}
    cues = []
    audio_inputs = []
    filters = []
    cursor = 8
    for index, (key, voice, line, pause) in enumerate(lines):
        target = ASSETS / f'voice-{key}.mp3'
        temp = target.with_suffix('.tmp')
        cached = target.is_file() and (
            (full and key in trial_keys) or previous.get(key, {}).get('text') == line
        )
        if not cached:
            await edge_tts.Communicate(line, f'zh-CN-{voice}Neural', rate='+8%').save(temp)
            temp.replace(target)
        duration = audio_duration(target)
        end = cursor + math.ceil(duration * FPS)
        timeline[key] = {'start': cursor, 'end': end, 'text': line}
        cues.append(f'{index + 1}\n{stamp(cursor)} --> {stamp(end)}\n{line}')
        audio_inputs.extend(['-i', str(target)])
        pitch = 'asetrate=42763,aresample=48000,atempo=1.12246,' if voice == 'Xiaoxiao' else ''
        filters.append(
            f'[{index}:a]aresample=48000,aformat=channel_layouts=stereo,{pitch}'
            f'adelay={cursor * 1600}S:all=1[voice{index}]'
        )
        cursor = end + pause
    duration = cursor / FPS
    bgm = ROOT.parent / 'bgm'
    main_music = bgm / '小さな巨人.m4a'
    sections = [(main_music, 0, cursor)]
    if full:
        sections = [
            (next(bgm.glob('推理*.m4a')), 0, timeline['rule']['start']),
            (main_music, timeline['rule']['start'], timeline['shortcut']['start']),
            (bgm / '対決のテーマ.m4a', timeline['shortcut']['start'], cursor),
        ]
    music_tracks = []
    for index, (source, start, end) in enumerate(sections):
        span = (end - start) / FPS
        audio_inputs.extend(['-i', str(source)])
        stream = f'[{len(lines) + index}:a]'
        if span > audio_duration(source):
            # 为当前主段补一次曲首，在原曲末尾交叠一秒。
            if span > 2 * audio_duration(source) - 1:
                raise ValueError(f'音源过短：{source.name}')
            filters.extend([
                f'{stream}asplit=2[tail{index}][head{index}]',
                f'[tail{index}][head{index}]acrossfade=d=1[extended{index}]',
            ])
            stream = f'[extended{index}]'
        label = f'music{index}'
        music_tracks.append(f'[{label}]')
        filters.append(
            f'{stream}aresample=48000,aformat=channel_layouts=stereo,'
            f'atrim=duration={span},asetpts=PTS-STARTPTS,volume=-22dB,afade=d=0.6,'
            f'afade=t=out:st={span - 0.8}:d=0.8,adelay={start * 1600}S:all=1[{label}]'
        )
    tracks = ''.join(f'[voice{i}]' for i in range(len(lines))) + ''.join(music_tracks)
    filters.append(f'{tracks}amix=inputs={len(lines)+len(sections)}:normalize=0,alimiter=limit=0.95:level=0:latency=1')
    run('ffmpeg', '-v', 'error', '-y', *audio_inputs,
        '-filter_complex', ';'.join(filters), '-t', str(duration), '-c:a', 'aac',
        '-b:a', '192k', str(ASSETS / f'{tag}-mix.m4a'))
    props_file.write_text(
        json.dumps({'timeline': timeline, 'frames': cursor}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    (OUT / f'{stem}.srt').write_text('\n\n'.join(cues) + '\n', encoding='utf-8')
    print(f'配音时间轴 {duration:.2f} 秒，{cursor} 帧')


if __name__ == '__main__':
    asyncio.run(main())
