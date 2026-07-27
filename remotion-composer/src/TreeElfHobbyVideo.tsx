import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type HobbyCaption = {start: number; end: number; text: string};
export type TreeElfHobbyVideoProps = {captions: HobbyCaption[]};

const ROOT = "treeelf-hobby-second-job";
const INK = "#10171C";
const IVORY = "#F7F1E6";
const RED = "#D9533F";
const asset = (path: string) => staticFile(`${ROOT}/${path}`);

const Still: React.FC<{src: string; zoom?: number; pan?: number}> = ({src, zoom = 1.08, pan = 0}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const p = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });
  return (
    <AbsoluteFill style={{backgroundColor: INK, overflow: "hidden"}}>
      <Img src={asset(`images/${src}.png`)} style={{width: "100%", height: "100%", objectFit: "cover", transform: `translateX(${pan * (p - 0.5)}px) scale(${1 + (zoom - 1) * p})`}} />
      <AbsoluteFill style={{background: "linear-gradient(180deg,rgba(4,8,12,.03),rgba(4,8,12,.13))"}} />
    </AbsoluteFill>
  );
};

const Clip: React.FC<{src: string; playbackRate?: number}> = ({src, playbackRate = 1}) => (
  <AbsoluteFill style={{backgroundColor: INK}}>
    <OffthreadVideo src={asset(`video/${src}.mp4`)} muted playbackRate={playbackRate} style={{width: "100%", height: "100%", objectFit: "cover"}} />
    <AbsoluteFill style={{background: "linear-gradient(180deg,rgba(4,8,12,.02),rgba(4,8,12,.12))"}} />
  </AbsoluteFill>
);

