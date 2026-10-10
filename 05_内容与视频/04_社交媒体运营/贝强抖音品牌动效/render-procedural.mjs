import {spawn} from 'node:child_process';
import {copyFile,mkdir,readdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.dirname(fileURLToPath(import.meta.url));
const frames=path.join(root,'out','程序绘制帧');
const output=path.join(root,'out','贝强_针织袜子鞋_程序绘制版.mp4');
const ffmpeg=process.env.BEIQIANG_FFMPEG || path.resolve(root,'../../..','08_工具链','02_视频工具','ffmpeg','ffmpeg-9.0-essentials_build','bin','ffmpeg.exe');
const browser=process.env.BEIQIANG_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
function run(exe,args) {
  return new Promise((resolve,reject)=>{
    const child=spawn(exe,args,{cwd:root,stdio:'inherit',windowsHide:true});
    child.once('error',reject);
    child.once('exit',code=>code===0?resolve():reject(new Error(`${exe}: exit ${code}`)));
  });
}
await mkdir(frames,{recursive:true});
if(!process.argv.includes('--encode-only')) {
  await run(process.execPath,['node_modules/@remotion/cli/remotion-cli.js','render','src/index.ts','ProceduralBrandFilm',frames,'--sequence','--image-format=png','--image-sequence-pattern=frame-[frame].png','--gl=angle','--concurrency=2',`--browser-executable=${browser}`]);
}
const files=(await readdir(frames)).filter(f=>/^frame-\d+\.png$/.test(f)).sort();
if(files.length!==1080)throw new Error(`Expected 1080 frames, found ${files.length}`);
for(let i=0;i<1080;i++)if(files[i]!==`frame-${String(i).padStart(4,'0')}.png`)throw new Error(`Missing frame ${i}`);
await run(ffmpeg,['-y','-framerate','30','-start_number','0','-i',path.join(frames,'frame-%04d.png'),'-i','public/music-commercial.wav','-vf','scale=1080:1920:out_color_matrix=bt709,format=yuv420p','-c:v','libx264','-crf','18','-preset','medium','-r','30','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-af','volume=0.85','-c:a','aac','-b:a','192k','-t','36','-movflags','+faststart',output]);
await writeFile(path.join(root,'out','程序绘制流程.json'),JSON.stringify({composition:'ProceduralBrandFilm',width:1080,height:1920,fps:30,frameCount:files.length,stages:['React/Three.js frame-driven geometry','Headless Chromium PNG screenshots','FFmpeg H.264/AAC encoding'],framePattern:'程序绘制帧/frame-%04d.png',audio:'public/music-commercial.wav',output:path.basename(output)},null,2));
await copyFile(path.join(frames,'frame-1010.png'),path.join(root,'out','贝强_程序绘制版_封面.png'));
