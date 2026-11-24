"""逐帧核对静止标题区域，检出拼贴／错位帧；忽略字幕、嘴型及片尾淡出。"""
import argparse
import json
from pathlib import Path
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parent


def inspect(video, timeline, start=0, end=None):
    t = timeline['timeline']
    end = timeline['frames'] if end is None else end
    # FFmpeg 只向本进程内存返回缩小的灰度像素，不输出媒体正文。
    raw = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(video), '-vf',
        'crop=1920:280:0:0,scale=480:70', '-pix_fmt', 'gray', '-f', 'rawvideo', '-',
    ])
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 70, 480)
    if len(frames) != end - start:
        raise ValueError(f'帧数不符：{len(frames)} != {end-start}')
    scenes = [
        ('开场', 0, t['rule']['start'], (35, 62, 290, 465)),
        ('父子提问', t['rule']['start'], t['assign']['start'], (35, 62, 290, 465)),
        ('分配假设', t['assign']['start'], t['first']['start'], (15, 53, 15, 460)),
        ('第一种假设', t['first']['start'], t['second']['start'], (15, 53, 15, 460)),
        ('第二种假设', t['second']['start'], t['third']['start'], (15, 53, 15, 460)),
        ('第三种假设', t['third']['start'], t['answer']['start'], (15, 53, 15, 460)),
        ('揭晓验算', t['answer']['start'], t['shortcut']['start'], (15, 53, 15, 460)),
        ('儿子宣言', t['shortcut']['start'], t['opposites']['start'], (50, 62, 267, 401)),
        ('儿子快解', t['opposites']['start'], t['praise']['start'], (50, 62, 267, 401)),
        ('爸爸点赞', t['praise']['start'], timeline['frames']-15, (50, 62, 267, 401)),
    ]
    results = []
    for name, begin, finish, (y1, y2, x1, x2) in scenes:
        begin, finish = max(begin, start), min(finish, end)
        if begin >= finish:
            continue
        region = frames[begin-start:finish-start, y1:y2, x1:x2]
        median = np.median(region, axis=0)
        scores = np.abs(region.astype(np.float32)-median).mean(axis=(1, 2))
        bad = np.flatnonzero(scores > 4)
        results.append({'scene': name, 'frames': len(region), 'anomalies': [
            {'frame': int(begin+i), 'time': round((begin+int(i))/30, 3), 'score': round(float(scores[i]), 3)}
            for i in bad
        ]})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--end', type=int)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    timeline = json.loads((ROOT/'.render-assets/full-props.json').read_text())
    results = inspect(args.video, timeline, args.start, args.end)
    args.report.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    for row in results:
        print(f"{row['scene']}：{row['frames']} 帧，{len(row['anomalies'])} 个异常帧")
    raise SystemExit(1 if any(row['anomalies'] for row in results) else 0)
