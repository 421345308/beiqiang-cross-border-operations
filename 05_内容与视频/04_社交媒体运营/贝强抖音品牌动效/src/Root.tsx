import React from 'react';
import {Composition} from 'remotion';
import {BrandFilm, TOTAL_FRAMES} from './BrandFilm';
export const Root: React.FC = () => <Composition id="BeiqiangBrandFilm" component={BrandFilm} durationInFrames={TOTAL_FRAMES} fps={24} width={1080} height={1920}/>;
