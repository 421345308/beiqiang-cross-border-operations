import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile} from 'remotion';
import {Opening} from './scenes/Opening';
import {Wearing} from './scenes/Wearing';
import {Lifestyle} from './scenes/Lifestyle';
import {Closing} from './scenes/Closing';

export const BrandFilm:React.FC=()=> <AbsoluteFill style={{backgroundColor:'#f1ece2'}}>
 <Audio src={staticFile('brand-score.wav')} volume={1}/>
 <Sequence from={0} durationInFrames={384}><Opening/></Sequence>
 <Sequence from={384} durationInFrames={720}><Wearing/></Sequence>
 <Sequence from={1104} durationInFrames={336}><Lifestyle/></Sequence>
 <Sequence from={1440} durationInFrames={288}><Closing/></Sequence>
</AbsoluteFill>;
