import argparse
import json
from copy import deepcopy
from pathlib import Path


FAQS = [
    (
        "Are you a factory or a trading company?",
        "We are a footwear factory supplier located in Quanzhou, Fujian, China, serving overseas B2B buyers.",
    ),
    (
        "What is your minimum order quantity?",
        "The current store baseline starts from 2 pairs. The applicable quantity, price and production arrangement are confirmed according to the selected style and order requirements.",
    ),
    (
        "Can I mix colors and sizes in one order?",
        "Mixed colors and sizes can be discussed, subject to current availability, size ratio and production confirmation.",
    ),
    (
        "Can I order samples before a bulk order?",
        "Samples can be arranged for quality checking. Sample price, courier charge and preparation time are quoted separately for the selected style before payment.",
    ),
    (
        "What is the standard packing for one pair?",
        "The current single-pair package baseline is 34 x 23 x 13 cm and approximately 0.5 kg. Order-specific packing is confirmed before shipment.",
    ),
    (
        "Do you support OEM and ODM customization?",
        "Logo, color, size ratio and packaging requirements can be discussed. Please provide your design and target quantity for production review.",
    ),
    (
        "What is the production lead time?",
        "The current store baseline is 31 days for 100 pairs. Final lead time depends on style, quantity, materials and customization requirements and is confirmed before order.",
    ),
    (
        "Can you provide a shipping quotation?",
        "Yes. Please provide the destination country, postal code, quantity and preferred trade term. Freight and delivery arrangements are confirmed separately for the current order.",
    ),
]
FAQ_COLUMN_PAIRS = [
    ("AC", "AD"), ("AE", "AF"), ("AG", "AH"), ("AI", "AJ"),
    ("AK", "AL"), ("AM", "AN"), ("AO", "AP"), ("AQ", "AR"),
]

SOURCE_DETAIL_IMAGES = {
    "BQ053 / 1888": [
        "https://sc04.alicdn.com/kf/Sb3b166d9a3df476ebd0ac3b41e91746b6/286385890/Sb3b166d9a3df476ebd0ac3b41e91746b6.jpg",
        "https://sc04.alicdn.com/kf/S319b270fdd134d6bb5ed66deb4c28b40L/286385890/S319b270fdd134d6bb5ed66deb4c28b40L.jpg",
        "https://sc04.alicdn.com/kf/S93c0372fe56544a98169dce8c602b494b/286385890/S93c0372fe56544a98169dce8c602b494b.jpg",
        "https://sc04.alicdn.com/kf/S0abcc56052034a4bbc60aef9cc974917O/286385890/S0abcc56052034a4bbc60aef9cc974917O.jpg",
    ],
    "BQ060 / A350": [
        "https://sc04.alicdn.com/kf/Sbc9549013cc548498eebfee6a568ffb4I/286385890/Sbc9549013cc548498eebfee6a568ffb4I.jpg",
        "https://sc04.alicdn.com/kf/Sbf79d80de1ba4549b7ceb8804dd08f2d7/286385890/Sbf79d80de1ba4549b7ceb8804dd08f2d7.jpg",
        "https://sc04.alicdn.com/kf/Se7484b7563954629a9f6e50e19d489165/286385890/Se7484b7563954629a9f6e50e19d489165.jpg",
        "https://sc04.alicdn.com/kf/S445fb790abce49f184e1de5b7ab76e3d6/286385890/S445fb790abce49f184e1de5b7ab76e3d6.jpg",
    ],
    "BQ061 / AA811": [
        "https://sc04.alicdn.com/kf/S19e4ebd13a944596a833eb1fa560dd289/286385890/S19e4ebd13a944596a833eb1fa560dd289.jpg",
        "https://sc04.alicdn.com/kf/S0fd61e2658a34e14afa797dac1b409d9G/286385890/S0fd61e2658a34e14afa797dac1b409d9G.jpg",
        "https://sc04.alicdn.com/kf/S1e9db7da3bc94b2da2243d7a2ecd7786B/286385890/S1e9db7da3bc94b2da2243d7a2ecd7786B.jpg",
        "https://sc04.alicdn.com/kf/S3c1f188198ae4384b4eac0ae0c66cf5f2/286385890/S3c1f188198ae4384b4eac0ae0c66cf5f2.jpg",
    ],
}


