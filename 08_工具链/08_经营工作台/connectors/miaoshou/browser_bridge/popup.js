'use strict';
document.getElementById('pair').addEventListener('click', async () => {
  const field = document.getElementById('code');
  const result = await chrome.runtime.sendMessage({type: 'pair', code: field.value.trim()}).catch(() => ({ok: false}));
  field.value = '';
  document.getElementById('status').textContent = result.ok ? '已配对；工作台将核验连接。' : '连接失败，请检查当前店铺、配对码及工作台。';
});
