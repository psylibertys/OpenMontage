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

export type TreeElfMotion = "push-right" | "push-left" | "drift-up" | "drift-down" | "pull-back";
export type TreeElfScene = {
  id: string;
  kind: "still" | "video";
  src: string;
  from: number;
  to: number;
  motion?: TreeElfMotion;
  playbackRate?: number;
};
export type TreeElfCaption = {start: number; end: number; text: string};
export type TreeElfInfoCard = {
  id: string;
  type: "comparison" | "questions" | "steps" | "keywords";
  from: number;
  to: number;
  eyebrow?: string;
  left?: string;
  operator?: string;
  right?: string;
  items?: string[];
};
export type TreeElfPhilosophyEpisodeProps = {
  assetRoot: string;
  brand?: string;
  durationSeconds: number;
  cover?: {src: string; title: string; englishTitle?: string};
  scenes: TreeElfScene[];
  infoCards: TreeElfInfoCard[];
  captions: TreeElfCaption[];
  narrationSrc?: string;
  musicSrc?: string;
  musicVolume?: number;
  captionStyle?: {
    color?: string;
    background?: string;
    outline_color?: string;
    outline_width?: number;
    font_size?: number;
    safe_bottom?: number;
  };
};

const seconds = (value: number) => Math.max(0, Math.round(value * 30));

const Still: React.FC<{src: string; motion?: TreeElfMotion}> = ({src, motion = "push-right"}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });
  const transforms: Record<TreeElfMotion, {x: [number, number]; y: [number, number]; scale: [number, number]}> = {
    "push-right": {x: [-34, 34], y: [12, -12], scale: [1.035, 1.15]},
    "push-left": {x: [38, -38], y: [-10, 14], scale: [1.04, 1.14]},
    "drift-up": {x: [-12, 18], y: [44, -44], scale: [1.09, 1.13]},
    "drift-down": {x: [16, -14], y: [-42, 42], scale: [1.1, 1.14]},
    "pull-back": {x: [-18, 18], y: [16, -18], scale: [1.17, 1.045]},
  };
  const selected = transforms[motion];
  const x = interpolate(progress, [0, 1], selected.x);
  const y = interpolate(progress, [0, 1], selected.y);
  const scale = interpolate(progress, [0, 1], selected.scale);
  return (
    <AbsoluteFill style={{overflow: "hidden", backgroundColor: "#07131C"}}>
      <Img src={src} style={{width: "100%", height: "100%", objectFit: "cover", transform: `translate3d(${x}px,${y}px,0) scale(${scale})`}} />
      <AbsoluteFill style={{background: "linear-gradient(180deg,rgba(3,9,14,.02),rgba(3,9,14,.18))"}} />
    </AbsoluteFill>
  );
};

const InfoCard: React.FC<{card: TreeElfInfoCard}> = ({card}) => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 16], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const panel: React.CSSProperties = {
    border: "1px solid rgba(255,255,255,.24)",
    borderRadius: 34,
    background: "rgba(4,17,27,.72)",
    boxShadow: "0 24px 80px rgba(0,0,0,.38)",
    backdropFilter: "blur(16px)",
  };
  return (
    <AbsoluteFill style={{justifyContent: "center", padding: "170px 72px 320px", background: "linear-gradient(180deg,rgba(2,9,15,.18),rgba(2,9,15,.72))"}}>
      <div style={{fontSize: 29, letterSpacing: 8, color: "rgba(255,255,255,.72)", marginBottom: 34}}>{card.eyebrow}</div>
      {card.type === "comparison" ? (
        <div style={{...panel, display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", padding: "66px 34px", opacity: enter, transform: `translateY(${(1 - enter) * 42}px)`}}>
          <div style={{fontSize: 55, fontWeight: 800, lineHeight: 1.25, textAlign: "center", color: "#8CE2D8"}}>{card.left}</div>
          <div style={{fontSize: 68, fontWeight: 900, color: "#F3C16B", padding: "0 24px"}}>{card.operator || "≠"}</div>
          <div style={{fontSize: 55, fontWeight: 800, lineHeight: 1.25, textAlign: "center", color: "white"}}>{card.right}</div>
        </div>
      ) : (
        <div style={{display: "flex", flexDirection: "column", gap: 24}}>
          {(card.items || []).map((item, index) => {
            const show = interpolate(frame, [8 + index * 12, 21 + index * 12], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic)});
            return (
              <div key={`${card.id}-${index}`} style={{...panel, minHeight: 142, display: "flex", alignItems: "center", gap: 30, padding: "28px 40px", opacity: show, transform: `translateX(${(1 - show) * (index % 2 ? 65 : -65)}px)`}}>
                <span style={{fontSize: 26, fontWeight: 850, color: index % 2 ? "#F3C16B" : "#78DDD4"}}>{String(index + 1).padStart(2, "0")}</span>
                <span style={{fontSize: 52, lineHeight: 1.25, fontWeight: 800, color: "white"}}>{item}</span>
              </div>
            );
          })}
        </div>
      )}
    </AbsoluteFill>
  );
};

