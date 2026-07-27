import React from "react";
import {Audio} from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type FableMotion =
  | "push-in"
  | "pull-back"
  | "drift-left"
  | "drift-right"
  | "drift-up";

export type FableScene = {
  id: string;
  kind: "still" | "video";
  src: string;
  from: number;
  to: number;
  motion?: FableMotion;
  focalPoint?: {x: number; y: number};
  playbackRate?: number;
};

export type FableCaption = {
  text: string;
  startMs: number;
  endMs: number;
};

export type TreeElfFableEpisodeProps = {
  assetRoot: string;
  title: string;
  totalSeconds: number;
  coverSrc?: string;
  scenes: FableScene[];
  captions: FableCaption[];
  narrationSrc?: string;
  musicSrc?: string;
  musicVolume?: number;
  brand?: string;
  transitionFrames?: number;
  captionStyle?: {
    fontSize?: number;
    color?: string;
    outlineColor?: string;
    outlineWidth?: number;
    safeBottom?: number;
  };
};

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

const MOTIONS: Record<FableMotion, {x: [number, number]; y: [number, number]; scale: [number, number]}> = {
  "push-in": {x: [0, -8], y: [7, -5], scale: [1.025, 1.09]},
  "pull-back": {x: [-9, 8], y: [-5, 5], scale: [1.1, 1.03]},
  "drift-left": {x: [20, -20], y: [4, -4], scale: [1.055, 1.075]},
  "drift-right": {x: [-20, 20], y: [-4, 4], scale: [1.06, 1.08]},
  "drift-up": {x: [-5, 5], y: [24, -24], scale: [1.055, 1.08]},
};

