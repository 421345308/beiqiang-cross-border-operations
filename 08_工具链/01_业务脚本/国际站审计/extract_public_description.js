(() => {
  const R = {
    url: location.href,
    title: document.title,
    blockDetected: '',
    template: '',
    gallery: { slideCount: 0, slideSrcs: [], thumbCount: 0 },
    desc: { headingFound: false, reportAbuse: false, layoutFound: false, container: '', iframeFound: false, iframeReady: false, iframeSrc: '', imgTotal: 0, imgLoaded: 0, srcs: [], texts: [], textSample: '', blank: null }
  };

  const bodyText = (document.body ? document.body.innerText : '').slice(0, 4000);
  const low = bodyText.toLowerCase();
  if (/captcha|verify you are human|unusual traffic|security check/i.test(low)) R.blockDetected = 'captcha';
  else if (/not available in your|unavailable in your region|access denied/i.test(low)) R.blockDetected = 'region-block';
  else if (/sign in to view|log in to see|login required|please sign in/i.test(low)) R.blockDetected = 'login-wall';

  const scrollY = window.scrollY;

  // ---- Main gallery (top of page) ----
  const slides = Array.from(document.querySelectorAll('img')).filter(i => {
    const r = i.getBoundingClientRect();
    return (r.top + scrollY) < 800 && r.width >= 300;
  });
  R.gallery.slideCount = slides.length;
  R.gallery.slideSrcs = slides.map(i => i.currentSrc || i.src || '').slice(0, 12);
  const thumbs = Array.from(document.querySelectorAll('img')).filter(i => {
    const r = i.getBoundingClientRect();
    const y = r.top + scrollY;
    return y >= 350 && y <= 650 && r.width >= 40 && r.width < 70;
  });
  R.gallery.thumbCount = thumbs.length;

  // ---- Description section ----
  const h2 = document.querySelector('#more-detail');
  R.desc.headingFound = !!h2 && /product descriptions from the supplier/i.test(h2.textContent || '');
  R.desc.reportAbuse = !!document.querySelector('.module_report') || /report abuse/i.test(bodyText + (document.body ? document.body.innerText.slice(-1500) : ''));
  R.desc.layoutFound = !!document.querySelector('#description-layout, .module_description, .description-layout, .module-structure-description');

  const f = Array.from(document.querySelectorAll('iframe')).find(x => (x.src || '').includes('descIframe'));
  if (f) {
    R.template = 'A-iframe';
    R.desc.iframeFound = true;
    R.desc.iframeSrc = f.src.slice(0, 140);
    R.desc.iframeY = Math.round(f.getBoundingClientRect().top + scrollY);
    let doc = null;
    try { doc = f.contentDocument; } catch (e) { R.desc.iframeReady = 'blocked'; }
    if (doc && doc.body) {
      R.desc.iframeReady = true;
      const dw = doc.defaultView;
      if (dw && doc.body.scrollHeight) dw.scrollTo(0, doc.body.scrollHeight);
      const imgs = Array.from(doc.images);
      R.desc.imgTotal = imgs.length;
      R.desc.imgLoaded = imgs.filter(i => i.complete && i.naturalWidth > 0).length;
      R.desc.srcs = imgs.map(i => i.currentSrc || i.src || i.getAttribute('data-src') || i.getAttribute('data-lazy-src') || '').slice(0, 10);
      imgs.forEach(i => {
        if (!(i.complete && i.naturalWidth > 0)) {
          i.loading = 'eager';
          const ds = i.getAttribute('data-src') || i.getAttribute('data-lazy-src');
          if (ds && ds !== i.src) i.src = ds;
        }
      });
      const seen = new Set(); const uniq = [];
      for (const p of doc.querySelectorAll('p, h1, h2, h3, h4, h5, li, td, span, div')) {
        if (p.childElementCount > 8) continue;
        const t = p.innerText ? p.innerText.trim() : '';
        if (t.length >= 8 && t.length <= 400 && !seen.has(t)) { seen.add(t); uniq.push(t); if (uniq.length >= 10) break; }
      }
      R.desc.texts = uniq.slice(0, 3).map(t => t.slice(0, 80));
      R.desc.textSample = (doc.body.innerText || '').trim().slice(0, 150);
      R.desc.blank = R.desc.imgTotal === 0 && uniq.length === 0;
    }
  } else {
    // Template B: inline description module
    let headEl = null;
    for (const el of document.querySelectorAll('div, span, h1, h2, h3, h4, h5, p')) {
      if (el.childElementCount > 10) continue;
      const own = Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
      if (own === 'Product descriptions from the supplier') { headEl = el; break; }
    }
    if (headEl) {
      R.template = 'B-inline';
      R.desc.headingFound = true;
      let container = headEl.closest('.module-structure-description') || headEl.parentElement.parentElement;
      R.desc.container = container.tagName + '#' + container.id + '.' + (typeof container.className === 'string' ? container.className.slice(0, 60) : '');
      const imgs = Array.from(container.querySelectorAll('img'));
      R.desc.imgTotal = imgs.length;
      R.desc.imgLoaded = imgs.filter(i => i.complete && i.naturalWidth > 0).length;
      R.desc.srcs = imgs.map(i => i.currentSrc || i.src || i.getAttribute('data-src') || i.getAttribute('data-lazy-src') || '').slice(0, 10);
      const seen = new Set(); const uniq = [];
      for (const p of container.querySelectorAll('p, h1, h2, h3, h4, h5, li, td, span, div')) {
        if (p.childElementCount > 8) continue;
        const t = p.innerText ? p.innerText.trim() : '';
        if (t.length >= 8 && t.length <= 400 && !seen.has(t)) { seen.add(t); uniq.push(t); if (uniq.length >= 10) break; }
      }
      R.desc.texts = uniq.slice(0, 3).map(t => t.slice(0, 80));
      R.desc.textSample = (container.innerText || '').trim().slice(0, 150);
      R.desc.blank = R.desc.imgTotal === 0 && uniq.length === 0;
    } else {
      const cand = document.querySelector('#description-layout, .module_description, [class*="detail-description"], [id*="description"]');
      if (cand) {
        R.template = 'B-fallback';
        R.desc.container = cand.tagName + '#' + cand.id + '.' + (typeof cand.className === 'string' ? cand.className.slice(0, 60) : '');
        const imgs = Array.from(cand.querySelectorAll('img'));
        R.desc.imgTotal = imgs.length;
        R.desc.imgLoaded = imgs.filter(i => i.complete && i.naturalWidth > 0).length;
        R.desc.srcs = imgs.map(i => i.currentSrc || i.src || i.getAttribute('data-src') || i.getAttribute('data-lazy-src') || '').slice(0, 10);
        R.desc.blank = R.desc.imgTotal === 0;
      } else {
        R.desc.blank = null;
      }
    }
  }

  return R;
})()
