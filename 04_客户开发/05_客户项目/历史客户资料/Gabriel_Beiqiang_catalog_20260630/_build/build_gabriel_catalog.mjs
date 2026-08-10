import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const buildDir = path.dirname(__filename);
const root = path.resolve(buildDir, "..", "..", "..");
const outputDir = path.join(root, "customers", "Gabriel_Beiqiang_Ready_To_Send_20260630");
const today = "2026-06-30";

const imageExts = new Set([".jpg", ".jpeg", ".png", ".webp"]);
const riskyPatterns = [
  [/orthopedic/gi, "Comfort"],
  [/diabetic friendly/gi, "Wide Fit"],
  [/diabetic/gi, "Comfort"],
  [/plantar fasciitis/gi, "Daily Walking Comfort"],
  [/bunion friendly/gi, "Wide Toe Comfort"],
  [/bunion/gi, "Wide Toe Comfort"],
  [/arch support/gi, "Cushioned Support"],
  [/pain relief/gi, "Walking Comfort"],
  [/medical/gi, "Comfort"],
  [/fly-?knit/gi, "knit"],
];

function assertInsideOutput(target) {
  const resolved = path.resolve(target);
  if (!resolved.startsWith(outputDir)) {
    throw new Error(`Refusing to write outside output folder: ${resolved}`);
  }
  return resolved;
}

async function resetGeneratedDir(dir) {
  const safeDir = assertInsideOutput(dir);
  await fs.rm(safeDir, { recursive: true, force: true });
  await fs.mkdir(safeDir, { recursive: true });
}

async function findChildDir(parent, predicate) {
  const entries = await fs.readdir(parent, { withFileTypes: true });
  const found = entries.find((entry) => entry.isDirectory() && predicate(entry.name));
  if (!found) throw new Error(`Missing expected folder under ${parent}`);
  return path.join(parent, found.name);
}

async function findChildFile(parent, predicate) {
  const entries = await fs.readdir(parent, { withFileTypes: true });
  const found = entries.find((entry) => entry.isFile() && predicate(entry.name));
  if (!found) return null;
  return path.join(parent, found.name);
}

async function listImageFiles(dir) {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isFile() && imageExts.has(path.extname(entry.name).toLowerCase()))
      .map((entry) => path.join(dir, entry.name))
      .sort((a, b) => path.basename(a).localeCompare(path.basename(b), "en", { numeric: true }));
  } catch {
    return [];
  }
}

async function listFilesRecursive(dir, filterFn) {
  const results = [];
  async function walk(current) {
    const entries = await fs.readdir(current, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        await walk(full);
      } else if (!filterFn || filterFn(full)) {
        results.push(full);
      }
    }
  }
  await walk(dir);
  return results.sort((a, b) => a.localeCompare(b, "en", { numeric: true }));
}

