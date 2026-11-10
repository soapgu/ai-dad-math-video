import React from 'react';
import { AbsoluteFill, Composition, Img, interpolate, registerRoot, staticFile, useCurrentFrame } from 'remotion';
import { StudyScene } from './StudyScene.jsx';
import './preview.css';

const children = [
  { id: 'xiaohua', name: '小华' },
  { id: 'huanhuan', name: '欢欢' },
  { id: 'lele', name: '乐乐' },
];

const fade = (frame, start, end, from = 0, to = 1) => interpolate(frame, [start, end], [from, to], {
  extrapolateLeft: 'clamp',
  extrapolateRight: 'clamp',
});

function Icon({ name, size, style }) {
  return <Img src={staticFile(name + '.svg')} width={size} height={size} style={style} />;
}

function Question({ frame }) {
  return (
    <div className="question-stage" style={{ opacity: fade(frame, 150, 174, 1, 0) }}>
      <StudyScene frame={frame} />
      <div className="question-panel">
        <div className="question-kicker">逻辑推理题 · 谁打扫了教室</div>
        <div className="question-title">三个人，只有一句真话</div>
        <div className="legend">
          <div className="truth"><Icon name="angel" size={33} />1 人说真话</div>
          <div className="false"><Icon name="devil" size={33} /><Icon name="devil" size={33} />2 人说假话</div>
        </div>
        <div className="choices">
          {children.map(({ id, name }) => (
            <div className="choice" key={id}>
              <div className="choice-portrait"><Icon name={id} size={105} /><span className="empty-badge" /></div>
              <strong>{name}</strong>
            </div>
          ))}
        </div>
        {frame >= 60 && <div className="question">小天使该给谁？</div>}
      </div>
    </div>
  );
}

function AssumptionRow({ speaker, frame }) {
  const start = 180 + speaker * 60;
  const progress = fade(frame, start, start + 10);
  return (
    <div className="assumption" style={{ opacity: progress, transform: `translateY(${(1 - progress) * 9}px)` }}>
      <div className="assumption-label">
        <span>假设 {speaker + 1}</span>
        <strong>{children[speaker].name}说真话</strong>
      </div>
      {children.map(({ id, name }, index) => {
        const truthful = speaker === index;
        const badge = truthful ? fade(frame, start, start + 16) : fade(frame, start + 16, start + 25);
        return (
          <div className="assignment" key={id}>
            <div className="assignment-portrait">
              <Icon name={id} size={83} />
              <Icon name={truthful ? 'angel' : 'devil'} size={42} style={{
                position: 'absolute', top: -5, right: -9, opacity: badge,
                transform: `translateY(${(1 - badge) * -25}px)`,
              }} />
            </div>
            <div><strong>{name}</strong><span className={truthful ? 'true-label' : 'false-label'} style={{ opacity: badge }}>{truthful ? '说真话' : '说假话'}</span></div>
          </div>
        );
      })}
    </div>
  );
}

function Preview() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: '#FCF4E7' }}>
      <div className="canvas">
        {frame < 175 && <Question frame={frame} />}
        {frame >= 175 && (
          <>
            <div className="eyebrow">逻辑推理题 · 谁打扫了教室</div>
            <div className="title">排出三种假设</div>
            <div className="assumptions">
              {children.map(({ id }, speaker) => <AssumptionRow key={id} speaker={speaker} frame={frame} />)}
            </div>
          </>
        )}
        {frame >= 360 && <div className="closing">接下来，逐一检查</div>}
      </div>
    </AbsoluteFill>
  );
}

registerRoot(() => <Composition id="ClassroomBadgePreview" component={Preview} width={1920} height={1080} fps={30} durationInFrames={450} />);
