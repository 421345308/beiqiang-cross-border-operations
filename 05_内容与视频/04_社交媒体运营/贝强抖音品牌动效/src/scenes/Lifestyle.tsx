import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

/** 7 seconds at 48 fps: whole person -> pause -> tactile detail. */
const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};
const ease = Easing.bezier(0.22, 1, 0.36, 1);
const font = '"Microsoft YaHei", "PingFang SC", sans-serif';

const Photograph: React.FC<{src: string; frame: number; duration: number; kind: 'city' | 'park' | 'detail'}> = ({src, frame, duration, kind}) => (
  <AbsoluteFill style={{backgroundColor: '#efe7d9', overflow: 'hidden'}}>
    <Img src={staticFile(src)} style={{
      width: '100%', height: '100%', objectFit: 'cover',
      scale: interpolate(frame, [0, duration], kind === 'detail' ? [1, 1.018] : [1.016, 1.045], clamp),
      translate: `${interpolate(frame, [0, duration], kind === 'city' ? [5, -8] : kind === 'park' ? [-3, 6] : [0, 2], clamp)}px ${interpolate(frame, [0, duration], kind === 'park' ? [6, -9] : [0, -5], clamp)}px`,
      transformOrigin: kind === 'detail' ? '55% 60%' : '50% 58%',
    }} />
    <AbsoluteFill style={{pointerEvents: 'none',
      background: 'radial-gradient(ellipse at 54% 45%, transparent 40%, rgba(74,50,23,0.09) 100%)'}} />
    <AbsoluteFill style={{pointerEvents: 'none',
      background: 'linear-gradient(112deg, transparent 15%, rgba(255,250,223,0.055) 40%, transparent 70%)',
      translate: `${interpolate(frame, [0, duration], [-200, 140], clamp)}px 0px`,
      mixBlendMode: 'screen'}} />
  </AbsoluteFill>
);

const Caption: React.FC<{children: React.ReactNode; frame: number; duration: number; align?: 'left' | 'right'}> = ({children, frame, duration, align = 'left'}) => (
  <>
    <AbsoluteFill style={{pointerEvents: 'none',
      opacity: interpolate(frame, [4, 22, duration - 13, duration], [0, 1, 1, 0], clamp),
      background: 'linear-gradient(180deg, transparent 73%, rgba(24,18,11,0.32) 100%)'}} />
    <div style={{position: 'absolute', left: 88, right: 80, top: 1622,
      fontFamily: font, fontSize: 84, fontWeight: 500, letterSpacing: 2, lineHeight: 1.16,
      color: '#fffaf1', textAlign: align, textShadow: '0 2px 14px rgba(43,30,15,0.14)',
      opacity: interpolate(frame, [9, 28, duration - 17, duration - 4], [0, 1, 1, 0], {...clamp, easing: ease}),
      translate: `0px ${interpolate(frame, [9, 31], [18, 0], {...clamp, easing: ease})}px`}}>{children}</div>
  </>
);

export const Lifestyle: React.FC = () => {
  const frame = useCurrentFrame();
  // Internal cuts at frame 168 (26.5 s global) and 264 (28.5 s global).
  const parkBlend = interpolate(frame, [162, 174], [0, 1], clamp);
  const detailBlend = interpolate(frame, [258, 270], [0, 1], clamp);
  return (
    <AbsoluteFill style={{backgroundColor: '#efe7d9', overflow: 'hidden'}}>
      {frame < 174 && <>
        <Photograph src="campaign-city.png" frame={frame} duration={168} kind="city" />
        <Caption frame={frame} duration={168} align="right">走一段。</Caption>
      </>}
      {frame >= 162 && frame < 270 && <AbsoluteFill style={{opacity: parkBlend}}>
        <Photograph src="sock-park.png" frame={Math.max(0, frame - 168)} duration={96} kind="park" />
        <Caption frame={Math.max(0, frame - 168)} duration={96}>歇一会儿。</Caption>
      </AbsoluteFill>}
      {frame >= 258 && <AbsoluteFill style={{opacity: detailBlend}}>
        <Photograph src="sock-knit.png" frame={Math.max(0, frame - 264)} duration={72} kind="detail" />
      </AbsoluteFill>}
    </AbsoluteFill>
  );
};
