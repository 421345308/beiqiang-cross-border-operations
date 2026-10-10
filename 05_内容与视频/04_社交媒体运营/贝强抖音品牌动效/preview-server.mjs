import {createServer} from 'node:http';
import {createReadStream,statSync} from 'node:fs';
import {resolve,extname} from 'node:path';
const root=process.cwd();
const mime={'.html':'text/html; charset=utf-8','.png':'image/png','.mp4':'video/mp4'};
createServer((req,res)=> {
  const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname).replace(/^\//,'')||'preview.html';
  if(!/^(preview\.html|public\/(warm|dark|color)\.png|out\/[^/]+\.(mp4|png))$/.test(name)){res.writeHead(404).end();return;}
  const file=resolve(root,name);
  try{
    const size=statSync(file).size;
    const match=req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
    if(match){const start=Number(match[1]);const end=Math.min(match[2]?Number(match[2]):size-1,size-1);res.writeHead(206,{'Content-Type':mime[extname(file)],'Accept-Ranges':'bytes','Content-Range':`bytes ${start}-${end}/${size}`,'Content-Length':end-start+1});createReadStream(file,{start,end}).pipe(res);}
    else{res.writeHead(200,{'Content-Type':mime[extname(file)],'Accept-Ranges':'bytes','Content-Length':size});createReadStream(file).pipe(res);}
  }catch{res.writeHead(404).end();}
}).listen(3417,'127.0.0.1',()=>console.log('Preview: http://127.0.0.1:3417'));