const StillScene: React.FC<{scene: FableScene; fadeFrames: number}> = ({scene, fadeFrames}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const motion = MOTIONS[scene.motion ?? "push-in"];
  const progress = interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [0, 1], {
    ...clamp,
    easing: Easing.inOut(Easing.sin),
  });
  const opacity = interpolate(frame, [0, Math.max(1, fadeFrames)], [0, 1], clamp);
  const x = interpolate(progress, [0, 1], motion.x);
  const y = interpolate(progress, [0, 1], motion.y);
  const scale = interpolate(progress, [0, 1], motion.scale);
  const focal = scene.focalPoint ?? {x: 50, y: 50};

  return (
    <AbsoluteFill style={{overflow: "hidden", backgroundColor: "#d7cfbd", opacity}}>
      <Img
        src={staticFile(`${scene.src}`)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: `${focal.x}% ${focal.y}%`,
          transform: `translate3d(${x}px, ${y}px, 0) scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};

const VideoScene: React.FC<{scene: FableScene; fadeFrames: number}> = ({scene, fadeFrames}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, Math.max(1, fadeFrames)], [0, 1], clamp);
  return (
    <AbsoluteFill style={{backgroundColor: "#d7cfbd", opacity}}>
      <OffthreadVideo
        src={staticFile(scene.src)}
        muted
        playbackRate={scene.playbackRate ?? 1}
        style={{width: "100%", height: "100%", objectFit: "cover"}}
      />
    </AbsoluteFill>
  );
};

const CaptionLayer: React.FC<{
  caption: FableCaption;
  style?: TreeElfFableEpisodeProps["captionStyle"];
}> = ({caption, style}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 4], [0, 1], clamp);
  const baseSize = style?.fontSize ?? 42;
  const fontSize = caption.text.length > 24 ? baseSize - 4 : caption.text.length > 18 ? baseSize - 2 : baseSize;
  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        padding: `0 76px ${style?.safeBottom ?? 360}px`,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          maxWidth: 920,
          opacity,
          color: style?.color ?? "#FFFFFF",
          fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif',
          fontSize,
          fontWeight: 600,
          lineHeight: 1.32,
          letterSpacing: 0.5,
          textAlign: "center",
          WebkitTextStroke: `${style?.outlineWidth ?? 3}px ${style?.outlineColor ?? "#000000"}`,
          paintOrder: "stroke fill",
          textShadow: "0 2px 4px rgba(0,0,0,.55)",
        }}
      >
        {caption.text}
      </div>
    </AbsoluteFill>
  );
};

const PaperTreatment: React.FC = () => (
  <AbsoluteFill style={{pointerEvents: "none"}}>
    <AbsoluteFill
      style={{
        boxShadow: "inset 0 0 130px rgba(30,35,29,.20)",
        background: "linear-gradient(180deg, rgba(255,248,224,.025), rgba(52,60,48,.045))",
      }}
    />
    <AbsoluteFill
      style={{
        opacity: 0.1,
        backgroundImage:
          "repeating-linear-gradient(16deg, rgba(255,255,255,.13) 0px, rgba(255,255,255,.13) 1px, transparent 1px, transparent 5px)",
        mixBlendMode: "soft-light",
      }}
    />
  </AbsoluteFill>
);

export const TreeElfFableEpisode: React.FC<TreeElfFableEpisodeProps> = (props) => {
  const {fps, durationInFrames} = useVideoConfig();
  const transitionFrames = props.transitionFrames ?? 10;
  const source = (relative: string) => `${props.assetRoot}/${relative}`;
  const musicFade = (frame: number) => {
    const second = frame / fps;
    const speaking = props.captions.some((caption) => second >= caption.start - 0.08 && second <= caption.end + 0.1);
    const envelope = interpolate(
      frame,
      [0, fps, Math.max(fps + 1, durationInFrames - 2 * fps), durationInFrames],
      [0, 1, 1, 0],
      clamp,
    );
    return (props.musicVolume ?? 0.3) * (speaking ? 0.42 : 0.75) * envelope;
  };

  return (
    <AbsoluteFill style={{backgroundColor: "#d7cfbd"}}>
      {props.scenes.map((scene, index) => {
        const start = Math.round(scene.from * fps);
        const end = Math.round(scene.to * fps);
        const overlap = index === 0 ? 0 : transitionFrames;
        const from = Math.max(0, start - overlap);
        const duration = Math.max(1, end - from);
        const mediaScene = {...scene, src: source(scene.src)};
        return (
          <Sequence key={scene.id} from={from} durationInFrames={duration} premountFor={fps}>
            {scene.kind === "video" ? (
              <VideoScene scene={mediaScene} fadeFrames={overlap} />
            ) : (
              <StillScene scene={mediaScene} fadeFrames={overlap} />
            )}
          </Sequence>
        );
      })}

      {props.narrationSrc ? <Audio src={staticFile(source(props.narrationSrc))} /> : null}
      {props.musicSrc ? <Audio src={staticFile(source(props.musicSrc))} loop volume={musicFade} /> : null}

      {props.coverSrc ? (
        <Sequence from={0} durationInFrames={1}>
          <AbsoluteFill style={{backgroundColor: "#d7cfbd"}}>
            <Img
              src={staticFile(source(props.coverSrc))}
              style={{width: "100%", height: "100%", objectFit: "cover"}}
            />
          </AbsoluteFill>
        </Sequence>
      ) : null}

      <div
        style={{
          position: "absolute",
          right: 54,
          top: 64,
          display: "flex",
          alignItems: "center",
          gap: 11,
          color: "rgba(255,255,255,.82)",
          fontFamily: '"PingFang SC", sans-serif',
          fontSize: 22,
          letterSpacing: 6,
          textShadow: "0 2px 5px rgba(0,0,0,.55)",
        }}
      >
        <span style={{width: 24, height: 2, background: "#d8c287"}} />
        {props.brand ?? "树精灵"}
      </div>

      {props.captions.map((caption, index) => {
        const from = Math.floor((caption.startMs / 1000) * fps);
        const duration = Math.max(1, Math.ceil(((caption.endMs - caption.startMs) / 1000) * fps));
        return (
          <Sequence key={`${caption.startMs}-${index}`} from={from} durationInFrames={duration} premountFor={12}>
            <CaptionLayer caption={caption} style={props.captionStyle} />
          </Sequence>
        );
      })}
      <PaperTreatment />
    </AbsoluteFill>
  );
};
