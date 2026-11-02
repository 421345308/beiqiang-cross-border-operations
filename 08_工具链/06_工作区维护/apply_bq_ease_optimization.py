"""Retired entry point for applying the old BQ title-draft queue.

Its fixed target list and draft payloads are historical; current product
information and the current channel SOP govern any new title changes.
Historical requests and readbacks remain in the corresponding product records.
"""


def main():
    raise SystemExit(
        "旧版 BQ 标题队列已停用；请依据国际站现行商品 SOP 和当前逐商品"
        "事实重新处理，历史请求与回读保留在对应商品记录中。"
    )


if __name__ == "__main__":
    main()
