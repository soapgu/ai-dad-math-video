import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, readFileSync, renameSync, unlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mouthTrack } from './mouth-tracks.mjs';

const project = fileURLToPath(new URL('.', import.meta.url));
const assets = join(project, '.render-assets');
const output = join(project, 'out');
const chrome = process.env.CHROME_EXECUTABLE || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

mkdirSync(assets, { recursive: true });
mkdirSync(output, { recursive: true });
copyFileSync(
  join(project, '../../../digital-dad-math/characters/father-son/father-son-scale-room-v1.png'),
  join(assets, 'study.png'),
);

const overview = readFileSync(join(project, '../images/07-truth-assignments.svg'), 'utf8');
const definitions = overview.match(/<defs>[\s\S]*?<\/defs>/)?.[0];
if (!definitions) throw new Error('找不到组合图里的头像和徽章定义');
for (const name of ['xiaohua', 'huanhuan', 'lele', 'angel', 'devil']) {
  const radius = ['angel', 'devil'].includes(name) ? 25 : 48;
  writeFileSync(join(assets, name + '.svg'),
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"' +
    ' viewBox="' + [-radius, -radius, radius * 2, radius * 2].join(' ') + '">' +
    definitions + '<use xlink:href="#' + name + '"/></svg>');
}

const full = process.argv.includes('--full');
const lips = full || process.argv.includes('--lip-sync');
const voice = lips || process.argv.includes('--voice');
const voiceStem = '谁打扫了教室_有声试片';
const stem = full ? '谁打扫了教室_成片' : voice ? voiceStem + (lips ? '_v2' : '') : '谁打扫了教室_15秒无旁白样片_v2';
const tag = full ? 'full' : 'voice';
let propsPath = join(assets, tag + '-props.json');
if (full) copyFileSync(join(project, '../images/01-classroom.png'), join(assets, 'classroom.png'));
if (lips) {
  const props = JSON.parse(readFileSync(propsPath, 'utf8'));
  const track = (key) => {
    const { start, end } = props.timeline[key];
    return mouthTrack(join(assets, 'voice-' + key + '.mp3'), end - start);
  };
  props.mouthTracks = { dad: track('rule'), son: track('question') };
  if (full) {
    for (const key of ['shortcut', 'opposites', 'oneTruth', 'shortcutWhy', 'shortcutAnswer', 'praise']) {
      props.mouthTracks[key] = track(key);
    }
  }
  propsPath = join(assets, tag + '-lips-props.json');
  writeFileSync(propsPath, JSON.stringify(props));
}
const draft = join(output, stem + '.render.mp4');
const destination = join(output, stem + '.mp4');
const result = spawnSync(join(project, 'node_modules/.bin/remotion'), [
  'render', 'src/index.jsx', full ? 'ClassroomFullLesson' : voice ? 'ClassroomVoicePreview' : 'ClassroomBadgePreview', draft,
  ...(voice ? ['--props', propsPath] : []),
  '--public-dir', assets, '--browser-executable', chrome,
  '--codec', 'h264', '--crf', '20', '--concurrency', '4', '--muted', '--overwrite',
], { cwd: project, stdio: 'inherit' });
if (result.error) throw result.error;
if (result.status !== 0) process.exit(result.status ?? 1);
if (voice) {
  const mixed = join(output, stem + '.mix.mp4');
  const mux = spawnSync('ffmpeg', [
    '-v', 'error', '-y', '-i', draft, '-i', join(assets, tag + '-mix.m4a'),
    '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', '-movflags', '+faststart', mixed,
  ], { stdio: 'inherit' });
  if (mux.error) throw mux.error;
  if (mux.status !== 0) process.exit(mux.status ?? 1);
  renameSync(mixed, destination);
  unlinkSync(draft);
  if (lips && !full) copyFileSync(join(output, voiceStem + '.srt'), join(output, stem + '.srt'));
} else {
  renameSync(draft, destination);
}
