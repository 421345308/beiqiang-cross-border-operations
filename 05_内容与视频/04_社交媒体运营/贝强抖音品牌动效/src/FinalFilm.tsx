import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';

const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const ease=Easing.bezier(0.25,0.05,0.2,1);
const m=(f:number,t:number[],v:number[])=>interpolate(f,t,v,{...clamp,easing:ease});
const ink='#514331',cream='#eee4d3';

const Caption:React.FC<{lines:string[];f:number;start?:number;end:number;size?:number}>=({lines,f,start=10,end,size=78})=> {
  const opacity=m(f,[start,start+18,end-16,end],[0,1,1,0]);
  return <div style={{position:'absolute',left:88,top:290,color:ink,fontSize:size,letterSpacing:4,lineHeight:1.5,opacity}}>
    {lines.map((line,i)=><div key={i} style={{transform:`translateY(${m(f,[start+i*9,start+28+i*9],[32,0])}px)`,opacity:m(f,[start+i*9,start+28+i*9],[0,1])}}>{line}</div>)}
  </div>;
};

const Cloth:React.FC<{f:number;x:number;y:number;width?:number;rotate?:number;scale?:number;opacity?:number}>=({f,x,y,width=1280,rotate=0,scale=1,opacity=1})=> <div style={{position:'absolute',left:x,top:y,width,height:width*2/3,opacity,transform:`rotate(${rotate+Math.sin(f/66)*3}deg) scale(${scale})`,transformOrigin:'50% 50%',filter:'url(#final-cloth-wave)'}}><Img src={staticFile('ribbon-v2.png')} style={{width:'100%',height:'100%',objectFit:'contain'}}/></div>;

const Space:React.FC<{f:number;opacity?:number}>=({f,opacity=0.38})=> <><Img src={staticFile('space-v2.png')} style={{width:'100%',height:'100%',objectFit:'cover',opacity,transform:`scale(1.08) translateY(${m(f,[0,200],[15,-20])}px)`}}/><AbsoluteFill style={{background:'radial-gradient(ellipse at 8% 30%,#fff6dc88,transparent 72%)'}}/></>;

const Shoe:React.FC<{file?:string;f:number;x:number;y:number;width?:number;rotate?:number;scale?:number;opacity?:number}>=({file='shoe-v2.png',f,x,y,width=980,rotate=0,scale=1,opacity=1})=> <div style={{position:'absolute',left:x,top:y,width,height:width*0.78,opacity,transform:`translateY(${Math.sin(f/47)*10}px) rotate(${rotate}deg) scale(${scale})`,transformOrigin:'50% 50%'}}><Img src={staticFile(file)} style={{width:'100%',height:'100%',objectFit:'contain',filter:'drop-shadow(0 24px 24px #7c65451a)'}}/></div>;

const Opening:React.FC=()=> {
  const f=useCurrentFrame();
  return <AbsoluteFill><Space f={f} opacity={0.28}/>
    <Cloth f={f} x={m(f,[0,100],[-420,-280])} y={1050} scale={1.5} rotate={-18}/>
    <Shoe file="shoe-angle-final.png" f={f} x={m(f,[0,100],[30,0])} y={m(f,[0,100],[685,730])} scale={m(f,[0,100],[1.1,1.02])} rotate={m(f,[0,100],[-5,1])}/>
    <Cloth f={f} x={m(f,[0,100],[-560,-400])} y={1420} scale={1.08} rotate={-7}/>
    <Caption lines={['把灵感']} f={f} start={0} end={106} size={96}/>
  </AbsoluteFill>;
};

