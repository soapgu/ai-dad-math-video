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

function DeductionArt({ ending, opening }) {
  const anchor = ending ? [399, 255, 10] : [638, 377, 10];
  return <svg className="deduction-art" viewBox="0 0 1672 941">
    <image href={staticFile(ending ? '11-dad-thumbs-up-ending.png' : '10-son-deduction-highlight.png')} width="1672" height="941" />
    {opening > 0 && <ellipse cx={anchor[0]} cy={anchor[1]} rx={anchor[2]} ry={1 + opening * 4} fill="#683b2c" opacity={opening * 0.8} />}
  </svg>;
}

function CaseTable({ speaker, frame, t }) {
  const starts = speaker === 0 ? [t.first.start, t.huan.start, t.le.start] :
    speaker === 1 ? [t.secondX.start, t.second.start, t.secondL.start] : [t.thirdX.start, t.third.start, t.third.start];
  const results = [['小华没打扫', '欢欢打扫了', '欢欢没打扫'], ['小华打扫了', '欢欢没打扫', '欢欢没打扫'], ['小华打扫了', '欢欢打扫了', '欢欢打扫了']][speaker];
  const candidates = [[[0,1,1],[0,1,0],[1,0,1]], [[1,0,0],[1,0,1],[1,0,1]], [[1,0,0],[0,1,0],[0,1,0]]][speaker];
  const done = frame >= [t.judge.start,t.keep.start,t.thirdAsk.start][speaker];
  return <div className="case-table">
    <div className="case-header"><span>人物 · 原话</span><span>真假</span><span>推论</span><span>小华　欢欢　乐乐</span></div>
    {children.map(({id,name},i)=><div key={id} className="case-line" style={{visibility: frame >= starts[i] ? 'visible' : 'hidden'}}>
      <span className="case-person"><Icon name={id} size={48}/><strong>{name}</strong>「{quotes[i]}」</span>
      <span className={speaker === i ? 'true-label':'false-label'}>{speaker === i ? '真':'假'}</span>
      <strong>{results[i]}</strong><span>{candidates[i].map((v,j)=><span key={j} className={v?'true-label':'false-label'}>{v?'☑':'✖'}　</span>)}</span>
    </div>)}
    {done && <div className="case-summary">{speaker === 1 ? '共同候选人：小华 🧹　成立' : '共同候选人：无　矛盾，排除'}</div>}
  </div>;
}

function FullLesson({ timeline: t, mouthTracks, frames }) {
  const frame = useCurrentFrame();
  if (!t.intro) return null;
  const started = key => frame >= t[key].start;
  const caption = Object.entries(t).find(([,line])=>line.start<=frame && frame<line.end);
  const ending = started('praise');
  const activeOpening = caption ? mouthTracks[caption[0]]?.[frame-caption[1].start] ?? 0 : 0;
  const speaker = started('third') ? 2 : started('second') ? 1 : 0;
  const swap = started('oneTruth') && frame < t.shortcutAnswer.start && Math.floor((frame-t.oneTruth.start)/45)%2 === 1;
  return <AbsoluteFill style={{backgroundColor:'#FCF4E7',opacity:fade(frame,frames-15,frames-1,1,0)}}><div className="canvas">
    {!started('rule') ? <div className="lesson-split">
      <Img src={staticFile('classroom.png')} className="classroom-art"/>
      <div className="lesson-panel opening-panel"><div className="mom-avatar"><svg width="100" height="100" viewBox="80 0 500 570"><image href={staticFile('mom.png')} width="1726" height="911"/></svg></div><div className="mom-name">兔子妈妈</div>
      <h1>谁打扫了教室？</h1><p>今天出一道推理题</p><p>只有一人打扫，只有一句真话</p>
      {['quoteX','quoteH','quoteL'].map((key,i)=>started(key)&&<Statement key={key} index={i}/>)}</div>
    </div> : !started('assign') ? <Question frame={frame-t.rule.start} promptFrame={t.question.start-t.rule.start} exitFrame={99999} mouths={{dad:mouthTracks.dad?.[frame-t.rule.start],son:mouthTracks.son?.[frame-t.question.start]}}/>
    : !started('first') ? <><div className="eyebrow">逻辑推理题 · 谁打扫了教室</div><div className="title">排出三种假设</div><div className="assumptions">{children.map(({id},i)=><AssumptionRow key={id} speaker={i} frame={frame} start={t.assign.start+i*Math.floor((t.first.start-t.assign.start)/3)}/>)}</div></>
    : started('shortcut') ? <>
      <DeductionArt ending={ending} opening={activeOpening}/>
      <div className="board-panel"><h1>{ending?'长江后浪推前浪！':!started('opposites')?'真相只有一个！':'先找相反的两句话'}</h1>
      {!ending && !started('opposites') && <p>解法不止一种！</p>}
      {!ending && started('opposites') && <><Statement index={1} badge={started('oneTruth')?(swap?'devil':'angel'):null}/><Statement index={2} badge={started('oneTruth')?(swap?'angel':'devil'):null}/>
      {started('oneTruth')&&<p>一真一假 → 唯一真话在这里</p>}
      {started('shortcutFalse')&&<Statement index={0} badge="devil"/>}
      {started('shortcutAnswer')&&<p>小华打扫了教室 🧹</p>}</>}
      {ending && <p>会检验，也会发现更快的解法。</p>}</div>
    </> : started('answer') ? <><div className="eyebrow">逻辑推理题 · 揭晓与验算</div><div className="title">答案：小华打扫了教室 🧹</div><div className="reveal-panel">{['checkX','checkH','checkL'].map((key,i)=><Statement key={key} index={i} label={started(key)?(i===1?'真话':'假话'):null}/>)}{started('checkDone')&&<p>只有一人打扫，只有一句真话 ✓</p>}</div></>
    : <><div className="eyebrow">逻辑推理题 · 谁打扫了教室</div><div className="title">检验第{['一','二','三'][speaker]}种假设：{children[speaker].name}说真话</div><CaseTable speaker={speaker} frame={frame} t={t}/></>}
    {caption&&<div className="voice-caption">{caption[1].text}</div>}
  </div></AbsoluteFill>;
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
