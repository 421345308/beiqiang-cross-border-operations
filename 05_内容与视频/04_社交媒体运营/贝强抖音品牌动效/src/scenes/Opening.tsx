import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

/** Local timing: 384 frames / 48 fps. Each shot uses a different source image. */
export const OPENING_SHOT_BOUNDARIES = [0, 72, 182, 288, 384] as const;

const ease = Easing.bezier(0.22, 1, 0.36, 1);
const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};
const ink = '#282520';
const cream = '#f1ece2';
const font = '"Microsoft YaHei", "PingFang SC", sans-serif';

const Lens: React.FC<{warm?: boolean}> = ({warm = false}) => (
  <AbsoluteFill style={{pointerEvents: 'none', background: warm
    ? 'radial-gradient(ellipse at 45% 44%, transparent 40%, rgba(75,49,24,0.12) 100%)'
    : 'radial-gradient(ellipse at 52% 42%, transparent 28%, rgba(0,0,0,0.29) 100%)'}} />
);

const Fabric: React.FC<{frame: number}> = ({frame}) => (
  <AbsoluteFill style={{backgroundColor: cream, overflow: 'hidden'}}>
    <Img src={staticFile('campaign-fabric.png')} style={{
      position: 'absolute', inset: -110, width: 1300, height: 2140, objectFit: 'cover',
      scale: interpolate(frame, [0, 86], [1.28, 1.06], clamp),
      translate: `${interpolate(frame, [0, 86], [-62, 18], clamp)}px ${interpolate(frame, [0, 86], [30, -54], clamp)}px`,
      filter: `blur(${interpolate(frame, [0, 34], [1.8, 0], clamp)}px)`,
    }} />
    <AbsoluteFill style={{
      background: 'linear-gradient(110deg, transparent 20%, rgba(255,255,245,0.21) 44%, transparent 64%)',
      translate: `${interpolate(frame, [0, 86], [-540, 470], clamp)}px 0px`,
      mixBlendMode: 'screen',
    }} />
    <Lens warm />
  </AbsoluteFill>
);

const Product: React.FC<{frame: number}> = ({frame}) => (
  <AbsoluteFill style={{backgroundColor: cream, overflow: 'hidden'}}>
    <AbsoluteFill style={{background: 'radial-gradient(ellipse at 55% 30%, #fffdf7 0%, #efe8dc 65%, #e2d7c5 100%)'}} />
    <div style={{position: 'absolute', left: 92, top: 128, color: ink, fontFamily: font,
      fontSize: 43, fontWeight: 600, letterSpacing: 5, opacity: interpolate(frame, [8, 23], [0, 1], {...clamp, easing: ease}),
      translate: `0px ${interpolate(frame, [8, 28], [22, 0], {...clamp, easing: ease})}px`}}>贝强 BEIQIANG</div>
    <div style={{position: 'absolute', left: 88, top: 284, color: ink, fontFamily: font,
      fontSize: 94, fontWeight: 500, letterSpacing: 2, lineHeight: 1.22,
      clipPath: `inset(0 0 ${interpolate(frame, [13, 33], [100, 0], {...clamp, easing: ease})}% 0)`,
      translate: `0px ${interpolate(frame, [13, 33], [26, 0], {...clamp, easing: ease})}px`}}>针织袜子鞋</div>
    <div style={{position: 'absolute', left: 119, top: 1470, width: 835, height: 88,
      background: 'radial-gradient(ellipse, rgba(78,59,37,0.24), rgba(78,59,37,0.09) 44%, transparent 70%)',
      scale: interpolate(frame, [0, 122], [0.88, 1.04], clamp), filter: 'blur(14px)'}} />
    <Img src={staticFile('sock-hero.png')} style={{position: 'absolute', left: 18, top: 458,
      width: 1038, height: 1038, objectFit: 'contain',
      scale: interpolate(frame, [0, 122], [0.89, 1.01], clamp),
      translate: `${interpolate(frame, [0, 122], [34, -8], clamp)}px ${interpolate(frame, [0, 122], [50, -4], clamp)}px`,
      filter: 'drop-shadow(0px 24px 28px rgba(74,53,33,0.11))',
    }} />
    <Lens warm />
  </AbsoluteFill>
);

const Touch: React.FC<{frame: number}> = ({frame}) => (
  <AbsoluteFill style={{backgroundColor: cream, overflow: 'hidden'}}>
    <Img src={staticFile('campaign-touch.png')} style={{
      position: 'absolute', inset: -70, width: 1220, height: 2060, objectFit: 'cover',
      scale: interpolate(frame, [0, 116], [1.1, 1.02], clamp),
      translate: `${interpolate(frame, [0, 116], [20, -22], clamp)}px ${interpolate(frame, [0, 116], [26, -20], clamp)}px`,
    }} />
    <Lens warm />
  </AbsoluteFill>
);

const Knit: React.FC<{frame: number}> = ({frame}) => (
  <AbsoluteFill style={{backgroundColor: '#1c1915', overflow: 'hidden'}}>
    <Img src={staticFile('sock-knit.png')} style={{
      position: 'absolute', inset: -85, width: 1250, height: 2090, objectFit: 'cover',
      scale: interpolate(frame, [0, 96], [1.16, 1.02], clamp),
      translate: `${interpolate(frame, [0, 96], [-20, 24], clamp)}px ${interpolate(frame, [0, 96], [30, -18], clamp)}px`,
    }} />
    <AbsoluteFill style={{background: 'linear-gradient(180deg, transparent 55%, rgba(10,8,6,0.62) 100%)'}} />
    <Lens />
    <div style={{position: 'absolute', left: 88, top: 1460, right: 80, fontFamily: font,
      fontSize: 84, lineHeight: 1.15, letterSpacing: 3, fontWeight: 500, color: '#fff8ed',
      opacity: interpolate(frame, [12, 30], [0, 1], {...clamp, easing: ease}),
      translate: `0px ${interpolate(frame, [12, 32], [26, 0], {...clamp, easing: ease})}px`}}>针织鞋面</div>
    <div style={{position: 'absolute', left: 91, top: 1586, fontFamily: font, fontSize: 44,
      fontWeight: 400, letterSpacing: 2, color: '#e6ddcf',
      opacity: interpolate(frame, [25, 43], [0, 1], {...clamp, easing: ease})}}>看得见的细密织纹</div>
  </AbsoluteFill>
);

/** Four full-frame photographic shots; masks and camera moves are deterministic. */
export const Opening: React.FC = () => {
  const frame = useCurrentFrame();
  const productEnter = interpolate(frame, [68, 80], [0, 1], {...clamp, easing: ease});
  const touchEnter = interpolate(frame, [180, 190], [0, 1], {...clamp, easing: ease});
  const knitEnter = interpolate(frame, [284, 298], [0, 1], {...clamp, easing: ease});
  return (
    <AbsoluteFill style={{backgroundColor: cream, overflow: 'hidden'}}>
      {frame < 80 && <Fabric frame={frame} />}
      {frame >= 68 && frame < 190 && <AbsoluteFill style={{
        clipPath: `inset(${(1 - productEnter) * 100}% 0 0 0)`}}><Product frame={Math.max(0, frame - 72)} /></AbsoluteFill>}
      {frame >= 180 && frame < 298 && <AbsoluteFill style={{
        opacity: touchEnter}}><Touch frame={Math.max(0, frame - 182)} /></AbsoluteFill>}
      {frame >= 284 && <AbsoluteFill style={{opacity: knitEnter}}><Knit frame={Math.max(0, frame - 288)} /></AbsoluteFill>}
    </AbsoluteFill>
  );
};
