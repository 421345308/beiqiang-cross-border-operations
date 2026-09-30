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
 const body=Buffer.concat(chunks);const params={method:req.method,path:u.pathname,query:Object.fromEntries(u.searchParams),headers:{}};
 for(const h of ['content-type','accept'])if(req.headers[h])params.headers[h]=req.headers[h];if(body.length)params.body_b64=body.toString('base64');
 const result=await c.call(`${pipe.channel}/http.fetch`,params);requests.push({method:req.method,path:u.pathname,status:result.status});res.writeHead(result.status,Object.fromEntries(Object.entries(result.headers).filter(([h])=>h!=='content-length')));res.end(Buffer.from(result.body_b64,'base64'));
 }catch(e){requests.push({method:req.method,path:new URL(req.url,'http://127.0.0.1').pathname,error:String(e)});res.writeHead(502,{'content-type':'application/json'});res.end(JSON.stringify({error:String(e)}));}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const endpoint=`http://127.0.0.1:${server.address().port}`;
const profile=JSON.parse(fs.readFileSync('C:/Users/spq/.workbuddy/cache/acc-product-config-v3.json','utf8'));
profile.endpoint=endpoint;profile.stagingEndpoint=endpoint;profile.officialEndpoints=[endpoint];profile.authentication={id:'beiqiang-wbipc-local',type:'custom-token',attributes:{tokenType:'bearerToken',token:key}};
const env={...process.env,ACC_PRODUCT_CONFIG_V3:JSON.stringify(profile),WORKBUDDY_CONFIG_DIR:'C:/Users/spq/.workbuddy',CODEBUDDY_FORCE_LITE_WB_BUNDLE:'1',CODEBUDDY_BASE_URL:endpoint+'/v2',CODEBUDDY_API_KEY:key,CODEBUDDY_CREDENTIALS_IN_MEMORY:'1'};delete env.ACC_PRODUCT_CONFIG_PATH;
fs.writeFileSync(path.join(dir,'task.md'),task);fs.writeFileSync(path.join(dir,'empty_mcp.json'),'{"mcpServers":{}}');
const start=Date.now();fs.writeFileSync(path.join(dir,'started.json'),JSON.stringify({epoch:start,workspace:root,product:'WorkBuddy',model:'glm-5.0-turbo',maxTurns:8,transport:'authenticated WBIPC',upstreamCredentialsCopied:false}));
const cli='C:/Users/spq/AppData/Local/Programs/WorkBuddy/resources/app.asar.unpacked/cli/bin/codebuddy';
const child=spawn(process.execPath,[cli,'-p',task,'--model','glm-5.0-turbo','--effort','minimal','--max-turns','8','--output-format','stream-json','--session-id','bq-wbipc-'+crypto.randomUUID(),'--add-dir',root,'--tools','Read,Write','--permission-mode','acceptEdits','--strict-mcp-config','--mcp-config',path.join(dir,'empty_mcp.json')],{cwd:root,env,windowsHide:true});
let stdout='',stderr='';child.stdout.on('data',d=>stdout+=d);child.stderr.on('data',d=>stderr+=d);
const timer=setTimeout(()=>child.kill(),150000);const exitCode=await new Promise((r,j)=>{child.on('exit',r);child.on('error',j)});clearTimeout(timer);
await new Promise(r=>server.close(r));c.close();
stdout=stdout.split(key).join('[LOCAL_KEY_REDACTED]');stderr=stderr.split(key).join('[LOCAL_KEY_REDACTED]');
fs.writeFileSync(path.join(dir,'stream.jsonl'),stdout);fs.writeFileSync(path.join(dir,'stderr.txt'),stderr);fs.writeFileSync(path.join(dir,'requests.json'),JSON.stringify(requests,null,2));
const events=stdout.split('\n').flatMap(l=>{try{return[JSON.parse(l)]}catch{return[]}});const last=events.findLast(e=>e.type==='result')||{};
const summary={exitCode,elapsedSeconds:(Date.now()-start)/1000,isError:last.is_error,terminalType:last.subtype,turns:last.num_turns,deliverablesPresent:['result.md','cached_bank_checks.json'].every(f=>fs.existsSync(path.join(dir,f))),modelRequests,requestStatuses:requests};
fs.writeFileSync(path.join(dir,'finished.json'),JSON.stringify(summary,null,2));console.log(JSON.stringify(summary));
