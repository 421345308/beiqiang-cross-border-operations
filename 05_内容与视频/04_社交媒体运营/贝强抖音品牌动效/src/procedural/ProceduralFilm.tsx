import React from 'react';
import {AbsoluteFill,Audio,Easing,Sequence,interpolate,staticFile,useCurrentFrame} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {AssistHand,Camera,Foot,KnitLoops,Lights,Shoe,WearingRig} from './Models';

const C={bg:'#f0ebe2',ink:'#302e2a',gold:'#988369'};
const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const ease=Easing.bezier(.22,.65,.25,1);
const progress=(f:number,a:number,b:number)=>interpolate(f,[a,b],[0,1],{...clamp,easing:ease});
const copy=[
  ['针织袜子鞋','穿上，就出发。','01 / KNIT SOCK SHOES'],
  ['一圈一圈','织成细密鞋面','02 / THE KNIT'],
  ['袜套鞋口','让鞋面，延伸到脚踝','03 / SOCK COLLAR'],
  ['少一步系带','套脚穿着，准备出发','04 / SLIP ON'],
  ['把舒适','穿进日常','05 / EVERYDAY'],
  ['贝强鞋业','针织袜子鞋','BEIQIANG FOOTWEAR'],
];

const Stage:React.FC<{scene:number;f:number}>=({scene,f})=> {
  const opening=scene===0, macro=scene===1, collar=scene===2, wear=scene===3, walk=scene===4;
  const shoeTurn=opening?-.20+f*.004:collar?-.65+f*.005:scene===5?-.35+f*.002:0;
  const enter=progress(f,30,150);
  const flare=wear?.07*Math.sin(enter*Math.PI):0;
  const camera:[number,number,number]=macro?[0,0,13]:collar?[3.4,4.3,5.6]:wear?[3.0,2.5,5.8]:walk?[4,2.8,7]:[3.7,2.55,6];
  const target:[number,number,number]=macro?[0,0,0]:collar?[-.65,1.30,0]:wear?[-.15,1.8,0]:walk?[0,1.8,0]:[0,1.0,0];
  const zoom=macro?95:collar?270:wear?235:walk?220:265;
  return <ThreeCanvas width={1080} height={1240} style={{position:'absolute',top:475,width:1080,height:1240,maskImage:'linear-gradient(to bottom,transparent,black 12%,black 92%,transparent)'}} orthographic camera={{position:camera,zoom}} gl={{antialias:true,alpha:true,preserveDrawingBuffer:true,localClippingEnabled:true}}>
    <Camera position={camera} target={target} zoom={zoom}/><Lights/>
    {macro?<KnitLoops progress={progress(f,0,120)} turn={Math.sin(f/140)*.2}/>:walk?<group>
      {[0,1].map(i=> {
        const phase=f/20+i*Math.PI, stride=Math.sin(phase);
        const rise=Math.max(0,Math.cos(phase))*.18;
        return <group key={i} position={[stride*.62,rise,i===0?.47:-.47]} rotation={[0,0,stride*.17]}><Shoe/><Foot/></group>;
      })}
    </group>:<group rotation={[0,shoeTurn,0]} position={[0,opening?.18*Math.sin(f/40):0,0]}>
      <Shoe flare={flare} reveal={collar?.36+.64*progress(f,0,58):1}/>
      {wear&&<>
        <WearingRig progress={enter}/>
        {f<172&&<group position={[-progress(f,145,172)*1.7,progress(f,145,172)*.75,0]}><AssistHand pull={Math.sin(enter*Math.PI)}/></group>}
      </>}
    </group>}
    {!macro&&<mesh position={[0,-.032,0]} rotation={[-Math.PI/2,0,0]} scale={[1.75,.76,1]}><circleGeometry args={[1,64]}/><meshBasicMaterial color="#bdb4a4" transparent opacity={.18}/></mesh>}
  </ThreeCanvas>;
};

