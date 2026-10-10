// Original, locally synthesized sound bed for this study. No sampled music.
import {writeFileSync, mkdirSync} from 'node:fs';
const v2=process.argv.includes('--v2');
const rate=48000, duration=v2?20:18, count=rate*duration;
const buffer=Buffer.alloc(44+count*4);
buffer.write('RIFF',0);buffer.writeUInt32LE(36+count*4,4);buffer.write('WAVEfmt ',8);
buffer.writeUInt32LE(16,16);buffer.writeUInt16LE(1,20);buffer.writeUInt16LE(2,22);
buffer.writeUInt32LE(rate,24);buffer.writeUInt32LE(rate*4,28);buffer.writeUInt16LE(4,32);buffer.writeUInt16LE(16,34);
buffer.write('data',36);buffer.writeUInt32LE(count*4,40);
const notes=[220,261.6256,329.6276,391.9954];
let state=7301;
const noise=()=>{state=(1664525*state+1013904223)>>>0;return state/4294967296*2-1;};
for(let i=0;i<count;i++) {
  const t=i/rate; const fade=Math.min(1,t/0.8,(duration-t)/1.4);
  let left=0,right=0;
  notes.forEach((hz,j)=>{
    const swell=0.012*(1+0.2*Math.sin(t*0.7+j));
    left+=Math.sin(2*Math.PI*hz*t)*swell;
    right+=Math.sin(2*Math.PI*(hz+0.25)*t)*swell;
  });
  for(const [start,hz] of (v2?[[0.35,880],[2.2,1046.5],[5.1,1318.5],[10.2,1046.5],[14.4,880],[16.4,1318.5]]:[[0.35,880],[4.8,1046.5],[9.6,1318.5],[14.5,880]])){
    const age=t-start;if(age>=0&&age<3.5){
      const env=(1-Math.exp(-age*50))*Math.exp(-age*1.7)*0.12;
      const chime=(Math.sin(2*Math.PI*hz*age)+0.2*Math.sin(2*Math.PI*hz*2.01*age))*env;
      left+=chime;right+=chime;
    }
  }
  for(const start of (v2?[2.2,5.1,10.2,14.4]:[4.8,9.6,14.5])){
    const age=t-start;if(age>-0.4&&age<0.5){const sw=noise()*0.012*Math.exp(-age*age*28);left+=sw;right+=sw;}
  }
  const gain=v2?2.5:1;
  buffer.writeInt16LE(Math.round(Math.max(-1,Math.min(1,left*fade*gain))*32767),44+i*4);
  buffer.writeInt16LE(Math.round(Math.max(-1,Math.min(1,right*fade*gain))*32767),46+i*4);
}
mkdirSync('public',{recursive:true});writeFileSync(v2?'public/sound-v2.wav':'public/sound.wav',buffer);