function cleanText(value) {
  if (!value) return "";
  let text = String(value)
    .replace(/`/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s+([,.;:])/g, "$1")
    .trim();
  for (const [pattern, replacement] of riskyPatterns) {
    text = text.replace(pattern, replacement);
  }
  return text
    .replace(/\bComfortable\s+Comfortable\b/gi, "Comfortable")
    .replace(/\bComfort\s+Comfort\b/gi, "Comfort")
    .replace(/\bWide Toe Comfort\s+Wide Toe Comfort\b/gi, "Wide Toe Comfort")
    .replace(/\s+/g, " ")
    .trim();
}

function extractFirst(regexes, text) {
  for (const regex of regexes) {
    const match = text.match(regex);
    if (match && match[1]) return cleanText(match[1]);
  }
  return "";
}

function extractFencedAfterHeading(heading, text) {
  const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(`##\\s*${escaped}[\\s\\S]*?\`\`\`(?:text)?\\s*([\\s\\S]*?)\\s*\`\`\``, "i");
  const match = text.match(regex);
  return match ? cleanText(match[1].split(/\r?\n/).find(Boolean) || match[1]) : "";
}

function extractSellingPoints(text) {
  const section = text.split(/##\s*商品卖点/i)[1]?.split(/\n##\s+/)[0] || "";
  const lines = section
    .split(/\r?\n/)
    .map((line) => cleanText(line.replace(/^\s*(?:[-*]|\d+\.)\s*/, "")))
    .filter((line) => line && !line.startsWith("```") && !line.endsWith("```"));
  return lines.slice(0, 4).join("\n");
}

function parseBacktickList(raw) {
  if (!raw) return "";
  const ticks = [...raw.matchAll(/`([^`]+)`/g)].map((m) => m[1]);
  const base = ticks.length ? ticks.join(", ") : raw;
  return cleanText(
    base
      .replace(/[，、]/g, ", ")
      .replace(/\s*\/\s*/g, ", ")
      .replace(/\s*,\s*/g, ", ")
      .replace(/（.*?）|\(.*?\)/g, ""),
  );
}

function conciseTitle(rawTitle, group, code) {
  const cleaned = cleanText(rawTitle);
  const fallbackGroup = group || "Wide Toe Box Comfort Walking Shoes";
  const title = cleaned || `Wholesale Beiqiang ${fallbackGroup} Lightweight Casual Shoes Custom Logo`;
  const words = title.split(/\s+/);
  if (title.length <= 118) return title;
  const trimmed = [];
  for (const word of words) {
    const next = [...trimmed, word].join(" ");
    if (next.length > 112) break;
    trimmed.push(word);
  }
  const joined = trimmed.join(" ").replace(/\s+(for|with|and)$/i, "");
  return joined.includes(code) ? joined : `${joined} ${code}`.slice(0, 118);
}

function normalizeModel(raw, code) {
  const model = cleanText(raw);
  if (!model || /^BQ-?\d{3}$/i.test(model)) return code;
  return model;
}

function inferClosure(text) {
  const closure = extractFirst([
    /Closure type[：:]\s*`?([^`\n]+)/i,
    /开口\/闭合方式[：:]\s*`?([^`\n]+)/i,
  ], text);
  if (closure) return closure;
  if (/slip[- ]?on/i.test(text)) return "Slip-On";
  if (/lace[- ]?up/i.test(text)) return "Lace-Up";
  return "To be confirmed";
}

async function loadProducts(uploadDir) {
  const entries = await fs.readdir(uploadDir, { withFileTypes: true });
  const productDirs = entries
    .filter((entry) => entry.isDirectory() && /^BQ\d{3}/.test(entry.name))
    .map((entry) => path.join(uploadDir, entry.name))
    .sort((a, b) => path.basename(a).localeCompare(path.basename(b), "en", { numeric: true }));

  const products = [];
  for (const dir of productDirs) {
    const folder = path.basename(dir);
    const code = folder.match(/BQ\d{3}/)?.[0] || folder.slice(0, 5);
    const mdPath = await findChildFile(dir, (name) => name.endsWith(".md"));
    const text = mdPath ? await fs.readFile(mdPath, "utf8") : "";
    const mainDir = await findChildDir(dir, (name) => name.startsWith("01_"));
    const colorDir = await findChildDir(dir, (name) => name.startsWith("03_"));
    const detailDir = await findChildDir(dir, (name) => name.startsWith("02_"));
    const mainImages = await listImageFiles(mainDir);
    const colorImages = await listImageFiles(colorDir);
    const detailImages = await listImageFiles(detailDir);
    const hero = mainImages.find((file) => /^01[_-]?main/i.test(path.basename(file))) || mainImages[0];

    const group = extractFirst([
      /商品分组[：:]\s*`?([^`\n]+)/i,
      /建议产品组[：:]\s*`?([^`\n]+)/i,
    ], text);
    const rawTitle =
      extractFirst([/商品名称[：:]\s*`([^`]+)/i], text) ||
      extractFencedAfterHeading("建议标题", text) ||
      extractFirst([/优化后标题[：:]\s*`?([^`\n]+)/i], text);
    const title = conciseTitle(rawTitle, group, code);

    const model = normalizeModel(
      extractFirst([
        /(?:建议型号|原始货号|型号)[：:]\s*`?([^`\n]+)/i,
        /\|\s*Model\s*\|\s*([^|\n]+)/i,
      ], text),
      code,
    );
    const sizeRange = parseBacktickList(extractFirst([
      /尺码范围[：:]\s*([^\n]+)/i,
      /尺码[：:]\s*([^\n]+)/i,
      /Size Range\s*\|\s*([^|\n]+)/i,
      /Size Range[：:]\s*([^\n]+)/i,
    ], text));
    const colors = parseBacktickList(extractFirst([
      /主要颜色[：:]\s*([^\n]+)/i,
      /颜色[：:]\s*([^\n]+)/i,
    ], text));
    const upper = extractFirst([
      /Upper material\s*\|\s*`?([^`|\n]+)/i,
      /Upper material[：:]\s*`?([^`\n]+)/i,
      /鞋面材质[：:]\s*`?([^`\n]+)/i,
      /Upper Material Detail[：:]\s*([^\n]+)/i,
      /\|\s*Upper Material Detail\s*\|\s*([^|\n]+)/i,
    ], text) || "Textile / knit upper";
    const outsole = extractFirst([
      /Outsole material\s*\|\s*`?([^`|\n]+)/i,
      /Outsole material[：:]\s*`?([^`\n]+)/i,
      /大底材质[：:]\s*`?([^`\n]+)/i,
      /Outsole Material[：:]\s*([^\n]+)/i,
      /\|\s*Sole Type\s*\|\s*([^|\n]+)/i,
    ], text) || "EVA / cushion sole, final material to confirm";
    const closure = inferClosure(text);
    const sellingPoints = extractSellingPoints(text) ||
      "Roomy toe space for daily walking comfort.\nLightweight textile upper and flexible sole.\nMixed colors and sizes can be discussed for wholesale orders.";

    products.push({
      code,
      folder,
      model,
      group: group || "Comfort Walking Shoes",
      title,
      sizeRange: sizeRange || "To be confirmed",
      colors: colors || "Mixed colors can be discussed",
      upper: cleanText(upper),
      outsole: cleanText(outsole),
      closure,
      sellingPoints,
      hero,
      mainImages,
      colorImages,
      detailImages,
      sourceFolder: dir,
    });
  }
  return products;
}

async function copyProductAssets(products, productImagesDir) {
  const heroDir = path.join(productImagesDir, "_Catalog_Hero_Images");
  await fs.mkdir(heroDir, { recursive: true });
  for (const product of products) {
    const destDir = path.join(productImagesDir, `${product.code}_${product.model.replace(/[\\/:*?"<>|]/g, "_")}`);
    await fs.mkdir(destDir, { recursive: true });
    const files = [
      ...product.mainImages.map((file) => ({ file, prefix: "main" })),
      ...product.colorImages.map((file) => ({ file, prefix: "color" })),
      ...product.detailImages.slice(0, 2).map((file) => ({ file, prefix: "detail" })),
    ];
    let counter = 1;
    for (const { file, prefix } of files) {
      const ext = path.extname(file).toLowerCase() || ".jpg";
      const dest = path.join(destDir, `${String(counter).padStart(2, "0")}_${prefix}_${path.basename(file)}`);
      await fs.copyFile(file, dest);
      counter += 1;
    }
    if (product.hero) {
      const heroExt = path.extname(product.hero).toLowerCase() || ".jpg";
      const heroDest = path.join(heroDir, `${product.code}_main${heroExt}`);
      await fs.copyFile(product.hero, heroDest);
      product.heroCopied = heroDest;
      product.assetFolder = destDir;
    }
  }
}

async function copyFactoryAssets(uploadDir, factoryDir) {
  const selected = [];
  const factoryRoot = await findChildDir(uploadDir, (name) => name.includes("厂家"));
  const curated = await findChildDir(factoryRoot, (name) => name.includes("精选") || name.startsWith("00_"));
  const curatedImages = await listFilesRecursive(curated, (file) => imageExts.has(path.extname(file).toLowerCase()));
  for (const file of curatedImages) {
    const relative = path.relative(curated, file);
    const dest = path.join(factoryDir, "Selected_Factory_Photos", relative);
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.copyFile(file, dest);
    selected.push(dest);
  }
  try {
    const companyDir = await findChildDir(uploadDir, (name) => name.includes("公司资料"));
    const companyImages = await listFilesRecursive(companyDir, (file) => imageExts.has(path.extname(file).toLowerCase()));
    for (const file of companyImages) {
      const relative = path.relative(companyDir, file);
      const dest = path.join(factoryDir, "Company_Detail_Images", relative);
      await fs.mkdir(path.dirname(dest), { recursive: true });
      await fs.copyFile(file, dest);
      selected.push(dest);
    }
  } catch {
    // Company images are helpful but not required for the package.
  }
  return selected;
}

function dataUrlForImage(file) {
  return fs.readFile(file).then((buffer) => {
    const ext = path.extname(file).toLowerCase();
    const mime = ext === ".png" ? "image/png" : ext === ".webp" ? "image/webp" : "image/jpeg";
    return `data:${mime};base64,${buffer.toString("base64")}`;
  });
}

function quoteMessage() {
  return `Hi Gabriel,

Thank you for your detailed inquiry.

We are Quanzhou Beiqiang Footwear & Apparel Co., Ltd., a source footwear factory supplier in Quanzhou, Fujian, China. We focus on wide toe box comfort walking shoes, lightweight casual walking shoes, breathable knit/textile shoes, and slip-on shoes for wholesale and OEM/ODM cooperation.

Attached is our current 30-style product catalog with real product photos and factory reference photos. For orders of 500 pairs and above, we can quote a competitive FOB reference price of USD 8.00/pair for suitable selected styles. The final price depends on selected style, quantity, material confirmation, size ratio, color mix, logo/custom packaging requirements, and final order details.

We can support:
- Sample checking before bulk order
- Mixed colors and mixed sizes according to stock and order quantity
- Logo, insole, label, hangtag, shoe box, and custom packaging discussion
- Bulk wholesale orders for U.S. importers, resellers, Amazon/TikTok sellers, and brand buyers
- Product photos, unedited product videos, factory/warehouse photos, and pre-shipment quality checking photos when available

Our regular reference:
- Sample order: can be arranged before bulk order
- Bulk MOQ: normally from 100 pairs per style; 500+ pairs can receive stronger factory pricing
- Lead time reference: about 10 days for sample/small quantity if available, and about 20-30 days for bulk orders after details are confirmed
- Shipping methods: express, air freight, and sea freight can be discussed based on urgency and quantity

To prepare an accurate quotation and sample shipping cost to California, please confirm:
1. Preferred style numbers from the catalog
2. Estimated first order quantity
3. Size range and size ratio
4. Preferred colors
5. Logo or custom packaging requirements
6. Sample delivery ZIP code in California

We are looking for long-term cooperation and can provide competitive factory pricing, stable quality checking, and flexible customization discussion for recurring bulk orders.

Best regards,
Quanzhou Beiqiang Footwear & Apparel Co., Ltd.`;
}

function packageReadme() {
  return `Beiqiang customer package for Gabriel
Generated: ${today}

Folder contents:
- Gabriel_Beiqiang_30_Styles_Catalog.xlsx: customer-facing product catalog with images and quotation terms.
- Product_Images/: copied product photos for all 30 styles.
- Factory_Info_and_Photos/: factory, warehouse, product checking, stock, and packing photos currently available.
- Gabriel_Quotation_Message.txt: English quotation message ready to paste into Alibaba/Email/WhatsApp.

Important notes:
- FOB USD 8.00/pair is positioned as a 500+ pairs reference price for suitable styles, not a fixed promise for every specification.
- Confirm exact materials, color availability, size ratio, packaging, logo/custom options, sample cost, and shipping cost before final quotation.
- Share only confirmed factory documents, photos, and order details with the buyer.
`;
}

async function buildWorkbook(products, factoryImages, xlsxPath, previewPath) {
  const workbook = Workbook.create();

  const catalog = workbook.worksheets.add("Product Catalog");
  catalog.showGridLines = false;
  catalog.freezePanes.freezeRows(1);
  catalog.getRange("A1:N1").values = [[
    "Photo",
    "Style No.",
    "Model",
    "Customer-Facing Product Name",
    "Category",
    "Size Range",
    "Colorways",
    "Upper",
    "Sole",
    "Closure",
    "Bulk MOQ",
    "500+ FOB Reference",
    "Lead Time Reference",
    "Customization / Notes",
  ]];
  catalog.getRange("A1:N1").format = {
    fill: "#0F766E",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  catalog.getRange("A1:N1").format.rowHeightPx = 42;
  catalog.getRange("A:A").format.columnWidthPx = 120;
  catalog.getRange("B:B").format.columnWidthPx = 70;
  catalog.getRange("C:C").format.columnWidthPx = 82;
  catalog.getRange("D:D").format.columnWidthPx = 300;
  catalog.getRange("E:E").format.columnWidthPx = 155;
  catalog.getRange("F:F").format.columnWidthPx = 100;
  catalog.getRange("G:G").format.columnWidthPx = 175;
  catalog.getRange("H:I").format.columnWidthPx = 130;
  catalog.getRange("J:J").format.columnWidthPx = 78;
  catalog.getRange("K:M").format.columnWidthPx = 118;
  catalog.getRange("N:N").format.columnWidthPx = 220;

  const rows = products.map((p) => [
    "",
    p.code,
    p.model,
    p.title,
    p.group,
    p.sizeRange,
    p.colors,
    p.upper,
    p.outsole,
    p.closure,
    "100 pairs/style reference",
    "FOB USD 8.00/pair for 500+ pairs",
    "Sample/small qty: about 10 days; bulk: about 20-30 days after confirmation",
    "Logo, insole, label, box, hangtag and custom packaging can be discussed. Final quote depends on specs.",
  ]);
  catalog.getRangeByIndexes(1, 0, rows.length, 14).values = rows;
  catalog.getRangeByIndexes(1, 0, rows.length, 14).format = {
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "inside", style: "thin", color: "#DDE7E5" },
  };
  catalog.getRangeByIndexes(1, 1, rows.length, 2).format = { horizontalAlignment: "center", verticalAlignment: "center" };
  catalog.getRangeByIndexes(1, 10, rows.length, 3).format = { horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
  catalog.getRangeByIndexes(1, 0, rows.length, 1).format.rowHeightPx = 92;

  for (let i = 0; i < products.length; i += 1) {
    const imageFile = products[i].heroCopied || products[i].hero;
    if (!imageFile) continue;
    catalog.images.add({
      dataUrl: await dataUrlForImage(imageFile),
      anchor: {
        from: { row: i + 1, col: 0, rowOffsetPx: 6, colOffsetPx: 8 },
        extent: { widthPx: 96, heightPx: 78 },
      },
    });
  }

  const info = workbook.worksheets.add("Quote Message");
  info.showGridLines = false;
  info.getRange("A1:H1").merge();
  info.getRange("A1").values = [["Beiqiang Factory Quotation Message for Gabriel"]];
  info.getRange("A1").format = { fill: "#0F766E", font: { bold: true, color: "#FFFFFF", size: 15 }, horizontalAlignment: "left" };
  info.getRange("A3:H22").merge();
  info.getRange("A3").values = [[quoteMessage()]];
  info.getRange("A3").format = { wrapText: true, verticalAlignment: "top", font: { size: 11 } };
  info.getRange("A:H").format.columnWidthPx = 120;
  info.getRange("A3").format.rowHeightPx = 560;

  const factory = workbook.worksheets.add("Factory Info");
  factory.showGridLines = false;
  factory.getRange("A1:H1").merge();
  factory.getRange("A1").values = [["Factory, Quality Check & Packing Support"]];
  factory.getRange("A1").format = { fill: "#0F766E", font: { bold: true, color: "#FFFFFF", size: 15 } };
  factory.getRange("A3:B9").values = [
    ["Company", "Quanzhou Beiqiang Footwear & Apparel Co., Ltd."],
    ["Supplier Type", "Source footwear factory supplier in Quanzhou, Fujian, China"],
    ["Main Products", "Wide toe box comfort walking shoes, casual walking shoes, lightweight slip-on shoes, breathable knit/textile shoes"],
    ["Buyer Fit", "U.S. importers, resellers, wholesalers, Amazon/TikTok sellers, and private-label buyers"],
    ["Quality Check", "Manual product checking before packing; final QC details can be confirmed per order"],
    ["Customization", "Logo, insole, label, hangtag, shoe box and packaging can be discussed according to order quantity"],
    ["Shipping", "Express, air freight and sea freight can be discussed after confirming quantity, packing, carton size and destination"],
  ];
  factory.getRange("A3:B9").format = { wrapText: true, verticalAlignment: "top", borders: { preset: "inside", style: "thin", color: "#DDE7E5" } };
  factory.getRange("A3:A9").format = { font: { bold: true }, fill: "#E7F4F1" };
  factory.getRange("A:A").format.columnWidthPx = 150;
  factory.getRange("B:B").format.columnWidthPx = 480;
  factory.getRange("A3:B9").format.rowHeightPx = 48;

  const factoryHeroImages = factoryImages.slice(0, 6);
  for (let i = 0; i < factoryHeroImages.length; i += 1) {
    const row = 11 + Math.floor(i / 3) * 9;
    const col = (i % 3) * 3;
    factory.images.add({
      dataUrl: await dataUrlForImage(factoryHeroImages[i]),
      anchor: {
        from: { row, col, rowOffsetPx: 4, colOffsetPx: 4 },
        extent: { widthPx: 210, heightPx: 150 },
      },
    });
  }

  const terms = workbook.worksheets.add("Commercial Terms");
  terms.showGridLines = false;
  terms.getRange("A1:D1").merge();
  terms.getRange("A1").values = [["Commercial Terms and Buyer Confirmation Items"]];
  terms.getRange("A1").format = { fill: "#0F766E", font: { bold: true, color: "#FFFFFF", size: 14 } };
  terms.getRange("A3:D14").values = [
    ["Item", "Our Current Position", "Details Needed From Buyer", "Notes"],
    ["500+ pairs FOB price", "USD 8.00/pair FOB reference for suitable selected styles", "Style, quantity, material confirmation, color mix, size ratio and packing", "Final price is confirmed after order details are clear."],
    ["Sample order", "Samples can be arranged before bulk order", "Selected style, size, receiver ZIP code, sample quantity and courier preference", "Sample fee and express cost are quoted separately."],
    ["MOQ", "100 pairs/style reference; 500+ pairs can receive stronger factory pricing", "Per-style quantity and whether logo/custom packaging is required", "Mixed sizes and colors can be discussed."],
    ["Lead time", "Sample/small quantity about 10 days if available; bulk about 20-30 days after confirmation", "Order schedule and delivery deadline", "Lead time depends on stock, materials and customization."],
    ["Materials", "Many styles use textile/knit upper and EVA/cushion sole", "Exact upper, sole, insole and lining for selected models", "Material details will be confirmed by style."],
    ["Logo/custom packaging", "Logo, insole, label, hangtag, shoe box and packaging can be discussed", "Logo artwork, box design, quantity and target delivery time", "Customization cost and sample time depend on design."],
    ["Product photos/videos", "Real product photos are included; product videos can be shared when available", "Selected style numbers and angles needed", "Unedited all-angle videos can be arranged for key styles."],
    ["Factory/warehouse photos", "Factory, warehouse, product checking and packing photos are included", "Any specific process or area the buyer wants to see", "Additional photos can be requested for serious sample/bulk discussion."],
    ["Quality control", "Manual product checking before packing and pre-shipment checking can be discussed", "Buyer quality standard and inspection requirement", "Specific QC checklist can be aligned before order."],
    ["Shipping", "Express, air freight and sea freight can be discussed", "Destination address/ZIP, quantity, carton data and delivery deadline", "Freight is quoted separately after logistics data is confirmed."],
    ["Documents", "Available factory documents can be shared after confirmation", "Specific document request from buyer", "Only confirmed documents will be listed or sent."],
  ];
  terms.getRange("A3:D3").format = { fill: "#0F766E", font: { bold: true, color: "#FFFFFF" }, wrapText: true };
  terms.getRange("A4:D14").format = { wrapText: true, verticalAlignment: "top", borders: { preset: "inside", style: "thin", color: "#DDE7E5" } };
  terms.getRange("A:A").format.columnWidthPx = 160;
  terms.getRange("B:D").format.columnWidthPx = 285;
  terms.getRange("A4:D14").format.rowHeightPx = 58;

  const inspect = await workbook.inspect({
    kind: "sheet,table,drawing",
    maxChars: 4000,
    tableMaxRows: 5,
    tableMaxCols: 6,
  });
  console.log(inspect.ndjson);

  const preview = await workbook.render({ sheetName: "Product Catalog", range: "A1:N8", scale: 1, format: "png" });
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(xlsxPath);
}

async function main() {
  const uploadRoot = await findChildDir(root, (name) => name.startsWith("02_"));
  const uploadDir = await findChildDir(uploadRoot, (name) => name.startsWith("00_"));
  const productImagesDir = path.join(outputDir, "Product_Images");
  const factoryDir = path.join(outputDir, "Factory_Info_and_Photos");

  await resetGeneratedDir(productImagesDir);
  await resetGeneratedDir(factoryDir);

  const products = await loadProducts(uploadDir);
  if (products.length !== 30) {
    throw new Error(`Expected 30 products, found ${products.length}`);
  }
  await copyProductAssets(products, productImagesDir);
  const factoryImages = await copyFactoryAssets(uploadDir, factoryDir);

  const quotePath = path.join(outputDir, "Gabriel_Quotation_Message.txt");
  const readmePath = path.join(outputDir, "README_customer_package.txt");
  const jsonPath = path.join(buildDir, "catalog_data_ready.json");
  const xlsxPath = path.join(outputDir, "Gabriel_Beiqiang_30_Styles_Catalog.xlsx");
  const previewPath = path.join(buildDir, "catalog_preview_ready.png");

  await fs.writeFile(assertInsideOutput(quotePath), quoteMessage(), "utf8");
  await fs.writeFile(assertInsideOutput(readmePath), packageReadme(), "utf8");
  await fs.writeFile(jsonPath, JSON.stringify(products.map((p) => ({
    code: p.code,
    model: p.model,
    title: p.title,
    group: p.group,
    sizeRange: p.sizeRange,
    colors: p.colors,
    upper: p.upper,
    outsole: p.outsole,
    closure: p.closure,
    heroCopied: p.heroCopied,
    assetFolder: p.assetFolder,
  })), null, 2), "utf8");

  await buildWorkbook(products, factoryImages, xlsxPath, previewPath);
  await fs.rm(`${xlsxPath}.inspect.ndjson`, { force: true });

  console.log(JSON.stringify({
    outputDir,
    xlsxPath,
    quotePath,
    readmePath,
    productCount: products.length,
    factoryImageCount: factoryImages.length,
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