VARIANTS = {
    "BQ053 / 1888": [
        {
            "code": "BQ053-R1",
            "model": "BQ053-R1 / 1888",
            "title": "Wholesale High Top Knit Sock Sneakers Slip On Walking Casual Shoes PU Segmented Sole Model 1888 EU 35-45",
            "description": "High-top knit sock sneakers for wholesale walking and casual footwear programs. Slip-on construction, PU segmented sole, regular fit, EU sizes 35-45, and regular or fleece-lined photographed options. Buyer search focus: high top knit sneakers, sock shoes, slip on walking shoes and wholesale casual shoes.",
            "hero_url": "https://sc04.alicdn.com/kf/See85439c5acd43e4a022b42fcbf092664/286385890/See85439c5acd43e4a022b42fcbf092664.jpg",
            "gallery_extras": ["https://sc04.alicdn.com/kf/S680c4e088ddc44889d07eba33a0961d4V/286385890/S680c4e088ddc44889d07eba33a0961d4V.png"],
            "main_perm": [1, 2, 3, 4, 5, 0],
            "detail_perm": [0, 2, 1, 3],
        },
        {
            "code": "BQ053-W1",
            "model": "BQ053-W1 / 1888",
            "title": "Regular or Fleece Lined High Top Knit Sock Sneakers Winter Slip On Walking Shoes Wholesale Model 1888",
            "description": "High-top knit sock sneakers with photographed regular and fleece-lined options for winter and all-season sourcing. Slip-on construction, PU segmented sole, regular fit and the original EU 35-45 size range remain unchanged. Buyer search focus: fleece lined sneakers, winter sock shoes, high top walking shoes and wholesale slip on shoes.",
            "hero_url": "https://sc04.alicdn.com/kf/S3f07ad641cee4739a8aa8c5b564eec663/286385890/S3f07ad641cee4739a8aa8c5b564eec663.jpg",
            "gallery_extras": ["https://sc04.alicdn.com/kf/S3e3a9572ce594f1e8748a89821ac0499w/286385890/S3e3a9572ce594f1e8748a89821ac0499w.png"],
            "main_perm": [2, 3, 4, 5, 0, 1],
            "detail_perm": [0, 3, 1, 2],
        },
        {
            "code": "BQ053-O1",
            "model": "BQ053-O1 / 1888",
            "title": "OEM ODM Private Label High Top Knit Sock Sneakers Slip On Casual Walking Shoes Factory Wholesale Model 1888",
            "description": "OEM/ODM and private-label high-top knit sock sneaker program with photographed regular and fleece-lined options. PU segmented sole, regular fit and original EU 35-45 size range remain unchanged. Logo, color, insole and packaging requirements can be discussed by order quantity. Buyer search focus: OEM sneakers, private label shoes, factory wholesale footwear and custom logo walking shoes.",
            "hero_url": "https://sc04.alicdn.com/kf/S4e8f60302524413691fb80ceb0107ffap/286385890/S4e8f60302524413691fb80ceb0107ffap.jpg",
            "gallery_extras": ["https://sc04.alicdn.com/kf/S27c09bf8d8114d379104184ec342ad021/286385890/S27c09bf8d8114d379104184ec342ad021.png"],
            "main_perm": [5, 0, 1, 2, 3, 4],
            "detail_perm": [0, 1, 3, 2],
        },
    ],
    "BQ060 / A350": [
        {
            "code": "BQ060-W1",
            "model": "BQ060-W1 / A350",
            "title": "Wholesale Women's Breathable Knit Lace Up Walking Shoes Lightweight Casual Sneakers Rubber Plastic Sole A350",
            "description": "Women's breathable knit lace-up walking shoes with a lightweight rubber-plastic sole, regular fit, original EU 35-45 size range and three photographed colors. Buyer search focus: women's walking shoes, breathable knit sneakers, lightweight casual shoes and wholesale lace-up footwear.",
            "hero_url": "https://sc04.alicdn.com/kf/Sed15c41bf71d44179086d619e68d452dS/286385890/Sed15c41bf71d44179086d619e68d452dS.jpg",
            "gallery_extras": ["https://sc04.alicdn.com/kf/S84b846d1281d4066bc4a6622bc4fd940L/286385890/S84b846d1281d4066bc4a6622bc4fd940L.png"],
            "main_perm": [1, 2, 3, 4, 5, 0],
            "detail_perm": [0, 2, 1, 3],
        },
        {
            "code": "BQ060-T1",
            "model": "BQ060-T1 / A350",
            "title": "Women's Lightweight Travel Walking Shoes Breathable Knit Lace Up Casual Sneakers Factory Wholesale Model A350",
            "description": "Lightweight knit lace-up walking shoes positioned for travel, commuting and daily-use wholesale programs. Regular fit, original EU 35-45 size range, rubber-plastic sole and photographed black, black-white and off-white colors remain unchanged. Buyer search focus: travel walking shoes, lightweight sneakers, breathable casual shoes and wholesale women's footwear.",
            "hero_url": "https://sc04.alicdn.com/kf/Sa405877c023d4ce593fcf876d46ccf5ac/286385890/Sa405877c023d4ce593fcf876d46ccf5ac.jpg",
            "gallery_extras": ["https://sc04.alicdn.com/kf/Sf7d93e4ffa7344dba1ed808d9eda4dfek/286385890/Sf7d93e4ffa7344dba1ed808d9eda4dfek.png"],
            "main_perm": [2, 3, 4, 5, 0, 1],
            "detail_perm": [0, 3, 1, 2],
        },
        {
            "code": "BQ060-O1",
            "model": "BQ060-O1 / A350",
            "title": "OEM ODM Private Label Women's Knit Lace Up Walking Shoes Lightweight Casual Sneakers Factory Wholesale A350",
            "description": "OEM/ODM and private-label knit lace-up walking shoe program for importers, wholesalers and online sellers. Rubber-plastic sole, regular fit, original EU 35-45 size range and photographed colors remain unchanged. Logo, color, insole and packaging details can be discussed by quantity. Buyer search focus: OEM walking shoes, private label sneakers, custom logo footwear and factory wholesale shoes.",
            "hero_url": "https://sc04.alicdn.com/kf/S2f751fd115f74a91b7619b09c4469223l/286385890/S2f751fd115f74a91b7619b09c4469223l.jpg",
            "gallery_extras": ["https://sc04.alicdn.com/kf/S7d0b7e878aeb46699de0a510fb6b50a9H/286385890/S7d0b7e878aeb46699de0a510fb6b50a9H.png"],
            "main_perm": [5, 0, 1, 2, 3, 4],
            "detail_perm": [0, 1, 3, 2],
        },
    ],
    "BQ061 / AA811": [
        {
            "code": "BQ061-W1",
            "model": "BQ061-W1 / AA811",
            "title": "Wholesale Women's Breathable Knit Lace Up Walking Shoes Lightweight Cushioned Casual Sneakers Model AA811",
            "description": "Women's breathable knit lace-up walking shoes for wholesale and online-seller programs. Lightweight cushioned sole presentation, regular fit, original EU 35-45 size range and four photographed colors remain unchanged. Buyer search focus: breathable walking shoes, knit sneakers, lightweight casual footwear and wholesale women's shoes.",
            "hero_url": "https://sc04.alicdn.com/kf/Sb5e647fdb79d4a75a5d133f8a77191581/286385890/Sb5e647fdb79d4a75a5d133f8a77191581.jpg",
            "gallery_extras": ["https://sc04.alicdn.com/kf/Sad6670985e414f4eb1ce409e2ccae9b5S/286385890/Sad6670985e414f4eb1ce409e2ccae9b5S.png"],
            "main_perm": [1, 2, 3, 4, 5, 0],
            "detail_perm": [0, 2, 1, 3],
        },
        {
            "code": "BQ061-C1",
            "model": "BQ061-C1 / AA811",
            "title": "Women's Colorful Knit Casual Sneakers Lightweight Lace Up Walking Shoes for Online Sellers Wholesale AA811",
            "description": "Color-focused knit casual walking shoes for wholesale collections and online sellers. Four photographed colors, lace-up construction, regular fit and original EU 35-45 size range remain unchanged. Buyer search focus: colorful sneakers, knit walking shoes, lightweight women's shoes and wholesale casual footwear.",
            "hero_url": "https://sc04.alicdn.com/kf/Sb7427532624f491f96eaa38c8348fe468/286385890/Sb7427532624f491f96eaa38c8348fe468.jpg",
            "gallery_extras": ["https://sc04.alicdn.com/kf/Sd1cdc79cf16d4cdd8376432bc48615bfU/286385890/Sd1cdc79cf16d4cdd8376432bc48615bfU.png"],
            "main_perm": [2, 3, 4, 5, 0, 1],
            "detail_perm": [0, 3, 1, 2],
        },
        {
            "code": "BQ061-O1",
            "model": "BQ061-O1 / AA811",
            "title": "OEM ODM Private Label Women's Breathable Knit Walking Shoes Lightweight Lace Up Casual Sneakers AA811",
            "description": "OEM/ODM and private-label breathable knit lace-up walking shoes for importers, wholesalers and online sellers. Regular fit, original EU 35-45 size range and photographed colors remain unchanged. Logo, color, insole and packaging requirements can be discussed by order quantity. Buyer search focus: OEM walking shoes, private label sneakers, custom logo footwear and factory wholesale shoes.",
            "hero_url": "https://sc04.alicdn.com/kf/Sfcae3c1790894a188ad4db6e74dc387cF/286385890/Sfcae3c1790894a188ad4db6e74dc387cF.jpg",
            "gallery_extras": ["https://sc04.alicdn.com/kf/S632c36e30f3746df8733869b9ee73742C/286385890/S632c36e30f3746df8733869b9ee73742C.png"],
            "main_perm": [5, 0, 1, 2, 3, 4],
            "detail_perm": [0, 1, 3, 2],
        },
    ],
}


