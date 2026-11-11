import React from 'react';
import { Img, interpolate, staticFile } from 'remotion';

// Anchors are measured in the shared illustration's 720×405 coordinate space.
const hosts = [
  {
    id: 'dad', head: [296, 72, 41, 46], shoulders: [294, 135, 67, 41],
    eyes: [[285, 82], [304, 80.5]], blinks: [43, 109], phase: 0, mouth: [297, 98.8, 8.3, 2.6, -5],
  },
  {
    id: 'son', head: [408, 138, 34, 38], shoulders: [411, 192, 46, 29],
    eyes: [[399, 149], [417, 147.5]], blinks: [73, 131], phase: 1.7, mouth: [409, 164.2, 6.2, 2.1, -4],
  },
];

function RegionMask({ id, area }) {
  const [cx, cy, rx, ry] = area;
  return <mask id={id} maskUnits="userSpaceOnUse" x="0" y="0" width="720" height="405">
    <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="url(#study-soft-edge)" />
  </mask>;
}

function Mouth({ anchor, opening }) {
  const [x, y, width, depth, angle] = anchor;
  const height = depth * opening;
  return (
    <g transform={`translate(${x} ${y}) rotate(${angle})`} opacity={Math.min(1, opening * 3)}>
      <path d={`M ${-width} 0 Q 0 1.3 ${width} 0 Q 0 ${1.3 + height * 2.8} ${-width} 0 Z`}
        fill="#683b2c" />
      <path d={`M ${-width * 0.65} 0.65 Q 0 1.8 ${width * 0.65} 0.55 Q 0 ${1.8 + height * 0.65} ${-width * 0.65} 0.65 Z`}
        fill="#f8dfbe" opacity={opening * 0.9} />
    </g>
  );
}

function HostMotion({ host, frame, opening }) {
  const { id, head, shoulders, eyes, blinks, phase } = host;
  const breath = Math.sin(frame / 24 + phase) * 0.85;
  const tilt = Math.sin(frame / 28 + phase) * 1.15;
  const blink = Math.max(...blinks.map((center) => Math.max(0, 1 - Math.abs(frame - center) / 3)));
  const [headX, headY] = head;
  return <>
    <g mask={`url(#${id}-shoulders)`}>
      <use href="#study-art" transform={`translate(0 ${breath})`} />
    </g>
    <g mask={`url(#${id}-head)`}>
      <g transform={`rotate(${tilt} ${headX} ${headY + 29})`}>
        <use href="#study-art" />
        {opening > 0 && <Mouth anchor={host.mouth} opening={opening} />}
        {blink > 0 && eyes.map(([x, y], index) => (
          <g key={index} opacity={blink}>
            <g mask={`url(#${id}-eye-${index})`}>
              <use href="#study-art" transform="translate(0 -6.5)" />
            </g>
            <path d={`M ${x - 3.6} ${y} q 3.6 2.1 7.2 0`} fill="none" stroke="#5b3a24" strokeWidth="0.85" strokeLinecap="round" />
          </g>
        ))}
      </g>
    </g>
  </>;
}

export function StudyScene({ frame, mouths }) {
  const art = staticFile('study.png');
  const zoom = interpolate(frame, [0, 59], [1, 1.026], { extrapolateRight: 'clamp' });
  return <>
    <Img src={art} className="study-preload" />
    <svg className="study-scene" viewBox="129 0 427.5 405" aria-label="数字爸爸和儿子在书房并肩思考">
      <defs>
        <image id="study-art" href={art} width="720" height="405" />
        <radialGradient id="study-soft-edge">
          <stop offset="68%" stopColor="white" />
          <stop offset="100%" stopColor="black" />
        </radialGradient>
        {hosts.map(({ id, head, shoulders, eyes }) => (
          <React.Fragment key={id}>
            <RegionMask id={id + '-head'} area={head} />
            <RegionMask id={id + '-shoulders'} area={shoulders} />
            {eyes.map(([x, y], index) => <RegionMask key={index} id={`${id}-eye-${index}`} area={[x, y, 5.8, 4.8]} />)}
          </React.Fragment>
        ))}
      </defs>
      <g transform={`translate(344 405) scale(${zoom}) translate(-344 -405)`}>
        <use href="#study-art" />
        {hosts.map((host) => <HostMotion key={host.id} host={host} frame={frame} opening={mouths?.[host.id] ?? 0} />)}
      </g>
    </svg>
  </>;
}
