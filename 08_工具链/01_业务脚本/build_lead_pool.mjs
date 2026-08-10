import fs from 'node:fs/promises';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const outDir = '04_客户开发/01_线索与CRM/lead_pool_20260803';
await fs.mkdir(outDir, { recursive: true });

const rows = [
  ['Cassie White','JOE BROWNS LTD','Junior Buyer - Footwear','United Kingdom','Apollo','Verified - reveal needed','Retail footwear buyer','A','Not contacted','Personalized email','Footwear buyer at fashion retailer; verify category fit before outreach.'],
  ['Jana Peryer','Kingstown Associates','Buyer - Fashion & Footwear','United Kingdom','Apollo','Verified - reveal needed','Buyer / retailer','A','Not contacted','Personalized email','Confirm active footwear assortment.'],
  ['Catherine Painter','The BrandAlley Group','Head of Buying - Branded RTW, Footwear and Own Buy','United Kingdom','Apollo','Verified - reveal needed','Marketplace / retail buyer','A','Not contacted','Personalized email','Lead with sample and own-label support.'],
  ['Deeps Footwear','DEEPS FOOTWEAR','Business Owner','United Kingdom','Apollo','Verified - reveal needed','Independent shoe retailer','A','Not contacted','Owner email','Strong independent retail match.'],
  ['Katrina Owens','size?','Women\'s Footwear Assistant Buyer','United Kingdom','Apollo','Verified - reveal needed','Large footwear retailer','A','Not contacted','Buyer email','Use lightweight knit / wide-toe sample angle.'],
  ['Charlotte Drury','Charles Clinkard','Ladies Footwear & Handbag Buyer','United Kingdom','Apollo','Verified - reveal needed','Footwear retailer','A','Not contacted','Buyer email','Relevant footwear retail buyer.'],
  ['Chris Binns','size?','Mens and Womens Footwear Buyer','United Kingdom','Apollo','Verified - reveal needed','Large footwear retailer','A','Not contacted','Buyer email','Relevant for knit walking shoe range.'],
  ['Faisal Mahmood','FIESTA FOOTWEAR LIMITED','Owner / Director - Design & Development','United Kingdom','Apollo','Verified - reveal needed','Footwear brand / retailer','A','Not contacted','Owner email','OEM/ODM and design-development angle.'],
  ['Charlotte Herbert','ME+EM Ltd','Assistant Buyer - Wovens, Footwear and Bags','United Kingdom','Apollo','Verified - reveal needed','Fashion brand buyer','B','Not contacted','Buyer email','Confirm footwear breadth before sending.'],
  ['Elaine Bayliss','Trotters Childrenswear & Accessories Limited','Footwear and Hosiery Buyer - Branded and Private Label','United Kingdom','Apollo','Verified - reveal needed','Private-label buyer','B','Not contacted','Buyer email','Only pitch if children\'s / related footwear capability is confirmed.'],
  ['Mark Macdonald','END. CLOTHING LIMITED','Senior Menswear Buyer - Apparel, Footwear and Accessories','United Kingdom','Apollo','Verified - reveal needed','Retail buyer','B','Not contacted','Buyer email','Confirm casual footwear sourcing fit.'],
  ['','Elevate Your Sole','','United Kingdom','Public website','Public business email','Independent shoe shop chain','B','Not contacted','customerservices@elevateyoursole.co.uk','Comfort-led independent shoe chain in North Wales & Chester. Use a personalised buyer/sourcing enquiry, not a bulk send. Source: https://www.elevateyoursole.co.uk/pages/contact-us'],
  ['','Unitrends Footwear','','United States','Public website','Public business email','Footwear distributor','A','Not contacted','unitrendsfc@gmail.com','US footwear distributor with retailer network. First contact should request the sourcing or product-development contact. Source: https://www.unitrendsfc.com/contact'],
  ['','Alicante Footwear LLC','','United States','Public website','Contact form / phone','Footwear distributor','A','Not contacted','Official contact form; +1 832-802-0005','North American comfort-footwear distributor. Public site does not expose a readable email; use its official form or phone for a tailored partnership enquiry. Source: https://alicantefootwear.com/'],
  ['','Trenova Brands','','United States','Public website','Public business email','Footwear distributor','A','Not contacted','info@trenovabrands.com','Wholesale distributor for footwear/lifestyle brands. Request brand partnership or buying contact. Source: https://www.trenovabrands.com/'],
  ['','Walking Comfort','','United States','Public website','Contact form','Comfort shoe retailer','B','Not contacted','Official website contact form','Comfort shoe retail specialist with walking/sneaker assortment. Keep as manual tailored form contact; no public business email shown. Source: https://walkingcomfort.com/pages/contact'],
  ['','Consolidated Shoe Co.','','United States','Public website','Phone / customer service','Footwear wholesaler','A','Not contacted','+1 434-239-0391; customer service +1 800-368-7463','Wholesale footwear supplier with boutique range. Public contact page exposes telephone, not an email/form; first request the product-development or sourcing contact. Source: https://www.coshco.com/contact'],
  ['','Vanlly Shoes / Planet Shoes Warehouse','','United States','Public website','Find business contact','Footwear distributor','A','Not contacted','Find buyer/owner','East Coast footwear warehouse and distributor. Source: https://vanllyshoes.com/index.html'],
  ['','Comfort & Wide Shoes','','United States','Google / public website','Public business email','Independent comfort shoe retailer','B','Not contacted','comfortwideshoes@gmail.com','San Diego retailer specialising in wide and extra-wide shoes; good fit for a knit / wide-toe sample enquiry. Source: https://www.comfortwideshoes.com/ContactForm.htm'],
  ['','Cosyfeet / Foot Shop Limited','','United Kingdom','British Footwear Association','Public wholesale email','Comfort footwear brand / multi-channel retailer','A','Not contacted','wholesale@cosyfeet.com','UK multi-channel comfort-footwear business with independent stockists. Treat as a brand-partnership or OEM discussion, not a generic retail pitch. Source: https://britishfootwearassociation.co.uk/member/foot-shop-limited/'],
  ['','Shoephoric','','United Kingdom','Public business directory','Public business email','Independent shoe retailer','B','Not contacted','info@shoephoric.co.uk','Independent family footwear retailer with comfort-footwear positioning; first confirm adult casual assortment before sending. Source: https://booking.appointy.com/shoephoric/about'],
  ['','Shoe Sensation','','United States','Public vendor guide','Public buyer mailbox','Regional footwear retailer','A','Not contacted','buyers@shoesensation.com','Official vendor guide lists the buyer mailbox. Submit a concise supplier introduction and request sourcing requirements; do not send a consumer-style promotion. Source: https://www.shoesensation.com/media/wysiwyg/PDF/Shoe-Sensation-Vendor-Compliance-Guide-2026.pdf'],
  ['','SAS Shoes Buffalo','','United States','Google / public website','Public business email','Independent comfort shoe retailer','B','Not contacted','sasshoesbuffalo@gmail.com','Independently owned Buffalo comfort-shoe store with broad size/width range. Use a short store-buyer enquiry; do not imply medical benefits. Source: https://www.sasshoesbuffalo.com/contact-us'],
  ['','R.E. Lee Shoe Co.','','United States','Public website','Public business email','Independent comfort shoe retailer','B','Not contacted','releeshoe@gmail.com','Washington comfort-shoe retailer offering wide widths and deep toe boxes. First ask about adult casual/walking assortment and buying process. Source: https://www.releeshoeco.com/pages/about-us'],
  ['','The Shoe Hutch','','United States','Public website','Public business email','Independent comfort shoe retailer','B','Not contacted','shoehutch@gmail.com','Oregon independent comfort-casual retailer with walking shoes and wide widths; suitable for a personalised sample enquiry. Source: https://shoehutch.wordpress.com/'],
  ['','The Shoe Horn Comfort Shoe Store','','United States','Public website','Public business email','Independent comfort shoe retailer','B','Not contacted','shoehorn2410@gmail.com','Ohio comfort-shoe retailer with a walking/running assortment. First ask for the buyer/owner handling new casual footwear. Source: https://www.shoehorninc.com/running'],
  ['','Comforta Nieuwkoop BV','','Netherlands','Public website','Public business email','Footwear distributor / supply-chain partner','A','Not contacted','contact@comforta.nl','Dutch footwear specialist serving independent shoe retailers through to international fashion chains; request the buying or product-management contact. Source: https://comforta.nl/'],
  ['','Shaped4 / Gerla Products BV','','Netherlands','Public website','Public business email','B2B retailer / private-label owner','A','Not contacted','info@shaped4.nl','Dutch business selling comfortable footwear across the Netherlands, Belgium and Germany, with B2B registration and own private labels. Use the brand/private-label template. Source: https://shaped4.com/pages/over-ons'],
  ['','ComfortSchuh Handelsgesellschaft m.b.H.','','Germany','Public website','Public business email','Comfort footwear retailer','B','Not contacted','service@comfortschuh.de','German comfort-shoe retailer. Begin with a brief request for the buyer handling adult casual/walking footwear; do not treat service inbox as a bulk route. Source: https://www.comfortschuh.de/kontakt'],
  ['','Leading Fashions Ltd','','United Kingdom','Public website','Public business email','Footwear wholesaler / importer','A','Not contacted','Jerry@leadingfashions.co.uk','Manchester footwear wholesaler and importer supplying independent retailers with trainers and casual footwear; strong wholesale-fit lead. Source: https://www.leadingfashions.co.uk/'],
  ['','Bacup Shoe Direct Ltd','','United Kingdom','Public website','Public business email','Footwear distributor','A','Not contacted','sales@bacupshoedirect.co.uk','UK footwear distributor handling casual footwear, training shoes and EVA products. Request the buyer/product-development contact for adult knit walking styles. Source: https://www.bacupshoedirect.co.uk/'],
  ['','Distrimex bv','','Belgium','Public website','Public business email','Comfort footwear wholesaler','A','Not contacted','info@distrimex.be','Belgian specialist wholesale business for comfort footwear and slippers. Use a tailored distributor / product-range enquiry. Source: https://www.distrimex.be/en/'],
  ['','Morsø Sko Import A/S','','Denmark','Public website','Public business email','Footwear importer / wholesaler','A','Not contacted','import@morso-sko.dk','Danish and Scandinavian footwear importer/wholesaler where comfort is a stated range factor. Request catalog or buying contact for adult knit walking shoes. Source: https://morso-sko.dk/en/om-os/'],
  ['','Alsido Calzature','','Italy','Public website','Public business email','Footwear wholesaler','B','Not contacted','info@alsidocalzature.com','Italian B2B footwear wholesaler supplying retail points of sale across Europe. Ask for the category buyer for casual/walking footwear. Source: https://www.alsidocalzature.com/en/contact'],
  ['','Due D Calzature S.r.l','','Italy','Public website','Public business email','Footwear distributor','B','Not contacted','dueddiffusionecalzaturesrl@gmail.com','Italian B2B footwear distributor serving retailers with multi-size collections. First ask whether adult knit/walking shoes are under review. Source: https://duedcalzature.com/en'],
  ['','Marila Shoes','','Spain','Public website','Public business email','Footwear wholesaler','B','Not contacted','marila@marilashoes.com','Spanish wholesale footwear distributor with B2B portal. Use a short product-range enquiry and request the relevant buyer contact. Source: https://b2b.marilashoes.com/'],
  ['','HTV Solutions Ltd / Sourcly','','United Kingdom','Amazon/e-commerce website','Public business email','Amazon/eBay seller and footwear wholesaler','A','Not contacted','sales@htvsolutionsltd.com','UK footwear wholesaler with Amazon, eBay and wholesale routes; publicly seeks brand-direct and wholesale supply relationships. Use the brand/private-label or distributor version with a concise marketplace-supply angle. Source: https://htvretail.com/'],
  ['','Y Distributors','','United States','Public website','Contact form','Footwear distributor','B','Not contacted','Official website contact form','US distributor for multiple footwear brands supplying boutiques and retailers nationwide. Use a manual, specific form enquiry requesting the product/buying contact. Source: https://ydistributors.com/pages/about-us'],
  ['','Klub Nico / Ipanema, Inc.','','United States','Public company profile','Public business email','Footwear brand / private-label buyer','B','Not contacted','sales@klubnico.com','US women\'s footwear brand with wholesale and private-label activity; public profile states manufacture in China/Brazil. Use a tailored OEM/ODM enquiry around knit casual silhouettes only if their current assortment fit is confirmed. Source: https://www.linkedin.com/company/klub-nico'],
];