const Page:React.FC<{scene:number;duration:number;stillFrame?:number}>=({scene,duration,stillFrame})=> {
  const current=useCurrentFrame(); const f=stillFrame??current; const p=progress(f,0,18), exit=scene===5?1:1-progress(f,duration-8,duration);
  const c=copy[scene];
  return <AbsoluteFill style={{background:C.bg,opacity:exit,color:C.ink,overflow:'hidden'}}>
    <svg width="1080" height="1920" style={{position:'absolute',inset:0}}>
      <defs><linearGradient id={`paper${scene}`} x2="1" y2="1"><stop stopColor="#faf7f0"/><stop offset="1" stopColor="#e9e1d5"/></linearGradient></defs>
      <rect width="1080" height="1920" fill={`url(#paper${scene})`}/>
      <circle cx={scene===1?530:560} cy="1110" r={scene===1?660:440} fill="none" stroke="#c5bba8" strokeWidth="1" opacity=".5"/>
      <path d={`M 80 1715 L ${80+920*progress(f,5,duration-12)} 1715`} stroke={C.gold} strokeWidth="1" opacity=".5"/>
    </svg>
    <Stage scene={scene} f={f}/>
    <div style={{position:'absolute',left:86,top:123,fontSize:34,fontWeight:600,letterSpacing:9}}>贝强 <span style={{fontSize:22,letterSpacing:5,fontFamily:'Arial',marginLeft:16}}>BEIQIANG</span></div>
    <div style={{position:'absolute',left:86,top:263,transform:`translateY(${(1-p)*28}px)`,opacity:p}}>
      <div style={{fontSize:scene===5?114:92,fontWeight:500,letterSpacing:4,lineHeight:1.3}}>{c[0]}</div>
      <div style={{fontSize:46,letterSpacing:2,marginTop:27,color:'#706657'}}>{c[1]}</div>
    </div>
    <div style={{position:'absolute',left:86,bottom:241,fontSize:22,fontFamily:'Arial',letterSpacing:3,color:C.gold}}>{c[2]}</div>
    {scene===1&&<div style={{position:'absolute',left:86,bottom:176,fontSize:39,letterSpacing:3}}>针织，是一环扣一环的细节。</div>}
    {scene===2&&<div style={{position:'absolute',left:86,bottom:176,fontSize:39,letterSpacing:3}}>针织鞋面 · 袜套轮廓</div>}
    {scene===3&&<div style={{position:'absolute',left:86,bottom:176,fontSize:39,letterSpacing:3}}>提拉鞋口 · 套脚穿入</div>}
    {scene===4&&<div style={{position:'absolute',left:86,bottom:176,fontSize:39,letterSpacing:5}}>通勤　/　散步　/　日常穿搭</div>}
    {scene===5&&<>
      <div style={{position:'absolute',left:86,bottom:174,fontSize:43,letterSpacing:3}}>一脚穿上，自在出发。</div>
      <div style={{position:'absolute',left:86,bottom:113,fontSize:25,color:'#8a7c68',letterSpacing:1}}>泉州贝强鞋业服饰有限公司</div>
    </>}
  </AbsoluteFill>;
};

export const ProceduralFilm:React.FC=()=> <AbsoluteFill style={{fontFamily:'"Microsoft YaHei",sans-serif',background:C.bg}}>
  <Sequence from={0} durationInFrames={105}><Page scene={0} duration={105}/></Sequence>
  <Sequence from={105} durationInFrames={195}><Page scene={1} duration={195}/></Sequence>
  <Sequence from={300} durationInFrames={180}><Page scene={2} duration={180}/></Sequence>
  <Sequence from={480} durationInFrames={240}><Page scene={3} duration={240}/></Sequence>
  <Sequence from={720} durationInFrames={180}><Page scene={4} duration={180}/></Sequence>
  <Sequence from={900} durationInFrames={180}><Page scene={5} duration={180}/></Sequence>
  <Audio src={staticFile('music-commercial.wav')} volume={.85}/>
</AbsoluteFill>;

export const ProceduralCover:React.FC=()=> <AbsoluteFill style={{fontFamily:'"Microsoft YaHei",sans-serif'}}><Page scene={5} duration={10000} stillFrame={70}/></AbsoluteFill>;
