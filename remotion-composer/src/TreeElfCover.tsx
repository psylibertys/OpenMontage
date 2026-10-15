import React, {useEffect, useState} from "react";
import {AbsoluteFill, cancelRender, continueRender, delayRender, Img, staticFile, useVideoConfig} from "remotion";
import defaultChineseFontUrl from "../../fronts/漓雨手书_100font/LiyuXingkai.ttf";

export type TreeElfCoverProps = {
  backgroundSrc: string;
  chineseTitle: string;
  englishTitle?: string;
  brand?: string;
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

const CoverFont: React.FC<{url: string}> = ({url}) => {
  const [handle] = useState(() => delayRender("Loading TreeElf cover font"));

  useEffect(() => {
    const font = new FontFace("TreeElfCoverCN", `url('${url}')`, {
      style: "normal",
      weight: "400",
    });
    font.load()
      .then((loaded) => {
        document.fonts.add(loaded);
        continueRender(handle);
      })
      .catch((error) => cancelRender(error));
  }, [handle, url]);

  return null;
};

const verticalPosition = (
  position: TreeElfCoverProps["titlePosition"],
  landscape: boolean,
): React.CSSProperties => {
  if (position === "top") return {justifyContent: "flex-start", paddingTop: landscape ? 92 : 220};
  if (position === "bottom") return {justifyContent: "flex-end", paddingBottom: landscape ? 92 : 300};
  return {justifyContent: "center"};
};

const splitChineseTitle = (title: string, landscape: boolean): string => {
  if (!landscape || title.includes("\n") || title.length <= 9) return title;
  const midpoint = Math.ceil(title.length / 2);
  return `${title.slice(0, midpoint)}\n${title.slice(midpoint)}`;
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
  brand = "树精灵",
  titlePosition = "center",
  textAlign = "center",
  textColor = "#F7F2E8",
  accentColor = "#D9B56D",
  overlayOpacity = 0.34,
  gradientDirection = "center",
  chineseFontSrc,
}) => {
  const {width, height} = useVideoConfig();
  const landscape = width / height > 1.4;
  const alignItems = textAlign === "left" ? "flex-start" : textAlign === "right" ? "flex-end" : "center";
  const titleWidth = landscape
    ? Math.round(width * (textAlign === "center" ? 0.74 : 0.58))
    : textAlign === "center" ? 850 : 760;
  // 漓雨手书是树精灵封面的默认中文字体；显式传参时才覆盖。
  const fontUrl = chineseFontSrc ? resolveAsset(chineseFontSrc) : defaultChineseFontUrl;
  const displayTitle = splitChineseTitle(chineseTitle, landscape);
  const longestLine = Math.max(...displayTitle.split("\n").map((line) => line.length), 1);
  const landscapeTitleSize = Math.max(82, Math.min(174, Math.floor(titleWidth / (longestLine * 1.04))));
  const portraitTitleSize = chineseTitle.length <= 3 ? 214 : chineseTitle.length === 4 ? 172 : 150;
  const titleSize = landscape ? landscapeTitleSize : portraitTitleSize;
  const horizontalPadding = landscape ? 138 : 112;

  return (
    <AbsoluteFill style={{backgroundColor: "#090B0D", overflow: "hidden"}}>
      <CoverFont url={fontUrl} />
      <Img
        src={resolveAsset(backgroundSrc)}
        style={{width: "100%", height: "100%", objectFit: "cover"}}
      />
      <AbsoluteFill style={{background: gradient(gradientDirection, overlayOpacity)}} />
      <AbsoluteFill
        style={{
          paddingLeft: horizontalPadding,
          paddingRight: horizontalPadding,
          display: "flex",
          alignItems,
          ...verticalPosition(titlePosition, landscape),
        }}
      >
        <div style={{width: titleWidth, textAlign}}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 18,
              marginBottom: landscape ? 20 : 34,
              color: accentColor,
              fontFamily: "Inter, PingFang SC, sans-serif",
              fontSize: landscape ? 24 : 30,
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
              fontFamily: "TreeElfCoverCN, STKaiti, serif",
              fontSize: titleSize,
              fontWeight: 700,
              letterSpacing: landscape ? Math.max(6, Math.round(titleSize * 0.08)) : chineseTitle.length <= 3 ? 26 : chineseTitle.length === 4 ? 18 : 10,
              lineHeight: 1.08,
              textShadow: "0 10px 34px rgba(0,0,0,0.48)",
              whiteSpace: "pre-line",
            }}
          >
            {displayTitle}
          </div>
          {englishTitle ? <div
            style={{
              marginTop: landscape ? 64 : 96,
              color: "#FFD34E",
              fontFamily: "TreeElfCoverCN, Georgia, serif",
              fontSize: landscape ? 30 : 40,
              fontWeight: 700,
              letterSpacing: 7,
              lineHeight: 1.3,
              textTransform: "uppercase",
              textShadow: "0 6px 22px rgba(0,0,0,0.5)",
            }}
          >
            {englishTitle}
          </div> : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
