import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const buildDir = path.dirname(__filename);
const root = path.resolve(buildDir, "..", "..", "..");
const outputDir = path.join(root, "customers", "Gabriel_Beiqiang_Upload_Under5MB_20260630");
const manifestPath = path.join(buildDir, "catalog_data_ready.json");
const under5ManifestPath = path.join(buildDir, "under5_manifest.json");
const imageExts = new Set([".jpg", ".jpeg", ".png", ".webp"]);

function assertInsideOutput(target) {
  const resolved = path.resolve(target);
  if (!resolved.startsWith(outputDir)) throw new Error(`Unsafe output path: ${resolved}`);
  return resolved;
}

async function findChildDir(parent, predicate) {
  const entries = await fs.readdir(parent, { withFileTypes: true });
  const found = entries.find((entry) => entry.isDirectory() && predicate(entry.name));
  if (!found) throw new Error(`Missing expected folder under ${parent}`);
  return path.join(parent, found.name);
}

async function listImages(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && imageExts.has(path.extname(entry.name).toLowerCase()))
    .map((entry) => path.join(dir, entry.name))
    .sort((a, b) => path.basename(a).localeCompare(path.basename(b), "en", { numeric: true }));
}

async function findProductHero(uploadDir, code) {
  const entries = await fs.readdir(uploadDir, { withFileTypes: true });
  const productDirName = entries.find((entry) => entry.isDirectory() && entry.name.startsWith(code))?.name;
  if (!productDirName) throw new Error(`Cannot find product folder for ${code}`);
  const productDir = path.join(uploadDir, productDirName);
  const mainDir = await findChildDir(productDir, (name) => name.startsWith("01_"));
  const images = await listImages(mainDir);
  return images.find((file) => /^01[_-]?main/i.test(path.basename(file))) || images[0];
}

function quoteMessage() {
  return `Hi Gabriel,

Thank you for your detailed inquiry.

We are Quanzhou Beiqiang Footwear & Apparel Co., Ltd., a source footwear factory supplier in Quanzhou, Fujian, China. We focus on wide toe box comfort walking shoes, lightweight casual walking shoes, breathable knit/textile shoes, and slip-on shoes for wholesale and OEM/ODM cooperation.

Attached is our current 30-style product catalog with product photos and factory information. For orders of 500 pairs and above, we can quote a competitive FOB reference price of USD 8.00/pair for suitable selected styles. The final price depends on selected style, quantity, material confirmation, size ratio, color mix, logo/custom packaging requirements, and final order details.

We can support sample checking before bulk order, mixed colors and sizes, logo/insole/label/hangtag/shoe box/custom packaging discussion, and recurring wholesale cooperation.

To prepare an accurate quotation and sample shipping cost to California, please confirm:
1. Preferred style numbers from the catalog
2. Estimated first order quantity
3. Size range and size ratio
4. Preferred colors
5. Logo or custom packaging requirements
6. Sample delivery ZIP code in California

Best regards,
Quanzhou Beiqiang Footwear & Apparel Co., Ltd.`;
}

async function dataUrlForImage(file) {
  const buffer = await fs.readFile(file);
  return `data:image/jpeg;base64,${buffer.toString("base64")}`;
}

