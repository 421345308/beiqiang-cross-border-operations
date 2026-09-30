import fs from 'node:fs';
import net from 'node:net';
import crypto from 'node:crypto';
export async function connectWB() {
 const {endpoint,ticket}=JSON.parse(fs.readFileSync('C:/Users/spq/.workbuddy/wbipc/endpoint.json','utf8'));
 const socket=net.connect(endpoint); let buffer=''; const queue=[], waiters=[];
 socket.on('data',d=>{buffer+=d.toString(); if(buffer.length>1048576) socket.destroy(new Error('frame limit')); let i; while((i=buffer.indexOf('\n'))>=0){const x=JSON.parse(buffer.slice(0,i));buffer=buffer.slice(i+1); if(waiters.length)waiters.shift().resolve(x);else queue.push(x);}});
 socket.on('error',e=>{while(waiters.length)waiters.shift().reject(e);});
 const receive=()=>queue.length?Promise.resolve(queue.shift()):new Promise((resolve,reject)=>{const item={resolve:x=>{clearTimeout(timer);resolve(x)},reject};const timer=setTimeout(()=>{const i=waiters.indexOf(item);if(i>=0)waiters.splice(i,1);reject(new Error('IPC timeout'));},55000);waiters.push(item);});
 const send=x=>socket.write(JSON.stringify(x)+'\n');
 const nonce=crypto.randomBytes(16).toString('base64url');
 const proof=(role,sn)=>{const parts=[role,'1',endpoint,nonce,sn].map(s=>{const b=Buffer.from(s);const n=Buffer.alloc(4);n.writeUInt32BE(b.length);return Buffer.concat([n,b]);});return crypto.createHmac('sha256',ticket).update(Buffer.concat(parts)).digest('base64url');};
 send({type:'session_hello',protocol_min:1,protocol_max:1,client_nonce:nonce,ticket_id:crypto.createHash('sha256').update(ticket).digest('hex').slice(0,16),client:{kind:'integration',id:'beiqiang-codex',version:'1'}});
 const challenge=await receive();
 if(challenge.type!=='session_challenge'||challenge.protocol!==1)throw new Error('Unexpected handshake');
 const expected=Buffer.from(proof('wbipc-s',challenge.server_nonce));const actual=Buffer.from(challenge.server_proof||'');
 if(actual.length!==expected.length||!crypto.timingSafeEqual(actual,expected))throw new Error('Untrusted endpoint');
 send({type:'session_prove',client_proof:proof('wbipc-c',challenge.server_nonce)});
 const ack=await receive();if(ack.type!=='session_hello_ack')throw new Error('Handshake rejected');
 let id=0; let chain=Promise.resolve();
 const call=(method,params)=>{const work=chain.then(async()=>{const n=++id;send({jsonrpc:'2.0',id:n,method,mode:'call',params});let r;do{r=await receive();}while(r.id!==n);if(r.error)throw new Error(JSON.stringify(r.error));return r.result;});chain=work.catch(()=>{});return work;};
 return {ack,call,close:()=>socket.destroy()};
}