const Caption: React.FC<{caption: TreeElfCaption; style?: TreeElfPhilosophyEpisodeProps["captionStyle"]}> = ({caption, style}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 4], [0, 1], {extrapolateRight: "clamp"});
  const fontSize = caption.text.length > 24 ? (style?.font_size || 42) - 4 : caption.text.length > 17 ? (style?.font_size || 42) - 2 : style?.font_size || 42;
  return (
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center", paddingBottom: style?.safe_bottom || 360, pointerEvents: "none"}}>
      <div style={{maxWidth: 900, padding: "4px 14px", opacity, textAlign: "center", fontFamily: "PingFang SC, Hiragino Sans GB, sans-serif", fontSize, fontWeight: 650, lineHeight: 1.38, letterSpacing: 1.2, color: style?.color || "#FFFFFF", background: style?.background === "none" ? "transparent" : style?.background, WebkitTextStroke: `${style?.outline_width || 3.5}px ${style?.outline_color || "rgba(0,0,0,.92)"}`, paintOrder: "stroke fill", textShadow: "0 3px 7px rgba(0,0,0,.9)"}}>{caption.text}</div>
    </AbsoluteFill>
  );
};

export const TreeElfPhilosophyEpisode: React.FC<TreeElfPhilosophyEpisodeProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const second = frame / fps;
  const speaking = props.captions.some((caption) => second >= caption.start - 0.08 && second <= caption.end + 0.1);
  const musicFade = interpolate(frame, [0, 24, durationInFrames - 48, durationInFrames], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const music = (props.musicVolume ?? 0.3) * (speaking ? 0.42 : 0.75) * musicFade;
  const source = (relative: string) => staticFile(`${props.assetRoot}/${relative}`);
  return (
    <AbsoluteFill style={{backgroundColor: "#07131C"}}>
      {props.scenes.map((scene) => (
        <Sequence key={scene.id} from={seconds(scene.from)} durationInFrames={Math.max(1, seconds(scene.to - scene.from))}>
          {scene.kind === "video" ? (
            <OffthreadVideo src={source(scene.src)} muted playbackRate={scene.playbackRate || 1} style={{width: "100%", height: "100%", objectFit: "cover"}} />
          ) : (
            <Still src={source(scene.src)} motion={scene.motion} />
          )}
        </Sequence>
      ))}
      {props.infoCards.map((card) => (
        <Sequence key={card.id} from={seconds(card.from)} durationInFrames={Math.max(1, seconds(card.to - card.from))}>
          <InfoCard card={card} />
        </Sequence>
      ))}
      {props.narrationSrc ? <Audio src={source(props.narrationSrc)} /> : null}
      {props.musicSrc ? <Audio src={source(props.musicSrc)} volume={music} /> : null}
      <div style={{position: "absolute", right: 68, top: 88, display: "flex", alignItems: "center", gap: 13, fontSize: 24, letterSpacing: 7, color: "rgba(255,255,255,.8)", textShadow: "0 2px 5px rgba(0,0,0,.8)"}}><span style={{width: 30, height: 2, background: "#78DDD4"}} />{props.brand || "树精灵"}</div>
      {props.captions.map((caption, index) => (
        <Sequence key={`${index}-${caption.start}`} from={seconds(caption.start)} durationInFrames={Math.max(1, seconds(caption.end - caption.start))}>
          <Caption caption={caption} style={props.captionStyle} />
        </Sequence>
      ))}
      {props.cover?.src ? (
        <Sequence from={0} durationInFrames={1}>
          <AbsoluteFill>
            <Img src={source(props.cover.src)} style={{width: "100%", height: "100%", objectFit: "cover"}} />
            <AbsoluteFill style={{justifyContent: "center", alignItems: "center", padding: "180px 80px", background: "linear-gradient(180deg,rgba(2,8,14,.14),rgba(2,8,14,.48))"}}>
              <div style={{fontSize: 112, fontWeight: 850, letterSpacing: 15, color: "#F7F2E8", textShadow: "0 6px 24px rgba(0,0,0,.75)"}}>{props.cover.title}</div>
              <div style={{marginTop: 26, fontSize: 26, letterSpacing: 8, color: "rgba(247,242,232,.8)"}}>{props.cover.englishTitle}</div>
            </AbsoluteFill>
            <div style={{position: "absolute", right: 68, top: 88, display: "flex", alignItems: "center", gap: 13, fontSize: 24, letterSpacing: 7, color: "rgba(255,255,255,.82)", textShadow: "0 2px 5px rgba(0,0,0,.8)"}}><span style={{width: 30, height: 2, background: "#78DDD4"}} />{props.brand || "树精灵"}</div>
          </AbsoluteFill>
        </Sequence>
      ) : null}
    </AbsoluteFill>
  );
};
