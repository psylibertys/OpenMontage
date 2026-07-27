import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Sequence,
  Video,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type TreeElfCaption = {
  start: number;
  end: number;
  text: string;
};

export type TreeElfHabitVideoProps = {
  captions: TreeElfCaption[];
};

const A = "#D9B56D";
const INK = "#10161A";

const asset = (path: string) => staticFile(`treeelf-habit-door/${path}`);

const Still: React.FC<{src: string; zoom?: number; panX?: number}> = ({
  src,
  zoom = 1.08,
  panX = 0,
}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });
  return (
    <AbsoluteFill style={{backgroundColor: INK, overflow: "hidden"}}>
      <Img
        src={asset(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `translateX(${panX * (progress - 0.5)}px) scale(${1 + (zoom - 1) * progress})`,
        }}
      />
      <AbsoluteFill style={{background: "linear-gradient(180deg,rgba(6,10,12,.05),rgba(6,10,12,.18))"}} />
    </AbsoluteFill>
  );
};

const Footage: React.FC<{src: string; startFrom?: number; playbackRate?: number}> = ({src, startFrom = 0, playbackRate = 1}) => (
  <AbsoluteFill style={{backgroundColor: INK}}>
    <Video
      src={asset(src)}
      startFrom={startFrom}
      playbackRate={playbackRate}
      muted
      style={{width: "100%", height: "100%", objectFit: "cover"}}
    />
    <AbsoluteFill style={{background: "linear-gradient(180deg,rgba(5,8,10,.03),rgba(5,8,10,.16))"}} />
  </AbsoluteFill>
);

