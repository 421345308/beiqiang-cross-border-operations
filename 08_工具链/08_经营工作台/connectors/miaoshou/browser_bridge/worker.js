'use strict';
const BASE = 'http://127.0.0.1:8766/api/desk/miaoshou-bridge/';
let busy = false;
async function post(path, body, token) {
  const r = await fetch(BASE + path, {method: 'POST', headers: {'Content-Type': 'application/json', ...(token ? {Authorization: `Bearer ${token}`} : {})}, body: JSON.stringify(body), cache: 'no-store'});
  if (!r.ok) throw new Error('bridge_failed');
  return r.json();
}
async function pair(code) {
  if (typeof code !== 'string' || !/^[A-Za-z0-9_-]{40,60}$/.test(code)) throw new Error('pairing_failed');
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  if (!tab?.id || !tab.url?.startsWith('https://v2-dd.chengji-inc.com/')) throw new Error('pairing_failed');
  const identity = await chrome.tabs.sendMessage(tab.id, {type: 'identity'});
  if (!identity?.shopId) throw new Error('pairing_failed');
  const result = await post('pair', {code, shop_id: identity.shopId});
  if (typeof result.token !== 'string') throw new Error('pairing_failed');
  await chrome.storage.session.set({bridge: {token: result.token, tabId: tab.id}});
}
async function tick(sender) {
  if (busy || !sender.tab?.id || sender.url?.startsWith('https://v2-dd.chengji-inc.com/') !== true) return;
  const {bridge} = await chrome.storage.session.get('bridge');
  if (!bridge || sender.tab.id !== bridge.tabId) return;
  busy = true;
  try {
    const {task} = await post('poll', {}, bridge.token);
    if (!task) return;
    const payload = await chrome.tabs.sendMessage(bridge.tabId, {type: 'execute', job: task});
    await post('complete', {task_id: task.task_id, payload}, bridge.token);
  } catch (_) { /* No credentials or vendor responses are logged. */ }
  finally { busy = false; }
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) return;
  if (message?.type === 'pair' && !sender.tab && sender.url === chrome.runtime.getURL('popup.html')) {
    pair(message.code).then(() => sendResponse({ok: true}), () => sendResponse({ok: false}));
    return true;
  }
  if (message?.type === 'tick') tick(sender);
});
