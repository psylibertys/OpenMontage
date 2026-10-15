import {
  AbsoluteFill,
  CalculateMetadataFunction,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {Audio} from "@remotion/media";
import { CaptionOverlay, WordCaption } from "./components/CaptionOverlay";
import { TextCard } from "./components/TextCard";
import { StatCard } from "./components/StatCard";
import { CalloutBox } from "./components/CalloutBox";
import { ComparisonCard } from "./components/ComparisonCard";
import { BarChart } from "./components/charts/BarChart";
import { LineChart } from "./components/charts/LineChart";
import { PieChart } from "./components/charts/PieChart";
import { KPIGrid } from "./components/charts/KPIGrid";
import { HeroTitle } from "./components/HeroTitle";
import { SectionTitle } from "./components/SectionTitle";
import { StatReveal } from "./components/StatReveal";

// ---------------------------------------------------------------------------
// Overlay types for talking-head video
// ---------------------------------------------------------------------------

export interface TalkingHeadOverlay {
  id?: string;
  type: string;
  in_seconds: number;
  out_seconds: number;
  position?:
    | "lower_third"
    | "upper_third"
    | "left_panel"
    | "right_panel"
    | "full_overlay";
  // Component-specific props (same as Explainer Cut)
  text?: string;
  stat?: string;
  subtitle?: string;
  callout_type?: "info" | "warning" | "tip" | "quote";
  title?: string;
  leftLabel?: string;
  rightLabel?: string;
  leftValue?: string;
  rightValue?: string;
  chartData?: any[];
  chartSeries?: any[];
  chartColors?: string[];
  chartAnimation?: string;
  donut?: boolean;
  centerLabel?: string;
  centerValue?: string;
  showGrid?: boolean;
  showValues?: boolean;
  showLegend?: boolean;
  showMarkers?: boolean;
  columns?: 2 | 3 | 4;
  // Styling
  backgroundColor?: string;
  color?: string;
  accentColor?: string;
  fontSize?: number;
}

// ---------------------------------------------------------------------------
// Position presets for 9:16 (1080x1920) frame
// ---------------------------------------------------------------------------

const POSITION_STYLES: Record<string, React.CSSProperties> = {
  lower_third: {
    position: "absolute",
    bottom: 320, // Above caption area (~1600px)
    left: 40,
    right: 40,
    height: 480,
  },
  upper_third: {
    position: "absolute",
    top: 80,
    left: 40,
    right: 40,
    height: 480,
  },
  left_panel: {
    position: "absolute",
    top: 200,
    left: 40,
    width: 480,
    bottom: 400,
  },
  right_panel: {
    position: "absolute",
    top: 200,
    right: 40,
    width: 480,
    bottom: 400,
  },
  full_overlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
};

// ---------------------------------------------------------------------------
// Overlay component dispatcher — maps overlay type to Remotion component
// ---------------------------------------------------------------------------

const OverlayContent: React.FC<{ overlay: TalkingHeadOverlay }> = ({
  overlay,
}) => {
  const bgColor = overlay.backgroundColor || "#0F172A";

  if (overlay.type === "text_card" && overlay.text) {
    return (
      <TextCard
        text={overlay.text}
        fontSize={overlay.fontSize}
        color={overlay.color}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "stat_card" && overlay.stat) {
    return (
      <StatCard
        stat={overlay.stat}
        subtitle={overlay.subtitle}
        accentColor={overlay.accentColor}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "callout" && overlay.text) {
    return (
      <CalloutBox
        text={overlay.text}
        type={overlay.callout_type}
        title={overlay.title}
        borderColor={overlay.accentColor}
        backgroundColor={overlay.backgroundColor}
        textColor={overlay.color}
        containerBackgroundColor={bgColor}
      />
    );
  }
  if (
    overlay.type === "comparison" &&
    overlay.leftLabel &&
    overlay.rightLabel
  ) {
    return (
      <ComparisonCard
        leftLabel={overlay.leftLabel}
        rightLabel={overlay.rightLabel}
        leftValue={overlay.leftValue || ""}
        rightValue={overlay.rightValue || ""}
        title={overlay.title}
        backgroundColor={bgColor}
        textColor={overlay.color}
      />
    );
  }
  if (overlay.type === "bar_chart" && overlay.chartData) {
    return (
      <BarChart
        data={overlay.chartData}
        title={overlay.title}
        colors={overlay.chartColors}
        animationStyle={(overlay.chartAnimation as any) || "grow-up"}
        showValues={overlay.showValues}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "line_chart" && overlay.chartSeries) {
    return (
      <LineChart
        series={overlay.chartSeries}
        title={overlay.title}
        colors={overlay.chartColors}
        animationStyle={(overlay.chartAnimation as any) || "draw"}
        showGrid={overlay.showGrid}
        showMarkers={overlay.showMarkers}
        showLegend={overlay.showLegend}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "pie_chart" && overlay.chartData) {
    return (
      <PieChart
        data={overlay.chartData}
        title={overlay.title}
        colors={overlay.chartColors}
        animationStyle={(overlay.chartAnimation as any) || "expand"}
        donut={overlay.donut}
        centerLabel={overlay.centerLabel}
        centerValue={overlay.centerValue}
        showLegend={overlay.showLegend}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "kpi_grid" && overlay.chartData) {
    return (
      <KPIGrid
        metrics={overlay.chartData}
        title={overlay.title}
        columns={overlay.columns}
        colors={overlay.chartColors}
        animationStyle={(overlay.chartAnimation as any) || "count-up"}
        backgroundColor={bgColor}
      />
    );
  }
  if (overlay.type === "hero_title" && overlay.text) {
    return <HeroTitle title={overlay.text} subtitle={overlay.subtitle} />;
  }
  if (overlay.type === "section_title" && overlay.text) {
    return (
      <SectionTitle
        title={overlay.text}
        subtitle={overlay.subtitle}
        accentColor={overlay.accentColor}
        position="top-left"
      />
    );
  }
  if (overlay.type === "stat_reveal" && overlay.text) {
    return (
      <StatReveal
        stat={overlay.text}
        label={overlay.subtitle}
        accentColor={overlay.accentColor}
        position="bottom-right"
      />
    );
  }
  return null;
};

// ---------------------------------------------------------------------------
// Positioned overlay wrapper — handles position + fade in/out
// ---------------------------------------------------------------------------

const PositionedOverlay: React.FC<{ overlay: TalkingHeadOverlay }> = ({
  overlay,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Fade in over 8 frames (~0.27s), fade out over 8 frames
  const fadeIn = interpolate(frame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 8, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const opacity = fadeIn * fadeOut;

  const position = overlay.position || "lower_third";
  const posStyle = POSITION_STYLES[position] || POSITION_STYLES.lower_third;
  const isFullOverlay = position === "full_overlay";

  return (
    <div
      style={{
        ...posStyle,
        opacity,
        overflow: "hidden",
        borderRadius: isFullOverlay ? 0 : 16,
        boxShadow: isFullOverlay
          ? "none"
          : "0 8px 32px rgba(0, 0, 0, 0.4)",
      }}
    >
      {isFullOverlay && (
        <AbsoluteFill style={{ background: "rgba(0, 0, 0, 0.7)" }} />
      )}
      <OverlayContent overlay={overlay} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main TalkingHead composition
// ---------------------------------------------------------------------------

export interface TalkingHeadProps {
  [key: string]: unknown;
  videoSrc: string;
  captions: WordCaption[];
  overlays?: TalkingHeadOverlay[];
  wordsPerPage?: number;
  fontSize?: number;
  highlightColor?: string;
  audioSrc?: string;
  durationSeconds?: number;
  hookTitle?: string;
  hookDurationSeconds?: number;
  hookDisplayMode?: "persistent" | "intro";
  watermarkLines?: string[];
  sourceLayout?: "cover" | "contain-blur";
  captionBottomPx?: number;
  captionOutlineWidth?: number;
  captionBackgroundColor?: string;
  captionFontFamily?: string;
  hookFontFamily?: string;
  hookFontSrc?: string;
}

const resolveMedia = (src: string): string => {
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:") || src.startsWith("file://")) {
    return src;
  }
  if (src.startsWith("/")) return `file://${src}`;
  return staticFile(src);
};

const HookTitle: React.FC<{text: string; fadeAtEnd?: boolean; instant?: boolean; fontFamily?: string}> = ({
  text,
  fadeAtEnd = false,
  instant = false,
  fontFamily = '"Kaiti SC", "STKaiti", serif',
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const enter = instant
    ? 1
    : spring({frame, fps, config: {damping: 18, stiffness: 110}});
  const fadeOut = fadeAtEnd
    ? interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;
  return (
    <div style={{
      position: "absolute",
      top: 245,
      left: 70,
      right: 70,
      textAlign: "center",
      color: "#FFD34E",
      fontFamily,
      fontSize: 70,
      fontWeight: 900,
      lineHeight: 1.28,
      WebkitTextStroke: "7px #000000",
      paintOrder: "stroke fill",
      textShadow: "0 3px 4px rgba(0,0,0,0.95)",
      whiteSpace: "pre-wrap",
      opacity: enter * fadeOut,
      transform: `translateY(${interpolate(enter, [0, 1], [22, 0])}px)`,
    }}>{text}</div>
  );
};

export const TalkingHead: React.FC<TalkingHeadProps> = ({
  videoSrc,
  captions,
  overlays,
  wordsPerPage = 4,
  fontSize = 52,
  highlightColor = "#FFD34E",
  audioSrc,
  hookTitle,
  hookDurationSeconds = 2.2,
  hookDisplayMode = "persistent",
  watermarkLines = [
    "九重天小熊猫版权所有｜用传统文化陪您过得更好",
    "虚构演绎，仅供参考；相信科学，拒绝迷信！",
  ],
  sourceLayout = "cover",
  captionBottomPx = 380,
  captionOutlineWidth = 5,
  captionBackgroundColor = "transparent",
  captionFontFamily = '"Heiti SC", "STHeiti", sans-serif',
  hookFontFamily = '"Kaiti SC", "STKaiti", serif',
  hookFontSrc,
}) => {
  const { fps } = useVideoConfig();
  const resolvedVideo = resolveMedia(videoSrc);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {hookFontSrc ? (
        <style>{`@font-face { font-family: "TreeElfHook"; src: url("${staticFile(hookFontSrc)}") format("truetype"); font-weight: 400 900; font-style: normal; font-display: block; }`}</style>
      ) : null}
      {/* Layer 1: Video background */}
      {sourceLayout === "contain-blur" ? (
        <>
          <OffthreadVideo
            src={resolvedVideo}
            muted
            style={{
              width: "100%",
              height: "100%",
              position: "absolute",
              inset: 0,
              objectFit: "cover",
              filter: "blur(34px)",
              transform: "scale(1.12)",
              opacity: 0.82,
            }}
          />
          <OffthreadVideo
            src={resolvedVideo}
            muted={Boolean(audioSrc)}
            style={{ width: "100%", height: "100%", position: "absolute", inset: 0, objectFit: "contain" }}
          />
        </>
      ) : (
        <OffthreadVideo
          src={resolvedVideo}
          muted={Boolean(audioSrc)}
          style={{ width: "100%", height: "100%", position: "absolute", inset: 0, objectFit: "cover" }}
        />
      )}

      {audioSrc ? <Audio src={resolveMedia(audioSrc)} /> : null}

      <div style={{
        position: "absolute",
        top: 78,
        left: 38,
        right: 38,
        color: "#FFFFFF",
        fontFamily: '"Heiti SC", "STHeiti", sans-serif',
        fontSize: 28,
        fontWeight: 700,
        lineHeight: 1.55,
        textAlign: "center",
        WebkitTextStroke: "3px #000000",
        paintOrder: "stroke fill",
        textShadow: "0 2px 4px rgba(0,0,0,0.95)",
      }}>
        {watermarkLines.map((line, index) => <div key={index}>{line}</div>)}
      </div>

      {hookTitle && hookDisplayMode === "persistent" ? (
        <HookTitle text={hookTitle} instant fontFamily={hookFontSrc ? '"TreeElfHook", serif' : hookFontFamily} />
      ) : hookTitle ? (
        <Sequence from={0} durationInFrames={Math.max(1, Math.round(hookDurationSeconds * fps))}>
          <HookTitle text={hookTitle} fadeAtEnd fontFamily={hookFontSrc ? '"TreeElfHook", serif' : hookFontFamily} />
        </Sequence>
      ) : null}

      {/* Layer 2: Overlays (charts, stats, callouts, etc.) */}
      {overlays?.map((overlay, i) => {
        const from = Math.round(overlay.in_seconds * fps);
        const duration = Math.round(
          (overlay.out_seconds - overlay.in_seconds) * fps
        );
        return (
          <Sequence
            key={overlay.id || `overlay-${i}`}
            from={from}
            durationInFrames={duration}
          >
            <PositionedOverlay overlay={overlay} />
          </Sequence>
        );
      })}

      {/* Layer 3: Captions (topmost — always visible above overlays) */}
      <CaptionOverlay
        words={captions}
        wordsPerPage={wordsPerPage}
        fontSize={fontSize}
        highlightColor={highlightColor}
        backgroundColor={captionBackgroundColor}
        color="#FFFFFF"
        outlineColor="#000000"
        outlineWidth={captionOutlineWidth}
        fontFamily={captionFontFamily}
        bottomPx={captionBottomPx}
        maxWidth="88%"
      />
    </AbsoluteFill>
  );
};

export const calculateTalkingHeadMetadata: CalculateMetadataFunction<TalkingHeadProps> = async ({props}) => ({
  durationInFrames: Math.max(1, Math.round((props.durationSeconds || 300) * 30)),
  fps: 30,
  width: 1080,
  height: 1920,
});
