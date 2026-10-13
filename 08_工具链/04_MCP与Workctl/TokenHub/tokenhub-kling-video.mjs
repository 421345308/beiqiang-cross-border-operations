import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// The API key stays in memory; CLI-managed credentials are never modified.
// Submit once. An ambiguous network failure must not trigger a paid resubmission.
const [mode, recipePath, jobId] = process.argv.slice(2);
if (!['submit','poll','resume-connect-failure'].includes(mode) || !recipePath || !jobId)
  throw new Error('Usage: submit|poll|resume-connect-failure recipe.json job-id');
const recipe = JSON.parse(fs.readFileSync(recipePath,'utf8'));
const job = recipe.jobs.find(j=>j.id===jobId);
if (!job || recipe.model !== 'kling-video-v3' || recipe.status !== 'approved')
  throw new Error('Missing approved Kling V3 trial.');
const settings = {...recipe.settings, ...job.settings};
if (!Number.isInteger(settings.duration) || settings.duration < 3 || settings.duration > 15)
  throw new Error('Kling V3 duration must be an explicitly approved integer from 3 to 15 seconds.');
const base = path.dirname(path.resolve(recipePath));
const dir = path.join(base,'edit','generation','tokenhub-kling-v3');
fs.mkdirSync(dir,{recursive:true});
const receiptPath = path.join(dir,job.id + '.json');
const config = JSON.parse(fs.readFileSync(path.join(os.homedir(),'.thcli',recipe.auth.profile+'.tokenhub.json'),'utf8'));
const key = config.sites?.[recipe.site]?.[recipe.area]?.th?.[recipe.auth.alias];
if (!key || typeof key !== 'string') throw new Error('CLI-managed API key unavailable.');
const clean = value => {
  if (typeof value === 'string') {
    const safe = value.replaceAll(key,'[REDACTED]');
    if (/^https?:/.test(safe)) { try {const u=new URL(safe);u.search='';return u.toString();}catch{} }
    return safe;
  }
  if (Array.isArray(value)) return value.map(clean);
  if (value && typeof value==='object') return Object.fromEntries(Object.entries(value).map(([k,v]) =>
    [k, /^(secretKey|secretId|accessToken|refreshToken|apiKey|authorization)$/i.test(k)?'[REDACTED]':clean(v)]));
  return value;
};
const write = value => fs.writeFileSync(receiptPath,JSON.stringify(clean(value),null,2)+'\n');
const call = async (url,body) => {
  const r = await fetch(url,{method:body?'POST':'GET',
    headers:{Authorization:'Bearer '+key,...(body?{'Content-Type':'application/json'}:{})},
    ...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(120000)});
  let data; try {data=await r.json();} catch {throw new Error('Non-JSON response; HTTP '+r.status);}
  if (!r.ok || data.code !== 0) throw new Error(JSON.stringify(clean({http:r.status,response:data})));
  return data;
};
let receipt;
if (mode === 'submit' || mode === 'resume-connect-failure') {
  let prior;
  if (mode === 'submit' && fs.existsSync(receiptPath)) throw new Error('Submission ledger exists; do not resubmit automatically.');
  if (mode === 'resume-connect-failure') {
    prior=JSON.parse(fs.readFileSync(receiptPath,'utf8'));
    if (prior.task_id || prior.status !== 'transport_connect_failed' || prior.error_code !== 'UND_ERR_CONNECT_TIMEOUT')
      throw new Error('Only proven pre-connection failure can resume; ambiguous dispatch may not.');
  }
  receipt={job:job.id,model:recipe.model,status:'dispatching',settings,started_at:new Date().toISOString(),
    ...(prior?{previous_transport_attempt:prior}:{})};
  write(receipt);
  const contents=[{type:'prompt',text:job.prompt}];
  for (const role of ['first_frame','last_frame']) if(job[role])
    contents.push({type:role,url:fs.readFileSync(path.resolve(base,job[role])).toString('base64')});
  try {
    const response=await call('https://tokenhub.tencentmaas.com/v1/wand/kling/image-to-video',
      {model:recipe.model,contents,settings});
    receipt={...receipt,status:response.data?.status??'submitted',task_id:response.data?.id,response};
    write(receipt); console.log(JSON.stringify({job:job.id,status:receipt.status,task_id:receipt.task_id}));
  } catch(error) {
    const errorCode=error.cause?.code;
    write({...receipt,status:errorCode==='UND_ERR_CONNECT_TIMEOUT'?'transport_connect_failed':'submission_failed_or_unknown',
      error:clean(error.message),...(errorCode?{error_code:errorCode}:{})});
    throw error;
  }
} else {
  receipt=JSON.parse(fs.readFileSync(receiptPath,'utf8'));
  if (!receipt.task_id) throw new Error('No recoverable task ID; do not submit again.');
  const response=await call('https://tokenhub.tencentmaas.com/v1/wand/kling/tasks/'+encodeURIComponent(receipt.task_id));
  const result=Array.isArray(response.data)?response.data.find(d=>d.id===receipt.task_id)??response.data[0]:response.data;
  const status=result?.status??result?.task_status;
  receipt={...receipt,status,query_response:response,checked_at:new Date().toISOString()};
  if (status==='succeeded' && !receipt.local_video) {
    const video=result.outputs?.find(o=>o.type==='video');
    if (!video?.url || new URL(video.url).protocol!=='https:') throw new Error('Missing HTTPS video output.');
    const r=await fetch(video.url,{signal:AbortSignal.timeout(120000)});
    if (!r.ok) throw new Error('Video download HTTP '+r.status);
    const target=path.join(base,'public','dynamic',job.id+'.mp4');
    fs.mkdirSync(path.dirname(target),{recursive:true});
    fs.writeFileSync(target,Buffer.from(await r.arrayBuffer()));
    receipt.local_video=path.relative(base,target).split(path.sep).join('/');
  }
  write(receipt);
  console.log(JSON.stringify({job:job.id,status:receipt.status,local_video:receipt.local_video,message:result?.message,
    usage:response.tokenhub_usage}));
}
