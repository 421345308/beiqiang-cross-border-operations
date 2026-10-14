"""Editorial channel/category/creative catalogs. These are recommendations, not live platform schemas or SKU facts."""

CATALOG_VERSION = "2026-10-14.1"

def placement(kind, focus, sections, metrics, families, cta, media_type=None):
    return dict(artifact_kind=kind, focus=focus, sections=sections, metrics=metrics, family_preferences=families, cta=cta,
                media_type=media_type or ("video" if kind == "channel_content" else "page"))

PLATFORMS = {
    "alibaba": {
        "name": "Alibaba国际站", "aliases": ["alibaba.com", "国际站", "阿里巴巴国际站"],
        "default_business_model": "b2b", "business_models": ["b2b"], "default_placement": "listing",
        "audience": "进口商、批发商、电商卖家及品牌采购", "source_ids": ["bq_sop"],
        "schema_basis": "本款当前类目Schema＋唯一商品SOP；采购条件逐对象核验",
        "placements": {
            "listing": placement("channel_listing", "选款及采购询盘", ["采购意图标题", "属性与SKU", "图像角色", "详情与供给证据", "询盘问题"], ["search_ctr", "qualified_inquiries", "sample_discussions"], {"trust": 3, "education": 2, "demo": 2}, "询问匹配款式、数量及样品条件"),
            "product_video": placement("channel_content", "让采购者看懂结构、使用和可核实供给", ["采购问题", "商品结构与用途", "实物/流程证据", "下一采购动作"], ["video_completion", "qualified_inquiries"], {"trust": 3, "demo": 3, "education": 2}, "进入明确SKU的样品或报价讨论"),
        },
        "live_status": {"read": "existing_official_client", "write": "existing_skill_outside_runtime"},
    },
    "douyin": {
        "name": "抖音/抖店", "aliases": ["抖音", "抖店", "doudian"], "default_business_model": "retail",
        "business_models": ["retail", "brand"], "default_placement": "short_video",
        "audience": "按内容兴趣或即时使用需求发现商品的人", "source_ids": ["douyin_video", "doudian_portal"],
        "schema_basis": "抖店类目/属性/资质/运费与SKU按商家当前门户；视频OAuth发布是另一权限",
        "placements": {
            "listing": placement("channel_listing", "货架购买信息", ["商品名称与类目", "真实规格与SKU", "主图/详情", "价格履约待核", "尺寸选购"], ["product_clicks", "paid_orders", "refund_rate"], {"demo": 3, "education": 2}, "查看款式尺码及已确认履约条件"),
            "short_video": placement("channel_content", "快速读懂具体处境与商品参与的变化", ["可见开头事件", "使用/试穿", "结果或笑点", "按目标选择收尾"], ["early_retention", "completion_rate", "product_clicks", "paid_orders"], {"narrative": 3, "demo": 3, "routine": 2}, "剧情可自然收束；转化版才引向已核商品"),
            "live_clip": placement("channel_content", "独立可理解的讲解片段", ["当下问题", "完整演示", "适合与不适合", "选购信息"], ["product_clicks", "paid_orders"], {"demo": 3, "education": 3}, "按观众问题选择尺码/版本"),
        }, "live_status": {"read": "not_connected", "write": "not_connected"},
    },
    "xiaohongshu": {
        "name": "小红书", "aliases": ["小红书", "xhs", "rednote"], "default_business_model": "retail",
        "business_models": ["retail", "brand"], "default_placement": "note",
        "audience": "搜索具体生活问题、比较选择和收藏经验的人", "source_ids": ["xhs_portal"],
        "schema_basis": "笔记、商品及广告合作分别核权限/字段；当前门户正文未取得，不写死接口或字数限额",
        "placements": {
            "note": placement("channel_content", "可搜索、可复用的场景经验", ["处境标题/封面", "选择标准", "细节/步骤", "适用边界", "实际结论"], ["search_impressions", "saves", "qualified_comments", "product_clicks"], {"education": 3, "routine": 3, "demo": 2}, "回答具体选择问题；不伪装买家评价", "image_text"),
            "video_note": placement("channel_content", "生活场景下的使用与选择", ["生活问题", "试用或穿搭", "细节证据", "经验结论"], ["completion_rate", "saves", "qualified_comments"], {"routine": 3, "education": 3, "demo": 2}, "说明适合什么场景与仍待确认的地方"),
            "listing": placement("channel_listing", "笔记承接后的真实商品信息", ["商品身份", "规格/尺码", "图库/详情", "履约与服务待核"], ["product_clicks", "paid_orders", "refund_rate"], {"demo": 2, "education": 2}, "选择真实版本与规格"),
        }, "live_status": {"read": "not_connected", "write": "not_connected"},
    },
    "amazon": {
        "name": "Amazon", "aliases": ["亚马逊", "amazon.com"], "default_business_model": "retail",
        "business_models": ["retail", "b2b"], "default_placement": "listing",
        "audience": "按搜索需求比较规格、用途和购买条件的人", "source_ids": ["amazon_listings"],
        "schema_basis": "marketplace＋productType动态JSON Schema；ASIN、卖家SKU、父子变体和offer分别处理",
        "placements": {
            "listing": placement("channel_listing", "匹配搜索意图并减少购买不确定性", ["标题", "要点与描述", "真实属性/变体", "图像与选购说明", "offer与履约待核"], ["search_ctr", "detail_conversion", "paid_orders", "return_rate"], {"demo": 3, "education": 3, "comparison": 2}, "确认具体变体与使用适配"),
            "product_video": placement("channel_content", "补足图片难以说明的使用与结构", ["产品/用途识别", "实际操作", "细节与尺度", "适配边界"], ["video_completion", "detail_conversion", "return_rate"], {"demo": 3, "education": 3, "aesthetic": 2}, "让使用、尺寸或版本选择更清楚；页面规范另核"),
        }, "live_status": {"read": "not_connected", "write": "not_connected"},
    },
    "storefront": {
        "name": "独立站", "aliases": ["独立站", "官网", "shopify", "website"], "default_business_model": "b2b",
        "business_models": ["b2b", "retail", "brand"], "default_placement": "landing_page",
        "audience": "由搜索、内容或广告进入网站，需要连贯选款与下一步的人", "source_ids": ["shopify_products", "bq_site"],
        "schema_basis": "先选站点技术栈/商业模式；当前贝强网站为B2B，不能自动改成Shopify零售站",
        "placements": {
            "landing_page": placement("landing_page", "广告/搜索承诺与页面信息一致", ["核心使用场景", "商品与主张证据", "选择说明", "服务/FAQ", "下一步入口"], ["landing_engagement", "qualified_inquiries", "checkout_conversion"], {"demo": 3, "trust": 3, "narrative": 2}, "B2B进入咨询；零售需真实offer和结算入口"),
            "listing": placement("channel_listing", "站内商品发现与版本选择", ["标题/slug", "规格/变体", "图片角色", "SEO摘要", "可核购买/咨询条件"], ["organic_clicks", "qualified_inquiries", "paid_orders"], {"demo": 2, "education": 3}, "按商业模式咨询或选购"),
            "brand_video": placement("channel_content", "品牌记忆与商品相关", ["品牌处境/世界", "商品参与", "可核细节", "行为结果或品牌收束"], ["video_completion", "landing_engagement", "qualified_inquiries"], {"narrative": 3, "aesthetic": 3, "trust": 2}, "收束到对应落地页，不套固定电商口播"),
        }, "live_status": {"read": "site_tools_outside_runtime", "write": "site_tools_outside_runtime"},
    },
    "tiktok": {
        "name": "TikTok", "aliases": ["tik tok"], "default_business_model": "b2b",
        "business_models": ["b2b", "retail", "brand"], "default_placement": "short_video",
        "audience": "海外短视频观众；贝强当前采购目标与零售消费者分别设定", "source_ids": ["bq_growth"],
        "schema_basis": "账号/受众/语言由项目选择，内容发布与Shop商品不同；沿用现有连接规则",
        "placements": {
            "short_video": placement("channel_content", "短事件或演示建立产品认知", ["具体开头", "演示/事件", "可核细节", "目标相关结果"], ["early_retention", "completion_rate", "qualified_inquiries", "product_clicks"], {"demo": 3, "narrative": 3, "trust": 2}, "采购内容与零售内容使用不同下一步"),
        }, "live_status": {"read": "not_connected", "write": "not_connected"},
    },
}