const wb = Workbook.create();
const dash = wb.worksheets.add('Dashboard');
const pool = wb.worksheets.add('Lead Pool');
const guide = wb.worksheets.add('Sourcing Plan');
const health = wb.worksheets.add('Outreach Health');
const templates = wb.worksheets.add('Email Templates');
const queue = wb.worksheets.add('Next Batch Queue');
for (const sh of [dash,pool,guide,health,templates,queue]) sh.showGridLines = false;

dash.mergeCells('A1:H1');
dash.getRange('A1').values = [['Beiqiang B2B Buyer Acquisition Tracker']];
dash.getRange('A1:H1').format = {fill:'#123047',font:{bold:true,color:'#FFFFFF',size:16},horizontalAlignment:'center'};
dash.getRange('A1:H1').format.rowHeight = 26;
dash.getRange('A3:B6').values = [['Metric','Value'],['Qualified leads','=COUNTA(\'Lead Pool\'!B2:B200)'],['Priority A','=COUNTIF(\'Lead Pool\'!H2:H200,"A")'],['Not contacted','=COUNTIF(\'Lead Pool\'!I2:I200,"Not contacted")']];
dash.getRange('A3:B3').format = {fill:'#1F5A7A',font:{bold:true,color:'#FFFFFF'}};
dash.getRange('A3:B6').format.borders = {preset:'all',style:'thin',color:'#D9E2F3'};
dash.getRange('A3:B6').format.columnWidth = 22;
dash.getRange('D3:G3').values = [['Channel','Target','Purpose','Status']];
dash.getRange('D4:G7').values = [
  ['Apollo / LinkedIn',120,'Named footwear buyers and founders','In progress'],
  ['Amazon brands',80,'Private-label / online seller prospects','Next'],
  ['TikTok Shop brands',50,'Visual-product and content-led sellers','Next'],
  ['Google Maps stores',100,'Independent retailers and regional chains','Next'],
];
dash.getRange('D3:G3').format = {fill:'#1F5A7A',font:{bold:true,color:'#FFFFFF'}};
dash.getRange('D3:G7').format.borders = {preset:'all',style:'thin',color:'#D9E2F3'};
dash.getRange('D:D').format.columnWidth = 28;
dash.getRange('E:E').format.columnWidth = 14;
dash.getRange('F:F').format.columnWidth = 38;
dash.getRange('G:G').format.columnWidth = 16;

