"""Register the authored BQ028 example in local task state; no external execution.

This is a reviewed fixture, not a general campaign-writing model. Other tasks use
host reasoning and commerce_submit_artifact with their own current evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from commerce.runtime import Engine, discover_workspace

def run(workspace=None):
    envelope = json.loads((ROOT / "examples/bq028-campaign.request.json").read_text(encoding="utf-8"))
    content_path = ROOT / "examples/bq028-campaign.content.json"
    content = json.loads(content_path.read_text(encoding="utf-8"))
    engine = Engine(discover_workspace(workspace))
    # Changed example content gets a new object; repeated execution resumes its
    # own completed steps rather than overwriting another task or old review.
    key = envelope["idempotency_key"] + "-" + hashlib.sha256(content_path.read_bytes()).hexdigest()[:12]
    task = engine.create_task(envelope["request"], key)
    if task["status"] == "needs_refresh":
        raise RuntimeError("Existing task sources changed. Review those changes and refresh explicitly; this example does not auto-approve a refreshed task.")
    def submit(step, data):
        nonlocal task
        if step["state"] == "completed":
            return
        task = engine.submit_artifact(task["id"], step["id"], data, task["revision"])
    for original in list(task["steps"]):
        step = next(s for s in task["steps"] if s["id"] == original["id"])
        if step["state"] == "completed":
            continue
        if step["executor"] == "runtime":
            task = engine.run_step(task["id"], step["id"], task["revision"])
            continue
        data = {"kind": step["artifact_kind"]}
        if step["id"] == "positioning":
            p = content["positioning"]
            data.update({k: v for k, v in p.items() if k != "differences"})
            data.update(claim_evidence=content["sources"], unconfirmed=content["unconfirmed"],
                        channel_differences={p["target"]["id"]: content["positioning"]["differences"][p["target"]["platform"] + "_" + p["target"]["placement"]] for p in task["strategy"]["targets"]})
        elif step.get("target"):
            target = step["target"]
            authored = content["deliverables"][target["platform"] + "_" + target["placement"]]
            data.update({k: v for k, v in authored.items() if k != "variants"})
            data.update(target_id=target["id"], platform=target["platform"], placement=target["placement"], language=target["language"], market_scope=target["market_scope"], customer_segment=target["customer_segment"], claim_evidence=content["sources"], unconfirmed=content["unconfirmed"])
            if "variants" in authored:
                data["variants"] = [{"variant_id": v["variant_id"], **authored["variants"][v["style"]]} for v in step["target_profile"]["variants"]]
        elif step["id"] == "experiment":
            data.update(summary="初步方向筛选与同方向开头测试分两轮；平台数据各自留存，当前无基线和效果结论。", experiments=[])
            for row in task["experiment_outline"]["rows"]:
                target = next(p["target"] for p in task["strategy"]["targets"] if p["target"]["id"] == row["target_id"])
                data["experiments"].append(dict(target_id=row["target_id"],
                    hypothesis="这一位置的受众能从当前商品/内容理解下一步选择；有数据后验证，不以草稿质量预测转化。",
                    variable="第一轮比较不同呈现方式，视为探索；选出方向后第二轮仅改开头，其它事件与时长保持一致。" if target["placement"] in ("short_video", "note", "product_video") else "商品页第一信息顺序；其它字段和商业条件保持一致。",
                    primary_metric=row["primary_metric"], baseline=None, hold_constant=row["hold_constant"],
                    data_needed="实际账号/页面数据、同一口径与时间窗、受众与投放条件、商品点击和后续有效询盘或订单归因；缺数据不报效果。",
                    stop_rule="先取得实际基线与预算再设测试门槛；产品错绑或主张无证据时停止。按明确观察窗复核主要指标和下游结果，不因单次播放高自动推广。"))
        elif step["id"] == "review":
            evidence = dict(audience="国外采购、国内消费者和国内经销/品牌客户分别路由；当前示例的国内内容选消费者，网站保留B2B。", platform_fit="当前范围、已开始/未开始、未来选项及连接分别记录；Amazon排除，小红书和微信仅准备，未形成发布请求。",
                claims="真实资料和虚构人物感受分开；价格库存、美国尺码、测试及自产主张不臆填。", creative_difference="生活因果、选择信息、试穿与细节各有具体事件/图页；并非只换平台名称。",
                asset_feasibility="参考职责、动作接触和图文素材差异已列；这是制作方案检查，未证明新生成质量。", measurement="基线为null、归因待取得；方向探索与单变量测试分开，跨渠道不加总。",
                handoff="仅交付方案；用户认可影片基线保持，未付费生成、发布、改平台字段或发送。")
            data.update(summary="已完成草稿范围审核，可以交给负责人阅读；不是用户批准或商业效果验收。", reviewer="agent", decision="ready_for_user_review",
                        target_checks={p["target"]["id"]: {k: dict(status="pass", evidence=v) for k, v in evidence.items()} for p in task["strategy"]["targets"]})
        submit(step, data)
    exported = engine.export_task(task["id"])
    result = dict(task_id=task["id"], status=task["status"], revision=task["revision"], targets=len(task["strategy"]["targets"]),
                  creative_variants=sum(len(content["deliverables"][p["target"]["platform"] + "_" + p["target"]["placement"]].get("variants", {})) for p in task["strategy"]["targets"]),
                  export=exported, published=task["platform_published"])
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace")
    args = parser.parse_args()
    print(json.dumps(run(args.workspace), ensure_ascii=False, indent=2))
