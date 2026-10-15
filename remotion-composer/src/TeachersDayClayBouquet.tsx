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

export type ClayMotion = "push-in" | "pull-back" | "drift-left" | "drift-right" | "drift-up";

export type ClayScene = {
  id: string;
  kind: "still" | "video";
  src: string;
  from: number;
  to: number;
  motion?: ClayMotion;
  focalPoint?: {x: number; y: number};
  playbackRate?: number;
};

export type ClayCaption = {
  text: string;
  startMs: number;
  endMs: number;
};

export type ClayNarrationBeat = {
  src: string;
  atMs: number;
  durationMs: number;
};

export type ClayEndCard = {
  fromMs: number;
  mainText: string;
  subText: string;
  footnote: string;
};

export type TeachersDayClayBouquetProps = {
  assetRoot: string;
  title: string;
  totalSeconds: number;
  scenes: ClayScene[];
  captions: ClayCaption[];
  narration: ClayNarrationBeat[];
  musicSrc?: string;
  musicVolume?: number;
  endCard?: ClayEndCard;
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

const MOTIONS: Record<ClayMotion, {x: [number, number]; y: [number, number]; scale: [number, number]}> = {
  "push-in": {x: [0, -8], y: [7, -5], scale: [1.025, 1.09]},
  "pull-back": {x: [-9, 8], y: [-5, 5], scale: [1.1, 1.03]},
  "drift-left": {x: [20, -20], y: [4, -4], scale: [1.055, 1.075]},
  "drift-right": {x: [-20, 20], y: [-4, 4], scale: [1.06, 1.08]},
  "drift-up": {x: [-5, 5], y: [24, -24], scale: [1.055, 1.08]},
};

const StillScene: React.FC<{scene: ClayScene; fadeFrames: number}> = ({scene, fadeFrames}) => {
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
    <AbsoluteFill style={{overflow: "hidden", backgroundColor: "#f2e6d0", opacity}}>
      <Img
        src={staticFile(scene.src)}
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

const VideoScene: React.FC<{scene: ClayScene; fadeFrames: number}> = ({scene, fadeFrames}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, Math.max(1, fadeFrames)], [0, 1], clamp);
  return (
    <AbsoluteFill style={{backgroundColor: "#f2e6d0", opacity}}>
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
  caption: ClayCaption;
  style?: TeachersDayClayBouquetProps["captionStyle"];
}> = ({caption, style}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 4], [0, 1], clamp);
  const baseSize = style?.fontSize ?? 46;
  const fontSize = caption.text.length > 24 ? baseSize - 6 : caption.text.length > 18 ? baseSize - 3 : baseSize;
  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        padding: `0 76px ${style?.safeBottom ?? 330}px`,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          maxWidth: 930,
          opacity,
          color: style?.color ?? "#FFFFFF",
          fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif',
          fontSize,
          fontWeight: 600,
          lineHeight: 1.34,
          letterSpacing: 1,
          textAlign: "center",
          WebkitTextStroke: `${style?.outlineWidth ?? 3}px ${style?.outlineColor ?? "#4a3826"}`,
          paintOrder: "stroke fill",
          textShadow: "0 2px 5px rgba(0,0,0,.5)",
        }}
      >
        {caption.text}
      </div>
    </AbsoluteFill>
  );
};

const WarmTreatment: React.FC = () => (
  <AbsoluteFill style={{pointerEvents: "none"}}>
    <AbsoluteFill
      style={{
        boxShadow: "inset 0 0 120px rgba(74,56,38,.16)",
        background: "linear-gradient(180deg, rgba(255,246,222,.03), rgba(74,56,38,.05))",
      }}
    />
  </AbsoluteFill>
);