LENSES = {
    "footwear": {"name": "鞋类", "candidate_affordances": ["wearable", "in_use", "size_selection", "visual_detail"], "questions": ["什么使用场景？", "鞋型/尺码/穿脱证据是什么？", "怎样在正常动作中读清鞋？"], "failure_modes": ["鞋型漂移", "步态或接地异常", "主观舒服被写成性能证明"]},
    "apparel": {"name": "服装", "candidate_affordances": ["wearable", "styling", "visual_detail"], "questions": ["版型/尺码是否有真实依据？", "穿着动作是否可展示剪裁？"], "failure_modes": ["版型/花纹改变", "把穿搭偏好冒充所有人的效果"]},
    "beauty": {"name": "美妆个护", "candidate_affordances": ["routine", "sensory", "moving_parts"], "questions": ["实际使用步骤？", "可展示质地还是有验证功效？"], "failure_modes": ["伪造前后效果", "容器/开合机制错误", "未经证实的功效"]},
    "home_living": {"name": "家居生活", "candidate_affordances": ["in_use", "moving_parts", "visual_detail"], "questions": ["尺度与空间关系？", "装配/支撑和接触是否明确？"], "failure_modes": ["尺度不一致", "道具变形", "功能演示与实物不符"]},
    "electronics": {"name": "消费电子", "candidate_affordances": ["setup_steps", "in_use", "visual_detail"], "questions": ["接口/操作顺序？", "屏幕与实际反馈是否有原件？"], "failure_modes": ["伪造UI/接口", "缺少操作条件", "未测性能被当结论"]},
    "food_beverage": {"name": "食品饮料", "candidate_affordances": ["sensory", "routine", "moving_parts"], "questions": ["包装/份量/食用方式？", "口感主观描述与配料事实是否分开？"], "failure_modes": ["编造配料/健康效果", "食物物理形态错误"]},
    "accessories": {"name": "配饰", "candidate_affordances": ["styling", "visual_detail", "aesthetic_form"], "questions": ["佩戴/尺寸/材质证据？", "细节在什么尺度下可读？"], "failure_modes": ["扣件/文字漂移", "金属或材质被无依据推断"]},
    "general": {"name": "待分类商品", "candidate_affordances": [], "questions": ["是谁在什么场景使用？", "必须保持什么外观？", "实际操作与主张有何证据？"], "failure_modes": ["由品类猜商品事实"]},
}

