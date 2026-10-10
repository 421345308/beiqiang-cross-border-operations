import React from 'react';
import {AbsoluteFill, Audio, Composition, Easing, Img, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {WarmFilm} from './WarmFilm';
import {FinalFilm, BrandCover} from './FinalFilm';
import {SockShoeCommercial,SockShoeCover} from './commercial/Commercial';

const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};
const ease = Easing.bezier(0.2, 0.65, 0.25, 1);
const styles = [
  {file:'warm.png', bg:'#e9dcc3', fg:'#453c2e', accent:'#887552', title:'从一缕灵感', sub:'让想象，慢慢成形。', label:'01 / 暖白 · 织物', dx:30},
  {file:'dark.png', bg:'#101113', fg:'#f5eee2', accent:'#c0955c', title:'到一寸细节', sub:'在光影中，留下印象。', label:'02 / 深色 · 光影', dx:-30},
  {file:'color.png', bg:'#f4ece0', fg:'#443a33', accent:'#c85032', title:'让脚步有色彩', sub:'每一步，都有自己的风格。', label:'03 / 彩色 · 雕塑', dx:25},
];

const TextReveal: React.FC<{text:string; frame:number; delay:number; color:string}> = ({text,frame,delay,color}) => <div style={{display:'flex',fontSize:84,fontWeight:500,letterSpacing:3,color,lineHeight:1.35}}>{Array.from(text).map((char,i)=> {
  const p=interpolate(frame,[delay+i*2,delay+24+i*2],[0,1],{...clamp,easing:ease});
  return <span key={i} style={{display:'block',opacity:p,transform:`translateY(${(1-p)*42}px)`,filter:`blur(${(1-p)*6}px)`}}>{char}</span>;
})}</div>;

const ArtScene: React.FC<{index:number}> = ({index}) => {
  const f=useCurrentFrame(); const s=styles[index];
  const progress=interpolate(f,[0,112],[0,1],{...clamp,easing:ease});
  const reveal=index===0?1:interpolate(f,[0,23],[0,1],{...clamp,easing:ease});
  const scale=interpolate(progress,[0,1],[1.22,1.015]);
  return <AbsoluteFill style={{backgroundColor:s.bg,clipPath:`inset(${(1-reveal)*100}% 0 0 0)`}}>
    <Img src={staticFile(s.file)} style={{width:'100%',height:'100%',objectFit:'cover',transform:`translate(${s.dx*(1-progress)}px,${60*(1-progress)}px) scale(${scale})`}} />
    <AbsoluteFill style={{background:`linear-gradient(180deg, ${s.bg}${index===1?'a8':'8c'} 0%, transparent 44%, transparent 83%, ${s.bg}99 100%)`}} />
    <svg viewBox="0 0 1080 1920" style={{position:'absolute',inset:0,width:'100%',height:'100%',opacity:index===1?0.35:0.23}}>
      <path d="M 80 1660 C 350 1810, 790 1770, 1000 1480" fill="none" stroke={s.accent} strokeWidth="1.5" strokeDasharray="1400" strokeDashoffset={interpolate(f,[15,120],[1400,0],clamp)}/>
    </svg>
    <div style={{position:'absolute',left:86,top:132,color:s.fg,fontSize:39,letterSpacing:12,fontWeight:600}}>贝强 <span style={{fontFamily:'Arial',letterSpacing:5,fontSize:24,marginLeft:18}}>BEIQIANG</span></div>
    <div style={{position:'absolute',left:86,top:292}}><TextReveal text={s.title} frame={f} delay={8} color={s.fg}/></div>
    <div style={{position:'absolute',left:88,bottom:182,color:s.fg,opacity:0.7,fontSize:28,letterSpacing:4}}>{s.label}</div>
    <div style={{position:'absolute',left:86,bottom:148,height:2,width:interpolate(f,[5,140],[0,240],clamp),background:s.accent,opacity:0.6}}/>
  </AbsoluteFill>;
};

const End:React.FC=()=> {
  const f=useCurrentFrame();
  const p=interpolate(f,[0,22],[0,1],{...clamp,easing:ease});
  return <AbsoluteFill style={{background:'#f0e8da',opacity:p,alignItems:'center',justifyContent:'center',color:'#453d30'}}>
    <svg viewBox="0 0 1080 1920" style={{position:'absolute',inset:0,width:'100%',height:'100%',opacity:0.17}}>
      {[0,1,2,3,4].map(i=><path key={i} d={`M -100 ${1380+i*24} C 260 ${960+i*24}, 740 ${1650+i*24}, 1200 ${1000+i*24}`} fill="none" stroke="#aa8960" strokeWidth="1.5" strokeDasharray="2000" strokeDashoffset={interpolate(f,[0,80],[1500,0],clamp)}/>) }
    </svg>
    <div style={{transform:`translateY(${(1-p)*24}px)`,textAlign:'center'}}>
      <div style={{fontSize:148,fontWeight:500,letterSpacing:24,paddingLeft:24}}>贝强</div>
      <div style={{fontFamily:'Arial',fontSize:31,letterSpacing:13,paddingLeft:13,marginTop:30}}>BEIQIANG</div>
      <div style={{height:1,width:60,background:'#a88a5f',margin:'62px auto 43px'}}/>
      <div style={{fontSize:38,letterSpacing:5}}>步履之间，自有风格。</div>
    </div>
  </AbsoluteFill>;
};

const Film:React.FC=()=> <AbsoluteFill style={{fontFamily:'"Microsoft YaHei", "PingFang SC", sans-serif',backgroundColor:'#e9dcc3'}}>
  <Sequence from={0} durationInFrames={162}><ArtScene index={0}/></Sequence>
  <Sequence from={144} durationInFrames={162}><ArtScene index={1}/></Sequence>
  <Sequence from={288} durationInFrames={171}><ArtScene index={2}/></Sequence>
  <Sequence from={435} durationInFrames={105}><End/></Sequence>
  <Audio src={staticFile('sound.wav')} volume={0.8}/>
</AbsoluteFill>;

export const Root:React.FC=()=> <><Composition id="BrandStudy" component={Film} durationInFrames={540} fps={30} width={1080} height={1920}/><Composition id="WarmBrandFilm" component={WarmFilm} durationInFrames={600} fps={30} width={1080} height={1920}/><Composition id="BeiqiangBrandFilm" component={FinalFilm} durationInFrames={960} fps={30} width={1080} height={1920}/><Composition id="BrandCover" component={BrandCover} durationInFrames={1} fps={30} width={1080} height={1920}/><Composition id="SockShoeCommercial" component={SockShoeCommercial} durationInFrames={1080} fps={30} width={1080} height={1920}/><Composition id="SockShoeCover" component={SockShoeCover} durationInFrames={1} fps={30} width={1080} height={1920}/></>;
