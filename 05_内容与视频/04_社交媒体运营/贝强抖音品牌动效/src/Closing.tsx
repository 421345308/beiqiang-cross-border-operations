import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};
const settle = Easing.bezier(.2, .75, .3, 1);

/** Three-second photographic end card. Everything settles by local frame 9. */
export const Closing: React.FC = () => {
  const frame = useCurrentFrame();

  return <AbsoluteFill style={{
    backgroundColor: '#F2EDE3', color: '#211f1b', overflow: 'hidden',
    fontFamily: '"Microsoft YaHei", sans-serif',
  }}>
    <Img src={staticFile('campaign-product.png')} style={{
      position: 'absolute', left: 0, top: 0, width: 1080, height: 1920,
      objectFit: 'contain',
    }}/>
    <AbsoluteFill style={{backgroundColor: '#fffaf2', opacity: interpolate(frame, [0, 9], [.08, 0], clamp)}}/>

    <div style={{position: 'absolute', left: 90, top: 159, width: 900, textAlign: 'center',
      opacity: interpolate(frame, [0, 6], [.25, 1], clamp),
      translate: `0 ${interpolate(frame, [0, 9], [6, 0], {...clamp, easing: settle})}px`,
    }}>
      <div style={{fontSize: 136, fontWeight: 600, lineHeight: 1.3, letterSpacing: 9, paddingLeft: 9}}>贝强</div>
      <div style={{marginTop: 12, fontSize: 32, fontWeight: 400, lineHeight: 1.4, letterSpacing: 8, paddingLeft: 8}}>BEIQIANG</div>
    </div>

    <div style={{position: 'absolute', left: 90, top: 445, width: 900, textAlign: 'center',
      fontSize: 38, lineHeight: 1.4, letterSpacing: 4, paddingLeft: 4, color: '#71675b',
      opacity: interpolate(frame, [1, 8], [0, 1], clamp),
    }}>针织袜子鞋</div>
    <div style={{position: 'absolute', left: 90, top: 523, width: 900, textAlign: 'center',
      fontSize: 48, fontWeight: 400, lineHeight: 1.4, letterSpacing: 1,
      opacity: interpolate(frame, [2, 9], [0, 1], clamp),
    }}>把日常，穿得舒服一点。</div>
  </AbsoluteFill>;
};
