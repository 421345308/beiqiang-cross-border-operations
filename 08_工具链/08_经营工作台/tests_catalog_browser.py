"""Isolated Chrome check of the product status cache and exact product link."""
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch

import tests_customer_browser as browser

DRIVER = r'''(() => {
const out=document.createElement('pre');out.id='revision-acceptance';out.dataset.state='running';document.body.append(out);
const wait=()=>new Promise(resolve=>setTimeout(resolve,50));
(async()=>{
  location.hash='/channels?view=alibaba';
  for(let i=0;i<300 && !document.querySelector('.channel-catalog');i++)await wait();
  const card=document.querySelector('.channel-catalog');if(!card)throw Error('catalog status missing');
  if(!card.textContent.includes('状态不同 1 条'))throw Error('exact status difference missing');
  if(!card.textContent.includes('未出现不等于下架'))throw Error('missing observation boundary');
  const open=[...card.querySelectorAll('button')].find(x=>x.textContent==='查看对应商品');if(!open)throw Error('product link missing');
  open.click();for(let i=0;i<300 && !location.hash.includes('/object/product%3ABQ009');i++)await wait();
  if(!location.hash.includes('/object/product%3ABQ009'))throw Error('product mapping incorrect');
  out.dataset.state='pass';out.textContent='Synthetic official snapshot displayed with exact product link';
})().catch(error=>{out.dataset.state='fail';out.textContent=String(error.stack||error);});
})();'''


class CatalogBrowserTests(browser.CustomerBrowserTests):
    def test_stale_forms_return_409_and_preserve_input_and_latest_values(self):
        previous_driver=browser.DRIVER
        fixture_class=browser.tests_desk_http.DeskHTTPTests
        original_setup=fixture_class.setUp
        def setup_with_catalog(fixture):
            original_setup(fixture)
            source=fixture.root/'catalog-fixture.json'
            source.write_text(json.dumps({'complete':True,'collected_at_utc':datetime.now(timezone.utc).isoformat(),
                'platform_total':1,'pages':1,'records':[{'platform_id':'1601','status':'tbd','display':'N'}]}),encoding='utf8')
            fixture.app.catalog_monitor.seed(source)
        try:
            browser.DRIVER=DRIVER
            with patch.object(fixture_class,'setUp',setup_with_catalog):
                super().test_stale_forms_return_409_and_preserve_input_and_latest_values()
        finally:browser.DRIVER=previous_driver


if __name__=='__main__':unittest.main()
