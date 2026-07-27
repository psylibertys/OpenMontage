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

export type RankingCaption = {start: number; end: number; text: string};
export type TreeElfRankingVideoProps = {captions?: RankingCaption[]};

const ROOT = "treeelf-universal-ranking";
const COBALT = "#174A82";
const SAFFRON = "#E8A52B";
const asset = (path: string) => staticFile(`${ROOT}/${path}`);

export const rankingCaptions: RankingCaption[] = [
  {start: 0.48, end: 5.48, text: "刷一会儿手机，人生就会自动参加一场来历不明的排名。"},
  {start: 5.72, end: 11.58, text: "有人25岁买房，有人30岁环球旅行，有人凌晨5点健身。"},
  {start: 11.72, end: 17.64, text: "你只是躺着看了8分钟，系统已经很礼貌地通知：目前全面落后。"},
  {start: 18.2, end: 24.62, text: "哲学家阿格尼斯·卡拉德把现代人的一种处境叫作“单一语境”。"},
  {start: 24.84, end: 29.72, text: "原本在不同房间里运行的生活，被放进同一个评价场。"},
  {start: 30.0, end: 34.8, text: "厨房有厨房的事，病房有病房的事，舞台也有舞台的事。"},
  {start: 34.96, end: 40.64, text: "万能排行榜一进门，却坚持给做饭、康复和演出排出统一名次。"},
  {start: 41.28, end: 46.34, text: "卡拉德认为，这套公开标准一旦被越来越多人接受，"},
  {start: 46.48, end: 53.38, text: "比较不只会变频繁，大家也更容易朝相似的目标和生活模板靠拢。"},
  {start: 53.98, end: 58.0, text: "很多差异，只有在共同目的下才叫差距。"},
  {start: 58.0, end: 62.12, text: "两个参加同一场比赛的人，可以比较速度；"},
  {start: 62.2, end: 68.04, text: "一个照顾家人的人和一个创业的人，并没有在完成同一张试卷。"},
  {start: 68.22, end: 73.34, text: "把他们排在一起，数字会很热闹，意义却可能不在场。"},
  {start: 73.86, end: 78.32, text: "比较再次启动时，有句话可以把房间找回来。"},
  {start: 78.4, end: 81.06, text: "这张榜在替什么目的服务？"},
  {start: 81.2, end: 84.9, text: "目的说不清，那个名次就不必急着认领。"},
  {start: 85.12, end: 87.64, text: "榜单很忙，但不一定懂你。"},
  {start: 88.0, end: 94.14, text: "把人生送回各自的房间，万能榜单也只是一块过度热心的电子屏。"},
];

const Still: React.FC<{src: string; zoom?: number; pan?: number}> = ({src, zoom = 1.07, pan = 0}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });
  return (
    <AbsoluteFill style={{backgroundColor: "#F0E5D2", overflow: "hidden"}}>
      <Img
        src={asset(`images/${src}.png`)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `translateX(${pan * (progress - 0.5)}px) scale(${1 + (zoom - 1) * progress})`,
        }}
      />
      <AbsoluteFill style={{background: "linear-gradient(180deg,rgba(5,20,35,.02),rgba(5,20,35,.13))"}} />
    </AbsoluteFill>
  );
};

const Clip: React.FC<{src: string; playbackRate: number}> = ({src, playbackRate}) => (
  <AbsoluteFill style={{backgroundColor: "#0C2032"}}>
    <OffthreadVideo
      src={asset(`video/${src}.mp4`)}
      muted
      playbackRate={playbackRate}
      style={{width: "100%", height: "100%", objectFit: "cover"}}
    />
    <AbsoluteFill style={{background: "linear-gradient(180deg,rgba(5,20,35,.01),rgba(5,20,35,.12))"}} />
  </AbsoluteFill>
);

const Caption: React.FC<{caption: RankingCaption}> = ({caption}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 4], [0, 1], {extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center", paddingBottom: 235, pointerEvents: "none"}}>
      <div
        style={{
          maxWidth: 900,
          padding: "4px 16px",
          opacity,
          transform: `translateY(${(1 - opacity) * 10}px)`,
          textAlign: "center",
          fontFamily: "PingFang SC, Hiragino Sans GB, sans-serif",
          fontSize: caption.text.length > 24 ? 39 : caption.text.length > 17 ? 41 : 44,
          fontWeight: 650,
          lineHeight: 1.38,
          letterSpacing: 1.3,
          color: "white",
          WebkitTextStroke: "3.5px rgba(0,0,0,.92)",
          paintOrder: "stroke fill",
          textShadow: "0 3px 7px rgba(0,0,0,.95)",
        }}
      >
        {caption.text}
      </div>
    </AbsoluteFill>
  );
};

const Brand: React.FC = () => (
  <div style={{position: "absolute", right: 68, top: 88, display: "flex", alignItems: "center", gap: 13, fontSize: 24, letterSpacing: 7, color: "rgba(255,255,255,.78)", textShadow: "0 2px 5px rgba(0,0,0,.8)"}}>
    <span style={{width: 30, height: 2, background: SAFFRON}} />树精灵
  </div>
);

const Sec: React.FC<{from: number; to: number; children: React.ReactNode}> = ({from, to, children}) => (
  <Sequence from={Math.round(from * 30)} durationInFrames={Math.max(1, Math.round((to - from) * 30))}>{children}</Sequence>
);

export const TreeElfRankingVideo: React.FC<TreeElfRankingVideoProps> = ({captions = rankingCaptions}) => {
  const frame = useCurrentFrame();
  const music = interpolate(frame, [0, 45, 2710, 2826], [0, 0.046, 0.046, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{backgroundColor: COBALT}}>
      <Sec from={0} to={8.0}><Clip src="W01" playbackRate={0.5} /></Sec>
      <Sec from={8.0} to={17.8}><Still src="P00" zoom={1.06} pan={18} /></Sec>
      <Sec from={17.8} to={25.5}><Clip src="W02" playbackRate={0.53} /></Sec>
      <Sec from={25.5} to={34.9}><Still src="P01" zoom={1.04} /></Sec>
      <Sec from={34.9} to={42.5}><Still src="P02" zoom={1.06} pan={-14} /></Sec>
      <Sec from={42.5} to={48.0}><Still src="P03" zoom={1.03} /></Sec>
      <Sec from={48.0} to={53.5}><Clip src="W03" playbackRate={0.74} /></Sec>
      <Sec from={53.5} to={64.0}><Still src="P04" zoom={1.06} pan={16} /></Sec>
      <Sec from={64.0} to={73.8}><Still src="P05" zoom={1.05} /></Sec>
      <Sec from={73.8} to={82.0}><Clip src="W04" playbackRate={0.5} /></Sec>
      <Sec from={82.0} to={94.18}><Still src="P06" zoom={1.05} pan={-12} /></Sec>
      <Audio src={asset("audio/narration.wav")} />
      <Audio src={asset("audio/background.mp3")} volume={music} />
      <Brand />
      {captions.map((caption, index) => (
        <Sequence key={`${index}-${caption.start}`} from={Math.round(caption.start * 30)} durationInFrames={Math.max(1, Math.round((caption.end - caption.start) * 30))}>
          <Caption caption={caption} />
        </Sequence>
      ))}
      <Sequence from={0} durationInFrames={1}>
        <Img src={asset("images/platform_cover.png")} style={{width: "100%", height: "100%", objectFit: "cover"}} />
      </Sequence>
    </AbsoluteFill>
  );
};
