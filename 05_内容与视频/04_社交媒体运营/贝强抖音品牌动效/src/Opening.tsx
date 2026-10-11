import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};
const settle = Easing.bezier(.22, .8, .22, 1);
const photo: React.CSSProperties = {
  position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover',
};

/** Local frames 0–107 at 24fps: weave / overhead pair / campaign pair. */
export const Opening: React.FC = () => {
  const f = useCurrentFrame();
  const title = interpolate(f, [71, 81], [0, 1], {...clamp, easing: settle});

  return <AbsoluteFill style={{background: '#F2EDE3', overflow: 'hidden', fontFamily: '"Microsoft YaHei", sans-serif'}}>
    {/* A short material punctuation; no claims or graphics placed over the weave. */}
    {f < 24 && <Img src={staticFile('sock-knit.png')} style={{...photo,
      scale: interpolate(f, [0, 23], [1.025, 1.05], {...clamp, easing: settle}),
      transformOrigin: '55% 56%',
    }}/>}

    {/* New photographic angle at frame 24. Both shoes remain wholly on the stone. */}
    {f >= 24 && <Img src={staticFile('campaign-overhead.png')} style={{...photo,
      scale: interpolate(f, [24, 59], [1, 1.014], {...clamp, easing: settle}),
      transformOrigin: '50% 52%',
    }}/>}

    {/* An explicit angle change avoids joining halves of two different shoes. */}
    {f >= 60 && <AbsoluteFill>
      <Img src={staticFile('campaign-product.png')} style={{...photo,
        scale: interpolate(f, [60, 76], [1.016, 1], {...clamp, easing: settle}),
        transformOrigin: '50% 62%',
      }}/>
      <div style={{position: 'absolute', left: 140, right: 140, top: 210,
        color: '#171714', textAlign: 'center', opacity: title,
        translate: `0 ${(1 - title) * 12}px`,
      }}>
        <div style={{fontSize: 34, fontWeight: 600, letterSpacing: 8, lineHeight: 1.4, paddingLeft: 8}}>贝强</div>
        <div style={{fontSize: 76, fontWeight: 500, letterSpacing: 4, lineHeight: 1.35, marginTop: 31, paddingLeft: 4}}>针织袜子鞋</div>
      </div>
    </AbsoluteFill>}
  </AbsoluteFill>;
};
