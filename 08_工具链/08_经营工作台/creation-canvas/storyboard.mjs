export function addShot(nodes, id) {
 const count=nodes.filter(n=>n.data?.kind==='shot').length;
 return {id,type:'creation',position:{x:100+(count%3)*340,y:420+Math.floor(count/3)*280},data:{kind:'shot',title:`镜头 ${count+1}`,content:'',purpose:'',duration:'',visual:'',copy:'',status:'待制作',media_path:''}};
}
export function exportBrief(title,nodes,edges){
 const lines=[`# ${title}`, ''];
 const names=new Map(nodes.map(n=>[n.id,n.data?.title||n.data?.label||n.id]));
 nodes.forEach((n,i)=>{const d=n.data||{};lines.push(`## ${i+1}. ${names.get(n.id)}`);for(const [key,label] of [['purpose','用途'],['duration','时长（秒）'],['visual','画面'],['copy','文案 / 声音'],['status','状态'],['content','备注'],['media_path','素材路径']])if(d[key])lines.push(`${label}：${d[key]}`);lines.push('');});
 if(edges.length){lines.push('## 镜头与素材关系');edges.forEach(e=>lines.push(`- ${names.get(e.source)||e.source} → ${names.get(e.target)||e.target}${e.label?`：${e.label}`:''}`));}
 return lines.join('\n');
}
