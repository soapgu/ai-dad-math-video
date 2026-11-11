import { execFileSync } from 'node:child_process';

const samplesPerFrame = 1600;

export function mouthTrack(source, frames) {
  const pcm = execFileSync('ffmpeg', [
    '-v', 'error', '-i', source, '-ac', '1', '-ar', '48000', '-f', 's16le', '-',
  ]);
  const energy = Array.from({ length: frames }, (_, frame) => {
    const start = frame * samplesPerFrame * 2;
    const end = Math.min(start + samplesPerFrame * 2, pcm.length);
    let sum = 0;
    for (let i = start; i < end; i += 2) sum += pcm.readInt16LE(i) ** 2;
    return Math.sqrt(sum / samplesPerFrame);
  });
  const sorted = [...energy].sort((a, b) => a - b);
  const reference = sorted[Math.floor(sorted.length * 0.9)] || 1;
  const gate = Math.max(80, reference * 0.09);
  const opening = energy.map((level) => level < gate ? 0 :
    Math.min(1, Math.sqrt((level - gate) / reference)));
  return opening.map((level, i) => level === 0 ? 0 : Number(
    (level * 0.7 + ((opening[i - 1] ?? 0) + (opening[i + 1] ?? 0)) * 0.15).toFixed(3),
  ));
}
