# 竞品公司与出口商反查

初查日：2026-10-26；最新店铺补查：2026-11-02（北京时间）。本页扩展现有竞品研究，不新建CRM。**28家研究对象中，26家国际站店铺页面直接显示对应公司名称；另有2家未列入当前店铺清单。** 海外潜客、联系方式、提单关系及评分留现有客户发现助手的本地受控数据区。

数据入口：[候选JSON](competitors.json)、[候选CSV](competitors.csv)、[名称与别名检索CSV](aliases.csv)、[逐来源证据与访问限制](evidence.json)。工作台“客户开发 → 同行找客户”直接读取该名单，并关联本地受控买家研究；本机另有[海关数据查询公司名单.xlsx](海关数据查询公司名单.xlsx)。旧研究的商品、目录与图片证据继续保留在原位置，本表只引用。

## 2026-11-02：中文公司检索名

通过公开搜索和现有Firecrawl官方API补查，10家已有可引用的中文检索名：厦门凯顺贸易有限公司、东莞市爱美成鞋业有限公司、泉州泰汇鞋业有限公司、晋江科拓鞋业有限公司、泉州盛博进出口贸易有限公司、宜福（晋江）贸易有限公司、重庆朗驰鞋业有限公司、台州琳峰鞋业股份有限公司、泉州维升进出口贸易有限公司、洛阳锦世源进出口有限公司。其余店铺尚无足够可靠的中文对应依据，不按英文直译填充。工作台直接展示可复制的名称、已取得的信用代码和来源；查询海关时仍须对照公司地址、货描和日期。

追加定向检索时部分Firecrawl请求返回429，不能将这些请求算作“查无记录”；后续应降低并发、分次查公开资料，并优先用英文名、地址和店铺信息核对付费数据库或工商来源。

