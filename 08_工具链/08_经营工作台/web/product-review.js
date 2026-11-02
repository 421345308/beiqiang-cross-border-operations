'use strict';
(() => {
  const node = (tag, text, cls) => { const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e; };
  const roles={'Detail shot':'细节图','Scene image':'场景图','Product dimensions':'产品尺寸','Customization capabilities':'定制能力','Packaging & shipping specifications':'包装与运输','Competitive advantages':'工厂优势','Production workflow':'生产流程','Company overview':'工厂介绍'};
  const labels={same:'与本地记录一致',different:'与本地记录不同',not_recorded:'本地尚未登记',unavailable:'平台未返回'};
  const stamp=value=>{const date=new Date(value);return Number.isNaN(date.getTime())?'时间未知':date.toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});};
  window.mountProductReview = (host, object, api, {preview, titleDraft}) => {
    const card=node('section',undefined,'card listing-review');
    const head=node('div',undefined,'listing-review-head'),intro=node('div');
    intro.append(node('h2','国际站商品检查'),node('p','逐条查看平台上的标题、主图与详情图。'));
    const refresh=node('button','刷新平台数据','quiet');refresh.type='button';head.append(intro,refresh);card.append(head);
    const navigation=node('div',undefined,'listing-navigation'), select=node('select');select.setAttribute('aria-label','选择国际站商品链接');
    const open=node('a','打开国际站商品 ↗');open.target='_blank';open.rel='noopener noreferrer';navigation.append(select,open);card.append(navigation);
    const output=node('div',undefined,'listing-output');card.append(output);host.append(card);
    let listingId='',serial=0,prepared=false,translationTimer=null;
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
      if(cmp.main_images==='different' && selected.local.main_images?.length) {const more=node('details');more.append(node('summary','对照本地记录的主图'));showImages(more,'本地主图',selected.local.main_images,'主图');output.append(more);}
      if(cmp.detail_images==='different' && selected.local.detail_images?.length) {const more=node('details');more.append(node('summary','对照本地记录的详情图'));showImages(more,'本地详情图',selected.local.detail_images,'详情图');output.append(more);}
      if(live.company_images?.length){const more=node('details',undefined,'listing-company');more.append(node('summary',`工厂与包装图片 · ${live.company_images.length} 张`));showImages(more,'平台工厂图片',live.company_images,'工厂图');output.append(more);}
    }
    async function load(force=false,quiet=false) {
      clearTimeout(translationTimer);const request=++serial;if(!quiet)output.replaceChildren(node('p','正在读取国际站商品…','muted'));refresh.disabled=true;
      try {
        const params=new URLSearchParams({object_id:object.id});if(listingId)params.set('listing_id',listingId);if(force)params.set('refresh','1');
        const result=await api('/api/desk/product-review?'+params);if(request!==serial)return;show(result);
        if(result.selected?.platform?.title_zh?.state==='translating')translationTimer=setTimeout(()=>{if(card.isConnected!==false)load(false,true);},6000);
        if(result.selected && !prepared){const edit=node('details',undefined,'listing-edit');edit.append(node('summary','查看或准备标题修改'));titleDraft(edit,select);card.append(edit);prepared=true;}
      } catch(error){if(request===serial)output.replaceChildren(node('p',error.message,'inline-error'));}
      finally{if(request===serial)refresh.disabled=false;}
    }
    refresh.addEventListener('click',()=>load(true));select.addEventListener('change',()=>{listingId=select.value;load();});
    load();return card;
  };
})();