const Weave:React.FC=()=> {
  const f=useCurrentFrame();
  const fade=m(f,[0,15],[0,1]);
  return <AbsoluteFill style={{opacity:fade}}>
    <Img src={staticFile('macro-final.png')} style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${m(f,[0,155],[1.16,1.02])}) translateY(${m(f,[0,155],[32,-18])}px)`}}/>
    <AbsoluteFill style={{background:'linear-gradient(180deg,#eee4d385,transparent 45%)'}}/>
    <svg viewBox="0 0 1080 1920" style={{position:'absolute',inset:0,width:'100%',height:'100%',opacity:0.4}}>{[0,1,2,3,4].map(i=><path key={i} d={`M -60 ${1580+i*13} C 330 ${950+i*12}, 650 ${1410+i*14}, 1170 ${600+i*18}`} fill="none" stroke="#b19668" strokeWidth={i===2?2:1} pathLength="1" strokeDasharray="1" strokeDashoffset={m(f,[0,125],[1,0])}/>)}</svg>
    <Caption lines={['织进每一步']} f={f} start={17} end={155} size={84}/>
  </AbsoluteFill>;
};

export const Hero:React.FC<{frame?:number;caption?:boolean}>=({frame,caption=true})=> {
  const local=useCurrentFrame();const f=frame??local;
  return <AbsoluteFill style={{background:cream,opacity:frame!==undefined?1:m(f,[0,18],[0,1])}}><Space f={f}/>
    <Cloth f={f} x={m(f,[0,180],[-300,-70])} y={570} scale={1.18} rotate={14}/>
    <div style={{position:'absolute',left:145,top:1410,width:800,height:60,borderRadius:'50%',background:'#8d744d',filter:'blur(38px)',opacity:0.10}}/>
    <Shoe f={f} x={m(f,[0,180],[85,10])} y={m(f,[0,180],[940,750])} rotate={m(f,[0,180],[-4,4])} scale={m(f,[0,180],[0.93,1.06])}/>
    <Cloth f={f} x={m(f,[0,180],[-490,-280])} y={1430} scale={1.05} rotate={-12}/>
    {caption&&<Caption lines={['从想象，到成形']} f={f} start={25} end={180} size={73}/>}
  </AbsoluteFill>;
};

const Detail:React.FC=()=> {
  const f=useCurrentFrame();
  return <AbsoluteFill style={{background:cream,opacity:m(f,[0,17],[0,1])}}><Space f={f} opacity={0.25}/>
    <Cloth f={f} x={-80} y={590} rotate={16} scale={1.2}/>
    <Shoe f={f} x={m(f,[0,160],[-130,-340])} y={m(f,[0,160],[800,690])} scale={m(f,[0,160],[1.35,1.78])} rotate={m(f,[0,160],[3,-2])}/>
    <Cloth f={f} x={-390} y={1450} rotate={-8} scale={1.1}/>
    <Caption lines={['让细节','成为风格']} f={f} start={17} end={156} size={78}/>
  </AbsoluteFill>;
};

const Style:React.FC=()=> {
  const f=useCurrentFrame();
  return <AbsoluteFill style={{background:cream,opacity:m(f,[0,20],[0,1])}}><Space f={f} opacity={0.3}/>
    <Cloth f={f} x={m(f,[0,215],[-250,-510])} y={m(f,[0,215],[760,480])} scale={1.36} rotate={m(f,[0,215],[20,-4])}/>
    <Shoe file="shoe-angle-final.png" f={f} x={m(f,[0,215],[-45,95])} y={m(f,[0,215],[910,730])} width={940} rotate={m(f,[0,215],[-4,5])} scale={m(f,[0,215],[0.95,1.14])}/>
    <Cloth f={f} x={m(f,[0,215],[-630,-330])} y={1450} scale={1.15} rotate={-15}/>
    <Caption lines={['每一步','都有自己的风格']} f={f} start={20} end={203} size={73}/>
  </AbsoluteFill>;
};

const Finish:React.FC=()=> {
  const f=useCurrentFrame();
  const clean=m(f,[0,50],[0,0.98]);const solid=m(f,[47,87],[0,1]);const reveal=m(f,[17,56],[0,1]);
  return <AbsoluteFill style={{background:cream,opacity:m(f,[0,20],[0,1])}}>
    <Cloth f={f} x={m(f,[0,98],[-470,720])} y={m(f,[0,98],[490,1050])} scale={m(f,[0,90],[2.8,1.35])} rotate={-8}/>
    <AbsoluteFill style={{background:cream,opacity:clean}}/>
    <svg viewBox="0 0 1080 1920" style={{position:'absolute',inset:0,width:'100%',height:'100%'}}>
      <defs><pattern id="final-type-weave" patternUnits="userSpaceOnUse" width="1080" height="1920" patternTransform={`translate(${m(f,[20,95],[160,-160])},0)`}><image href={staticFile('macro-final.png')} x="0" y="-500" width="1080" height="2400" preserveAspectRatio="xMidYMid slice"/></pattern></defs>
      <g opacity={reveal}><text x="558" y="850" textAnchor="middle" fontFamily="Microsoft YaHei" fontSize="181" letterSpacing="29" fontWeight="600" stroke="#a28b65" strokeWidth="1.4" fill="url(#final-type-weave)">贝强</text><text x="558" y="850" textAnchor="middle" fontFamily="Microsoft YaHei" fontSize="181" letterSpacing="29" fontWeight="600" fill={ink} opacity={solid}>贝强</text></g>
      {[0,1,2,3,4,5,6].map(i=><path key={i} d={`M -160 ${1400+i*12} C 250 ${1040+i*14}, 420 ${1580+i*9}, 710 ${1380+i*11} S 1060 ${1220+i*14}, 1200 ${1500+i*13}`} fill="none" stroke="#bda67b" strokeWidth={i===3?1.5:0.8} pathLength="1" strokeDasharray="1" strokeDashoffset={m(f,[18,120],[1,0])} opacity="0.28"/>)}
    </svg>
    <div style={{position:'absolute',top:924,width:'100%',textAlign:'center',color:ink,fontFamily:'Arial',fontSize:31,letterSpacing:13,paddingLeft:13,opacity:m(f,[48,78],[0,1])}}>BEIQIANG</div>
    <div style={{position:'absolute',top:1050,left:510,height:1,width:60,background:'#ab8d5f',opacity:solid}}/>
    <div style={{position:'absolute',top:1110,width:'100%',textAlign:'center',color:ink,fontSize:42,letterSpacing:3,opacity:m(f,[80,107],[0,1])}}>把灵感，织进每一步。</div>
    <div style={{position:'absolute',top:1226,width:'100%',textAlign:'center',color:ink,fontSize:34,letterSpacing:2,opacity:m(f,[102,130],[0,0.72])}}>泉州贝强鞋业服饰有限公司</div>
  </AbsoluteFill>;
};

export const FinalFilm:React.FC=()=> {
  const f=useCurrentFrame();
  return <AbsoluteFill style={{background:cream,fontFamily:'"Microsoft YaHei",sans-serif',overflow:'hidden'}}>
    <svg width="0" height="0"><defs><filter id="final-cloth-wave" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="0.006 0.008" numOctaves="1" seed="8" result="wave"/><feDisplacementMap in="SourceGraphic" in2="wave" scale={8+4*Math.sin(f/66)} xChannelSelector="R" yChannelSelector="G"/></filter></defs></svg>
    <Sequence from={0} durationInFrames={111}><Opening/></Sequence>
    <Sequence from={92} durationInFrames={168}><Weave/></Sequence>
    <Sequence from={242} durationInFrames={190}><Hero/></Sequence>
    <Sequence from={414} durationInFrames={163}><Detail/></Sequence>
    <Sequence from={560} durationInFrames={218}><Style/></Sequence>
    <Sequence from={758} durationInFrames={202}><Finish/></Sequence>
    <div style={{position:'absolute',left:88,top:136,color:ink,fontSize:36,letterSpacing:10,fontWeight:600,opacity:m(f,[756,792],[1,0])}}>贝强 <span style={{fontFamily:'Arial',fontSize:23,letterSpacing:5,marginLeft:16}}>BEIQIANG</span></div>
    <Audio src={staticFile('music-final.wav')} volume={0.9}/>
  </AbsoluteFill>;
};

export const BrandCover:React.FC=()=> <AbsoluteFill style={{background:cream,fontFamily:'"Microsoft YaHei",sans-serif',overflow:'hidden'}}>
  <Hero frame={105} caption={false}/>
  <div style={{position:'absolute',left:88,top:147,color:ink,fontFamily:'Arial',fontSize:28,letterSpacing:9}}>BEIQIANG</div>
  <div style={{position:'absolute',left:88,top:273,color:ink,fontSize:122,fontWeight:600,letterSpacing:13}}>贝强鞋业</div>
  <div style={{position:'absolute',left:92,top:456,color:ink,fontSize:43,letterSpacing:3}}>把灵感，织进每一步。</div>
  <div style={{position:'absolute',left:92,bottom:130,color:ink,fontSize:28,opacity:0.72,letterSpacing:2}}>泉州贝强鞋业服饰有限公司</div>
</AbsoluteFill>;