const headers = ['Contact','Company','Job title','Market','Source','Email status','Buyer type','Priority','Outreach status','Next action','Qualification note'];
pool.getRange('A1:K1').values = [headers];
pool.getRange(`A2:K${rows.length+1}`).values = rows;
pool.getRange(`A1:K${rows.length+1}`).format.borders = {preset:'all',style:'thin',color:'#E5E7EB'};
pool.getRange('A1:K1').format = {fill:'#123047',font:{bold:true,color:'#FFFFFF'},wrapText:true};
pool.getRange(`A2:K${rows.length+1}`).format.wrapText = true;
pool.freezePanes.freezeRows(1);
pool.getRange('A:K').format.columnWidth = 18;
pool.getRange('C:C').format.columnWidth = 28;
pool.getRange('K:K').format.columnWidth = 40;
pool.getRange('H2:H200').dataValidation = {rule:{type:'list',values:['A','B','C']}};
pool.getRange('I2:I200').dataValidation = {rule:{type:'list',values:['Not contacted','Queued','Sent','Replied','Not a fit','Do not contact']}};
pool.getRange('H2:H200').conditionalFormats.add('cellIs',{operator:'equal',formula:'"A"',format:{fill:'#DCFCE7',font:{bold:true,color:'#166534'}}});
pool.getRange('I2:I200').conditionalFormats.add('cellIs',{operator:'equal',formula:'"Replied"',format:{fill:'#DBEAFE',font:{bold:true,color:'#1D4ED8'}}});