def route(name, family, categories, goals, affordances, complexity, hook, arc, proof, audio, ending, required_evidence=(), face_required=False):
    return dict(name=name, family=family, category_fit=categories, goal_fit=goals, affordances=affordances,
                complexity=complexity, hook=hook, story_beats=arc, proof=proof, audio=audio, ending=ending,
                required_evidence=list(required_evidence), face_required=face_required)

ROUTES = {
    "everyday_story": route("生活情节/轻喜剧", "narrative", ["footwear", "apparel", "home_living", "food_beverage"], ["discovery", "brand"], ["in_use", "wearable", "routine"], 3, "先发生一件能看懂的小事，人物处境通过动作出现", ["处境触发", "具体阻碍", "商品参与行动", "行为变化", "关系或情境收束"], "使用行为与主观感受，不能冒充长期功效", "现场口语优先；需要内心声时与口型分开", "剧情结果/位置交换；不自动加口号或费用笑话"),
    "problem_demo": route("具体问题→使用演示", "demo", ["footwear", "home_living", "electronics", "beauty"], ["consideration", "purchase", "inquiry"], ["in_use", "problem_demonstrable"], 2, "把真实使用问题放在第一个动作里", ["展示问题", "使用条件", "完整关键动作", "能看到的结果", "适用边界"], "演示确实能看见的部分；未知性能保留待测", "动作声＋一句生活反应或简短说明", "确认场景与版本，而非夸张万能结论"),
    "body_tryon": route("身体/手部试用与真实反应", "demo", ["footwear", "apparel", "accessories", "beauty"], ["consideration", "purchase"], ["wearable", "in_use", "styling"], 2, "直接进入穿好/用到的状态，展示一个完整动作", ["使用状态", "触感或活动", "细节", "主观反应", "适合的人/场景"], "演员主观体验；不伪造真实顾客购买或评价", "现场随口反馈可选，也可无露脸说明", "试过后再说感受，不列口号"),
    "selection_guide": route("选购问题/尺寸版本指南", "education", ["footwear", "apparel", "electronics", "home_living"], ["consideration", "purchase", "inquiry"], ["size_selection", "setup_steps"], 1, "提出具体选择问题，而非抽象卖点", ["选择条件", "标准及证据", "版本差别", "适合/不适合", "仍需核实的信息"], "实测尺寸/真实规格；缺少数据不编造建议", "清楚的说明声或字幕；术语按受众解释", "把观众带到正确版本与下一问题"),
    "routine_scene": route("一天中的使用场景", "routine", ["footwear", "apparel", "beauty", "food_beverage"], ["discovery", "consideration", "retention"], ["routine", "in_use", "wearable"], 2, "用明确时间/地点/动作说明为什么此刻要用", ["日常触发", "实际使用", "一处可读细节", "继续日常", "经验收束"], "场景适配，不能推断所有用户感受", "环境声和短口语，可用音乐但不吞对白", "回到生活行动，不强制硬卖"),
    "styling_options": route("不同场合/搭配呈现", "routine", ["footwear", "apparel", "accessories"], ["discovery", "consideration"], ["wearable", "styling", "color_selection"], 2, "让同一商品出现在两个不同但具体的场合", ["场合一", "搭配关键", "场合二", "商品身份保持", "选择建议"], "视觉搭配与主观风格；不创造不存在的颜色/SKU", "音乐节奏或场景声；避免动作加速失真", "按场景给选择，不把所有产品都拍成走秀"),
    "detail_hero": route("产品细节/质感展示", "aesthetic", ["footwear", "accessories", "beauty", "electronics", "home_living"], ["brand", "consideration"], ["visual_detail", "aesthetic_form"], 1, "以一个真实、可辨认的结构或表面引入", ["完整身份", "细节一", "使用尺度", "细节二", "整体收束"], "由原图/实拍支持的外观锚点；不凭视觉证明材料等级", "音乐/接触声可独立成立，不默认旁白", "产品完整状态或品牌世界收束，按平台目的选择CTA"),
    "unboxing_asmr": route("开盒/触感/ASMR", "sensory", ["beauty", "electronics", "accessories", "footwear", "food_beverage"], ["discovery", "brand"], ["moving_parts", "sensory", "visual_detail"], 2, "从清晰的接触、开合或材质声开始", ["支撑与接触", "开合", "物件出现", "一处使用细节", "完整物件"], "真实包装与开合路径；概念包装要标明", "纸/盒/触感等声音，保留真实接触节拍", "不让包装抢走产品；避免把开盒过程拖长"),
    "how_to": route("操作教程/步骤教学", "education", ["electronics", "home_living", "beauty", "food_beverage"], ["consideration", "retention"], ["setup_steps", "moving_parts", "in_use"], 2, "展示用户真正卡住的步骤", ["前提条件", "操作一", "操作二", "结果确认", "常见失误"], "真实说明书/操作参考；屏幕和反馈要可核", "动作与说明一一对应，不能只用旁白跳过关键动作", "完成操作或确认结果"),
    "grounded_comparison": route("有依据的条件比较", "comparison", ["footwear", "electronics", "home_living", "beauty"], ["consideration", "purchase", "inquiry"], ["size_selection", "visual_detail"], 2, "问一个可核对的差异，不先下胜负结论", ["相同条件", "维度一", "维度二", "取舍", "选择边界"], "双方原件/同条件记录；不虚构竞品缺陷", "比较项简短明确，保留不能比较的数据", "按需要选，不自动宣布本品全面胜出", ("comparison",)),
    "test_evidence": route("实测/验证证据", "trust", ["footwear", "electronics", "home_living", "beauty"], ["consideration", "inquiry"], ["verified_test"], 2, "提出一个有实际测试记录的问题", ["条件与方法", "过程", "真实结果", "局限", "适用范围"], "匹配该SKU的测试记录；不让生成视频充当测试", "说明真实条件，结果保持原口径", "用证据回答问题，不扩展功效", ("test",)),
    "factory_process": route("实物/工艺/采购证明", "trust", ["footwear", "apparel", "home_living", "accessories"], ["inquiry", "consideration"], ["verified_factory", "visual_detail"], 2, "从采购者关心的可核实流程或实物开始", ["产品与来源", "真实过程", "检查节点", "可供条件", "采购下一步"], "单款来源与实际工厂/流程记录；外采不冒充自产", "专业说明，必要术语解释给买家", "进入真实样品/定制讨论", ("factory",)),
}

