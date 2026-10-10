import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

const limits={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const ease=Easing.bezier(0.33,0,0.2,1);
const motion=(f:number,frames:number[],values:number[])=>interpolate(f,frames,values,{...limits,easing:ease});
const fade=(f:number,a:number,b:number,c:number,d:number)=>motion(f,[a,b,c,d],[0,1,1,0]);
const ink='#514331';

const Phrase:React.FC<{text:string;f:number;start:number;end:number}>=({text,f,start,end})=> {
  const alpha=fade(f,start,start+22,end-18,end);
  return <div style={{position:'absolute',top:300,left:88,opacity:alpha,display:'flex',fontSize:84,lineHeight:1.3,letterSpacing:5,color:ink}}>
    {Array.from(text).map((c,i)=><span key={i} style={{opacity:motion(f,[start+i*3,start+22+i*3],[0,1]),transform:`translateY(${motion(f,[start+i*3,start+22+i*3],[35,0])}px)`}}>{c}</span>)}
  </div>;
};

const Ribbon:React.FC<{f:number;front?:boolean}>=({f,front=false})=> {
  const curtain=motion(f,[382,437,480],[0,1,0]);
  const intro=motion(f,[0,72,145],[2.5,1.65,1.08]);
  const base=front?1.07:1.23;
  const scale=base*intro+curtain*2.1;
  const x=motion(f,[0,110,230,340,430,490,600],front?[-710,-420,-330,-400,-150,850,1200]:[-430,-150,-35,130,-350,-450,-540]);
  const y=motion(f,[0,100,230,340,430,500,600],front?[1170,1280,1420,1420,940,1350,1500]:[700,640,640,510,380,850,900]);
  const opacity=front?fade(f,100,150,451,510):motion(f,[0,15,450,525],[0.75,0.9,0.9,0.36]);
  return <div style={{position:'absolute',left:x,top:y,width:1320,height:900,opacity,transform:`rotate(${(front?-9:12)+Math.sin(f/83)*5+curtain*25}deg) scale(${scale})`,transformOrigin:'50% 50%',filter:'url(#cloth-wave)'}}>
    <Img src={staticFile('ribbon-v2.png')} style={{width:'100%',height:'100%',objectFit:'contain'}}/>
  </div>;
};

const Lockup:React.FC<{f:number}>=({f})=> {
  const alpha=motion(f,[445,475],[0,1]);
  const solid=motion(f,[485,523],[0,1]);
  const weave=motion(f,[445,525],[180,-180]);
  return <AbsoluteFill style={{opacity:alpha,color:ink}}>
    <svg width="1080" height="1920" viewBox="0 0 1080 1920" style={{position:'absolute',inset:0}}>
      <defs><pattern id="brand-weave" patternUnits="userSpaceOnUse" width="1080" height="1920" patternTransform={`translate(${weave} 0)`}><image href={staticFile('warm.png')} x="-300" y="-300" width="1680" height="2520" preserveAspectRatio="xMidYMid slice"/></pattern></defs>
      <text x="558" y="922" textAnchor="middle" fontFamily="Microsoft YaHei" fontSize="178" fontWeight="600" letterSpacing="28" fill="url(#brand-weave)" stroke="#aa8b5f" strokeWidth="1.4">贝强</text>
      <text x="558" y="922" textAnchor="middle" fontFamily="Microsoft YaHei" fontSize="178" fontWeight="600" letterSpacing="28" fill={ink} opacity={solid}>贝强</text>
    </svg>
    <div style={{position:'absolute',top:985,width:'100%',textAlign:'center',fontFamily:'Arial',fontSize:32,letterSpacing:13,paddingLeft:13,opacity:motion(f,[465,495],[0,1]),transform:`translateY(${motion(f,[465,495],[18,0])}px)`}}>BEIQIANG</div>
    <div style={{position:'absolute',top:1090,left:510,width:60,height:1,background:'#aa8a59',opacity:solid}}/>
    <div style={{position:'absolute',top:1147,width:'100%',textAlign:'center',fontSize:38,letterSpacing:4,opacity:motion(f,[495,526],[0,1])}}>步履之间，自有风格。</div>
  </AbsoluteFill>;
};

export const WarmFilm:React.FC=()=> {
  const f=useCurrentFrame();
  const shoeAlpha=fade(f,63,115,394,449);
  const detail=motion(f,[300,351,404],[0,1,0]);
  const shoeScale=motion(f,[60,150,285,350,412],[0.84,1,1.06,1.77,0.8]);
  const x=motion(f,[60,145,280,350,419],[210,10,-20,-290,100]);
  const y=motion(f,[60,145,280,350,419],[1200,780,780,725,980]);
  const shoeRotation=motion(f,[65,155,275,355,420],[-9,0,4,-2,13]);
  const exposure=motion(f,[66,116],[0,1]);
  const clean=motion(f,[428,492],[0,1]);
  return <AbsoluteFill style={{backgroundColor:'#eee4d3',fontFamily:'"Microsoft YaHei",sans-serif',overflow:'hidden'}}>
    <svg width="0" height="0" style={{position:'absolute'}}><defs>
      <filter id="cloth-wave" x="-6%" y="-6%" width="112%" height="112%"><feTurbulence type="fractalNoise" baseFrequency="0.006 0.009" numOctaves="1" seed="8" result="wave"/><feDisplacementMap in="SourceGraphic" in2="wave" scale={10+5*Math.sin(f/57)} xChannelSelector="R" yChannelSelector="G"/></filter>
    </defs></svg>
    <Img src={staticFile('space-v2.png')} style={{width:'100%',height:'100%',objectFit:'cover',opacity:motion(f,[0,85,315,435,495],[0.42,0.52,0.46,0.28,0]),transform:`translateY(${motion(f,[0,600],[25,-25])}px) scale(1.06)`}}/>
    <AbsoluteFill style={{background:'radial-gradient(ellipse at 15% 35%, #fff9e8a8, transparent 62%)'}}/>
    <Ribbon f={f}/>
    <div style={{position:'absolute',left:125,top:1330,width:840,height:95,background:'#846f46',borderRadius:'50%',filter:'blur(42px)',opacity:shoeAlpha*(0.13-detail*0.08),transform:`scaleX(${0.82+Math.sin(f/75)*0.05})`}}/>
    <div style={{position:'absolute',left:x,top:y,width:1030,height:710,opacity:shoeAlpha,transform:`translateY(${Math.sin(f/51)*13}px) rotate(${shoeRotation}deg) scale(${shoeScale})`,transformOrigin:'50% 50%',clipPath:`polygon(0 ${100-exposure*160}%, 100% ${145-exposure*145}%, 100% 100%, 0 100%)`}}>
      <Img src={staticFile('shoe-v2.png')} style={{width:'100%',height:'100%',objectFit:'contain',filter:'drop-shadow(0 28px 30px #72552f20)'}}/>
    </div>
    <Ribbon f={f} front/>
    <AbsoluteFill style={{background:'linear-gradient(180deg,#f0e7d688 0%,transparent 34%,transparent 90%,#eee4d344 100%)',opacity:1-clean}}/>
    <div style={{position:'absolute',left:88,top:138,fontSize:36,fontWeight:600,letterSpacing:10,color:ink,opacity:motion(f,[418,445],[1,0])}}>贝强 <span style={{fontFamily:'Arial',fontSize:23,letterSpacing:5,marginLeft:16}}>BEIQIANG</span></div>
    <Phrase text="从一缕灵感" f={f} start={7} end={122}/>
    <Phrase text="织成每一步" f={f} start={149} end={289}/>
    <Phrase text="让细节，留下印象" f={f} start={302} end={402}/>
    <AbsoluteFill style={{background:'#eee4d3',opacity:clean*0.95}}/>
    <Lockup f={f}/>
    <svg viewBox="0 0 1080 1920" style={{position:'absolute',inset:0,width:'100%',height:'100%',pointerEvents:'none'}}>
      {Array.from({length:7},(_,i)=><path key={i} d={`M -170 ${1480+i*11} C 90 ${1160+i*9}, 250 ${1470+i*6}, 520 ${1370+i*9} S 870 ${1260+i*13}, 1230 ${1600+i*10}`} fill="none" stroke={i%2?'#b4996b':'#cfb98b'} strokeWidth={i===3?2:0.8} pathLength="1" strokeDasharray="1" strokeDashoffset={motion(f,[0,140,410,490,600],[1,0,0,0,0])} opacity={motion(f,[0,70,150,410,500,600],[0.35,0.55,0.16,0.25,0.38,0.38])}/>) }
    </svg>
    <Audio src={staticFile('sound-v2.wav')} volume={0.88}/>
  </AbsoluteFill>;
};
