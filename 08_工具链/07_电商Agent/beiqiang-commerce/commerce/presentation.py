"""Human-readable review output; implementation payloads remain in local evidence."""
import json

LABELS = {
    "title": "标题", "description": "正文", "bullet_points": "要点", "inquiry_prompt": "询盘问题", "commercial_fields": "商业字段",
    "brand": "品牌", "variation_theme": "变体主题", "us_size_mapping": "美国尺码对应", "price": "价格", "inventory": "库存",
    "acting": "表演", "motion": "动作与接地", "props": "道具与接触", "continuity": "连续性", "claims": "主张证据", "review_scope": "核验范围",
    "authenticity": "真实性", "layout": "版面", "identity": "商品身份", "information": "选择信息", "measurement": "效果衡量",
    "product": "商品外观", "performance": "性能边界", "audience": "受众", "platform_fit": "平台适用", "creative_difference": "呈现差异", "asset_feasibility": "素材准备", "handoff": "交付状态"
}

def label(name):
    return LABELS.get(name, name)

def shown(value):
    if value is None:
        return "待核"
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "；".join(shown(v) for v in value)
    return json.dumps(value, ensure_ascii=False)

def bullets(values):
    return ["- " + shown(v) for v in values]

def artifact_lines(data, profile=None):
    kind = data.get("kind")
    lines = [data.get("summary", ""), ""]
    if kind in ("identity", "strategy"):
        return lines
    if kind in ("title_draft", "listing_draft", "channel_listing"):
        if data.get("title"):
            lines += ["**标题**：" + data["title"], "", data.get("rationale", ""), ""]
        for field, value in data.get("fields", {}).items():
            lines += ["**" + label(field) + "**：" + shown(value), ""]
        if data.get("image_roles"):
            lines += ["图片职责：", "", *bullets(data["image_roles"]), ""]
        if data.get("schema_status"):
            lines += ["平台字段准备度：" + data["schema_status"], ""]
    elif kind == "positioning":
        lines += ["产品参与：" + data["product_role"], "", "受众：", "", *bullets(data["audiences"]), "", "使用场景：", "", *bullets(data["use_cases"]), ""]
        lines += ["渠道差异：", "", *["- " + k + "：" + shown(v) for k, v in data["channel_differences"].items()], ""]
    elif kind == "channel_content":
        names = {v["variant_id"]: v["name"] for v in profile.get("variants", [])} if profile else {}
        for v in data["variants"]:
            lines += ["### " + v.get("name", names.get(v["variant_id"], v["variant_id"])), "",
                      "开头：" + v["hook"], "", "产品参与：" + v["product_role"], "",
                      *bullets(v["beats"]), "", "结尾：" + v["ending"], "", "声音：" + v["sound"], "", "下一步：" + v["cta"], "",
                      "素材职责：", "", *bullets(v["asset_plan"]), "", "检查：", "", *["- " + label(k) + "：" + shown(value) for k, value in v["production_checks"].items()], ""]
    elif kind == "landing_page":
        lines += [*bullets(data["sections"]), "", "入口承接：" + data["message_match"], "", "下一步：" + data["cta"], ""]
    elif kind == "video_brief":
        for s in data["scenes"]:
            lines += [f"- {s['start']}—{s['end']}秒：{s['action']}"]
        lines += ["", "检查：", "", *["- " + label(k) + "：" + shown(v) for k, v in data["production_checks"].items()], ""]
    elif kind == "experiment_plan":
        for e in data["experiments"]:
            lines += ["### " + e["target_id"], "", "假设：" + e["hypothesis"], "", "主要变化：" + e["variable"], "",
                      "主要指标：" + e["primary_metric"] + "；基线：" + shown(e["baseline"]), "", "保持不变：" + shown(e["hold_constant"]), "",
                      "数据缺口：" + e["data_needed"], "", "停止/继续判断：" + e["stop_rule"], ""]
    elif kind in ("review", "campaign_review"):
        groups = data.get("target_checks", {"当前任务": data.get("checks", {})})
        for name, checks in groups.items():
            lines += ["### " + name, "", *["- " + label(key) + "：" + value["status"] + "；" + value["evidence"] for key, value in checks.items()], ""]
        lines += ["上述为代理对方案的审核，不代表用户批准、成片验收或平台发布。", ""]
    elif kind == "operations_plan":
        for key in ("observations", "hypotheses", "actions", "missing_data"):
            lines += ["**" + key + "**", "", *bullets(data[key]), ""]
    elif kind == "customer_draft":
        lines += [data["message"], "", "下一步：" + data["next_action"], "", "当前为草稿，未发送。", ""]
    if data.get("unconfirmed"):
        lines += ["待核项：", "", *bullets(data["unconfirmed"]), ""]
    return lines
