// Original instrumental score, synthesized locally; no external recordings.
import {writeFileSync,mkdirSync} from 'node:fs';
const rate=48000,seconds=32,n=rate*seconds;
const left=new Float32Array(n),right=new Float32Array(n);
const freq=midi=>440*2**((midi-69)/12);
let seed=4813;
const noise=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296*2-1;};
function note(time,midi,gain,length=3.3,pan=0){
  const hz=freq(midi),start=Math.floor(time*rate),len=Math.min(Math.floor(length*rate),n-start);
  for(let j=0;j<len;j++){
    const t=j/rate,attack=1-Math.exp(-t*220),env=attack*Math.exp(-t*1.25)*(1-t/length);
    const signal=(Math.sin(2*Math.PI*hz*t)+0.32*Math.sin(2*Math.PI*hz*2.002*t)*Math.exp(-t*1.9)+0.12*Math.sin(2*Math.PI*hz*3.01*t)*Math.exp(-t*3.1)+0.08*Math.sin(2*Math.PI*hz*0.999*t))*env*gain;
    left[start+j]+=signal*(0.75-pan*0.25);right[start+j]+=signal*(0.75+pan*0.25);
  }
}
const beat=2/3;
const chords=[[48,55,60,64,67,74],[45,52,57,60,64,67],[41,48,53,57,60,64],[43,50,55,59,62,69]];
for(let bar=0;bar<12;bar++){
  const chord=chords[bar%4],time=bar*4*beat;
  note(time,chord[0],0.074,4.2,-0.1);note(time+0.04,chord[1],0.035,4.1,0.1);
  const order=bar%2?[2,4,3,5]:[2,3,4,5];
  for(let k=0;k<4;k++)note(time+k*beat+0.13,chord[order[k]],0.062+(k===0?0.014:0),2.7,(k-1.5)*0.28);
  if(bar===2||bar===5||bar===8||bar===10)note(time+1.5*beat,chord[4]+12,0.033,3.5,0.4);
}
// Quiet wide pad beneath the notes, with changing harmony.
for(let i=0;i<n;i++){
  const t=i/rate,bar=Math.min(11,Math.floor(t/(4*beat))),chord=chords[bar%4];
  const phase=t%(4*beat),env=Math.min(1,phase/0.55,(4*beat-phase)/0.55);
  for(const midi of [chord[2],chord[3],chord[4]]){
    const hz=freq(midi);left[i]+=Math.sin(2*Math.PI*hz*t)*0.007*env;right[i]+=Math.sin(2*Math.PI*(hz+0.2)*t)*0.007*env;
  }
}
// Air movement follows picture transitions; no heavy advertising impacts.
for(const time of [3.07,8.07,13.8,18.67,25.27]){
  const start=Math.floor((time-0.25)*rate),end=Math.min(n,Math.floor((time+0.4)*rate));let smooth=0;
  for(let i=start;i<end;i++){const age=i/rate-time;smooth=smooth*0.88+noise()*0.12;const signal=smooth*0.018*Math.exp(-age*age*35);left[i]+=signal;right[i]-=signal*0.7;}
}
// Deterministic short room reflections from a dry copy.
const dryL=left.slice(),dryR=right.slice();
for(const [delay,gain] of [[0.13,0.19],[0.29,0.12],[0.47,0.07],[0.71,0.035]]){
  const d=Math.round(delay*rate);for(let i=d;i<n;i++){left[i]+=dryR[i-d]*gain;right[i]+=dryL[i-d]*gain;}
}
const buffer=Buffer.alloc(44+n*4);buffer.write('RIFF',0);buffer.writeUInt32LE(36+n*4,4);buffer.write('WAVEfmt ',8);
buffer.writeUInt32LE(16,16);buffer.writeUInt16LE(1,20);buffer.writeUInt16LE(2,22);buffer.writeUInt32LE(rate,24);buffer.writeUInt32LE(rate*4,28);buffer.writeUInt16LE(4,32);buffer.writeUInt16LE(16,34);buffer.write('data',36);buffer.writeUInt32LE(n*4,40);
let peak=0;
for(let i=0;i<n;i++){
  const t=i/rate,fade=Math.min(1,t/0.3,(seconds-t)/2.2);
  const l=left[i]*fade*2.2,r=right[i]*fade*2.2;peak=Math.max(peak,Math.abs(l),Math.abs(r));
  buffer.writeInt16LE(Math.round(Math.max(-1,Math.min(1,l))*32767),44+i*4);buffer.writeInt16LE(Math.round(Math.max(-1,Math.min(1,r))*32767),46+i*4);
}
mkdirSync('public',{recursive:true});writeFileSync('public/music-final.wav',buffer);console.log(JSON.stringify({seconds,peak,peakDb:20*Math.log10(peak)}));
