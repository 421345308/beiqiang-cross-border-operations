'use strict';
(() => {
  const node = (tag, text, cls) => { const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e; };
  const roles={'Detail shot':'细节图','Scene image':'场景图','Product dimensions':'产品尺寸','Customization capabilities':'定制能力','Packaging & shipping specifications':'包装与运输','Competitive advantages':'工厂优势','Production workflow':'生产流程','Company overview':'工厂介绍'};
  const labels={same:'与本地记录一致',different:'与本地记录不同',not_recorded:'本地尚未登记',unavailable:'平台未返回'};
  const stamp=value=>{const date=new Date(value);return Number.isNaN(date.getTime())?'时间未知':date.toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});};
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
      let order=[0,1,2,3,4,5];
      const box=node('details',undefined,'listing-edit gallery-reorder'), controls=node('div',undefined,'gallery-sort-grid'), result=node('div'), note=node('p');
      box.append(node('summary','调整现有主图顺序'),node('p','调整后先查看新顺序，确认后再提交国际站。'),controls,note);
      function renderReview(change) {
        result.replaceChildren(node('h4','主图调整方案'));
        for(const [title,urls] of [['修改前',change.diff?.before || []],['调整后',change.diff?.after || []]]) {
          const group=node('div');showImages(group,title,urls.map(url=>({url})),'主图');result.append(group);
        }
        const state=node('p'), actions=node('div');result.append(state,actions);
        const labels={'not-submitted':'尚未提交','outcome-unknown':'结果待回读','submitted':'已提交','pending':'审核中','verified':'正式回读通过','synced':'已同步','not-synced':'尚未同步','not-verified':'尚未验收'};
        const update=()=>{state.textContent=`提交：${labels[change.submission?.state] || change.submission?.state || '未提交'} · 平台：${labels[change.formal?.state] || change.formal?.state || '未验收'} · 本地：${labels[change.localSync?.state] || change.localSync?.state || '未同步'}`;};
        if(change.submission?.state==='not-submitted') {
          const submit=node('button','确认提交主图顺序','primary');submit.type='button';
          submit.addEventListener('click',async()=>{submit.disabled=true;try{const value=await api(`/api/product-gallery-changes/${encodeURIComponent(change.id)}/apply`,{confirmed:true,expected_version:change.version});change=value.change;note.textContent='已提交，请回读平台结果。';update();}catch(error){note.textContent=error.message;}});actions.append(submit);
        }
        const check=node('button','回读平台和本地结果','quiet');check.type='button';check.addEventListener('click',async()=>{check.disabled=true;try{const value=await api(`/api/product-gallery-changes/${encodeURIComponent(change.id)}/reconcile`,{});change=value.change;update();note.textContent='已读取最新状态。';}catch(error){note.textContent=error.message;}finally{check.disabled=false;}});actions.append(check);update();
      }
      function draw() {
        controls.replaceChildren();
        order.forEach((slot,index)=>{
          const row=node('div',undefined,'gallery-sort-item'), image=node('img'), moves=node('div',undefined,'gallery-sort-actions');image.src=original[slot].url;image.alt=`第 ${index+1} 张主图`;image.referrerPolicy='no-referrer';row.append(image,node('span',`第 ${index+1} 张`),moves);
          for(const [label,delta] of [['前移',-1],['后移',1]]) {const move=node('button',label,'quiet');move.type='button';move.disabled=index+delta<0 || index+delta>=order.length;move.addEventListener('click',()=>{[order[index],order[index+delta]]=[order[index+delta],order[index]];draw();});moves.append(move);}
          controls.append(row);
        });
      }
      const prepare=node('button','生成主图调整方案','quiet');prepare.type='button';prepare.addEventListener('click',async()=>{prepare.disabled=true;note.textContent='正在核对平台主图和图片银行，首次查询可能需要几分钟…';try{const value=await api('/api/product-gallery-changes/prepare',{product_id:String(selected.id),order:order.map(n=>n+1)});renderReview(value.change);note.textContent='方案已准备，请查看前后顺序。';}catch(error){note.textContent=error.message;}finally{prepare.disabled=false;}});
      const saved=node('button','查看已有主图方案','quiet');saved.type='button';saved.addEventListener('click',async()=>{try{const value=await api('/api/product-gallery-changes');const rows=(value.changes || []).filter(row=>String(row.productId)===String(selected.id));result.replaceChildren();if(!rows.length){result.append(node('p','这条链接还没有主图方案。'));return;}for(const row of rows){const open=node('button',`查看 ${stamp(row.createdAt)} 的方案`,'quiet');open.type='button';open.addEventListener('click',()=>renderReview(row));result.append(open);}}catch(error){note.textContent=error.message;}});
      const footer=node('div',undefined,'gallery-footer');footer.append(prepare,saved);box.append(footer,result);draw();parent.append(box);
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
          const retry=()=>{if(card.isConnected===false)return;if(card.querySelector('.gallery-reorder')?.open){translationTimer=setTimeout(retry,6000);return;}load(false,true);};
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