const TaskTower: React.FC = () => {
  const frame = useCurrentFrame();
  const tasks = ["起床", "换衣", "下楼", "跑步", "拉伸"];
  const compress = interpolate(frame, [145, 250], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{background: "radial-gradient(circle at 50% 34%,#263238,#10161A 72%)", alignItems: "center", justifyContent: "center"}}>
      <div style={{position: "absolute", top: 160, color: "rgba(255,255,255,.52)", fontSize: 30, letterSpacing: 9}}>一次启动全部流程</div>
      <div style={{width: 720, transform: `translateY(${compress * 70}px) scaleY(${1 - compress * 0.08})`}}>
        {tasks.map((task, index) => {
          const enter = interpolate(frame, [index * 25, index * 25 + 18], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
          return (
            <div key={task} style={{height: 180, marginTop: 18, border: "1px solid rgba(217,181,109,.42)", background: "rgba(16,22,26,.9)", display: "flex", alignItems: "center", padding: "0 62px", opacity: enter, transform: `translateY(${(1 - enter) * -50}px)`, boxShadow: "0 24px 50px rgba(0,0,0,.24)"}}>
              <span style={{width: 58, height: 58, borderRadius: 40, border: `3px solid ${A}`, marginRight: 40}} />
              <span style={{fontSize: 66, fontFamily: "PingFang SC, sans-serif", color: "#F4F0E8", letterSpacing: 10}}>{task}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const NodeDiagram: React.FC = () => {
  const frame = useCurrentFrame();
  const columns = ["跑步", "做饭", "阅读"];
  return (
    <AbsoluteFill style={{background: "linear-gradient(150deg,#111A1E,#202A2E)", padding: "210px 92px 310px"}}>
      <div style={{color: "#F4F0E8", fontSize: 64, fontFamily: "STKaiti, serif", lineHeight: 1.25}}>整套流程，很难一次自动</div>
      <div style={{color: A, fontSize: 31, letterSpacing: 7, marginTop: 24}}>但入口节点可以被固定</div>
      <div style={{display: "flex", justifyContent: "space-between", marginTop: 160}}>
        {columns.map((label, col) => (
          <div key={label} style={{width: 250, textAlign: "center"}}>
            <div style={{fontSize: 44, color: "#F4F0E8", marginBottom: 70}}>{label}</div>
            {[0, 1, 2, 3].map((node) => {
              const active = interpolate(frame, [100 + col * 22 + node * 14, 118 + col * 22 + node * 14], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
              const entrance = node === 3;
              return (
                <React.Fragment key={node}>
                  <div style={{width: entrance ? 76 : 48, height: entrance ? 76 : 48, borderRadius: 50, margin: "0 auto", background: entrance ? A : `rgba(217,181,109,${0.15 + active * 0.45})`, border: `2px solid rgba(217,181,109,${0.35 + active * 0.5})`, boxShadow: entrance ? `0 0 ${18 + active * 28}px rgba(217,181,109,.55)` : "none"}} />
                  {node < 3 ? <div style={{height: 76, width: 2, background: "rgba(217,181,109,.32)", margin: "0 auto"}} /> : null}
                </React.Fragment>
              );
            })}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const ThreeDoors: React.FC = () => {
  const frame = useCurrentFrame();
  const doors = ["闹钟", "关电脑", "刷完牙"];
  return (
    <AbsoluteFill style={{background: "radial-gradient(circle at 50% 55%,#293337,#10161A 76%)", padding: "220px 92px 320px"}}>
      <div style={{fontFamily: "STKaiti, serif", color: "#F4F0E8", fontSize: 70, lineHeight: 1.25}}>线索只负责开门</div>
      <div style={{fontSize: 32, color: "rgba(255,255,255,.58)", marginTop: 28, letterSpacing: 4}}>不必承诺一次完成整套人生</div>
      <div style={{display: "flex", justifyContent: "space-between", marginTop: 235}}>
        {doors.map((label, index) => {
          const open = interpolate(frame, [index * 70 + 30, index * 70 + 80], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
          return (
            <div key={label} style={{width: 260, textAlign: "center"}}>
              <div style={{height: 490, border: "4px solid rgba(217,181,109,.6)", padding: 14, perspective: 500, boxShadow: `inset 0 0 ${open * 90}px rgba(217,181,109,.35)`}}>
                <div style={{height: "100%", background: "linear-gradient(90deg,#1A2327,#364044)", transformOrigin: "left", transform: `rotateY(${-open * 62}deg)`, position: "relative"}}>
                  <span style={{position: "absolute", right: 22, top: "50%", width: 25, height: 25, borderRadius: 20, background: A, boxShadow: `0 0 ${20 + open * 35}px ${A}`}} />
                </div>
              </div>
              <div style={{fontSize: 38, color: "#F4F0E8", marginTop: 38}}>{label}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const Caption: React.FC<{item: TreeElfCaption}> = ({item}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = interpolate(frame, [0, Math.round(fps * 0.12)], [0, 1], {extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center", paddingBottom: 245, pointerEvents: "none"}}>
      <div style={{maxWidth: 910, padding: "20px 34px 22px", borderRadius: 18, background: "rgba(7,10,12,.72)", boxShadow: "0 10px 42px rgba(0,0,0,.25)", opacity: enter, transform: `translateY(${(1 - enter) * 14}px)`}}>
        <div style={{fontFamily: "PingFang SC, Hiragino Sans GB, sans-serif", fontSize: item.text.length > 18 ? 50 : 58, fontWeight: 650, lineHeight: 1.35, textAlign: "center", color: "#FFFDF8", letterSpacing: 2, textShadow: "0 3px 8px rgba(0,0,0,.8)"}}>{item.text}</div>
      </div>
    </AbsoluteFill>
  );
};

const BrandBug: React.FC = () => (
  <div style={{position: "absolute", top: 92, right: 68, display: "flex", alignItems: "center", gap: 13, color: "rgba(255,255,255,.72)", fontFamily: "PingFang SC, sans-serif", fontSize: 25, letterSpacing: 7}}>
    <span style={{width: 30, height: 2, background: A}} />树精灵
  </div>
);

const Sec: React.FC<{from: number; to: number; children: React.ReactNode}> = ({from, to, children}) => (
  <Sequence from={Math.round(from * 30)} durationInFrames={Math.round((to - from) * 30)}>{children}</Sequence>
);

export const TreeElfHabitVideo: React.FC<TreeElfHabitVideoProps> = ({captions}) => {
  const frame = useCurrentFrame();
  const musicVolume = interpolate(frame, [0, 45, 2570, 2676], [0, 0.055, 0.055, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{backgroundColor: INK}}>
      <Sec from={0} to={4.64}><Still src="images/P00.png" /></Sec>
      <Sec from={4.64} to={12.68}><TaskTower /></Sec>
      <Sec from={12.68} to={22.4}><Still src="images/P01.png" zoom={1.12} /></Sec>
      <Sec from={22.4} to={36.28}><NodeDiagram /></Sec>
      <Sec from={36.28} to={43.2}><Footage src="video/W01.mp4" playbackRate={0.58} /></Sec>
      <Sec from={43.2} to={46.3}><Footage src="video/M01.mp4" /></Sec>
      <Sec from={46.3} to={50.84}><Footage src="video/W02.mp4" playbackRate={0.86} /></Sec>
      <Sec from={50.84} to={54.04}><Still src="images/P03.png" zoom={1.04} panX={36} /></Sec>
      <Sec from={54.04} to={70.18}><ThreeDoors /></Sec>
      <Sec from={70.18} to={81.52}><Still src="images/P04.png" zoom={1.1} /></Sec>
      <Sec from={81.52} to={84.0}><Footage src="video/W03.mp4" /></Sec>
      <Sec from={84.0} to={88.1}><Footage src="video/W04.mp4" /></Sec>
      <Sec from={88.1} to={89.2}><Still src="images/P05.png" zoom={1.02} /></Sec>
      <Audio src={asset("audio/narration.wav")} />
      <Audio src={asset("audio/background.mp3")} volume={musicVolume} />
      <BrandBug />
      {captions.map((item, index) => (
        <Sequence key={`${index}-${item.start}`} from={Math.round(item.start * 30)} durationInFrames={Math.max(1, Math.round((item.end - item.start) * 30))}>
          <Caption item={item} />
        </Sequence>
      ))}
      <Sequence from={0} durationInFrames={1}>
        <Img src={asset("images/platform_cover.png")} style={{width: "100%", height: "100%", objectFit: "cover"}} />
      </Sequence>
    </AbsoluteFill>
  );
};