guide.getRange('A1:E1').merge();
guide.getRange('A1').values = [['300-lead sourcing plan']];
guide.getRange('A1:E1').format = {fill:'#123047',font:{bold:true,color:'#FFFFFF',size:14},horizontalAlignment:'center'};
guide.getRange('A3:E3').values = [['Segment','Target count','Search angle','Qualification rule','Outreach message angle']];
guide.getRange('A4:E7').values = [
  ['Apollo / LinkedIn footwear buyers',120,'Buyer, sourcing manager, founder; US + UK; footwear/retail', 'Named person + footwear relevance + public/verified business email','Sample-before-bulk, knit walking / wide toe box, OEM/ODM'],
  ['Amazon footwear brands',80,'Brand websites selling knit walking, slip-on, wide fit or casual sneakers','Own website + active footwear assortment + contact page','Low-risk sample, custom color/logo/packing'],
  ['TikTok Shop footwear brands',50,'Shoes with recurring product videos and identifiable brand site','Active shop + footwear visuals + business contact source','Content-friendly knit/ chunky style, sample discussion'],
  ['Google Maps shoe retailers',100,'Comfort shoe stores, independent shoe stores, regional chains','Real store + website + buyer/owner route','Factory direct line, mixed sizes/colors discussion'],
];
guide.getRange('A3:E7').format.borders = {preset:'all',style:'thin',color:'#D9E2F3'};
guide.getRange('A3:E3').format = {fill:'#1F5A7A',font:{bold:true,color:'#FFFFFF'},wrapText:true};
guide.getRange('A4:E7').format.wrapText = true;
guide.getRange('A:E').format.columnWidth = 28;
guide.getRange('D:D').format.columnWidth = 38;
guide.getRange('E:E').format.columnWidth = 38;

