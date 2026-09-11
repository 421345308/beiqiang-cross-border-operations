import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "file:///C:/Users/spq/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const outputDir = "C:/Users/spq/Desktop/贝强/02_Alibaba运营/05_扩品工程/批量发品/历史批次执行产物_2026-08-28至09-02/20260829_remaining_multilink_batches";
const names = (await fs.readdir(outputDir)).filter((name) => name.endsWith(".xlsx")).sort();
const results = [];
for (const name of names) {
  const fullPath = path.join(outputDir, name);
  const input = await FileBlob.load(fullPath);
  const workbook = await SpreadsheetFile.importXlsx(input);
  const sheets = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 2000 });
  const sheet = workbook.worksheets.getItemAt(0);
  const region = await workbook.inspect({ kind: "region", sheetId: sheet.name, range: "E1:K4", maxChars: 5000, tableMaxRows: 4, tableMaxCols: 7 });
  results.push({ name, sheets: sheets.ndjson, region: region.ndjson });
}
await fs.writeFile(path.join(outputDir, "artifact_tool_导入检查_2026-08-29.json"), JSON.stringify(results, null, 2), "utf8");
console.log(JSON.stringify({ checked: results.length, files: names }, null, 2));