def permute(row, columns, order):
    old = [row.get(c) for c in columns]
    for col, idx in zip(columns, order):
        row[col] = old[idx]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = json.loads(Path(args.source).read_text(encoding="utf-8"))
    output = []
    for source_model, variants in VARIANTS.items():
        source_rows = [r for r in source if r.get("AU") == source_model]
        if not source_rows:
            raise SystemExit(f"Missing source rows: {source_model}")
        for variant in variants:
            # 同款多链接只改变流量入口，不改变原始 SKU、颜色或尺码集合。
            # 每个衍生链接完整继承该源产品的全部真实组合。
            for source_row in source_rows:
                row = deepcopy(source_row)
                row["E"] = variant["title"]
                row["S"] = variant["description"]
                row["AU"] = variant["model"]
                # FAQ columns in the current official template are AC:AR.
                for (question_column, answer_column), (question, answer) in zip(FAQ_COLUMN_PAIRS, FAQS):
                    row[question_column] = question
                    row[answer_column] = answer
                # 2026-08-28 最新中文模板的 logisticsProperty 有效值为“普货”。
                # 历史英文值 Ordinary goods 已被平台判为无效。
                row["DA"] = "普货"
                original_sku = str(row["CJ"])
                parts = original_sku.split("-", 1)
                row["CJ"] = f"{variant['code']}-{parts[1] if len(parts) > 1 else original_sku}"
                old_main = [row.get(c) for c in ["F", "G", "H", "I", "J", "K"]]
                ordered_main = [old_main[index] for index in variant["main_perm"]]
                main_candidates = [variant["hero_url"], *variant.get("gallery_extras", []), *ordered_main]
                unique_main = []
                for value in main_candidates:
                    if value and value not in unique_main:
                        unique_main.append(value)
                if len(unique_main) < 6:
                    raise SystemExit(f"Not enough unique main images: {variant['model']}")
                for column, value in zip(["F", "G", "H", "I", "J", "K"], unique_main[:6]):
                    row[column] = value
                source_detail = SOURCE_DETAIL_IMAGES[source_model]
                ordered_detail = [source_detail[index] for index in variant["detail_perm"]]
                if set(ordered_detail) & set(unique_main[:6]):
                    raise SystemExit(f"Main/detail image overlap: {variant['model']}")
                for column, value in zip(["O", "P", "Q", "R"], ordered_detail):
                    row[column] = value
                output.append(row)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"products": len({r['AU'] for r in output}), "rows": len(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
