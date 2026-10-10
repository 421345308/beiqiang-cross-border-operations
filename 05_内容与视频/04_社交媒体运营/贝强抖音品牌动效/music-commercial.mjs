// Original 36-second instrumental, synthesized locally without external samples.
import {writeFileSync,mkdirSync} from 'node:fs';
const rate=48000,seconds=36,n=rate*seconds,beat=.6;
const left=new Float32Array(n),right=new Float32Array(n);
const freq=m=>440*2**((m-69)/12);
let seed=7381;
const noise=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296*2-1;};
function note(time,midi,gain,length=2.8,pan=0){
 const start=Math.floor(time*rate),hz=freq(midi),count=Math.min(Math.floor(length*rate),n-start);
 for(let i=0;i<count;i++){
  const t=i/rate,env=(1-Math.exp(-t*250))*Math.exp(-t*1.7)*(1-t/length);
  const x=(Math.sin(2*Math.PI*hz*t)+.28*Math.sin(2*Math.PI*hz*2.003*t)*Math.exp(-t*2)+.1*Math.sin(2*Math.PI*hz*3*t)*Math.exp(-t*4))*env*gain;
  left[start+i]+=x*(.8-pan*.2);right[start+i]+=x*(.8+pan*.2);
 }
}
const chords=[[48,55,60,64,67,72],[45,52,57,60,64,69],[41,48,53,57,60,65],[43,50,55,59,62,67]];
for(let bar=0;bar<15;bar++){
 const c=bar===14?chords[0]:chords[bar%4],time=bar*4*beat;
 note(time,c[0],.072,3.5,-.1);note(time+.06,c[1],.024,3,.2);
 [2,4,3,5,4,3].forEach((degree,k)=>note(time+k*beat*.65+.08,c[degree],.043+(k===0?.02:0),2.2,(k%3-1)*.5));
 if(bar>=5&&bar<13)note(time+2.5*beat,c[5]+12,.022,2,.5);
}
// Restrained pulse helps the product and wearing edits without overpowering copy.
for(let b=0;b<55;b++){
 const time=b*beat+2.4,start=Math.round(time*rate);
 if(start>=n)break;
 for(let i=0;i<rate*.13&&start+i<n;i++){
  const t=i/rate,env=Math.exp(-t*35),kick=Math.sin(2*Math.PI*(65*t+1.2*(1-Math.exp(-t*30))))*.018*env;
  const tick=noise()*.005*Math.exp(-t*130);
  left[start+i]+=kick+tick;right[start+i]+=kick+tick*.6;
 }
}
for(const time of [4,7.5,13,14.93,17.07,19,24.5,27.1,31]){
 const start=Math.max(0,Math.floor((time-.15)*rate)),end=Math.min(n,Math.floor((time+.3)*rate));let sm=0;
 for(let i=start;i<end;i++){sm=sm*.9+noise()*.1;const x=sm*.019*Math.exp(-((i/rate-time)**2)*60);left[i]+=x;right[i]-=x*.6;}
}
const dryL=left.slice(),dryR=right.slice();
for(const [delay,gain] of [[.15,.17],[.31,.1],[.49,.055]]){const d=Math.round(delay*rate);for(let i=d;i<n;i++){left[i]+=dryR[i-d]*gain;right[i]+=dryL[i-d]*gain;}}
const wav=Buffer.alloc(44+n*4);wav.write('RIFF',0);wav.writeUInt32LE(36+n*4,4);wav.write('WAVEfmt ',8);
wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(2,22);wav.writeUInt32LE(rate,24);wav.writeUInt32LE(rate*4,28);wav.writeUInt16LE(4,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(n*4,40);
let peak=0;
for(let i=0;i<n;i++){const t=i/rate,fade=Math.max(0,Math.min(1,t/.15,(seconds-t)/2)),l=left[i]*2.6*fade,r=right[i]*2.6*fade;peak=Math.max(peak,Math.abs(l),Math.abs(r));wav.writeInt16LE(Math.round(Math.max(-1,Math.min(1,l))*32767),44+i*4);wav.writeInt16LE(Math.round(Math.max(-1,Math.min(1,r))*32767),46+i*4);}
mkdirSync('public',{recursive:true});writeFileSync('public/music-commercial.wav',wav);console.log(JSON.stringify({seconds,peakDb:20*Math.log10(peak)}));
