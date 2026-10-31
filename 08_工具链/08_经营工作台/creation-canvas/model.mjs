export function savePayload(objectId,nodes,edges,version){
 if(!objectId?.startsWith('creation:'))throw new Error('请选择原始创作项目');
 const ids=new Set(nodes.map(n=>n.id));
 if(edges.some(e=>!ids.has(e.source)||!ids.has(e.target)))throw new Error('连线缺少对应节点');
 return {object_id:objectId,version,nodes:nodes.map(({id,type,position,data})=>({id,type,position,data})),edges:edges.map(({id,source,target,sourceHandle,targetHandle,label})=>({id,source,target,sourceHandle,targetHandle,label}))};
}
export function safeMediaUrl(url){return typeof url==='string'&&url.startsWith('/api/media/')?url:null;}
