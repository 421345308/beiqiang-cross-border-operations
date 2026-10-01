import {connectWB} from './workbuddy_ipc_client.mjs';
import fs from 'node:fs';import path from 'node:path';import http from 'node:http';import crypto from 'node:crypto';import {spawn} from 'node:child_process';
const root='C:/Users/spq/Desktop/贝强';
const [taskFile,outputDir]=process.argv.slice(2);
if(!taskFile||!outputDir)throw new Error('Usage: node run_workbuddy_task.mjs TASK_FILE OUTPUT_DIR');
const dir=path.resolve(outputDir);const workspace=path.resolve(root)+path.sep;
if(!dir.startsWith(workspace)||dir===path.resolve(root))throw new Error('Output must be in the workspace');
fs.mkdirSync(dir,{recursive:true});if(fs.existsSync(path.join(dir,'started.json')))throw new Error('Already attempted; inspect prior result first');
const task=fs.readFileSync(taskFile,'utf8');if(task.length>20000)throw new Error('Task too large');
const c=await connectWB();const pipe=await c.call('broker/GetPipe',{pipe:'wb.request'});
const key=crypto.randomBytes(32).toString('hex');const requests=[];let modelRequests=0;
const server=http.createServer(async(req,res)=>{
 if(req.headers.authorization!==`Bearer ${key}`){res.writeHead(401);res.end();return;}
 try{const u=new URL(req.url,'http://127.0.0.1');const chunks=[];let size=0;for await(const d of req){size+=d.length;if(size>500000)throw new Error('Request too large');chunks.push(d);}
 if(u.pathname==='/v2/chat/completions'&&++modelRequests>8)throw new Error('Model request limit reached');
 let body=Buffer.concat(chunks);
 // WorkBuddy requires streaming, and its host pipe caps inline replies.
 // Bound each model answer; split large deliverables into smaller tasks.
 if(u.pathname==='/v2/chat/completions'){
  const payload=JSON.parse(body.toString('utf8'));
  payload.max_tokens=Math.min(payload.max_tokens||1800,1800);
  body=Buffer.from(JSON.stringify(payload));
 }
 const params={method:req.method,path:u.pathname,query:Object.fromEntries(u.searchParams),headers:{}};
 for(const h of ['content-type','accept'])if(req.headers[h])params.headers[h]=req.headers[h];if(body.length)params.body_b64=body.toString('base64');
 const result=await c.call(`${pipe.channel}/http.fetch`,params);requests.push({method:req.method,path:u.pathname,status:result.status});
 let responseBody=Buffer.from(result.body_b64,'base64');
 const headers=Object.fromEntries(Object.entries(result.headers).filter(([h])=>!['content-length','transfer-encoding','content-encoding'].includes(h.toLowerCase())));
 res.writeHead(result.status,headers);res.end(responseBody);
 }catch(e){requests.push({method:req.method,path:new URL(req.url,'http://127.0.0.1').pathname,error:String(e)});res.writeHead(502,{'content-type':'application/json'});res.end(JSON.stringify({error:String(e)}));}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const endpoint=`http://127.0.0.1:${server.address().port}`;
const profile=JSON.parse(fs.readFileSync('C:/Users/spq/.workbuddy/cache/acc-product-config-v3.json','utf8'));
profile.endpoint=endpoint;profile.stagingEndpoint=endpoint;profile.officialEndpoints=[endpoint];profile.authentication={id:'beiqiang-wbipc-local',type:'custom-token',attributes:{tokenType:'bearerToken',token:key}};
const env={...process.env,ACC_PRODUCT_CONFIG_V3:JSON.stringify(profile),WORKBUDDY_CONFIG_DIR:'C:/Users/spq/.workbuddy',CODEBUDDY_CONFIG_DIR:'C:/Users/spq/.workbuddy',CODEBUDDY_FORCE_LITE_WB_BUNDLE:'1',CODEBUDDY_BASE_URL:endpoint+'/v2',CODEBUDDY_API_KEY:key,CODEBUDDY_CREDENTIALS_IN_MEMORY:'1'};delete env.ACC_PRODUCT_CONFIG_PATH;
fs.writeFileSync(path.join(dir,'task.md'),task);fs.writeFileSync(path.join(dir,'empty_mcp.json'),'{"mcpServers":{}}');
const sessionId=crypto.randomUUID();
const start=Date.now();fs.writeFileSync(path.join(dir,'started.json'),JSON.stringify({epoch:start,sessionId,workspace:root,product:'WorkBuddy',model:'deepseek-v4.1-flash',maxTurns:8,transport:'authenticated WBIPC',upstreamCredentialsCopied:false,desktopVisibility:'not verified'}));
const cli='C:/Users/spq/AppData/Local/Programs/WorkBuddy/resources/app.asar.unpacked/cli/bin/codebuddy';
const child=spawn(process.execPath,[cli,'-p',task,'--model','deepseek-v4.1-flash','--effort','minimal','--max-turns','8','--output-format','stream-json','--session-id',sessionId,'--add-dir',root,'--tools','Read,Write','--permission-mode','acceptEdits','--strict-mcp-config','--mcp-config',path.join(dir,'empty_mcp.json')],{cwd:root,env,windowsHide:true});
let stdout='',stderr='';child.stdout.on('data',d=>{const s=d.toString().split(key).join('[LOCAL_KEY_REDACTED]');stdout+=s;fs.appendFileSync(path.join(dir,'stream.jsonl'),s);});child.stderr.on('data',d=>{const s=d.toString().split(key).join('[LOCAL_KEY_REDACTED]');stderr+=s;fs.appendFileSync(path.join(dir,'stderr.txt'),s);});
const timer=setTimeout(()=>child.kill(),240000);const exitCode=await new Promise((r,j)=>{child.on('exit',r);child.on('error',j)});clearTimeout(timer);
server.closeAllConnections();await new Promise(r=>server.close(r));c.close();
stdout=stdout.split(key).join('[LOCAL_KEY_REDACTED]');stderr=stderr.split(key).join('[LOCAL_KEY_REDACTED]');
fs.writeFileSync(path.join(dir,'stream.jsonl'),stdout);fs.writeFileSync(path.join(dir,'stderr.txt'),stderr);fs.writeFileSync(path.join(dir,'requests.json'),JSON.stringify(requests,null,2));
const events=stdout.split('\n').flatMap(l=>{try{return[JSON.parse(l)]}catch{return[]}});const last=events.findLast(e=>e.type==='result')||{};
const summary={sessionId,model:'deepseek-v4.1-flash',exitCode,elapsedSeconds:(Date.now()-start)/1000,isError:last.is_error,terminalType:last.subtype,turns:last.num_turns,result:last.result,modelRequests,requestStatuses:requests};
fs.writeFileSync(path.join(dir,'finished.json'),JSON.stringify(summary,null,2));console.log(JSON.stringify(summary));
