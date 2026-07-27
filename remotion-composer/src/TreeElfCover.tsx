import React from "react";
import {AbsoluteFill, Img, staticFile} from "remotion";

export type TreeElfCoverProps = {
  backgroundSrc: string;
  chineseTitle: string;
  englishTitle: string;
  brand: string;
  titlePosition?: "top" | "center" | "bottom";
  textAlign?: "left" | "center" | "right";
  textColor?: string;
  accentColor?: string;
  overlayOpacity?: number;
  gradientDirection?: "top" | "center" | "bottom";
  chineseFontSrc?: string;
};

const resolveAsset = (src: string): string => {
  if (/^(https?:|data:)/.test(src)) {
    return src;
  }
  return staticFile(src.replace(/^\/+/, "").replace(/^public\//, ""));
};

const verticalPosition = (position: TreeElfCoverProps["titlePosition"]): React.CSSProperties => {
  if (position === "top") return {justifyContent: "flex-start", paddingTop: 220};
  if (position === "bottom") return {justifyContent: "flex-end", paddingBottom: 300};
  return {justifyContent: "center"};
};

const gradient = (
  direction: TreeElfCoverProps["gradientDirection"],
  opacity: number,
): string => {
  const dark = `rgba(5, 8, 11, ${Math.min(0.92, opacity + 0.28)})`;
  const clear = `rgba(5, 8, 11, ${Math.max(0.04, opacity - 0.2)})`;
  if (direction === "top") return `linear-gradient(180deg, ${dark} 0%, ${clear} 58%, rgba(5,8,11,0.12) 100%)`;
  if (direction === "bottom") return `linear-gradient(180deg, rgba(5,8,11,0.10) 0%, ${clear} 42%, ${dark} 100%)`;
  return `linear-gradient(180deg, rgba(5,8,11,0.12) 0%, ${dark} 48%, rgba(5,8,11,0.22) 100%)`;
};

export const TreeElfCover: React.FC<TreeElfCoverProps> = ({
  backgroundSrc,
  chineseTitle,
  englishTitle,
  brand,
  titlePosition = "center",
  textAlign = "center",
  textColor = "#F7F2E8",
  accentColor = "#D9B56D",
  overlayOpacity = 0.34,
  gradientDirection = "center",
  chineseFontSrc,
}) => {
  const alignItems = textAlign === "left" ? "flex-start" : textAlign === "right" ? "flex-end" : "center";
  const titleWidth = textAlign === "center" ? 850 : 760;
  const fontUrl = chineseFontSrc ? resolveAsset(chineseFontSrc) : undefined;

  return (
    <AbsoluteFill style={{backgroundColor: "#090B0D", overflow: "hidden"}}>
      {fontUrl ? (
        <style>{`@font-face { font-family: 'TreeElfCoverCN'; src: url('${fontUrl}'); font-weight: 400; font-style: normal; }`}</style>
      ) : null}
      <Img
        src={resolveAsset(backgroundSrc)}
        style={{width: "100%", height: "100%", objectFit: "cover"}}
      />
      <AbsoluteFill style={{background: gradient(gradientDirection, overlayOpacity)}} />
      <AbsoluteFill
        style={{
          paddingLeft: 112,
          paddingRight: 112,
          display: "flex",
          alignItems,
          ...verticalPosition(titlePosition),
        }}
      >
        <div style={{width: titleWidth, textAlign}}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 18,
              marginBottom: 34,
              color: accentColor,
              fontFamily: "Inter, PingFang SC, sans-serif",
              fontSize: 30,
              fontWeight: 600,
              letterSpacing: 14,
            }}
          >
            <span style={{width: 44, height: 2, backgroundColor: accentColor, display: "inline-block"}} />
            {brand}
          </div>
          <div
            style={{
              color: textColor,
              fontFamily: fontUrl ? "TreeElfCoverCN, STKaiti, serif" : "STKaiti, serif",
              fontSize: chineseTitle.length <= 3 ? 214 : chineseTitle.length === 4 ? 172 : 150,
              fontWeight: 400,
              letterSpacing: chineseTitle.length <= 3 ? 26 : chineseTitle.length === 4 ? 18 : 10,
              lineHeight: 1.08,
              textShadow: "0 10px 34px rgba(0,0,0,0.48)",
              whiteSpace: "pre-line",
            }}
          >
            {chineseTitle}
          </div>
          <div
            style={{
              marginTop: 34,
              color: textColor,
              opacity: 0.9,
              fontFamily: "Georgia, Times New Roman, serif",
              fontSize: 35,
              fontWeight: 400,
              letterSpacing: 7,
              lineHeight: 1.3,
              textTransform: "uppercase",
              textShadow: "0 6px 22px rgba(0,0,0,0.5)",
            }}
          >
            {englishTitle}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