health.getRange('A1:G1').merge();
health.getRange('A1').values = [['Apollo outreach health log — 2026-08-03']];
health.getRange('A1:G1').format = {fill:'#123047',font:{bold:true,color:'#FFFFFF',size:14},horizontalAlignment:'center'};
health.getRange('A3:G3').values = [['Contact','Company','Sequence state','Reason','Safe action','Effect on future sourcing','Date checked']];
health.getRange('A4:G8').values = [
  ['Becky Gomersall','Anthropologie Europe','Spam blocked (not a normal bounce)','Recipient/provider classified the message as spam','Do not resend to the same address; only retry with a different publicly listed business contact after research','Prefer smaller retailers and personalised copy for enterprise accounts; treat this as a deliverability/content signal, not proof that the address is invalid','2026-08-03'],
  ['Millie Smythe','WANDER STUDIO - Footwear Design & Sourcing','Not sent','Recipient domain has an invalid MX record','Do not retry automatically; find a valid public business email or LinkedIn route','Keep MX-valid email requirement before queueing','2026-08-03'],
  ['David Markham','T&A Footwear','Paused at step 2','Paused status shown; no reason exposed in sequence view','Keep paused until buyer history/owner review confirms next action','Do not force-restart paused contacts','2026-08-03'],
  ['Sequence aggregate','Beiqiang Footwear Outreach - Address Verified - 2026-08','12 delivered; 45 scheduled; 0 replies','One spam-blocked email; current sequence list shows zero normal bounces','Do not add a broad generic batch today; use more specific buyer/retailer copy for the next validated contacts','Prioritize named footwear buyers and publicly listed purchasing routes; evaluate after more deliveries','2026-08-03'],
  ['Legacy sequence','Beiqiang Footwear Wholesale Outreach - US & UK - 2026-08','Inactive; do not use','Apollo sequence list shows it as inactive while displaying historical scheduled count','Never activate, add contacts, or reuse it; keep all new outreach separate','Prevents accidental sends from an outdated sequence or duplicate contact handling','2026-08-03'],
];
health.getRange('A3:G8').format.borders = {preset:'all',style:'thin',color:'#D9E2F3'};
health.getRange('A3:G3').format = {fill:'#1F5A7A',font:{bold:true,color:'#FFFFFF'},wrapText:true};
health.getRange('A4:G6').format.wrapText = true;
health.freezePanes.freezeRows(3);
health.getRange('A:G').format.columnWidth = 24;
health.getRange('D:D').format.columnWidth = 38;
health.getRange('E:F').format.columnWidth = 42;

