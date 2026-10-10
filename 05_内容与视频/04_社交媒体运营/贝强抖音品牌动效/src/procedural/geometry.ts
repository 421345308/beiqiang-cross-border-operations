import * as THREE from 'three';

type Ring = [number, number, number, number]; // height, rear, toe, half-width
const sample = (rings: Ring[], y: number): Ring => {
  let i = rings.findIndex((r) => r[0] >= y);
  if (i <= 0) return rings[0];
  const a = rings[i - 1], b = rings[i];
  const t = (y - a[0]) / (b[0] - a[0]);
  const tangent=(k:number,j:number)=> {
    if(k===0)return (rings[1][j]-rings[0][j])/(rings[1][0]-rings[0][0]);
    if(k===rings.length-1)return (rings[k][j]-rings[k-1][j])/(rings[k][0]-rings[k-1][0]);
    const left=(rings[k][j]-rings[k-1][j])/(rings[k][0]-rings[k-1][0]);
    const right=(rings[k+1][j]-rings[k][j])/(rings[k+1][0]-rings[k][0]);
    return left*right<=0?0:2*left*right/(left+right);
  };
  const span=b[0]-a[0];
  return [y,...[1,2,3].map(j=>(2*t*t*t-3*t*t+1)*a[j]+(t*t*t-2*t*t+t)*span*tangent(i-1,j)+(-2*t*t*t+3*t*t)*b[j]+(t*t*t-t*t)*span*tangent(i,j))] as Ring;
};

export function loft(rings: Ring[], rows = 100, cols = 128, rib = false, flare = 0) {
  const positions: number[] = [], uvs: number[] = [], indices: number[] = [];
  for (let j = 0; j <= rows; j++) {
    const v = j / rows, y = rings[0][0] + v * (rings[rings.length - 1][0] - rings[0][0]);
    const r = sample(rings, y), center = (r[1] + r[2]) / 2, len = (r[2] - r[1]) / 2;
    const spread = flare * Math.pow(Math.max(0, (v - .57) / .43), 2);
    for (let i = 0; i <= cols; i++) {
      const u = i / cols, a = u * Math.PI * 2;
      const ripple = rib ? .0035 * Math.sin(y * 85 + Math.cos(a) * .9) : 0;
      positions.push(center + (len + ripple + spread) * Math.cos(a), y, (r[3] + ripple + spread * .7) * Math.sin(a));
      uvs.push(u, v);
      if (i < cols && j < rows) {
        const n = j * (cols + 1) + i;
        indices.push(n, n + cols + 1, n + 1, n + 1, n + cols + 1, n + cols + 2);
      }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  g.setIndex(indices); g.computeVertexNormals(); return g;
}

export const upperRings: Ring[] = [
  [.24,-1.44,1.62,.62],[.36,-1.47,1.64,.64],[.50,-1.45,1.54,.62],
  [.66,-1.43,1.16,.58],[.85,-1.40,.38,.51],[1.06,-1.34,-.28,.42],
  [1.35,-1.29,-.40,.39],[1.72,-1.26,-.42,.385],[2.03,-1.25,-.43,.38],
];
export const soleRings: Ring[] = [
  [0,-1.35,1.53,.57],[.045,-1.47,1.65,.64],[.12,-1.49,1.68,.66],
  [.245,-1.48,1.67,.655],[.295,-1.43,1.62,.625],
];

export function knitTexture() {
  const canvas = document.createElement('canvas'); canvas.width = 256; canvas.height = 256;
  const c = canvas.getContext('2d')!;
  c.fillStyle = '#36383a'; c.fillRect(0,0,256,256);
  for (let row = -1; row < 9; row++) for (let col = -1; col < 9; col++) {
    const x = col * 32, y = row * 32;
    c.lineCap = 'round';
    for (let strand=0; strand<4; strand++) {
      c.strokeStyle = ['#17191b','#55585b','#313336','#424548'][strand];
      c.lineWidth = strand===0 ? 5 : 1.4;
      c.beginPath(); c.moveTo(x+3+strand*.6,y-7);
      c.bezierCurveTo(x+7,y+9,x+7,y+15,x+16,y+25);
      c.bezierCurveTo(x+25,y+15,x+25,y+9,x+29-strand*.6,y-7); c.stroke();
    }
  }
  const t = new THREE.CanvasTexture(canvas);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(10,7);
  t.colorSpace = THREE.SRGBColorSpace; t.anisotropy=8; return t;
}

export function loopGeometry() {
  const pts=[[-.30,-.56,-.035],[-.13,-.20,.06],[-.22,.20,.10],[-.19,.46,.03],[0,.57,-.10],[.19,.46,.03],[.22,.20,.10],[.13,-.20,.06],[.30,-.56,-.035]];
  return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts.map(p=>new THREE.Vector3(...p))),32,.047,8,false);
}

export function footGeometry() {
  return loft([[.30,-1.29,1.42,.43],[.45,-1.30,1.42,.45],[.61,-1.27,1.10,.44],[.84,-1.23,.18,.37],[1.03,-1.17,-.51,.28],[1.5,-1.10,-.55,.265],[2.2,-1.10,-.55,.285],[3.3,-1.14,-.50,.32],[4.4,-1.19,-.46,.365]],80,80);
}
