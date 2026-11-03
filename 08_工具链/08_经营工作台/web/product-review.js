'use strict';
(() => {
  const node = (tag, text, cls) => { const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e; };
  const roles={'Detail shot':'细节图','Scene image':'场景图','Product dimensions':'产品尺寸','Customization capabilities':'定制能力','Packaging & shipping specifications':'包装与运输','Competitive advantages':'工厂优势','Production workflow':'生产流程','Company overview':'工厂介绍'};
  const labels={same:'与本地记录一致',different:'与本地记录不同',not_recorded:'本地尚未登记',unavailable:'平台未返回'};
  const stamp=value=>{const date=new Date(value);return Number.isNaN(date.getTime())?'时间未知':date.toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});};
  const workflowLabels={business_rejected:'平台未受理商品修改','business-rejected':'平台未受理商品修改',outcome_unknown:'提交结果待回读',local_conflict:'平台已回读，本地同步冲突',formal_verified:'正式回读通过，本地尚未同步',conflict:'同步冲突'};
  const submissionMessage=value=>{
    if(value.state==='uploaded_submission_blocked')return '图片已上传，商品提交未完成，请查看方案状态。';
    if(value.state==='uploaded_preparation_failed')return '图片已上传，商品方案未准备完成。';
    if(value.state==='upload_outcome_unknown')return '图片上传结果待核对，请勿重复提交。';
    const submission=value.submissionResult?.change?.submission || value.submission;
    if(submission?.state==='business-rejected' || value.state==='business_rejected')return '平台未受理商品修改，请查看方案状态。';
    if(submission?.state==='outcome-unknown' || value.state==='outcome_unknown')return '提交结果未知，请回读核对，勿重复提交。';
    if(submission?.state==='submitted')return '已提交，请回读平台结果。';
    return '商品提交尚未确认，请查看方案状态。';
  };
  window.mountProductReview = (host, object, api, {preview, titleDraft, listingId: initialListingId = ''}) => {
    const card=node('section',undefined,'card listing-review');
    const head=node('div',undefined,'listing-review-head'),intro=node('div');
    intro.append(node('h2','国际站商品检查'),node('p','逐条查看平台上的标题、主图与详情图。'));
    const refresh=node('button','刷新平台数据','quiet');refresh.type='button';head.append(intro,refresh);card.append(head);
    const navigation=node('div',undefined,'listing-navigation'), select=node('select');select.setAttribute('aria-label','选择国际站商品链接');
    const open=node('a','打开国际站商品 ↗');open.target='_blank';open.rel='noopener noreferrer';navigation.append(select,open);card.append(navigation);
    const output=node('div',undefined,'listing-output');card.append(output);host.append(card);
    let listingId=String(initialListingId || ''),serial=0,prepared=false,translationTimer=null;
    function showImages(parent,title,rows,source) {
      const section=node('section',undefined,'listing-image-section');section.append(node('h3',`${title} · ${rows.length} 张`));
      const grid=node('div',undefined,source==='详情图'?'listing-image-grid details':'listing-image-grid');
      for(const [index,item] of rows.entries()) {
        const tile=node('button',undefined,'listing-image');tile.type='button';const img=node('img');img.src=item.url;img.alt=`${source} ${index+1}`;img.loading='lazy';img.referrerPolicy='no-referrer';
        img.addEventListener('error',()=>tile.classList.add('image-unavailable'));
        const label=`${source} ${index+1}${roles[item.role] ? ' · '+roles[item.role] : ''}`;
        tile.append(img,node('span',label));tile.addEventListener('click',()=>preview({url:item.url,label}));grid.append(tile);
      }
      if(!rows.length)section.append(node('p','平台没有返回图片。','muted'));else section.append(grid);
      parent.append(section);
    }
    function galleryEditor(parent, selected) {
      const original=selected.platform.main_images || [];
      if(original.length!==6)return;
      let order=[1,2,3,4,5,6];
      const assets=(object.assets || []).filter(item=>typeof item.path==='string' && /\.(jpg|jpeg|png)$/i.test(item.path) && item.url);
      const box=node('details',undefined,'listing-edit gallery-reorder'), controls=node('div',undefined,'gallery-sort-grid'), picker=node('div'), result=node('div'), note=node('p');
      box.append(node('summary','调整或替换主图'),node('p','可调整顺序或选择本商品已有图片，查看方案后再提交。'),controls,picker,note);
      function renderReview(change) {
        const isLocal=Array.isArray(change.previews), base=isLocal ? '/api/product-gallery-plans/' : '/api/product-gallery-changes/';
        const before=isLocal ? change.before : change.diff?.before, after=isLocal ? change.previews.map(item=>item.url || '/api/media/file?path='+encodeURIComponent(item.previewRef)) : change.diff?.after;
        result.replaceChildren(node('h4','主图调整方案'));
        for(const [title,urls] of [['修改前',before || []],['调整后',after || []]]) {
          const group=node('div');showImages(group,title,urls.map(url=>({url})),'主图');result.append(group);
        }
        const state=node('p'), actions=node('div');result.append(state,actions);
        const labels={'prepared':'待确认','uploaded':'图片已上传','uploaded_preparation_failed':'图片已上传，方案准备未完成','uploaded_submission_blocked':'图片已上传，商品未确认提交','upload_outcome_unknown':'图片上传结果待核对','formal_pending':'正式结果尚未核对通过','local_synced':'平台已回读并同步本地','not-submitted':'尚未提交','outcome-unknown':'结果待回读','submitted':'已提交','pending':'待核对','verified':'正式回读通过','synced':'已同步','not-synced':'尚未同步','not-verified':'尚未验收'};
        const update=()=>{if(isLocal){state.textContent=`方案状态：${labels[change.state] || workflowLabels[change.state] || change.state || '待提交'}`;return;}state.textContent=`提交：${labels[change.submission?.state] || workflowLabels[change.submission?.state] || change.submission?.state || '未提交'} · 平台：${labels[change.formal?.state] || change.formal?.state || '未验收'} · 本地：${labels[change.localSync?.state] || workflowLabels[change.localSync?.state] || change.localSync?.state || '未同步'}`;};
        if(isLocal ? change.state==='prepared' : change.submission?.state==='not-submitted') {
          const submit=node('button','确认提交主图方案','primary');submit.type='button';
          submit.addEventListener('click',async()=>{submit.disabled=true;try{const value=await api(`${base}${encodeURIComponent(change.id)}/${isLocal?'submit':'apply'}`,{confirmed:true,expected_version:change.version});change=value.change;note.textContent=submissionMessage(change);update();}catch(error){note.textContent=error.message;}});actions.append(submit);
        }
        const check=node('button','回读平台和本地结果','quiet');check.type='button';check.addEventListener('click',async()=>{check.disabled=true;try{const value=await api(`${base}${encodeURIComponent(change.id)}/reconcile`,{});change=value.change;update();note.textContent='已读取最新状态。';}catch(error){note.textContent=error.message;}finally{check.disabled=false;}});actions.append(check);update();
      }
      function draw() {
        controls.replaceChildren();
        order.forEach((slot,index)=>{
          const row=node('div',undefined,'gallery-sort-item'), image=node('img'), moves=node('div',undefined,'gallery-sort-actions');image.src=typeof slot==='number' ? original[slot-1].url : assets.find(item=>item.path===slot.path)?.url;image.alt=`第 ${index+1} 张主图`;image.referrerPolicy='no-referrer';row.append(image,node('span',`第 ${index+1} 张`),moves);
          for(const [label,delta] of [['前移',-1],['后移',1]]) {const move=node('button',label,'quiet');move.type='button';move.disabled=index+delta<0 || index+delta>=order.length;move.addEventListener('click',()=>{[order[index],order[index+delta]]=[order[index+delta],order[index]];draw();});moves.append(move);}
          if(assets.length){const replace=node('button','替换图片','quiet');replace.type='button';replace.addEventListener('click',()=>{picker.replaceChildren(node('p',`选择第 ${index+1} 张主图`));const choices=node('div',undefined,'listing-image-grid');for(const asset of assets){const option=node('button',undefined,'listing-image');option.type='button';const thumb=node('img');thumb.src=asset.url;thumb.alt='商品素材';thumb.loading='lazy';option.append(thumb,node('span',asset.label || '商品图片'));option.addEventListener('click',()=>{order[index]={path:asset.path};picker.replaceChildren();draw();});choices.append(option);}picker.append(choices);});row.append(replace);}
          controls.append(row);
        });
      }
      const prepare=node('button','生成主图调整方案','quiet');prepare.type='button';prepare.addEventListener('click',async()=>{prepare.disabled=true;note.textContent='正在核对平台主图和图片银行，首次查询可能需要几分钟…';try{const replaced=order.some(slot=>typeof slot!=='number'), endpoint=replaced?'/api/product-gallery-plans/prepare':'/api/product-gallery-changes/prepare';const value=await api(endpoint,{product_id:String(selected.id),...(replaced?{slots:order}:{order})});renderReview(value.change);note.textContent='方案已准备，请查看前后图片。';}catch(error){note.textContent=error.message;}finally{prepare.disabled=false;}});
      const saved=node('button','查看已有主图方案','quiet');saved.type='button';saved.addEventListener('click',async()=>{try{const values=await Promise.all([api('/api/product-gallery-changes'),api('/api/product-gallery-plans')]);const rows=values.flatMap(value=>value.changes || []).filter(row=>String(row.productId)===String(selected.id));result.replaceChildren();if(!rows.length){result.append(node('p','这条链接还没有主图方案。'));return;}for(const row of rows){const open=node('button',`查看 ${stamp(row.createdAt)} 的方案`,'quiet');open.type='button';open.addEventListener('click',()=>renderReview(row));result.append(open);}}catch(error){note.textContent=error.message;}});
      const footer=node('div',undefined,'gallery-footer');footer.append(prepare,saved);box.append(footer,result);draw();parent.append(box);
    }
    function detailEditor(parent, selected) {
      if(!(selected.platform.detail_images || []).length)return;
      const box=node('details',undefined,'listing-edit detail-reorder'), body=node('div'), footer=node('div',undefined,'gallery-footer'), note=node('p'), result=node('div');
      box.append(node('summary','调整详情图顺序'),node('p','按平台原有图片分组调整，图片说明随图片保留。'),body,footer,note,result);parent.append(box);
      function review(change) {
        result.replaceChildren(node('h4','详情图调整方案'));
        for(const [title,rows] of [['修改前',change.diff?.before || []],['调整后',change.diff?.after || []]]){const group=node('div');showImages(group,title,rows.map(row=>({url:row.image_url,role:row.image_set?.name})),'详情图');result.append(group);}
        const status=node('p'), actions=node('div');result.append(status,actions);
        const labels={'not-submitted':'尚未提交','outcome-unknown':'结果待回读','submitted':'已提交','pending':'待核对','verified':'正式回读通过','synced':'已同步','not-synced':'尚未同步','not-verified':'尚未验收'};const show=value=>labels[value] || workflowLabels[value] || value || '待处理';
        const update=()=>{status.textContent=`提交：${show(change.submission?.state)} · 平台：${show(change.formal?.state)} · 本地：${show(change.localSync?.state)}`;};
        if(change.submission?.state==='not-submitted'){const send=node('button','确认提交详情图顺序','primary');send.type='button';send.addEventListener('click',async()=>{send.disabled=true;try{const value=await api(`/api/product-detail-changes/${encodeURIComponent(change.id)}/apply`,{confirmed:true,expected_version:change.version});change=value.change;note.textContent=submissionMessage(change);update();}catch(error){note.textContent=error.message;}});actions.append(send);}
        const read=node('button','回读详情图结果','quiet');read.type='button';read.addEventListener('click',async()=>{read.disabled=true;try{const value=await api(`/api/product-detail-changes/${encodeURIComponent(change.id)}/reconcile`,{});change=value.change;update();note.textContent='已读取最新状态。';}catch(error){note.textContent=error.message;}finally{read.disabled=false;}});actions.append(read);update();
      }
      const load=node('button','读取详情图分组','quiet');load.type='button';load.addEventListener('click',async()=>{load.disabled=true;note.textContent='正在读取平台详情…';try{
        const response=await api('/api/desk/product-details-diagnosis?product_id='+encodeURIComponent(selected.id));const data=response.change, rows=data.platform.detail_images, groups=data.detailGroups.map(group=>({...group,slots:[...group.slots]}));note.textContent='';
        function draw(){body.replaceChildren();groups.forEach((group,index)=>{const block=node('section',undefined,'detail-group');block.append(node('h4',roles[group.roleName] || group.roleName || `图片组 ${index+1}`));const moves=node('div',undefined,'gallery-footer');for(const [label,delta] of [['整组前移',-1],['整组后移',1]]){const b=node('button',label,'quiet');b.type='button';b.disabled=index+delta<0 || index+delta>=groups.length;b.addEventListener('click',()=>{[groups[index],groups[index+delta]]=[groups[index+delta],groups[index]];draw();});moves.append(b);}block.append(moves);const grid=node('div',undefined,'gallery-sort-grid');group.slots.forEach((slot,n)=>{const item=node('div',undefined,'gallery-sort-item'),img=node('img'), actions=node('div',undefined,'gallery-sort-actions');img.src=rows[slot-1].image_url;img.alt=`详情图 ${slot}`;item.append(img,actions);for(const [label,delta] of [['前移',-1],['后移',1]]){const b=node('button',label,'quiet');b.type='button';b.disabled=n+delta<0 || n+delta>=group.slots.length;b.addEventListener('click',()=>{[group.slots[n],group.slots[n+delta]]=[group.slots[n+delta],group.slots[n]];draw();});actions.append(b);}grid.append(item);});block.append(grid);body.append(block);});}
        const save=node('button','生成详情图调整方案','quiet');save.type='button';save.addEventListener('click',async()=>{save.disabled=true;note.textContent='正在准备方案…';try{const value=await api('/api/product-detail-changes/prepare',{product_id:String(selected.id),order:groups.flatMap(group=>group.slots)});review(value.change);note.textContent='方案已准备，请查看图片顺序。';}catch(error){note.textContent=error.message;}finally{save.disabled=false;}});draw();footer.append(save);
      }catch(error){note.textContent=error.message;load.disabled=false;}});box.insertBefore(load,body);
      const saved=node('button','查看已有详情图方案','quiet');saved.type='button';saved.addEventListener('click',async()=>{try{const value=await api('/api/product-detail-changes');const rows=(value.changes || []).filter(row=>String(row.productId)===String(selected.id));result.replaceChildren();if(!rows.length){result.append(node('p','这条链接还没有详情图方案。'));return;}for(const row of rows){const open=node('button',`查看 ${stamp(row.createdAt)} 的方案`,'quiet');open.type='button';open.addEventListener('click',()=>review(row));result.append(open);}}catch(error){note.textContent=error.message;}});box.append(saved);
    }
    function detailReplacement(parent, selected) {
      if(!(selected.platform.detail_images || []).length)return;
      const assets=(object.assets || []).filter(item=>typeof item.path==='string' && /\.(jpg|jpeg|png)$/i.test(item.path) && item.url);
      const box=node('details',undefined,'listing-edit detail-replace'), body=node('div'), picker=node('div'), footer=node('div',undefined,'gallery-footer'), note=node('p'), result=node('div');
      box.append(node('summary','替换详情图'),node('p','可选择本商品素材或现有主图；保留原位置的图片说明和分组。'),body,picker,footer,note,result);parent.append(box);
      function review(plan){
        result.replaceChildren(node('h4','详情图替换方案'));
        const before=(plan.before || []).map(row=>({url:row.image_url,role:row.image_set?.name}));
        const after=(plan.previews || []).map((row,index)=>({url:row.url || '/api/media/file?path='+encodeURIComponent(row.previewRef),role:plan.before?.[index]?.image_set?.name}));
        showImages(result,'修改前',before,'详情图');showImages(result,'替换后',after,'详情图');
        const state=node('p'),actions=node('div');result.append(state,actions);const labels={prepared:'待确认',uploaded:'图片已上传',uploaded_preparation_failed:'图片已上传，方案准备未完成',uploaded_submission_blocked:'图片已上传，商品未确认提交',upload_outcome_unknown:'图片上传结果待核对',formal_pending:'正式结果尚未核对通过',local_synced:'平台已回读并同步本地'};
        const update=()=>{state.textContent=`方案状态：${labels[plan.state] || workflowLabels[plan.state] || plan.state || '待确认'}`;};
        if(plan.state==='prepared'){const submit=node('button','确认提交详情图替换','primary');submit.type='button';submit.addEventListener('click',async()=>{submit.disabled=true;try{const value=await api(`/api/product-detail-plans/${encodeURIComponent(plan.id)}/submit`,{confirmed:true,expected_version:plan.version});plan=value.change;note.textContent=submissionMessage(plan);update();}catch(error){note.textContent=error.message;}});actions.append(submit);}
        const check=node('button','回读详情图替换结果','quiet');check.type='button';check.addEventListener('click',async()=>{check.disabled=true;try{const value=await api(`/api/product-detail-plans/${encodeURIComponent(plan.id)}/reconcile`,{});plan=value.change;note.textContent='已读取最新状态。';update();}catch(error){note.textContent=error.message;}finally{check.disabled=false;}});actions.append(check);update();
      }
      const load=node('button','读取可替换的详情图','quiet');load.type='button';load.addEventListener('click',async()=>{load.disabled=true;note.textContent='正在读取平台详情…';try{
        const data=(await api('/api/desk/product-details-diagnosis?product_id='+encodeURIComponent(selected.id))).change, rows=data.platform.detail_images, slots=rows.map((_,index)=>index+1), main=selected.platform.main_images || [];
        function draw(){body.replaceChildren();const grid=node('div',undefined,'gallery-sort-grid');slots.forEach((slot,index)=>{const row=node('div',undefined,'gallery-sort-item'),img=node('img');img.src=typeof slot==='number'?rows[slot-1].image_url:slot.mainSlot?main[slot.mainSlot-1].url:assets.find(asset=>asset.path===slot.path)?.url;img.alt=`详情图 ${index+1}`;row.append(img,node('span',roles[rows[index].image_set?.name] || rows[index].image_set?.name || `详情图 ${index+1}`));const choose=node('button','替换图片','quiet');choose.type='button';choose.addEventListener('click',()=>{picker.replaceChildren(node('p',`选择第 ${index+1} 张详情图`));const choices=node('div',undefined,'listing-image-grid');for(const [i,item] of main.entries()){const b=node('button',undefined,'listing-image'),thumb=node('img');b.type='button';thumb.src=item.url;thumb.alt=`主图 ${i+1}`;b.append(thumb,node('span',`主图 ${i+1}`));b.addEventListener('click',()=>{slots[index]={mainSlot:i+1};picker.replaceChildren();draw();});choices.append(b);}for(const asset of assets){const b=node('button',undefined,'listing-image'),thumb=node('img');b.type='button';thumb.src=asset.url;thumb.alt='商品素材';b.append(thumb,node('span',asset.label || '商品素材'));b.addEventListener('click',()=>{slots[index]={path:asset.path};picker.replaceChildren();draw();});choices.append(b);}picker.append(choices);});row.append(choose);grid.append(row);});body.append(grid);}
        const prepare=node('button','生成详情图替换方案','quiet');prepare.type='button';prepare.addEventListener('click',async()=>{prepare.disabled=true;note.textContent='正在准备详情图方案…';try{const value=await api('/api/product-detail-plans/prepare',{product_id:String(selected.id),slots});review(value.change);note.textContent='方案已准备，请查看前后图片。';}catch(error){note.textContent=error.message;}finally{prepare.disabled=false;}});draw();footer.append(prepare);note.textContent='';
      }catch(error){note.textContent=error.message;load.disabled=false;}});box.insertBefore(load,body);
      const saved=node('button','查看已有详情图替换方案','quiet');saved.type='button';saved.addEventListener('click',async()=>{try{const value=await api('/api/product-detail-plans');const rows=(value.changes || []).filter(row=>String(row.productId)===String(selected.id));result.replaceChildren();if(!rows.length){result.append(node('p','这条链接还没有详情图替换方案。'));return;}for(const row of rows){const b=node('button',`查看 ${stamp(row.createdAt)} 的方案`,'quiet');b.type='button';b.addEventListener('click',()=>review(row));result.append(b);}}catch(error){note.textContent=error.message;}});box.append(saved);
    }
    function show(result) {
      const choices=result.listings || [], selected=result.selected;navigation.hidden=!choices.length;refresh.hidden=!choices.length;
      if(!choices.length){output.replaceChildren(node('p','这款商品暂未关联国际站链接。','muted'));return;}
      if(!select.children.length) {
        choices.forEach((row,index)=>{const name=(row.title || '').trim();const opt=node('option',`链接 ${index+1} · ${row.id}${name ? ' · '+name.slice(0,55) : ''}`);opt.value=row.id;select.append(opt);});
        select.value=selected.id;listingId=selected.id;
      }
      const choice=choices.find(item=>item.id===selected.id);open.href=choice?.url || '#';open.hidden=!choice?.url;
      output.replaceChildren();
      if(selected.state!=='ready') {
        output.append(node('p',selected.error || '国际站数据暂时无法读取。','inline-error'));
        if(selected.local?.title)output.append(node('p',`本地记录的标题：${selected.local.title}`,'listing-local-title'));
        if(selected.local?.main_images?.length)showImages(output,'本地已登记主图',selected.local.main_images,'主图');
        return;
      }
      const live=selected.platform, cmp=selected.comparison || {};
      const status={'approved':'已审核','pending':'审核中','modified':'修改审核中','published':'已发布'}[live.status] || live.status || '状态未返回';
      output.append(node('p',`平台读取 ${stamp(live.observed_at)} · ${status}${live.display==='Y'?' · 展示中':live.display==='N'?' · 未展示':''}`,'listing-meta'));
      const title=node('div',undefined,'listing-title'),translated=live.title_zh || {};
      title.append(node('h3','平台标题 · 中文'),node('p',translated.text || (translated.state==='translating'?'正在翻译标题…':translated.state==='error'?'中文翻译暂未完成，可刷新重试。':'暂无中文翻译。')),node('h3','英文原文'),node('p',live.title || '平台未返回标题'),node('small',`标题${labels[cmp.title] || ''}`));
      if(cmp.title==='different' && selected.local.title)title.append(node('p',`本地标题：${selected.local.title}`,'listing-local-title'));
      output.append(title);
      const checks=node('div',undefined,'listing-checks');
      for(const [name,key] of [['主图','main_images'],['详情图','detail_images']])checks.append(node('span',`${name}：${labels[cmp[key]] || '未比较'}`,`listing-check ${cmp[key] || ''}`));
      output.append(checks);showImages(output,'平台主图',live.main_images || [],'主图');showImages(output,'平台详情图',live.detail_images || [],'详情图');
      galleryEditor(output, selected);
      detailEditor(output, selected);
      detailReplacement(output, selected);
      if(cmp.main_images==='different' && selected.local.main_images?.length) {const more=node('details');more.append(node('summary','对照本地记录的主图'));showImages(more,'本地主图',selected.local.main_images,'主图');output.append(more);}
      if(cmp.detail_images==='different' && selected.local.detail_images?.length) {const more=node('details');more.append(node('summary','对照本地记录的详情图'));showImages(more,'本地详情图',selected.local.detail_images,'详情图');output.append(more);}
      if(live.company_images?.length){const more=node('details',undefined,'listing-company');more.append(node('summary',`工厂与包装图片 · ${live.company_images.length} 张`));showImages(more,'平台工厂图片',live.company_images,'工厂图');output.append(more);}
    }
    async function load(force=false,quiet=false) {
      clearTimeout(translationTimer);const request=++serial;if(!quiet)output.replaceChildren(node('p','正在读取国际站商品…','muted'));refresh.disabled=true;
      try {
        const params=new URLSearchParams({object_id:object.id});if(listingId)params.set('listing_id',listingId);if(force)params.set('refresh','1');
        const result=await api('/api/desk/product-review?'+params);if(request!==serial)return;show(result);
        if(result.selected?.platform?.title_zh?.state==='translating') {
          const retry=()=>{if(card.isConnected===false)return;if(card.querySelector('.gallery-reorder')?.open || card.querySelector('.detail-reorder')?.open || card.querySelector('.detail-replace')?.open){translationTimer=setTimeout(retry,6000);return;}load(false,true);};
          translationTimer=setTimeout(retry,6000);
        }
        if(result.selected && !prepared){const edit=node('details',undefined,'listing-edit');edit.append(node('summary','查看或准备标题修改'));titleDraft(edit,select);card.append(edit);prepared=true;}
      } catch(error){if(request===serial)output.replaceChildren(node('p',error.message,'inline-error'));}
      finally{if(request===serial)refresh.disabled=false;}
    }
    refresh.addEventListener('click',()=>load(true));select.addEventListener('change',()=>{listingId=select.value;load();});
    load();return card;
  };
})();
