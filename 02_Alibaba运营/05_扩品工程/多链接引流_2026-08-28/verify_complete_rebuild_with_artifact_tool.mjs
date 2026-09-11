import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "file:///C:/Users/spq/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const file = "C:/Users/spq/Desktop/贝强/02_Alibaba运营/05_扩品工程/批量发品/历史批次执行产物_2026-08-28至09-02/20260830_full_excel_rebuild/贝强53款159链接_国际站批量发品_完整重制_2026-08-30.xlsx";
const reportPath = "C:/Users/spq/Desktop/贝强/02_Alibaba运营/05_扩品工程/批量发品/历史批次执行产物_2026-08-28至09-02/20260830_full_excel_rebuild/artifact_tool_完整Excel导入检查_2026-08-30.json";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(file));
const sheet = workbook.worksheets.getItemAt(0);
const sheets = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 2000 });
const header = await workbook.inspect({ kind: "region", sheetId: sheet.name, range: "E1:K5", maxChars: 8000, tableMaxRows: 5, tableMaxCols: 7 });
const tail = await workbook.inspect({ kind: "region", sheetId: sheet.name, range: "E6419:K6422", maxChars: 8000, tableMaxRows: 4, tableMaxCols: 7 });
const result = { file, sheets: sheets.ndjson, header: header.ndjson, tail: tail.ndjson };
await fs.writeFile(reportPath, JSON.stringify(result, null, 2), "utf8");
console.log(JSON.stringify({ imported: true, sheet: sheet.name, reportPath }, null, 2));
