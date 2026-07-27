import React from "react";
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from "remotion";

export type SharedAlarmCaption = {start: number; end: number; text: string};
export type TreeElfSharedAlarmVideoProps = {captions?: SharedAlarmCaption[]};

const ROOT = "treeelf-shared-alarm";
const asset = (path: string) => staticFile(`${ROOT}/${path}`);

export const sharedAlarmCaptions: SharedAlarmCaption[] = [
  {start:0.0,end:2.94,text:"刷到和你立场相反的帖子。"},
  {start:2.98,end:5.08,text:"手指刚碰到评论框，"},
  {start:5.2,end:7.18,text:"大脑已经完成审判。"},
  {start:7.34,end:9.28,text:"这种人不是坏，就是蠢。"},
  {start:9.52,end:14.22,text:"奇怪的是，对面看你时，可能也刚盖完同一份判决书。"},
  {start:14.62,end:19.42,text:"一篇来自伯克利 Greater Good 的文章提出一个角度。"},
  {start:19.62,end:21.18,text:"政治对立有很多原因，"},
  {start:21.48,end:25.96,text:"但其中一部分攻击性，可能来自更底层的存在焦虑。"},
  {start:26.2,end:29.36,text:"有人怕安全、传统和生活方式消失；"},
  {start:29.36,end:32.3,text:"有人怕环境、平等和民主被毁。"},
  {start:32.42,end:37.9,text:"立场朝相反方向跑，心里拉响的却可能是同一种警报。"},
  {start:38.1,end:40.46,text:"我珍视的世界要保不住了。"},
  {start:40.64,end:45.12,text:"警报越响，人越容易把方案分歧听成人格威胁。"},
  {start:45.26,end:48.3,text:"于是声音更大，信息却更少了。"},
  {start:48.6,end:52.72,text:"这不是说双方都对，也不是让你容忍侮辱。"},
  {start:53.1,end:57.76,text:"文章引用的研究只说明，存在焦虑与攻击性有关，"},
  {start:57.76,end:60.06,text:"不能解释每一场争论。"},
  {start:60.14,end:64.78,text:"它真正有用的地方，是让你在回击前多一道门。"},
  {start:64.84,end:68.94,text:"先问：他在怕失去什么？我又在怕失去什么？"},
  {start:69.52,end:74.58,text:"然后只说具体担忧、证据和边界，不给整个人贴标签。"},
  {start:74.92,end:78.28,text:"看见警报，不等于认同对方的路线；"},
  {start:78.54,end:81.14,text:"只是别让警报替你开车。"}
];

