import {writeFileSync} from 'node:fs';
const rate=48000,seconds=31.5,n=rate*seconds;
const l=new Float32Array(n),r=new Float32Array(n);
let seed=17281;const noise=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2147483648-1};
const hz=m=>440*2**((m-69)/12);
function put(start,length,fn,pan=0){const a=Math.round(start*rate),b=Math.min(n,a+Math.round(length*rate));for(let i=a;i<b;i++){const v=fn((i-a)/rate);l[i]+=v*(1-pan*.35);r[i]+=v*(1+pan*.35)}}
function key(t,m,g=.035){const h=hz(m);put(t,2.4,s=>{const env=(1-Math.exp(-s*110))*Math.exp(-s*2.5);const fm=Math.sin(2*Math.PI*h*s+.72*Math.sin(2*Math.PI*h*2*s)*Math.exp(-s*4));return (fm+.12*Math.sin(2*Math.PI*h*3*s))*env*g},m%2?.35:-.35)}
function bass(t,m){const h=hz(m);put(t,.42,s=>(Math.sin(2*Math.PI*h*s)+.24*Math.sin(2*Math.PI*h*2*s))*(1-Math.exp(-s*90))*Math.exp(-s*7)*.082)}
function kick(t){put(t,.2,s=>Math.sin(2*Math.PI*(47*s+1.1*(1-Math.exp(-s*35))))*Math.exp(-s*26)*.1)}
function brush(t,g=.024){let sm=0;put(t,.16,s=>{sm=sm*.52+noise()*.48;return sm*Math.exp(-s*30)*g},.2)}
function hat(t){let last=0;put(t,.035,s=>{const v=noise(),hi=v-last;last=v;return hi*Math.exp(-s*130)*.009},-.4)}
const chords=[[50,57,60,64,69],[43,53,57,62,65],[48,55,59,62,67],[41,53,57,60,64]];
for(let bar=0;bar<16;bar++){
 const t=bar*2,c=chords[Math.floor(bar/2)%4];
 c.slice(1).forEach((m,i)=>key(t+.028*i,m,.027));
 if(bar<16){key(t+.75,c[3]+12,.016);key(t+1.5,c[2]+12,.022)}
 bass(t,c[0]-12);bass(t+1,c[0]-12);bass(t+1.75,c[1]-12);
 if(bar<17){kick(t);kick(t+1);brush(t+.5);brush(t+1.5);
 for(let k=0;k<8;k++)hat(t+k*.25+(k%2?.018:0))}
}
// Short air cues mark changes in perspective, never cover the source motion.
for(const t of [3,5,8,11,14.5,18.5,22,24,25.5,27.33]){let sm=0;put(Math.max(0,t-.12),.22,s=>{sm=.9*sm+.1*noise();return sm*Math.sin(Math.PI*s/.22)**2*.042},-.1)}
const dl=l.slice(),dr=r.slice();for(const [delay,g] of [[.125,.10],[.25,.065],[.375,.035]]){const d=Math.round(delay*rate);for(let i=d;i<n;i++){l[i]+=dr[i-d]*g;r[i]+=dl[i-d]*g}}
let peak=0;for(let i=0;i<n;i++)peak=Math.max(peak,Math.abs(l[i]),Math.abs(r[i]));
const gain=.82/peak,wav=Buffer.alloc(44+n*4);wav.write('RIFF',0);wav.writeUInt32LE(36+n*4,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(2,22);wav.writeUInt32LE(rate,24);wav.writeUInt32LE(rate*4,28);wav.writeUInt16LE(4,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(n*4,40);
for(let i=0;i<n;i++){const fade=Math.min(1,i/rate/.05,(seconds-i/rate)/1.8);wav.writeInt16LE(Math.round(l[i]*gain*fade*32767),44+i*4);wav.writeInt16LE(Math.round(r[i]*gain*fade*32767),46+i*4)}
writeFileSync('public/brand-score.wav',wav);console.log('Original instrumental: 31.5s, 120bpm, stereo, peak -1.72dBFS');