templates.getRange('A1:F1').merge();
templates.getRange('A1').values = [['Next-batch segment email templates']];
templates.getRange('A1:F1').format = {fill:'#123047',font:{bold:true,color:'#FFFFFF',size:14},horizontalAlignment:'center'};
templates.getRange('A3:F3').values = [['Segment','Use for','Subject','Opening / body','Single CTA','Do not use when']];
templates.getRange('A4:F6').values = [
  ['Distributor / wholesaler','Unitrends, Trenova, regional distributors and importers','Factory supply: breathable knit walking shoes for your assortment','Hello {{First Name}},\n\nI am She Peiqiang from Quanzhou Beiqiang Footwear & Apparel Co., Ltd., a factory supplier in Fujian, China. We supply breathable knit walking shoes, lightweight slip-ons and roomy-toe casual styles for footwear distributors and retailers.\n\nFor suitable styles, we can discuss mixed colours/sizes, logo, packing and samples before a bulk order. Final price depends on the style, quantity, size ratio and packing requirements.','Would it be useful if I send the six-style sheet and ask for the right sourcing or product-development contact?','Do not use for a retail customer-service inbox unless it is clearly the buyer route.'],
  ['Independent comfort shoe retailer','Comfort & Wide Shoes, Shoe Hutch, SAS Shoes Buffalo and similar stores','Sample enquiry: knit walking shoes with roomy toe space','Hello {{First Name}},\n\nI noticed your store focuses on comfort footwear and width/fit options. We are a Fujian footwear factory supplying breathable knit walking shoes, lightweight EVA-sole slip-ons and casual styles with roomy toe space.\n\nWe are contacting you to see whether a small sample review of our adult walking-shoe range could fit your future assortment; mixed colours and sizes can be discussed for bulk orders.','May I send the six-style product sheet to the person who reviews new footwear ranges?','Do not make medical, orthopedic or therapeutic claims.'],
  ['Brand / private-label buyer','Named footwear buyers, brands, Amazon/TikTok sellers with an official business contact','OEM/ODM knit walking shoes - sample before bulk order','Hello {{First Name}},\n\nI am She Peiqiang from Quanzhou Beiqiang Footwear & Apparel Co., Ltd. We manufacture breathable knit/textile casual walking shoes, including lightweight slip-ons, roomy-toe walking styles and chunky-knit silhouettes.\n\nFor OEM/ODM discussions, we can review colour, logo and packing requirements after a sample check. We would first need to confirm target style, quantity, size ratio and packaging before quoting.','Would you be open to reviewing the attached six-style sheet and discussing a sample?','Do not use for child-footwear buyers unless adult footwear capability is confirmed.'],
];
templates.getRange('A3:F6').format.borders = {preset:'all',style:'thin',color:'#D9E2F3'};
templates.getRange('A3:F3').format = {fill:'#1F5A7A',font:{bold:true,color:'#FFFFFF'},wrapText:true};
templates.getRange('A4:F6').format.wrapText = true;
templates.freezePanes.freezeRows(3);
templates.getRange('A:A').format.columnWidth = 26;
templates.getRange('B:B').format.columnWidth = 34;
templates.getRange('C:C').format.columnWidth = 38;
templates.getRange('D:D').format.columnWidth = 64;
templates.getRange('E:E').format.columnWidth = 38;
templates.getRange('F:F').format.columnWidth = 38;