async function buildWorkbook(products, factoryThumbs, xlsxPath) {
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add("30 Styles Catalog");
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.getRange("A1:L1").values = [[
    "Photo",
    "Style No.",
    "Model",
    "Product Name",
    "Category",
    "Size Range",
    "Colorways",
    "Upper",
    "Sole",
    "Closure",
    "500+ FOB Reference",
    "Notes",
  ]];
  sheet.getRange("A1:L1").format = {
    fill: "#0F766E",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  sheet.getRange("A:A").format.columnWidthPx = 76;
  sheet.getRange("B:C").format.columnWidthPx = 72;
  sheet.getRange("D:D").format.columnWidthPx = 265;
  sheet.getRange("E:E").format.columnWidthPx = 145;
  sheet.getRange("F:F").format.columnWidthPx = 92;
  sheet.getRange("G:G").format.columnWidthPx = 155;
  sheet.getRange("H:I").format.columnWidthPx = 112;
  sheet.getRange("J:J").format.columnWidthPx = 75;
  sheet.getRange("K:K").format.columnWidthPx = 135;
  sheet.getRange("L:L").format.columnWidthPx = 210;
  sheet.getRange("A1:L1").format.rowHeightPx = 38;

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
    "FOB USD 8.00/pair for 500+ pairs",
    "Sample before bulk order. Logo, insole, label, box and custom packaging can be discussed.",
  ]);
  sheet.getRangeByIndexes(1, 0, rows.length, 12).values = rows;
  sheet.getRangeByIndexes(1, 0, rows.length, 12).format = {
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "inside", style: "thin", color: "#DDE7E5" },
  };
  sheet.getRangeByIndexes(1, 0, rows.length, 1).format.rowHeightPx = 62;
  sheet.getRangeByIndexes(1, 1, rows.length, 2).format = { horizontalAlignment: "center", verticalAlignment: "center" };
  sheet.getRangeByIndexes(1, 10, rows.length, 1).format = { horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };

  for (let i = 0; i < products.length; i += 1) {
    sheet.images.add({
      dataUrl: await dataUrlForImage(products[i].thumbnail),
      anchor: {
        from: { row: i + 1, col: 0, rowOffsetPx: 4, colOffsetPx: 8 },
        extent: { widthPx: 58, heightPx: 52 },
      },
    });
  }

  const quote = workbook.worksheets.add("Quote Message");
  quote.showGridLines = false;
  quote.getRange("A1:F1").merge();
  quote.getRange("A1").values = [["Quotation Message"]];
  quote.getRange("A1").format = { fill: "#0F766E", font: { bold: true, color: "#FFFFFF", size: 14 } };
  quote.getRange("A3:F18").merge();
  quote.getRange("A3").values = [[quoteMessage()]];
  quote.getRange("A3").format = { wrapText: true, verticalAlignment: "top", font: { size: 11 } };
  quote.getRange("A:F").format.columnWidthPx = 125;
  quote.getRange("A3").format.rowHeightPx = 430;

  const factory = workbook.worksheets.add("Factory Info");
  factory.showGridLines = false;
  factory.getRange("A1:F1").merge();
  factory.getRange("A1").values = [["Factory Direct Supply, Quality Check & Customization Support"]];
  factory.getRange("A1").format = { fill: "#0F766E", font: { bold: true, color: "#FFFFFF", size: 14 } };
  factory.getRange("A3:B9").values = [
    ["Company", "Quanzhou Beiqiang Footwear & Apparel Co., Ltd."],
    ["Supplier Type", "Source footwear factory supplier in Quanzhou, Fujian, China"],
    ["Main Products", "Wide toe box comfort walking shoes, casual walking shoes, lightweight slip-on shoes, breathable knit/textile shoes"],
    ["Price Advantage", "Competitive factory quotation for 500+ pairs and recurring wholesale orders"],
    ["Customization", "Logo, insole, label, hangtag, shoe box and custom packaging can be discussed"],
    ["Quality Check", "Manual product checking before packing and pre-shipment checking can be discussed"],
    ["Shipping", "Express, air freight and sea freight can be quoted after quantity and destination are confirmed"],
  ];
  factory.getRange("A3:B9").format = { wrapText: true, borders: { preset: "inside", style: "thin", color: "#DDE7E5" }, verticalAlignment: "top" };
  factory.getRange("A3:A9").format = { fill: "#E7F4F1", font: { bold: true } };
  factory.getRange("A:A").format.columnWidthPx = 145;
  factory.getRange("B:B").format.columnWidthPx = 510;
  factory.getRange("A3:B9").format.rowHeightPx = 45;
  for (let i = 0; i < factoryThumbs.length; i += 1) {
    factory.images.add({
      dataUrl: await dataUrlForImage(factoryThumbs[i]),
      anchor: {
        from: { row: 11 + Math.floor(i / 2) * 8, col: (i % 2) * 3, rowOffsetPx: 4, colOffsetPx: 4 },
        extent: { widthPx: 190, heightPx: 135 },
      },
    });
  }

  const preview = await workbook.render({ sheetName: "30 Styles Catalog", range: "A1:L10", scale: 1, format: "png" });
  await fs.writeFile(path.join(buildDir, "under5mb_preview.png"), new Uint8Array(await preview.arrayBuffer()));
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(xlsxPath);
  await fs.rm(`${xlsxPath}.inspect.ndjson`, { force: true });
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true });
  const under5Manifest = JSON.parse(await fs.readFile(under5ManifestPath, "utf8"));
  const products = under5Manifest.products;
  const factoryThumbs = under5Manifest.factoryThumbs;

  const xlsxPath = path.join(outputDir, "Gabriel_Beiqiang_30_Styles_Catalog_Under5MB.xlsx");
  await buildWorkbook(products, factoryThumbs, xlsxPath);
  await fs.writeFile(assertInsideOutput(path.join(outputDir, "Gabriel_Quotation_Message.txt")), quoteMessage(), "utf8");
  await fs.writeFile(
    assertInsideOutput(path.join(outputDir, "README_upload_under5MB.txt")),
    "This is the lightweight upload package for Gabriel. The Excel includes compressed product thumbnails, factory information, and quotation message. Full-resolution photos/videos can be sent after Gabriel selects styles.\n",
    "utf8",
  );

  console.log(JSON.stringify({
    outputDir,
    xlsxPath,
    productCount: products.length,
    factoryThumbs: factoryThumbs.length,
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
