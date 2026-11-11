import React from 'react';
import { AbsoluteFill, Composition, Img, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame } from 'remotion';
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

function Question({ frame, promptFrame = 60, exitFrame = 150, mouths }) {
  return (
    <div className="question-stage" style={{ opacity: fade(frame, exitFrame, exitFrame + 24, 1, 0) }}>
      <StudyScene frame={frame} mouths={mouths} />
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
        {frame >= promptFrame && <div className="question">小天使该给谁？</div>}
      </div>
    </div>
  );
}

function AssumptionRow({ speaker, frame, start = 180 + speaker * 60 }) {
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

function VoicePreview({ timeline, mouthTracks }) {
  const frame = useCurrentFrame();
  const { question, assign, first, huan, le, judge, reject } = timeline;
  const caption = Object.values(timeline).find(({ start, end }) => start <= frame && frame < end);
  if (!assign) return null;
  const mouths = {
    dad: mouthTracks?.dad[frame - timeline.rule.start],
    son: mouthTracks?.son[frame - question.start],
  };
  const rowInterval = Math.floor((first.start - assign.start) / 3);

  return (
    <AbsoluteFill style={{ backgroundColor: '#FCF4E7' }}>
      <div className="canvas">
        {frame < assign.start ? (
          <Question frame={frame} promptFrame={question.start} exitFrame={assign.start} mouths={mouths} />
        ) : (
          <>
            <div className="eyebrow">逻辑推理题 · 谁打扫了教室</div>
            <div className="title">{frame < first.start ? '排出三种假设' : '检验第一种假设'}</div>
            <div className="assumptions">
              {frame < first.start ? children.map(({ id }, speaker) => (
                <AssumptionRow key={id} speaker={speaker} frame={frame} start={assign.start + speaker * rowInterval} />
              )) : (
                <>
                  <AssumptionRow speaker={0} frame={frame} start={assign.start} />
                  <div className="inferences">
                    <Inference name="欢欢" quote="也不是我做的。" result="欢欢打扫了" visible={frame >= huan.start} resolved={frame >= huan.end} />
                    <Inference name="乐乐" quote="是欢欢做的。" result="欢欢没打扫" visible={frame >= le.start} resolved={frame >= le.end} />
                  </div>
                  {frame >= judge.start && (
                    <div className="verdict">{frame >= reject.start ? '矛盾 · 第一种排除' : '两条能同时成立吗？'}</div>
                  )}
                </>
              )}
            </div>
          </>
        )}
        {caption && <div className="voice-caption">{caption.text}</div>}
      </div>
    </AbsoluteFill>
  );
}

function Inference({ name, quote, result, visible, resolved, truthful }) {
  return (
    <div className="inference" style={{ visibility: visible ? 'visible' : 'hidden' }}>
      <div><strong>{name}</strong>「{quote}」</div>
      <div style={{ visibility: resolved ? 'visible' : 'hidden' }}>
        <span>{truthful ? '真话照着听 ↓' : '假话反过来 ↓'}</span>
        <strong>{result}</strong>
      </div>
    </div>
  );
}

const quotes = ['不是我做的。', '也不是我做的。', '是欢欢做的。'];

function Statement({ index, label, badge }) {
  const { id, name } = children[index];
  return <div className="statement">
    <Icon name={id} size={64} />
    <strong>{name}</strong><span>「{quotes[index]}」</span>
    {badge && <Icon name={badge} size={36} />}
    {label && <span className={label === '真话' ? 'true-label' : 'false-label'}>{label}</span>}
  </div>;
}

function FullLesson({ timeline: t, mouthTracks }) {
  const frame = useCurrentFrame();
  if (!t.intro) return null;
  const opening = t.rule.start - 8;
  const swap = frame >= t.oneTruth.start + 36 && frame < t.shortcutAnswer.start;
  const started = (key) => frame >= t[key].start;
  const caption = Object.entries(t).find(([, line]) => line.start <= frame && frame < line.end);
  if (frame >= opening && !started('second')) {
    const local = Object.fromEntries(Object.entries(t).map(([key, line]) => [
      key, { ...line, start: line.start - opening, end: line.end - opening },
    ]));
    return <Sequence from={opening} layout="none">
      <VoicePreview timeline={local} mouthTracks={mouthTracks} />
    </Sequence>;
  }

  return <AbsoluteFill style={{ backgroundColor: '#FCF4E7' }}>
    <div className="canvas">
      {frame < opening ? (
        <div className="lesson-split">
          <Img src={staticFile('classroom.png')} className="classroom-art"
            style={{ transform: `scale(${1 + frame / opening * 0.035})` }} />
          <div className="lesson-panel">
            <h1>谁打扫了教室？</h1>
            <p>只有一人打扫，只有一句真话</p>
            {['quoteX', 'quoteH', 'quoteL'].map((key, index) =>
              started(key) && <Statement key={key} index={index} />)}
          </div>
        </div>
      ) : started('shortcut') ? (
        <div className="lesson-split">
          <StudyScene frame={frame - t.shortcut.start} mouths={{
            dad: mouthTracks.praise?.[frame - t.praise.start],
            son: caption && caption[0] !== 'praise' ? mouthTracks[caption[0]]?.[frame - caption[1].start] : 0,
          }} />
          <div className="lesson-panel">
            <h1>儿子发现了快解</h1>
            {started('opposites') && <>
              <Statement index={1} badge={started('oneTruth') ? (swap ? 'devil' : 'angel') : null} />
              <Statement index={2} badge={started('oneTruth') ? (swap ? 'angel' : 'devil') : null} />
            </>}
            {started('oneTruth') && <div className="fast-truth">
              <Icon name="angel" size={45} /><span>一真一假</span><Icon name="devil" size={45} />
            </div>}
            {started('shortcutWhy') && <Statement index={0} badge="devil" />}
            {started('shortcutAnswer') && <p className="answer-note">小华打扫了教室</p>}
          </div>
        </div>
      ) : (
        <>
          <div className="eyebrow">逻辑推理题 · 谁打扫了教室</div>
          <div className="title">{started('answer') ? '答案：小华打扫了教室' :
            started('third') ? '检验第三种假设' : '检验第二种假设'}</div>
          <div className="assumptions">
            <AssumptionRow speaker={started('third') && !started('answer') ? 2 : 1} frame={frame} start={0} />
            {started('answer') ? (
              <div className="answer-statements">
                {['checkX', 'checkH', 'checkL'].map((key, index) => (
                  <Statement key={key} index={index} label={started(key) ? (index === 1 ? '真话' : '假话') : null} />
                ))}
              </div>
            ) : started('third') ? (
              <>
                <div className="inferences">
                  <Inference name="乐乐" quote={quotes[2]} result="欢欢打扫了" visible resolved={started('thirdX')} truthful />
                  <Inference name="小华" quote={quotes[0]} result="小华也打扫了" visible={started('thirdX')} resolved={started('thirdAsk')} />
                </div>
                {started('thirdAsk') && <div className="verdict">{started('thirdReject') ?
                  '矛盾 · 只能有一人打扫' : '可以有两个人打扫吗？'}</div>}
              </>
            ) : (
              <>
                <div className="inferences">
                  <Inference name="欢欢" quote={quotes[1]} result="欢欢没打扫" visible resolved={started('secondX')} truthful />
                  <Inference name="小华" quote={quotes[0]} result="小华打扫了" visible={started('secondX')} resolved={started('secondL')} />
                </div>
                {started('secondL') && <div className="verdict true-label">{started('keep') ?
                  '成立 · 保留第二种' : '乐乐说假话，也推出欢欢没打扫'}</div>}
              </>
            )}
          </div>
        </>
      )}
      {caption && <div className="voice-caption">{caption[1].text}</div>}
    </div>
  </AbsoluteFill>;
}

registerRoot(() => (
  <>
    <Composition id="ClassroomBadgePreview" component={Preview} width={1920} height={1080} fps={30} durationInFrames={450} />
    <Composition id="ClassroomFullLesson" component={FullLesson} width={1920} height={1080} fps={30}
      durationInFrames={1} defaultProps={{ timeline: {}, frames: 1 }}
      calculateMetadata={({ props }) => ({ durationInFrames: props.frames })} />
    <Composition id="ClassroomVoicePreview" component={VoicePreview} width={1920} height={1080} fps={30}
      durationInFrames={1} defaultProps={{ timeline: {}, frames: 1 }}
      calculateMetadata={({ props }) => ({ durationInFrames: props.frames })} />
  </>
));
