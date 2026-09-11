(() => {
  const result = {
    url: location.href,
    title: document.title,
    blockDetected: '',
    descFound: false,
    descTitleText: '',
    descContainer: '',
    descImgTotal: 0,
    descImgLoaded: 0,
    descSrcs: [],
    descTexts: [],
    descBlank: null,
    descIframe: false,
    mainCarouselCount: 0,
    mainBigCount: 0,
    mainCarouselSrcs: []
  };

  const bodyText = (document.body ? document.body.innerText : '').slice(0, 4000);
  const lowBody = bodyText.toLowerCase();
  if (/captcha|verify you are human|unusual traffic|security check/i.test(lowBody)) result.blockDetected = 'captcha';
  else if (/not available in your|unavailable in your region|access denied/i.test(lowBody)) result.blockDetected = 'region-block';
  else if (/sign in to view|log in to see|login required|please sign in/i.test(lowBody)) result.blockDetected = 'login-wall';

  // ---- Description section ----
  const allEls = document.querySelectorAll('div, section, h1, h2, h3, h4, h5, span, p');
  let heading = null;
  for (const el of allEls) {
    if (el.childElementCount > 15) continue;
    let own = '';
    for (const c of el.childNodes) if (c.nodeType === 3) own += c.textContent;
    own = own.trim();
    if (own && /product descriptions from the supplier/i.test(own)) { heading = el; break; }
  }
  if (!heading) {
    for (const el of allEls) {
      if (el.childElementCount > 15) continue;
      const t = (el.textContent || '').trim();
      if (t.length <= 150 && /product descriptions from the supplier/i.test(t)) { heading = el; break; }
    }
  }

  if (heading) {
    result.descFound = true;
    result.descTitleText = heading.textContent.trim().slice(0, 80);
    let container = heading;
    let best = heading;
    for (let i = 0; i < 5; i++) {
      if (!container.parentElement) break;
      container = container.parentElement;
      best = container;
      const imgs = container.querySelectorAll('img').length;
      const innerLen = container.innerText ? container.innerText.trim().length : 0;
      if (imgs >= 1 && innerLen > 50) break;
      if (imgs >= 3) break;
    }
    const imgs = Array.from(best.querySelectorAll('img'));
    result.descContainer = best.tagName + (best.id ? '#' + best.id : '') + (typeof best.className === 'string' && best.className ? '.' + best.className.split(' ').slice(0, 3).join('.') : '');
    result.descImgTotal = imgs.length;
    result.descImgLoaded = imgs.filter(i => i.complete && i.naturalWidth > 0).length;
    result.descSrcs = imgs.map(i => i.currentSrc || i.src || i.getAttribute('data-src') || i.getAttribute('data-lazy-src') || '').slice(0, 10);
    result.descIframe = best.querySelectorAll('iframe').length > 0;

    const seen = new Set();
    const uniq = [];
    for (const p of best.querySelectorAll('p, h1, h2, h3, h4, h5, li, td, span, div')) {
      if (p.childElementCount > 8) continue;
      const t = p.innerText ? p.innerText.trim() : '';
      if (t.length >= 8 && t.length <= 400 && !seen.has(t)) { seen.add(t); uniq.push(t); if (uniq.length >= 12) break; }
    }
    result.descTexts = uniq.slice(0, 3).map(t => t.slice(0, 80));
    result.descBlank = (result.descImgTotal === 0 && uniq.length === 0);
  } else {
    const cands = Array.from(document.querySelectorAll('[class*="description" i], [id*="description" i], [class*="desc-wrap" i]')).slice(0, 8);
    result.fallbackCandidates = cands.map(c => ({ tag: c.tagName, id: c.id, cls: (typeof c.className === 'string' ? c.className : '').slice(0, 100), imgCount: c.querySelectorAll('img').length }));
  }

  // ---- Main gallery (top of page) ----
  const scrollY = window.scrollY;
  const topImgs = Array.from(document.querySelectorAll('img')).filter(i => {
    const r = i.getBoundingClientRect();
    const absTop = r.top + scrollY;
    return absTop > -300 && absTop < 1000 && r.width > 45;
  });
  result.mainCarouselCount = topImgs.length;
  result.mainBigCount = topImgs.filter(i => i.getBoundingClientRect().width > 300).length;
  result.mainCarouselSrcs = topImgs.map(i => i.currentSrc || i.src || '').slice(0, 12);

  return result;
})()
