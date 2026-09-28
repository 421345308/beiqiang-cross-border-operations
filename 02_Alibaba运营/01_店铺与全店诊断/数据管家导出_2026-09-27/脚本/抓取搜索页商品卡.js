// 抓 alibaba.com 公开搜索页商品卡主图（用已登录真实 Chrome），用于验证「热榜首图标 OEM/ODM」的普遍性
const PW = "/Users/shepeiqiang/.workbuddy/binaries/node/workspace/node_modules/playwright";
const fs = require("fs");
const { chromium } = require(PW);

const KEY = process.argv[2] || "walking shoes";
const URL = "https://www.alibaba.com/trade/search?SearchText=" + encodeURIComponent(KEY);

(async () => {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:9333");
  const ctx = browser.contexts()[0];
  const page = await ctx.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  console.log("打开:", URL);
  await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 90000 });
  await new Promise(r => setTimeout(r, 8000));

  // 关闭可能的登录弹窗
  for (const t of ["Close", "关闭", "×"]) {
    try { const b = page.locator(`text=${t}`).first(); if (await b.count()) { await b.click({ timeout: 2000 }); } } catch (e) { }
  }

  for (let i = 0; i < 8; i++) { await page.mouse.wheel(0, 2400); await new Promise(r => setTimeout(r, 1600)); }

  const data = await page.evaluate(() => {
    const imgs = [];
    document.querySelectorAll("img").forEach(im => {
      const src = im.currentSrc || im.src || "";
      if (!/alicdn/.test(src)) return;
      const w = im.naturalWidth || 0, h = im.naturalHeight || 0;
      if (w < 150) return;
      let el = im, txt = "";
      for (let i = 0; i < 8 && el; i++) {
        el = el.parentElement;
        if (el && (el.innerText || "").trim().length > 30) { txt = (el.innerText || "").trim(); break; }
      }
      imgs.push({ src, w, h, card: txt.slice(0, 260).replace(/\s+/g, " ") });
    });
    const seen = new Set(); const uniq = [];
    for (const x of imgs) { const k = x.src.replace(/_\d+x\d+\.(png|jpg|jpeg|webp)$/, ""); if (!seen.has(k)) { seen.add(k); uniq.push({ ...x, src: k }); } }
    return { url: location.href, title: document.title, count: uniq.length, items: uniq.slice(0, 80) };
  });

  fs.writeFileSync("/Users/shepeiqiang/WorkBuddy/2026-09-25-09-28-49/beiqiang_体检/搜索页_商品卡.json", JSON.stringify(data, null, 1));
  console.log("页面标题:", data.title);
  console.log("抓到唯一图片:", data.count);
  console.log(JSON.stringify(data.items.slice(0, 8).map(x => ({ w: x.w, card: x.card.slice(0, 80) })), null, 1));
  process.exit(0);
})().catch(e => { console.error("失败:", e.message); process.exit(1); });
