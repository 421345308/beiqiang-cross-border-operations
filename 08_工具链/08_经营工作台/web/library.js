(() => {
  const nav = document.querySelector('nav');
  const link = document.createElement('a');
  link.href = '#/library'; link.dataset.nav = 'library'; link.textContent = '▣ 客户资料包'; nav.append(link);
  let generation = 0;
  const element = (tag, text) => { const e = document.createElement(tag); if (text) e.textContent = text; return e; };
  async function request(url, body, token) {
    const response = await fetch(url, body ? {method:'POST', headers:{'Content-Type':'application/json','X-Workbench-Token':token}, body:JSON.stringify(body)} : {});
    const value = await response.json();
    if (!response.ok) throw Error(value.error || '操作未完成，请重试');
    return value;
  }
  async function render() {
    if (!location.hash.startsWith('#/library')) return;
    const ticket = ++generation;
    const page = document.getElementById('page');
    document.getElementById('page-name').textContent = '客户资料包';
    page.replaceChildren(element('p', '正在读取资料包…'));
    try {
      const [data, resources, candidates] = await Promise.all([request('/api/desk/bootstrap'), request('/api/library'), request('/api/library/candidates')]);
      if (ticket !== generation || !location.hash.startsWith('#/library')) return;
      const customers = data.objects.filter(o => o.kind === 'customer' || o.kind === 'prospect');
      const selected = new URLSearchParams(location.hash.split('?')[1] || '').get('customer') || '';
      const filter = element('select'); filter.setAttribute('aria-label','查看客户资料');
      filter.add(new Option('全部资料','')); filter.add(new Option('仅共用资料','shared'));
      for (const o of customers) filter.add(new Option(o.title,o.id));
      if ([...filter.options].some(o => o.value === selected)) filter.value = selected;
      const search = element('input'); search.placeholder = '查找资料名称'; search.setAttribute('aria-label','查找资料名称');
      const list = element('div'), editor = element('div'), feedback = element('p'); feedback.setAttribute('role','status');
      page.replaceChildren(element('h1','客户资料包'),element('p','整理准备发给买家的材料。每份文件登记一次，可关联多个客户；没有关联客户的材料作为共用资料。这里不会自动发送。'),filter,search,feedback,list,editor);
      function form(item) {
        editor.replaceChildren();
        const f = element('form'), title = element('input'), path = element('input');
        title.value = item?.title || ''; title.placeholder = '资料名称'; title.maxLength = 160; title.setAttribute('aria-label','资料名称'); title.required = true;
        path.placeholder = '工作区内原文件路径'; path.setAttribute('aria-label','原文件路径'); path.value = item?.path || ''; path.style.width = '100%'; path.readOnly = !!item;
        const picker = element('select'); picker.setAttribute('aria-label','选择已有材料'); picker.add(new Option('选择已有 PDF、图片或文档',''));
        for (const file of candidates.items) picker.add(new Option(file.name,file.path));
        picker.onchange = () => {path.value=picker.value; if(!title.value) title.value=picker.selectedOptions[0].textContent;};
        f.append(element('h2',item ? '编辑资料' : '关联原资料'));
        const status=element('p'); status.setAttribute('role','status');
        if (!item) {
          const keyword=element('input'), find=element('button'); keyword.placeholder='输入款号或资料名称，例如 BQ001'; keyword.setAttribute('aria-label','搜索已有材料'); find.textContent='查找已有材料'; find.type='button';
          find.onclick=async()=>{find.disabled=true;try {const result=await request('/api/library/candidates?q='+encodeURIComponent(keyword.value.trim())); picker.replaceChildren(new Option('选择已有 PDF、图片或文档',''));for(const file of result.items)picker.add(new Option(file.name,file.path));status.textContent=result.items.length ? `找到 ${result.items.length} 份材料，请选择。` : '没有找到，试试其他款号或资料名称。';} catch(error){status.textContent=error.message;} finally{find.disabled=false;}};
          const advanced=element('details'); advanced.append(element('summary','手动指定其他文件'),path);
          f.append(keyword,find,picker,advanced);
        }
        f.append(title,element('p','关联客户（可勾选多位；全部不选即共用资料）'));
        const choices=[];
        for (const customer of customers) {
          const label=element('label'), checkbox=element('input'); checkbox.type='checkbox'; checkbox.value=customer.id;
          checkbox.checked=item ? item.object_ids.includes(customer.id) : filter.value===customer.id;
          label.append(checkbox,document.createTextNode(customer.title)); label.style.display='block'; f.append(label); choices.push(checkbox);
        }
        const unknown = (item?.object_ids || []).filter(id => !customers.some(o=>o.id===id));
        if (unknown.length) f.append(element('p','此资料还关联其他业务对象，保存时会保留。'));
        const save=element('button',item?'保存修改':'关联原资料'), cancel=element('button','取消');
        save.type='submit'; cancel.type='button'; cancel.onclick=()=>editor.replaceChildren(); status.setAttribute('role','status'); f.append(save,cancel,status); editor.append(f);
        f.onsubmit=async event=>{
          event.preventDefault(); save.disabled=true;
          try {
            if(!path.value.trim()) throw Error('请先选择一份已有材料。');
            const body={title:title.value,path:path.value,object_ids:[...unknown,...choices.filter(c=>c.checked).map(c=>c.value)]};
            if(item) body.id=item.id;
            const result=await request(item?'/api/library/update':'/api/library',body,data.csrf_token);
            if(ticket!==generation || !location.hash.startsWith('#/library'))return;
            if(item) resources.items=resources.items.map(r=>r.id===item.id?result:r); else resources.items.unshift(result);
            editor.replaceChildren(); feedback.textContent=item?'资料已保存':'资料已关联'; draw();
          } catch(error) {status.textContent=error.message;} finally {save.disabled=false;}
        };
      }
      function draw() {
        list.replaceChildren();
        const query=search.value.trim().toLowerCase();
        const shown=resources.items.filter(r=>(!filter.value || (filter.value==='shared' ? !r.object_ids.length : !r.object_ids.length || r.object_ids.includes(filter.value))) && r.title.toLowerCase().includes(query));
        const groups=filter.value && filter.value!=='shared' ? [['该客户资料',shown.filter(r=>r.object_ids.includes(filter.value))],['共用资料',shown.filter(r=>!r.object_ids.length)]] : [['资料列表',shown]];
        for (const [label,items] of groups) {
          list.append(element('h2',`${label}（${items.length}）`));
          if(!items.length) list.append(element('p','暂无资料，可关联已有文件。'));
          for(const item of items) {
            const row=element('article'), a=element('a',item.title); a.href='/api/library/file?id='+encodeURIComponent(item.id); a.target='_blank'; a.rel='noopener';
            row.className='card'; row.append(a,element('p',item.object_ids.length ? '关联：'+item.object_ids.map(id=>data.objects.find(o=>o.id===id)?.title || '原关联对象').join('、') : '共用资料'));
            const edit=element('button','编辑名称和客户'), remove=element('button','移除记录'); edit.type=remove.type='button'; edit.onclick=()=>form(item);
            remove.onclick=async()=>{
              if(!window.confirm(`移除“${item.title}”的资料包记录？原始文件会保留；所有客户关联将一并移除。`))return;
              remove.disabled=true;
              try {await request('/api/library/remove',{id:item.id},data.csrf_token); if(ticket!==generation || !location.hash.startsWith('#/library'))return; resources.items=resources.items.filter(r=>r.id!==item.id); editor.replaceChildren(); feedback.textContent='记录已移除，原始文件保留'; draw();}
              catch(error){feedback.textContent=error.message;remove.disabled=false;}
            };
            row.append(edit,remove); list.append(row);
          }
        }
      }
      filter.onchange=()=>{editor.replaceChildren(); feedback.textContent=''; history.replaceState(null,'','#/library'+(filter.value?'?customer='+encodeURIComponent(filter.value):'')); draw();};
      search.oninput=draw;
      const add=element('button','关联原资料'); add.type='button'; add.onclick=()=>form(); page.insertBefore(add,list); draw();
    } catch(error) {if(ticket===generation && location.hash.startsWith('#/library'))page.replaceChildren(element('p','读取资料包失败：'+error.message));}
  }
  window.renderCustomerLibrary=render;
})();