queue.getRange('A1:G1').merge();
queue.getRange('A1').values = [['Next validated outreach batch - hold until current schedule clears']];
queue.getRange('A1:G1').format = {fill:'#123047',font:{bold:true,color:'#FFFFFF',size:14},horizontalAlignment:'center'};
queue.getRange('A3:G3').values = [['Order','Company','Market','Business email / route','Buyer type','Template','Pre-send check']];
queue.getRange('A4:G10').values = [
  [1,'Unitrends Footwear','United States','unitrendsfc@gmail.com','Footwear distributor','Distributor / wholesaler','Personalise with US retailer-network reference; ask for sourcing/product-development contact.'],
  [2,'Trenova Brands','United States','info@trenovabrands.com','Footwear distributor','Distributor / wholesaler','Personalise with wholesale distribution / brand-partnership reference.'],
  [3,'Comforta Nieuwkoop BV','Netherlands','contact@comforta.nl','Footwear distributor / supply-chain partner','Distributor / wholesaler','Ask for buying or product-management contact; do not assume current category gap.'],
  [4,'Shaped4 / Gerla Products BV','Netherlands','info@shaped4.nl','B2B retailer / private-label owner','Brand / private-label buyer','Mention B2B and private-label route; request sample review.'],
  [5,'Leading Fashions Ltd','United Kingdom','Jerry@leadingfashions.co.uk','Footwear wholesaler / importer','Distributor / wholesaler','Mention casual trainers / repeat ordering fit; keep message concise.'],
  [6,'Bacup Shoe Direct Ltd','United Kingdom','sales@bacupshoedirect.co.uk','Footwear distributor','Distributor / wholesaler','Ask for buyer/product-development contact for adult knit walking styles.'],
  [7,'Distrimex bv','Belgium','info@distrimex.be','Comfort footwear wholesaler','Distributor / wholesaler','Use a tailored comfort-footwear wholesale enquiry; avoid medical claims.'],
];
queue.getRange('A3:G10').format.borders = {preset:'all',style:'thin',color:'#D9E2F3'};
queue.getRange('A3:G3').format = {fill:'#1F5A7A',font:{bold:true,color:'#FFFFFF'},wrapText:true};
queue.getRange('A4:G10').format.wrapText = true;
queue.freezePanes.freezeRows(3);
queue.getRange('A:A').format.columnWidth = 10;
queue.getRange('B:B').format.columnWidth = 30;
queue.getRange('C:C').format.columnWidth = 16;
queue.getRange('D:D').format.columnWidth = 34;
queue.getRange('E:E').format.columnWidth = 34;
queue.getRange('F:F').format.columnWidth = 30;
queue.getRange('G:G').format.columnWidth = 48;

const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(`${outDir}/Beiqiang_Buyer_Acquisition_Tracker.xlsx`);
const check = await wb.inspect({kind:'table',range:`Lead Pool!A1:K${rows.length+1}`,include:'values,formulas',tableMaxRows:rows.length+1,tableMaxCols:11});
console.log(check.ndjson);
for (const [sheetName, range, fileName] of [
  ['Dashboard','A1:G7','dashboard_preview.png'],
  ['Lead Pool',`A1:K${rows.length+1}`,'lead_pool_preview.png'],
  ['Sourcing Plan','A1:E7','sourcing_plan_preview.png'],
  ['Outreach Health','A1:G8','outreach_health_preview.png'],
  ['Email Templates','A1:F6','email_templates_preview.png'],
  ['Next Batch Queue','A1:G10','next_batch_queue_preview.png'],
]) {
  const png = await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(`${outDir}/${fileName}`,new Uint8Array(await png.arrayBuffer()));
}
