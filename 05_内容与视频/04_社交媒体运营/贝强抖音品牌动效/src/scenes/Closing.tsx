import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};
const ease = Easing.bezier(0.22, 1, 0.36, 1);
const font = '"Microsoft YaHei", "PingFang SC", sans-serif';

/** New pair photograph stays structurally intact; 6 seconds / 288 frames. */
export const Closing: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: '#eee7dc', overflow: 'hidden'}}>
      <Img src={staticFile('campaign-product.png')} style={{
        width: '100%', height: '100%', objectFit: 'cover',
        scale: interpolate(frame, [0, 288], [1, 1.012], clamp),
        translate: `0px ${interpolate(frame, [0, 288], [0, -5], clamp)}px`,
        transformOrigin: '50% 69%',
      }} />
      <AbsoluteFill style={{pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 53%, transparent 42%, rgba(79,54,24,0.09) 100%)'}} />
      <AbsoluteFill style={{pointerEvents: 'none',
        background: 'linear-gradient(108deg, transparent 22%, rgba(255,253,239,0.07) 48%, transparent 70%)',
        translate: `${interpolate(frame, [0, 288], [-130, 130], clamp)}px 0px`, mixBlendMode: 'screen'}} />
      <div style={{position: 'absolute', left: 88, right: 80, top: 155,
        color: '#282520', fontFamily: font,
        opacity: interpolate(frame, [88, 119], [0, 1], {...clamp, easing: ease}),
        translate: `0px ${interpolate(frame, [88, 121], [20, 0], {...clamp, easing: ease})}px`}}>
        <div style={{fontSize: 132, fontWeight: 600, lineHeight: 1.2, letterSpacing: 12}}>贝强</div>
        <div style={{marginTop: 19, fontSize: 27, fontWeight: 500, letterSpacing: 8}}>BEIQIANG</div>
      </div>
      <div style={{position: 'absolute', left: 92, top: 419, color: '#39352f', fontFamily: font,
        fontSize: 50, letterSpacing: 4, lineHeight: 1.25, fontWeight: 400,
        opacity: interpolate(frame, [111, 139], [0, 1], {...clamp, easing: ease}),
        translate: `0px ${interpolate(frame, [111, 140], [14, 0], {...clamp, easing: ease})}px`}}>针织袜子鞋</div>
      <div style={{position: 'absolute', left: 92, right: 80, top: 513, color: '#575046', fontFamily: font,
        fontSize: 44, letterSpacing: 2, lineHeight: 1.35, fontWeight: 400,
        opacity: interpolate(frame, [129, 151], [0, 1], {...clamp, easing: ease})}}>把日常，穿得舒服一点</div>
    </AbsoluteFill>
  );
};