const WeekendTasks: React.FC = () => {
  const frame = useCurrentFrame();
  const items = ["跑步", "画画", "旅行", "散步"];
  return (
    <AbsoluteFill style={{background: "radial-gradient(circle at 50% 38%,#2B353A,#10171C 72%)", padding: "210px 105px 300px"}}>
      <div style={{fontFamily: "STKaiti, serif", fontSize: 74, color: IVORY}}>周末人事部</div>
      <div style={{marginTop: 22, color: "rgba(247,241,230,.56)", fontSize: 30, letterSpacing: 8}}>星期六自动上线</div>
      <div style={{marginTop: 150}}>
        {items.map((item, i) => {
          const enter = interpolate(frame, [i * 28, i * 28 + 18], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
          return (
            <div key={item} style={{height: 180, marginBottom: 24, border: "1px solid rgba(217,83,63,.48)", background: "rgba(13,20,24,.82)", display: "flex", alignItems: "center", opacity: enter, transform: `translateX(${(1 - enter) * 80}px)`, padding: "0 55px"}}>
              <div style={{width: 54, height: 54, borderRadius: 40, border: `3px solid ${RED}`, marginRight: 38}} />
              <div style={{fontSize: 62, color: IVORY, letterSpacing: 10}}>{item}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const ReviewRings: React.FC = () => {
  const frame = useCurrentFrame();
  const labels = ["自律", "有趣", "会生活"];
  return (
    <AbsoluteFill style={{background: "linear-gradient(145deg,#111A1F,#293238)", padding: "245px 90px 300px"}}>
      <div style={{fontFamily: "STKaiti, serif", color: IVORY, fontSize: 72, lineHeight: 1.2}}>爱好戴上工牌以后</div>
      <div style={{display: "flex", justifyContent: "space-between", marginTop: 230}}>
        {labels.map((label, i) => {
          const p = interpolate(frame, [30 + i * 35, 110 + i * 35], [0, 0.72], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
          return (
            <div key={label} style={{width: 280, textAlign: "center"}}>
              <div style={{width: 240, height: 240, margin: "0 auto", borderRadius: 150, background: `conic-gradient(${RED} ${p * 360}deg,rgba(255,255,255,.1) 0)`, padding: 12}}>
                <div style={{width: "100%", height: "100%", borderRadius: 140, background: INK, display: "grid", placeItems: "center", color: IVORY, fontSize: 50}}>{label}</div>
              </div>
              <div style={{marginTop: 42, height: 3, background: "rgba(217,83,63,.55)"}} />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const TwoQuestions: React.FC = () => {
  const frame = useCurrentFrame();
  const reveal = interpolate(frame, [70, 130], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{background: "radial-gradient(circle at 50% 50%,#2B353A,#10171C 74%)", padding: "330px 92px"}}>
      <div style={{fontFamily: "STKaiti, serif", fontSize: 72, lineHeight: 1.35, color: IVORY}}>我还想不想做？</div>
      <div style={{height: 2, background: RED, margin: "80px 0", transform: `scaleX(${reveal})`, transformOrigin: "left"}} />
      <div style={{fontFamily: "STKaiti, serif", fontSize: 72, lineHeight: 1.35, color: `rgba(247,241,230,${0.38 + reveal * 0.62})`, transform: `translateY(${(1 - reveal) * 28}px)`}}>这能不能证明<br />我是个不错的人？</div>
      <div style={{marginTop: 140, color: "rgba(247,241,230,.52)", fontSize: 30, letterSpacing: 4}}>两个问题，会把周末带去不同方向</div>
    </AbsoluteFill>
  );
};

const Caption: React.FC<{caption: HobbyCaption}> = ({caption}) => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 4], [0, 1], {extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center", paddingBottom: 235, pointerEvents: "none"}}>
      <div style={{maxWidth: 900, padding: "4px 16px", opacity: enter, transform: `translateY(${(1 - enter) * 10}px)`, textAlign: "center", fontFamily: "PingFang SC, Hiragino Sans GB, sans-serif", fontSize: caption.text.length > 19 ? 40 : 44, fontWeight: 650, lineHeight: 1.38, letterSpacing: 1.5, color: "white", WebkitTextStroke: "3.5px rgba(0,0,0,.92)", paintOrder: "stroke fill", textShadow: "0 3px 7px rgba(0,0,0,.95)"}}>
        {caption.text}
      </div>
    </AbsoluteFill>
  );
};

const Brand: React.FC = () => (
  <div style={{position: "absolute", right: 68, top: 88, display: "flex", alignItems: "center", gap: 13, fontSize: 24, letterSpacing: 7, color: "rgba(255,255,255,.72)"}}><span style={{width: 30, height: 2, background: RED}} />树精灵</div>
);

const Sec: React.FC<{from: number; to: number; children: React.ReactNode}> = ({from, to, children}) => <Sequence from={Math.round(from * 30)} durationInFrames={Math.max(1, Math.round((to - from) * 30))}>{children}</Sequence>;

export const TreeElfHobbyVideo: React.FC<TreeElfHobbyVideoProps> = ({captions}) => {
  const frame = useCurrentFrame();
  const music = interpolate(frame, [0, 45, 2470, 2575], [0, 0.052, 0.052, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{backgroundColor: INK}}>
      <Sec from={0} to={6}><Still src="P00" /></Sec>
      <Sec from={6} to={12.96}><WeekendTasks /></Sec>
      <Sec from={12.96} to={18.14}><Still src="P01" zoom={1.05} /></Sec>
      <Sec from={18.14} to={27.78}><Clip src="W01" playbackRate={0.42} /></Sec>
      <Sec from={27.78} to={32.42}><Still src="P03" zoom={1.04} /></Sec>
      <Sec from={32.42} to={38.02}><ReviewRings /></Sec>
      <Sec from={38.02} to={45.52}><Clip src="W02" playbackRate={0.54} /></Sec>
      <Sec from={45.52} to={53.74}><Still src="P05" zoom={1.07} /></Sec>
      <Sec from={53.74} to={58.8}><TwoQuestions /></Sec>
      <Sec from={58.8} to={67.86}><Still src="P06" zoom={1.07} pan={24} /></Sec>
      <Sec from={67.86} to={76.0}><Clip src="W03" playbackRate={0.5} /></Sec>
      <Sec from={76.0} to={80.96}><Still src="P06" zoom={1.03} pan={-18} /></Sec>
      <Sec from={80.96} to={84.52}><Clip src="W04" /></Sec>
      <Sec from={84.52} to={85.83}><Still src="P02" zoom={1.02} /></Sec>
      <Audio src={asset("audio/narration.wav")} />
      <Audio src={asset("audio/background.mp3")} volume={music} />
      <Brand />
      {captions.map((caption, i) => <Sequence key={`${i}-${caption.start}`} from={Math.round(caption.start * 30)} durationInFrames={Math.max(1, Math.round((caption.end - caption.start) * 30))}><Caption caption={caption} /></Sequence>)}
      <Sequence from={0} durationInFrames={1}><Img src={asset("images/platform_cover.png")} style={{width: "100%", height: "100%", objectFit: "cover"}} /></Sequence>
    </AbsoluteFill>
  );
};
