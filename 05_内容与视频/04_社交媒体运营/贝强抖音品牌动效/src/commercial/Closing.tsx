import React from 'react';
import {useCurrentFrame} from 'remotion';
import {Floor,Frame,Product,motion,palette} from './common';
export const Closing:React.FC<{cover?:boolean}>=({cover=false})=>{
 const current=useCurrentFrame(),f=cover?100:current;
 return <Frame fade={!cover}>
  <div style={{position:'absolute',left:86,top:155,color:palette.accent,fontFamily:'Arial',fontSize:29,letterSpacing:8}}>BEIQIANG FOOTWEAR</div>
  <div style={{position:'absolute',left:86,top:277,color:palette.ink,fontSize:126,fontWeight:600,letterSpacing:5,opacity:motion(f,[0,24],[0,1])}}>贝强鞋业</div>
  <div style={{position:'absolute',left:90,top:461,color:palette.ink,fontSize:72,letterSpacing:5,opacity:motion(f,[12,34],[0,1])}}>针织袜子鞋</div>
  <Floor top={1430}/><Product top={530} width={985} left={45} zoom={motion(f,[0,150],[.97,1])}/>
  <div style={{position:'absolute',left:88,top:1560,color:palette.ink,fontSize:52,lineHeight:1.5,letterSpacing:2,opacity:motion(f,[25,45],[0,1])}}>一脚穿上，自在出发。</div>
  <div style={{position:'absolute',left:90,top:1763,color:palette.muted,fontSize:30,letterSpacing:2,opacity:motion(f,[40,60],[0,1])}}>泉州贝强鞋业服饰有限公司</div>
 </Frame>;
};