厦门凯顺的历史LEI资料与英文贸易档案地址相同；泉州泰汇的[商标申请资料](https://tm.aliyun.com/detail/172f_92568154_25)与店铺英文登记地址的搜索索引、贸易目录门牌相同，部分AI摘要写作“泰辉”不采用。重庆朗驰的第三方中文公司资料与国际站英文主体成立日期一致。东莞爱美成的中文名与信用代码见[东莞市市场监管局历史公开文件](https://dgamr.dg.gov.cn/scjdgl/1200/201911/45d90caf8a5c40179befc15f86043445/files/c842ae8a84da4fb6aaf67747457718ba.pdf)，中英文公司和历史地址另有公开资料对应；宜福（晋江）的中文名、英文名及2012年成立年份可由第三方资料和展会资料对应。泉州盛博的中文名和信用代码可与[Bloomberg历史LEI记录](https://lei.bloomberg.com/leis/view/8368002MF2ZL9TTUL215)及英文公司历史地址交叉对应；两份LEI记录均已过期，不能据此判断公司当前状态。台州琳峰的[中英文名称](https://www.cnverify.com/company/Taizhou-Linfeng-Shoes-Co-Ltd)有中国轻工商会2025年名单的搜索索引佐证，但原PDF本次返回403。泉州维升、洛阳锦世源的第三方信息与国际站供应商资料成立日期一致；洛阳锦世源完整中文名来自搜索索引，另一缓存版本对名称有脱敏。晋江科拓沿用既有第三方资料，地址楼层存在差异。各条精确来源及限制见JSON的`company_zh_evidence`和[evidence.json](evidence.json)；这些均不等同于本次查到营业执照或工商实时回读。

## 2026-11-02：店铺重新核实

26家当前名单逐一实读国际站店铺首页并核对英文公司名，来源和核对日期随各公司保存在 `competitors.json` 的 `store_verification` 中。Fujian Fuyu只核到官网，未找到对应国际站店铺；Quanzhou DHD Global虽然有平台旧目录及店铺链接，但本次打开店铺入口返回搜索页，未确认当前可用。两者仍留研究池，暂不列入可直接查看的店铺清单。

原表误把Shijiazhuang Jinchen与galler店直接对应；本轮店铺首页显示该公司的是 [jchshoes](https://jchshoes.en.alibaba.com/)，原galler链接和原商品链接保留为历史线索，不合并。Langchi与Langji分别有店铺，不因名称相近合并。页面中的单款sold及其缓存、统计周期与整店销量均需区分；没有可复核数字的店铺不宣称销量高。国际站店铺与公司名对应，也不等于已核实每条海关记录的出口主体。

同日补入 [Quanzhou Weshine](https://weshineshoes.en.alibaba.com/) 与 [Luoyang Jinshiyuan](https://jsyshoes.en.alibaba.com/)，两家首页分别显示公司名及针织、休闲鞋方向；[Accio聚合页](https://www.accio.com/plp/nike-zoom-streak-fly)对应单款分别显示906和330 sold，统计周期未知，并非整店销量或实时海关数据。该页另显示Kaisun单款600 sold；国际站[公开索引](https://www.alibaba.com/picks/shoes-swiss.html)显示Yongge单款318 sold，均按来源性质展示，不据此推定实际出口买家。

## 2026-11-01：高销量线索与贸易反查补充

EX013 Quanzhou Simble 的[国际站搜索索引](https://www.alibaba.com/countrysearch/CN/mens-shoes-sneakers.html?intention_id=30ba6efb9e2e4cdeb7450916415c0347)显示一款男士休闲运动鞋“489 sold”；本次打开该页未返回该商品正文，数字和统计周期未能独立复核，只作优先研究线索，不当成当前月销量或整店销量。[官网](https://www.simblefootwear.com/)展示相近英文名及休闲运动鞋，贸易页有同名截断出口方和休闲鞋逐票；店铺主体与出口方地址关系仍需核。海外候选、逐票和各对象下一步保存在[本地客户研究](../../../04_客户开发/02_目标名单/.local/客户发现助手/海关反查/README.md)，不把关联聚合数当鞋类订单。

EX021 Quanzhou DHD Global Trading 在[国际站旧目录](https://www.alibaba.com/oem-shoes-wholesale-suppliers.html)有完整英文名、休闲鞋方向及店铺链接；[同名贸易页面](https://www.importinfo.com/quanzhou-dhd-global-trading-co-ltd)有鞋类逐票。店铺与贸易主体地址尚待交叉核对，该目录没有可核的当前销量。EX011 Yiwu Yongge 的[公开分类页缓存](https://www.alibaba.com/countrysearch/CN/sneaker.html)曾显示一款鞋 296 sold，缓存和统计周期不等于实时销量；本轮未找到同名双方均可读的鞋类提单，继续留在研究池。

本轮补入 EX022 Wenzhou Sipcope、EX023 Wenzhou Better Outdoor、EX024 Quanzhou Xiangchen、EX025 Chongqing Langji 和 EX026 Quanzhou Benmiao。平台搜索索引分别显示 Sipcope 一款男士休闲鞋318 sold、Better一款厚底休闲鞋151 sold、Xiangchen一款高帮鞋76 sold、Langji一款鞋750 sold；EX018 Langchi另有一款鞋256 sold。它们都是单品搜索缓存，统计周期未知，直接页面不一定在本次返回相同卡片，不能当整店销量或所有买家采购数量；Langji与Langchi不自动合并。Sipcope的同名贸易样本含青少年休闲鞋，海外收货人留本地客户研究。

## 覆盖与证据等级

原20家包括11家既有研究对象、9家新发现候选，后补EX021—026。2026-11-01时部分只取得类别搜索卡片；最新店铺对应以本页2026-11-02结论及JSON为准。不能把全部候选写成都有已核鞋类出口记录。

- E1：搜索结果正文、摘要或原本地历史研究。适合发现线索，仍须回原页核查；保留查询日及原证据日期。
- E2：本轮实际打开可读的官方/平台结构字段或公开企业目录。只证明该页面显示的身份/产品表述；第三方目录不是官方工商登记。
- E3：具体贸易行或买方发布的供应链名单，经名称、地址、货描和角色交叉核对。此等级在受控潜客研究维护，本候选表不因平台有同名记录自动升级。

`access_mode`写明本轮工具返回情况。公开搜索的抓取日期常早于本次核验日，`checked_date`不是记录/交易发生日。搜索与open可能返回不同缓存版本，不据此计算增长，也不把索引卡sold当当前销量。`source_urls`保留外链或已有本地证据位置。

## 十家优先调查结论

| ID | 主体检索用名 | 当前对应证据 | 缺口与下一步 |
| --- | --- | --- | --- |
| EX001 | Xiamen Kaisun Trading Co., Ltd. | 10/28 Firecrawl官方API实读kaisuntd首页，出现同英文名及Barefoot/Casual类目，首页升为E2；原544条目录保留原证据日期 | company_profile页返回滑块，登记地址与出口方对应仍未核。贸易关系须按逐票鞋类货描、地址及日期筛，不汇总全部同名交易 |
| EX002 | Xiamen Golden Heymann Import & Export Co., Ltd. | 原店/针织商品对应；本轮实读第三方公司目录，写Trading Company | 目录地址与历史提单地址不同；中文/信用代码、实际生产厂未确认。旧出口票只能证明该历史样例 |
| EX003 | Dongguan Ai Mei Cheng Shoes Co., Ltd. | 原amcshoes店/女士针织商品；公开资料对应东莞市爱美成鞋业有限公司，历史政府文件列出信用代码 | 品牌合作仅供应商故事自述，不能当买方确认；2002创业与2013登记信息分开，工商现状及提单主体仍须核 |
| EX004 | Shijiazhuang Jinchen Technology Co., Ltd. | 2026-11-02直接实读jchshoes首页，显示该公司名和鞋类；原galler店与本公司关系未证 | 不合并galler或同名交易；出口方地址仍须核对。平台AI Overview不作来源 |
| EX008 | Shenyang Hengshengwei Trading Co., Ltd. | 本轮实读套脚鞋商品页，供应商链接指向bairuilun.m；介绍明确贸易公司 | formerly Shenyang Flying Footwear Industry仅供应商自述旧名；BAIRUILUN是品牌，实际出口主体与工厂未核 |
| EX012 | Jinjiang Keytop Shoes Co., Ltd. | 本轮实读Alibaba结构页，Contact Supplier明确ketuoshoes；Tendata有中文名与信用代码 | 中文及代码为第三方资料，待国家企业信用信息公示系统/营业执照核；地址2楼/3楼冲突，保留而不抹平 |
| EX013 | Quanzhou Simble Import And Export Trading Co., Ltd. | 本轮实读Alibaba结构页并明确链接simblecn；官网页眉版权用同名 | 官网About正文用Quanzhou Simble Footwear Co., Ltd.；属关联用名线索，非同一法人证明。2001与2015年份不能自动选一个 |
| EX014 | Xiamen Jieruixin Trading Co., Ltd. | 本轮实读Alibaba结构页，明确链接jerycen；Trade栏显示市场自述 | 平台AI段落误写纺织服装且规模字段相互可疑，不采为制造实力；中文、登记地址及逐票出口方待核 |
| EX015 | Guangzhou Hotmarzz Trading Co., Ltd. | Alibaba搜索公司页正文有拖鞋、洞洞鞋产品及英文全名 | 本轮open空正文；2022成立与21年经验口径待核；Hotmarzz Network Technology同词商标主体不自动关联 |
| EX016 | Fujian Fuyu Technology Co., Ltd. | 本轮实读fuyufootwear官网，产品为EVA/PVC拖鞋、凉鞋和花园鞋 | 未确认Alibaba店。官网页脚Anhai/Tonglin与买方名单Neikeng地址需追溯历史/法人；不凭同名跨址并表 |

## 公司与别名索引的用法

`aliases.csv`含英文全名、大小写/标点/AND检索变体，以及少量公开用名。规范化变体只是查询输入，不证明法定历史名称。每个变体单独查询；结果为零不表示无出口。检索顺序为全名→无标点→AND/&变体→有出处的其他用名；有中文证据时再查中文。禁止自行翻译中文公司名作为已核事实。

公司、店铺、品牌、出口方、生产厂和收款主体分别记录。目前未取得官方工商完整资料；EX001、EX003、EX012、EX013、EX018和EX027已有历史政府、第三方或历史LEI明文信用代码，来源和实时性限制见上。官网提到的生产厂/合作品牌也不直接确认为同一法人或已成交客户。

## 可重复的反查流程

1. 从本表挑P1，回对应商品/店铺确认本次研究品类；旧卡价格、MOQ、成交信号不当现值。贝强产品匹配回产品中心与单款证据，尤其宽楦、免手穿脱和材料。
2. 按别名逐项查贸易平台，保留查询名、平台、日期、URL、访问结果。未命中、空正文、登录限制、付费墙分开；不绕过限制。
3. 提取具体票号/日期/发货方/收货方/通知方/货描/HS/数量重量；平台公司聚合页记录不能替代具体鞋类票。核地址与主体，纸品、家具、货代记录不得混成鞋买家。
4. 买方回官网核品类、国家、角色与公开供应商入口。供应商自述品牌合作、公开名单与报关交易分别标注；通知方不自动算采购商。
5. 无具体交易时可走品类匹配路线，明确标“品类匹配潜客”；不得写“竞品客户”。买家反查其他鞋供应商可保留独立关系边。
6. 海外对象进入现有客户发现助手本地候选区，用其官网域名稳定ID及原CRM精确域名/邮箱核对。人工核同名、品牌异名、母子公司与停止联系记录后才考虑正式Lead；不生成自动发送队列。
7. 单条关系保留原始事实、推断及反证。收费平台采购前先用这10家的全名和地址要求演示具体鞋类提单；演示命中率、日期和可导出字段确认后再评估费用。

## 本轮访问限制与人工入口

10/26初查时，7家原店首页正常公开open返回0行；AMC官网502/超时、Jinchen官网超时，保留当时访问记录。10/28使用现有密钥的Firecrawl官方API已读Kaisun首页，但company_profile返回滑块内容，未绕过。HTTP200不等于主体详情可读；首页与档案页分别记入evidence.json，其他对象不自动刷新核查日。具体贸易样本及原回读留现有本地受控研究区。

人工最小补充是优先主体的营业执照或官方工商结果、正常可见的公司页地址与出口方英文拼写；并非要求全店扫描。对Fuyu、Simble的地址/名称差异，应先取得对应关系证据再合并贸易记录。没有数据不推断没有出口。