const Still: React.FC<{src:string; zoom?:number; pan?:number; lift?:number; rotate?:number}> = ({src,zoom=1.13,pan=34,lift=20,rotate=0}) => {
  const frame=useCurrentFrame(); const {durationInFrames}=useVideoConfig();
  const p=interpolate(frame,[0,durationInFrames],[0,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp",easing:Easing.inOut(Easing.quad)});
  const scale=interpolate(p,[0,1],[1.025,zoom]);
  const x=interpolate(p,[0,1],[-pan/2,pan/2]);
  const y=interpolate(p,[0,1],[lift/2,-lift/2]);
  const angle=interpolate(p,[0,1],[-rotate/2,rotate/2]);
  return <AbsoluteFill style={{backgroundColor:"#07131C",overflow:"hidden"}}><Img src={asset(`images/${src}.png`)} style={{width:"100%",height:"100%",objectFit:"cover",transform:`translate3d(${x}px,${y}px,0) scale(${scale}) rotate(${angle}deg)`,transformOrigin:"center"}}/><AbsoluteFill style={{background:"linear-gradient(180deg,rgba(3,9,14,.01),rgba(3,9,14,.16))"}}/></AbsoluteFill>;
};

const Clip: React.FC<{src:string; playbackRate:number}> = ({src,playbackRate}) => <AbsoluteFill style={{backgroundColor:"#07131C"}}><OffthreadVideo src={asset(`video/${src}.mp4`)} muted playbackRate={playbackRate} style={{width:"100%",height:"100%",objectFit:"cover"}}/><AbsoluteFill style={{background:"linear-gradient(180deg,rgba(3,9,14,.01),rgba(3,9,14,.12))"}}/></AbsoluteFill>;

const Caption: React.FC<{caption:SharedAlarmCaption}> = ({caption}) => {
  const frame=useCurrentFrame(); const opacity=interpolate(frame,[0,4],[0,1],{extrapolateRight:"clamp"});
  return <AbsoluteFill style={{justifyContent:"flex-end",alignItems:"center",paddingBottom:235,pointerEvents:"none"}}><div style={{maxWidth:900,padding:"4px 16px",opacity,transform:`translateY(${(1-opacity)*10}px)`,textAlign:"center",fontFamily:"PingFang SC, Hiragino Sans GB, sans-serif",fontSize:caption.text.length>24?39:caption.text.length>17?41:44,fontWeight:650,lineHeight:1.38,letterSpacing:1.3,color:"white",WebkitTextStroke:"3.5px rgba(0,0,0,.92)",paintOrder:"stroke fill",textShadow:"0 3px 7px rgba(0,0,0,.95)"}}>{caption.text}</div></AbsoluteFill>;
};

const Brand=()=> <div style={{position:"absolute",right:68,top:88,display:"flex",alignItems:"center",gap:13,fontSize:24,letterSpacing:7,color:"rgba(255,255,255,.78)",textShadow:"0 2px 5px rgba(0,0,0,.8)"}}><span style={{width:30,height:2,background:"#36D6CF"}}/>树精灵</div>;
const Sec:React.FC<{from:number;to:number;children:React.ReactNode}>=({from,to,children})=><Sequence from={Math.round(from*30)} durationInFrames={Math.max(1,Math.round((to-from)*30))}>{children}</Sequence>;

const AlarmCompare:React.FC=()=>{
  const frame=useCurrentFrame();
  const enter=interpolate(frame,[0,18],[0,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp",easing:Easing.out(Easing.cubic)});
  const pulse=1+Math.sin(frame/10)*0.025;
  const panel:React.CSSProperties={width:410,minHeight:410,padding:"54px 38px",border:"1px solid rgba(255,255,255,.22)",borderRadius:34,background:"rgba(5,18,28,.68)",backdropFilter:"blur(14px)",boxShadow:"0 24px 70px rgba(0,0,0,.35)",display:"flex",flexDirection:"column",justifyContent:"center",alignItems:"center",gap:26};
  return <AbsoluteFill><Still src="P02" zoom={1.15} pan={42} lift={30}/><AbsoluteFill style={{background:"linear-gradient(180deg,rgba(2,10,17,.34),rgba(2,10,17,.72))"}}/><AbsoluteFill style={{justifyContent:"center",alignItems:"center",padding:"180px 70px 300px"}}><div style={{fontSize:28,letterSpacing:10,color:"rgba(255,255,255,.72)",marginBottom:38}}>立场相反</div><div style={{display:"flex",gap:30}}><div style={{...panel,transform:`translateX(${(1-enter)*-110}px)`,opacity:enter}}><div style={{fontSize:30,color:"#7EE7DE"}}>有人害怕</div><div style={{fontSize:54,fontWeight:760,lineHeight:1.32,textAlign:"center",color:"white"}}>安全 · 传统<br/>生活方式消失</div></div><div style={{...panel,transform:`translateX(${(1-enter)*110}px)`,opacity:enter}}><div style={{fontSize:30,color:"#FFC66D"}}>有人害怕</div><div style={{fontSize:54,fontWeight:760,lineHeight:1.32,textAlign:"center",color:"white"}}>环境 · 平等<br/>民主被毁</div></div></div><div style={{marginTop:46,padding:"22px 48px",borderRadius:999,background:"linear-gradient(90deg,#21BDB4,#E7A445)",fontSize:48,fontWeight:850,letterSpacing:8,color:"#06131B",transform:`scale(${pulse})`,boxShadow:"0 14px 50px rgba(54,214,207,.22)"}}>同一种警报</div></AbsoluteFill></AbsoluteFill>;
};

const StepsCard:React.FC=()=>{
  const frame=useCurrentFrame();
  const items=[{n:"01",t:"具体担忧",c:"#73DDD6"},{n:"02",t:"证据",c:"#F5C267"},{n:"03",t:"边界",c:"#EF8D78"}];
  return <AbsoluteFill><Still src="P06" zoom={1.16} pan={-46} lift={26}/><AbsoluteFill style={{background:"linear-gradient(180deg,rgba(3,12,20,.34),rgba(3,12,20,.82))"}}/><AbsoluteFill style={{justifyContent:"center",padding:"180px 76px 310px"}}><div style={{fontSize:30,letterSpacing:9,color:"rgba(255,255,255,.72)",marginBottom:30}}>让警报停在副驾驶</div><div style={{fontSize:68,fontWeight:850,lineHeight:1.18,color:"white",marginBottom:56}}>只说清楚三件事</div><div style={{display:"flex",flexDirection:"column",gap:24}}>{items.map((item,i)=>{const show=interpolate(frame,[8+i*13,22+i*13],[0,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp",easing:Easing.out(Easing.cubic)});return <div key={item.n} style={{height:154,borderRadius:30,border:`2px solid ${item.c}77`,background:"rgba(4,18,28,.72)",display:"flex",alignItems:"center",padding:"0 42px",gap:36,opacity:show,transform:`translateY(${(1-show)*34}px)`}}><div style={{fontSize:28,fontWeight:800,color:item.c,letterSpacing:3}}>{item.n}</div><div style={{height:58,width:2,background:item.c,opacity:.65}}/><div style={{fontSize:58,fontWeight:800,color:"white",letterSpacing:5}}>{item.t}</div></div>})}</div></AbsoluteFill></AbsoluteFill>;
};

export const TreeElfSharedAlarmVideo:React.FC<TreeElfSharedAlarmVideoProps>=({captions=sharedAlarmCaptions})=>{
  const frame=useCurrentFrame();
  const second=frame/30;
  const speaking=captions.some((caption)=>second>=caption.start-0.08&&second<=caption.end+0.10);
  const musicBed=speaking?0.34:0.48;
  const musicFade=interpolate(frame,[0,24,2394,2442],[0,1,1,0],{extrapolateLeft:"clamp",extrapolateRight:"clamp"});
  const music=musicBed*musicFade;
  return <AbsoluteFill style={{backgroundColor:"#07131C"}}>
    <Sec from={0} to={7.3}><Clip src="W01" playbackRate={0.56}/></Sec>
    <Sec from={7.3} to={14.6}><Still src="P00" zoom={1.14} pan={42} lift={24}/></Sec>
    <Sec from={14.6} to={22.0}><Still src="P01" zoom={1.13} pan={-36} lift={28}/></Sec>
    <Sec from={22.0} to={30.1}><Clip src="W02" playbackRate={0.5}/></Sec>
    <Sec from={30.1} to={38.1}><AlarmCompare/></Sec>
    <Sec from={38.1} to={46.2}><Clip src="W03" playbackRate={0.5}/></Sec>
    <Sec from={46.2} to={55.0}><Still src="P04" zoom={1.15} pan={-46} lift={22}/></Sec>
    <Sec from={55.0} to={64.0}><Still src="P05" zoom={1.14} pan={38} lift={-22}/></Sec>
    <Sec from={64.0} to={69.5}><Still src="P03" zoom={1.13} pan={-34} lift={28}/></Sec>
    <Sec from={69.5} to={77.0}><StepsCard/></Sec>
    <Sec from={77.0} to={81.38}><Clip src="W04" playbackRate={0.93}/></Sec>
    <Audio src={asset("audio/narration.wav")}/><Audio src={asset("audio/background.mp3")} volume={music}/><Brand/>
    {captions.map((c,i)=><Sequence key={`${i}-${c.start}`} from={Math.round(c.start*30)} durationInFrames={Math.max(1,Math.round((c.end-c.start)*30))}><Caption caption={c}/></Sequence>)}
    <Sequence from={0} durationInFrames={1}><Img src={asset("images/platform_cover.png")} style={{width:"100%",height:"100%",objectFit:"cover"}}/></Sequence>
  </AbsoluteFill>;
};
