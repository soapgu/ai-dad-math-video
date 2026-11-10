import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

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

const draft = join(output, 'badge-preview.render.mp4');
const result = spawnSync(join(project, 'node_modules/.bin/remotion'), [
  'render', 'src/index.jsx', 'ClassroomBadgePreview', draft,
  '--public-dir', assets, '--browser-executable', chrome,
  '--codec', 'h264', '--crf', '20', '--concurrency', '4', '--muted', '--overwrite',
], { cwd: project, stdio: 'inherit' });
if (result.error) throw result.error;
if (result.status !== 0) process.exit(result.status ?? 1);
renameSync(draft, join(output, '谁打扫了教室_15秒无旁白样片_v2.mp4'));
