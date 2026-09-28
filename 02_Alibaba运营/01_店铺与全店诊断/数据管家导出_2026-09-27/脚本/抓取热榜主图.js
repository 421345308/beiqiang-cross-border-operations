// 通过 CDP 抓取数据管家「产品参谋 → 产品发现」热榜商品卡的主图与标题
const PW = "/Users/shepeiqiang/.workbuddy/binaries/node/workspace/node_modules/playwright";
const fs = require("fs");
const { chromium } = require(PW);

(async () => {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:9333");
  const ctx = browser.contexts()[0];
  const pages = ctx.pages();
  let page = pages.find(p => /adviser\/product/.test(p.url())) || pages[0];
  console.log("使用页面:", page.url().slice(0, 110));

  if (!/adviser\/product/.test(page.url())) {
    await page.goto("https://data.alibaba.com/adviser/product?key=0", { waitUntil: "domcontentloaded", timeout: 60000 });
  }
  await page.bringToFront();
  await new Promise(r => setTimeout(r, 6000));

  // 尝试点「产品发现」标签
  for (const label of ["产品发现", "款式分析", "热品榜"]) {
    try {
      const t = page.locator(`text=${label}`).first();
      if (await t.count()) { await t.click({ timeout: 4000 }); console.log("已点击标签:", label); await new Promise(r => setTimeout(r, 5000)); break; }
    } catch (e) { }
  }

  const data = await page.evaluate(() => {
    const boot = {};
    const imgs = [];
    document.querySelectorAll("img").forEach(im => {
      const src = im.currentSrc || im.src || "";
      if (!/alicdn|alibaba/.test(src)) return;
      if ((im.naturalWidth || 0) < 100) return;
      // 向上找卡片容器，取其中的文本
      let el = im, txt = "";
      for (let i = 0; i < 6 && el; i++) {
        el = el.parentElement;
        if (el && (el.innerText || "").trim().length > 25) { txt = (el.innerText || "").trim(); break; }
      }
      imgs.push({ src, w: im.naturalWidth, h: im.naturalHeight, card: txt.slice(0, 220).replace(/\s+/g, " ") });
    });
    // 去重
    const seen = new Set(); const uniq = [];
    for (const x of imgs) { if (!seen.has(x.src)) { seen.add(x.src); uniq.push(x); } }
    return { title: document.title, url: location.href, count: uniq.length, items: uniq.slice(0, 60) };
  });

  fs.writeFileSync("/Users/shepeiqiang/WorkBuddy/2026-09-25-09-28-49/beiqiang_体检/热榜_主图清单.json",
    JSON.stringify(data, null, 1));
  console.log("页面标题:", data.title);
  console.log("抓到图片数:", data.count);
  console.log(JSON.stringify(data.items.slice(0, 12), null, 1));
  process.exit(0);
})().catch(e => { console.error("失败:", e.message); process.exit(1); });