SOURCES = {
    "anthropic": {"url": "https://github.com/anthropics/commerce-agents", "commit": "fd4d59224ab96b43c6dc6888207c67b3bd5a24cf", "license": "Apache-2.0", "read": "README/许可/backends/safety/backend/changes及catalog/marketing/performance Skills；gates/config/executor等作关键实现检索，其余已下载文件未声称完整阅读", "use": "独立实现后台能力分层、预备变更、身份/变体、缺数据留空和按需专业流程；未引入Claude运行库"},
    "supercmo": {"url": "https://github.com/SupercmoHQ/superCMO-skills", "commit": "a6dd060ed46132e1944b1dd38981cb9ffcc42fc8", "license": "Apache-2.0", "read": "广告制作技能与许可", "use": "参考商品部件/外观锚点、资产职责及任务接续；不继承固定模型/旁白/分段/packshot"},
    "shopify_example": {"url": "https://github.com/Shopify/claude-for-commerce-examples", "commit": "d68c7fa24f26ab138d8b4ccdd0488db140a6bfe6", "license": "Apache-2.0", "read": "仅README与许可，未阅读完整后端", "use": "商家后台与顾客购物助手分开；未安装或连接Shopify账户"},
    "amazon_listings": {"url": "https://developer-docs.amazon/sp-api/docs/manage-product-listings-guide", "status": "正文已读", "use": "动态商品类型Schema、ASIN/卖家SKU、提交与可购买/可发现分开"},
    "douyin_video": {"url": "https://open.douyin.com/platform/resource/docs/openapi/video-management/douyin/create/create-video", "status": "正文可读", "use": "视频发布Scope/OAuth与商品能力分开；未接账号"},
    "doudian_portal": {"url": "https://op.jinritemai.com/docs/guide-docs/1486", "status": "搜索可见，门户正文读取不完整", "use": "当前类目/商品接口需门户复核，不写死参数或调用"},
    "xhs_portal": {"url": "https://open.xiaohongshu.com/document/developer/file/33", "status": "动态门户未取得正文", "use": "保留笔记/商品不同准备包；执行字段与权限待实核"},
    "shopify_products": {"url": "https://shopify.dev/docs/api/admin-graphql/latest/mutations/productcreate", "status": "官方正文已读", "use": "产品/变体/发布渠道分别处理；Shopify只是可选站点提供方"},
    "bq_sop": {"path": "02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md", "use": "唯一国际站业务规则，现场读取"},
    "bq_site": {"path": "03_独立站/README.md", "use": "现有站点事实与B2B定位"},
    "bq_growth": {"path": "00_总控台/全渠道增长总控.md", "use": "现有渠道身份/数据/连接与执行范围"},
}
