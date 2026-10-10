import React from 'react';
import {AbsoluteFill,Audio,Sequence,staticFile} from 'remotion';
import {Opening} from './Opening';
import {ProductScene} from './ProductScene';
import {Knit} from './Knit';
import {SlipOn} from './SlipOn';
import {Comfort} from './Comfort';
import {Everyday} from './Everyday';
import {Closing} from './Closing';
import {palette} from './common';
export const SockShoeCommercial:React.FC=()=> <AbsoluteFill style={{background:palette.paper,fontFamily:'"Microsoft YaHei",sans-serif'}}>
 <Sequence from={0} durationInFrames={132}><Opening/></Sequence>
 <Sequence from={120} durationInFrames={117}><ProductScene/></Sequence>
 <Sequence from={225} durationInFrames={177}><Knit/></Sequence>
 <Sequence from={390} durationInFrames={192}><SlipOn/></Sequence>
 <Sequence from={570} durationInFrames={177}><Comfort/></Sequence>
 <Sequence from={735} durationInFrames={207}><Everyday/></Sequence>
 <Sequence from={930} durationInFrames={150}><Closing/></Sequence>
 <Audio src={staticFile('music-commercial.wav')} volume={.9}/>
</AbsoluteFill>;
export const SockShoeCover:React.FC=()=> <AbsoluteFill style={{background:palette.paper,fontFamily:'"Microsoft YaHei",sans-serif'}}><Closing cover/></AbsoluteFill>;
