const csrf = document.querySelector("meta[name=csrf]").content;
let state = {
  skus: [],
  orders: [],
  lines: [],
  movements: [],
  audit: [],
  models: [],
};
const $ = (id) => document.getElementById(id);
const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
function toast(text) {
  $("message").textContent = text;
  $("message").classList.remove("hidden");
  setTimeout(() => $("message").classList.add("hidden"), 7000);
}
async function call(path, data) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify(data),
  });
  const result = await r.json();
  if (!r.ok) throw Error(result.error);
  toast(result.message);
  await refresh();
}
function table(headers, rows) {
  return rows.length
    ? "<table><thead><tr>" +
        headers.map((x) => "<th>" + esc(x) + "</th>").join("") +
        "</tr></thead><tbody>" +
        rows
          .map(
            (row) =>
              "<tr>" +
              row.map((cell) => "<td>" + cell + "</td>").join("") +
              "</tr>",
          )
          .join("") +
        "</tbody></table>"
    : '<div class="empty">暂无记录</div>';
}
function renderSkus() {
  const q = $("search").value.toLowerCase();
  const rows = state.skus.filter((x) =>
    [x.code, x.model, x.title, x.color, x.size].some((v) =>
      v.toLowerCase().includes(q),
    ),
  );
  $("skuTable").innerHTML = table(
    ["SKU / 型号", "渠道名称", "颜色 / 尺码", "价格", "可用库存", "操作"],
    rows.map((x) => [
      esc(x.code) + '<br><span class="muted">' + esc(x.model) + "</span>",
      esc(x.title),
      esc(x.color) + " / " + esc(x.size),
      "¥" + (x.price_cents / 100).toFixed(2),
      esc(x.stock),
      '<button class="secondary" data-edit="' + esc(x.code) + '">编辑</button>',
    ]),
  );
}
function options() {
  return state.skus
    .map(
      (x) =>
        '<option value="' +
        esc(x.code) +
        '">' +
        esc(x.code + " " + x.color + " " + x.size + "（可用" + x.stock + "）") +
        "</option>",
    )
    .join("");
}
function addLine() {
  const node = document.createElement("div");
  node.className = "line-entry";
  node.innerHTML =
    '<select class="skuSelect" required>' +
    options() +
    '</select><input type="number" min="1" step="1" value="1" required><button type="button" class="secondary">移除</button>';
  node.querySelector("button").onclick = () => node.remove();
  $("orderLines").append(node);
}
function auditDetail(x) {
  try {
    const d = JSON.parse(x.detail);
    if (x.action === "保存SKU") {
      const f = d.fields;
      return (
        "型号 " +
        f[1] +
        "，名称 " +
        f[2] +
        "，" +
        f[3] +
        " / " +
        f[4] +
        "，价格 ¥" +
        (f[5] / 100).toFixed(2)
      );
    }
    if (x.action === "库存调整")
      return "变化 " + d.delta + "，余额 " + d.balance + "，依据：" + d.note;
    if (x.action === "创建订单")
      return (
        d.lines.map((l) => l[0] + " × " + l[1]).join("；") + "。来源：" + d.note
      );
    if (x.action === "订单状态")
      return (
        d.from + " → " + d.to + (d.tracking ? "，凭证：" + d.tracking : "")
      );
    return x.detail;
  } catch {
    return x.detail;
  }
}
async function refresh() {
  const r = await fetch("/api/state");
  if (!r.ok) throw Error("读取状态失败");
  state = await r.json();
  $("mode").textContent = state.demo
    ? "演示模式：商品、价格、库存与订单均为测试数据，不代表真实商品、实物库存或交易。"
    : "正式本地模式：资料由操作员登记，商品身份引用产品台账；抖店尚未连接。";
  $("skuCount").textContent = state.skus.length;
  $("stockCount").textContent = state.skus.reduce((a, x) => a + x.stock, 0);
  $("pendingCount").textContent = state.orders.filter(
    (x) => x.status === "待发货",
  ).length;
  $("amountCount").textContent =
    "¥" +
    (
      state.orders
        .filter((x) => x.status !== "已取消")
        .reduce((a, x) => a + x.total_cents, 0) / 100
    ).toFixed(2);
  const model = $("modelSelect").value;
  $("modelSelect").innerHTML = state.models
    .map((x) => "<option>" + esc(x) + "</option>")
    .join("");
  if (state.models.includes(model)) $("modelSelect").value = model;
  document.querySelectorAll(".skuSelect").forEach((el) => {
    const v = el.value;
    el.innerHTML = options();
    if (state.skus.some((x) => x.code === v)) el.value = v;
  });
  renderSkus();
  $("movementTable").innerHTML = table(
    ["时间", "SKU", "变化", "登记余额", "依据"],
    state.movements.map((x) => [
      esc(x.created),
      esc(x.sku),
      esc(x.delta),
      esc(x.balance),
      esc(x.note),
    ]),
  );
  $("orderTable").innerHTML = table(
    ["订单", "商品", "金额", "状态", "物流凭证", "操作"],
    state.orders.map((x) => [
      esc(x.number) + '<br><span class="muted">' + esc(x.note) + "</span>",
      state.lines
        .filter((l) => l.number === x.number)
        .map((l) => esc(l.sku) + " × " + esc(l.quantity))
        .join("<br>"),
      "¥" + (x.total_cents / 100).toFixed(2),
      esc(x.status),
      esc(x.tracking),
      x.status === "待发货"
        ? '<div class="inline"><button data-ship="' +
          esc(x.number) +
          '">登记发货</button><button class="secondary" data-cancel="' +
          esc(x.number) +
          '">取消</button></div>'
        : "已处理",
    ]),
  );
  $("auditTable").innerHTML = table(
    ["时间", "操作", "对象", "详情"],
    state.audit.map((x) => [
      esc(x.created),
      esc(x.action),
      esc(x.object_id),
      '<span class="muted">' + esc(auditDetail(x)) + "</span>",
    ]),
  );
  if (!$("orderLines").children.length) addLine();
}
document.querySelectorAll("nav button").forEach(
  (b) =>
    (b.onclick = () => {
      document
        .querySelectorAll("nav button,.view")
        .forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      $(b.dataset.view).classList.add("active");
    }),
);
function bind(id, path, transform = (x) => x) {
  $(id).onsubmit = async (e) => {
    e.preventDefault();
    try {
      await call(path, transform(Object.fromEntries(new FormData(e.target))));
    } catch (err) {
      toast(err.message);
    }
  };
}
bind("skuForm", "/api/sku");
bind("stockForm", "/api/stock");
bind("orderForm", "/api/order", (x) => ({
  ...x,
  lines: [...$("orderLines").children].map((el) => ({
    code: el.querySelector("select").value,
    quantity: el.querySelector("input").value,
  })),
}));
bind("importForm", "/api/import", () => ({ csv: $("csvText").value }));
$("search").oninput = renderSkus;
$("addLine").onclick = addLine;
$("importToggle").onclick = () => $("importPanel").classList.toggle("hidden");
$("csvFile").onchange = async (e) => {
  if (e.target.files[0]) $("csvText").value = await e.target.files[0].text();
};
let pendingAction = null;
function openAction(number, status) {
  pendingAction = { number, status };
  $("actionTitle").textContent =
    status === "已取消" ? "确认取消本地订单" : "登记本地发货";
  $("actionText").textContent =
    status === "已取消"
      ? "取消订单 " + number + " 并返还预留数量。此操作仅改变本地记录。"
      : "订单 " + number + "：填写实际发货凭证。此操作不会通知抖店。";
  $("trackingValue").value = "";
  $("trackingValue").classList.toggle("hidden", status === "已取消");
  $("actionDialog").style.display = "flex";
  $("actionDialog").classList.remove("hidden");
  $("actionConfirm").focus();
}
function closeAction() {
  pendingAction = null;
  $("actionDialog").style.display = "none";
  $("actionDialog").classList.add("hidden");
}
$("actionDismiss").onclick = closeAction;
$("actionConfirm").onclick = async () => {
  if (!pendingAction) return;
  try {
    await call("/api/transition", {
      ...pendingAction,
      tracking: $("trackingValue").value,
    });
    closeAction();
  } catch (err) {
    toast(err.message);
  }
};
document.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.edit) {
    const row = state.skus.find((x) => x.code === b.dataset.edit);
    for (const key of ["code", "model", "title", "color", "size"])
      $("skuForm").elements[key].value = row[key];
    $("skuForm").elements.price.value = (row.price_cents / 100).toFixed(2);
  }
  if (b.dataset.cancel) openAction(b.dataset.cancel, "已取消");
  if (b.dataset.ship) openAction(b.dataset.ship, "已发货");
});
$("logoutButton").onclick = async () => {
  try {
    const response = await fetch('/api/logout', {
      method: 'POST', headers: {'Content-Type':'application/json', 'X-CSRF-Token':csrf}, body: '{}',
    });
    if (!response.ok) throw new Error('会话已失效，请刷新页面重新登录');
    location.reload();
  } catch (error) { toast(error.message); }
};
refresh().catch((err) => toast(err.message));