const EndCardLayer: React.FC<{endCard: ClayEndCard}> = ({endCard}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scrim = interpolate(frame, [0, fps * 0.7], [0, 0.66], clamp);
  const rise = interpolate(frame, [fps * 0.25, fps * 1.1], [26, 0], {
    ...clamp,
    easing: Easing.out(Easing.cubic),
  });
  const textOpacity = interpolate(frame, [fps * 0.25, fps * 0.9], [0, 1], clamp);
  return (
    <AbsoluteFill style={{pointerEvents: "none"}} id="endcard">
      <AbsoluteFill style={{background: `linear-gradient(180deg, rgba(58,42,26,${scrim}), rgba(43,30,18,${scrim + 0.08}))`}} />
      <AbsoluteFill
        style={{
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          gap: 26,
          padding: "0 90px",
          opacity: textOpacity,
          transform: `translateY(${rise}px)`,
        }}
      >
        <div
          style={{
            color: "#FFF6E5",
            fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif',
            fontSize: 84,
            fontWeight: 700,
            letterSpacing: 8,
            textShadow: "0 3px 12px rgba(0,0,0,.45)",
          }}
        >
          {endCard.mainText}
        </div>
        <div style={{width: 64, height: 3, background: "#E8A33D", borderRadius: 2}} />
        <div
          style={{
            color: "rgba(255,246,229,.94)",
            fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif',
            fontSize: 40,
            fontWeight: 500,
            letterSpacing: 3,
            textAlign: "center",
          }}
        >
          {endCard.subText}
        </div>
      </AbsoluteFill>
      <div
        style={{
          position: "absolute",
          bottom: 150,
          left: 0,
          right: 0,
          textAlign: "center",
          color: "rgba(255,246,229,.62)",
          fontFamily: '"PingFang SC", "Hiragino Sans GB", sans-serif',
          fontSize: 22,
          letterSpacing: 2,
          opacity: textOpacity,
        }}
      >
        {endCard.footnote}
      </div>
    </AbsoluteFill>
  );
};

export const TeachersDayClayBouquet: React.FC<TeachersDayClayBouquetProps> = (props) => {
  const {fps, durationInFrames} = useVideoConfig();
  const transitionFrames = props.transitionFrames ?? 10;
  const source = (relative: string) => `${props.assetRoot}/${relative}`;
  const musicFade = (frame: number) => {
    const second = frame / fps;
    const speaking = props.narration.some((beat) => {
      const beatStart = beat.atMs / 1000;
      const beatEnd = (beat.atMs + beat.durationMs) / 1000;
      return second >= beatStart - 0.15 && second <= beatEnd + 0.2;
    });
    const envelope = interpolate(
      frame,
      [0, fps * 0.8, Math.max(fps * 0.8 + 1, durationInFrames - fps * 1.6), durationInFrames],
      [0, 1, 1, 0],
      clamp,
    );
    return (props.musicVolume ?? 0.2) * (speaking ? 0.4 : 0.85) * envelope;
  };

  return (
    <AbsoluteFill style={{backgroundColor: "#f2e6d0"}}>
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

      {props.narration.map((beat, index) => {
        const from = Math.round((beat.atMs / 1000) * fps);
        return (
          <Sequence key={`${beat.src}-${index}`} from={from} durationInFrames={Math.max(1, durationInFrames - from)}>
            <Audio src={staticFile(source(beat.src))} />
          </Sequence>
        );
      })}

      {props.musicSrc ? (
        <Sequence from={0} durationInFrames={durationInFrames}>
          <Audio src={staticFile(source(props.musicSrc))} loop volume={musicFade} />
        </Sequence>
      ) : null}

      {props.captions.map((caption, index) => {
        const from = Math.floor((caption.startMs / 1000) * fps);
        const duration = Math.max(1, Math.ceil(((caption.endMs - caption.startMs) / 1000) * fps));
        return (
          <Sequence key={`${caption.startMs}-${index}`} from={from} durationInFrames={duration} premountFor={12}>
            <CaptionLayer caption={caption} style={props.captionStyle} />
          </Sequence>
        );
      })}

      {props.endCard ? (
        <Sequence from={Math.floor((props.endCard.fromMs / 1000) * fps)} durationInFrames={Math.max(1, durationInFrames)}>
          <EndCardLayer endCard={props.endCard} />
        </Sequence>
      ) : null}

      <WarmTreatment />
    </AbsoluteFill>
  );
};
