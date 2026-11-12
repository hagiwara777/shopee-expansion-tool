"""Owner policy: shared rules plus market data, independent of ASIN origin.

Amazon category nodes are product evidence only. They never assign a Shopee
category, produce SLS ALLOW, or override another Safety result.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata

from modules.match_context import excerpt_at
from modules.ingredient_text_sections import ingredient_spans


POLICY_DIR = Path(__file__).resolve().parents[1] / "guardrails" / "policy"
FIELDS = {"title", "text", "ingredients", "category", "brand", "asin"}
CONDITIONS = {"always", "medical", "general", "spray", "mask", "weapon_attachment",
              "food", "laser", "certification", "sample", "used", "food_review", "battery",
              "sg_knife", "ph_contact_lens", "flammable_liquid", "alcohol_strength",
              "weapon_part", "mushroom_food", "toy_weapon", "pet_drug", "ph_weapon_decoration",
              "pet_food_category"}
RISKS = {"drug_or_hemp", "medical_or_therapeutic", "regulated_ingredient", "brand_ip",
         "weapon", "weapon_related_toy", "food_restricted", "shipping_restricted",
         "tobacco_or_vape", "alcohol", "license_or_certification_required", "own_penalty_product", "other"}
TEXT_FIELDS = ("description", "features", "shortDescription", "safetyWarning", "itemHighlights")
INGREDIENT_FIELDS = ("ingredients", "activeIngredients", "specialIngredients")


class SafetyPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class PolicyHit:
    rule_id: str
    term: str
    action: str
    risk: str
    field: str
    note: str
    source: str


def load_policy_rules(directory=None):
    """No missing/malformed asset may silently become an empty policy."""
    path = Path(directory) if directory is not None else POLICY_DIR
    try:
        data = json.loads((path / "rules.json").read_text(encoding="utf-8"))
        if set(data) != {"schema", "decision", "rules"} or data["schema"] != "SORA_SAFETY_POLICY_V1":
            raise ValueError
        if data["decision"] != "DEC-0167" or not isinstance(data["rules"], list) or not data["rules"]:
            raise ValueError
        seen = set()
        for rule in data["rules"]:
            if set(rule) != {"id", "markets", "action", "risk", "fields", "terms", "condition", "note", "source"}:
                raise ValueError
            if not isinstance(rule["id"], str) or not rule["id"] or rule["id"] in seen:
                raise ValueError
            seen.add(rule["id"])
            if rule["action"] not in {"BLOCK", "REVIEW"} or rule["risk"] not in RISKS:
                raise ValueError
            if rule["condition"] not in CONDITIONS or rule["source"] not in {"internal_rule", "shopee_policy", "own_penalty_case"}:
                raise ValueError
            for key, allowed in (("fields", FIELDS), ("markets", {"ALL", "SG", "PH", "MY", "TH", "TW"})):
                if (not isinstance(rule[key], list) or not rule[key] or len(set(rule[key])) != len(rule[key])
                        or any(value not in allowed for value in rule[key])):
                    raise ValueError
            if "ALL" in rule["markets"] and rule["markets"] != ["ALL"]:
                raise ValueError
            if (not isinstance(rule["terms"], list) or not rule["terms"]
                    or any(not isinstance(t, str) or not t.strip() or "\n" in t for t in rule["terms"])
                    or len(set(rule["terms"])) != len(rule["terms"])):
                raise ValueError
            if not isinstance(rule["note"], str) or not rule["note"].strip():
                raise ValueError
        return tuple(data["rules"])
    except (OSError, ValueError, KeyError, TypeError):
        raise SafetyPolicyError("共通・国別の保安ルール設定を確認できません。判定を停止しました。") from None


def _values(row, fields):
    for group in fields:
        names = {"title": ("product_title",), "text": TEXT_FIELDS, "ingredients": INGREDIENT_FIELDS,
                 "category": ("category",), "brand": ("brand",), "asin": ("candidate_asin",)}[group]
        for name in names:
            raw = row.get(name)
            if raw is None:
                continue
            if isinstance(raw, str):
                raw = (raw,)
            if not isinstance(raw, (tuple, list)) or any(not isinstance(v, str) for v in raw):
                raise SafetyPolicyError("商品情報の形式を確認できません。判定を停止しました。")
            for value in raw:
                if value.strip():
                    yield group, name, value


def mask_harmless_phrases(value):
    """Suppress only these occurrences, not other positive statements nearby."""
    return re.sub(r"アルコールフリー|ノンアルコール|(?<![a-z0-9])alcohol[- ]free(?![a-z0-9])"
                  r"|(?<![a-z0-9])fake\s+lashes(?![a-z0-9])|つけまつげ",
                  lambda match: " " * len(match[0]), value)


def _condition(rule, value, row, group):
    """Return BLOCK/REVIEW for a match, or None for a bounded exclusion."""
    condition = rule["condition"]
    action = rule["action"]
    if condition == "battery":
        if group != "title" or re.search(r"(?:ケース|ホルダー|用カバー|用替刃|別売|付属しません|not included|holder|case|cover|not supplied)", value):
            return None
        return action
    if condition in {"always", "medical"}:
        return action
    from modules.guardrails import normalize_text
    title = normalize_text(row.get("product_title", ""))
    category = normalize_text(row.get("category", ""))
    context = title + " " + value
    if condition == "alcohol_strength":
        strength = re.search(r"アルコール分\s*(?:約)?\s*\d+(?:\.\d+)?\s*%", value)
        beverage = re.search(r"飲料|飲み物|飲みもの|ドリンク|酒|ビール|ワイン|カクテル|"
                             r"チューハイ|酎ハイ|ハイボール|beverage|drink", title + " " + category + " " + value)
        return action if beverage and strength else None
    if condition == "pet_food_category":
        # DEC-0182: the top "ペット用品" node alone is not a food; a later node
        # (フード・おやつ・ごはん・ミルク) shows the product is pet food.
        nodes = [node.strip() for node in category.split(">")]
        return action if any(re.search(r"フード|おやつ|ごはん|ご飯|ミルク|ジャーキー|(?<![a-z])(?:food|treats?|snacks?)(?![a-z])", node)
                             for node in nodes[1:]) else None
    if condition == "weapon_part":
        return action if re.search(r"銃|ガン|ライフル|ピストル|firearm|rifle|pistol|airsoft", title + " " + category + " " + value) else None
    if condition == "mushroom_food":
        # DEC-0181 follow-up: processed foods containing mushrooms also stop.
        food = re.search(r"食品|食材|食用|食料|青果|野菜|乾燥|干し|冷凍|調理|料理|スープ|だし|出汁|"
                         r"食べ|生鮮|ご飯|ごはん|炊き込み|パスタ|ソース|カレー|レトルト|缶詰|味噌汁|"
                         r"みそ汁|調味料|佃煮|漬け|grocery|food|edible|dried", title + " " + category + " " + value)
        return action if food else None
    if condition == "toy_weapon":
        return action if _category_is_toy(row) or re.search(r"おもちゃ|玩具|(?:^|\W)toys?(?:$|\W)", context) else None
    if condition == "pet_drug":
        animal = re.search(r"ペット|動物|犬|猫|いぬ|ねこ|(?<![a-z])(?:pets?|animals?|dogs?|cats?)(?![a-z])",
                           title + " " + category + " " + value)
        treatment = re.search(r"駆虫薬|(?:ノミ|ダニ)[^。.!?！？]{0,20}駆除", value)
        return action if animal and treatment else None
    if condition == "flammable_liquid":
        # A warning alone can also describe an aerosol or a solid.  The new
        # BLOCK is specific to a liquid identifiable in the available facts.
        details = " ".join(normalize_text(raw) for _, _, raw in _values(row, ("text",)))
        product_kind = " ".join((title, category))
        oil = re.search(r"(?:ヘア|クレンジング|美容|ボディ|マッサージ|ベビー|スキンケア|"
                        r"アロマ|エッセンシャル)オイル|オイルクレンジング|精油|"
                        r"(?:hair|cleansing|body|massage|baby|essential) oil", product_kind)
        oil_is_liquid = oil and not re.search(r"スプレー|エアゾール|spray|aerosol", product_kind)
        liquid = (re.search(r"液体|液状|液剤|溶液|化粧水|ローション|リキッド|乳液|"
                            r"シャンプー|ボディソープ|液体洗剤|(?:^|\W)liquids?(?:$|\W)",
                            product_kind)
                  or oil_is_liquid
                  or re.search(r"(?:本品|本製品|この商品).{0,12}(?:液体|液状|液剤)|"
                               r"引火性(?:の)?液体|\bflammable liquids?\b", details))
        return action if liquid else None
    decoration = re.search(r"フィギュア|キーホルダー|キーチェーン|ペンダント|figure|keychain|pendant", context)
    if condition in {"sg_knife", "ph_contact_lens"}:
        # A bare accessory name is not proof that it contains the body.  Keep
        # the existing SG body-confirmation gate and all other policy hits.
        # Explicit inclusion, including in another text field, still blocks.
        if condition == "sg_knife":
            accessory = r"(?:kitchen|chef)[ -]+knife[ -]+(?:sharpener|case|sheath|holder|storage)\b|包丁(?:研ぎ器|研ぎ|ケース|収納|ホルダー)"
            inclusion = r"(?:with|includes?|including|contains?)\s+(?:a\s+)?(?:(?:kitchen|chef)\s+)?knife\b|包丁(?:付き|付属|同梱|入り)"
        else:
            accessory = r"contact[ -]+lens[ -]+(?:case|holder|storage)\b"
            inclusion = r"(?:with|includes?|including|contains?)\s+(?:a\s+)?contact[ -]+lens(?:es)?\b"
        all_text = [title]
        all_text.extend(normalize_text(raw) for _, _, raw in _values(row, ("text",)))
        if any(re.search(inclusion, text) for text in all_text):
            return action
        remaining = re.sub(accessory, " ", value)
        from modules.guardrails import _contains_term
        return action if any(_contains_term(remaining, normalize_text(term)) for term in rule["terms"]) else None
    if condition == "general":
        if decoration and rule["risk"] in {"weapon", "weapon_related_toy"}:
            return None  # Dedicated attachment rule decides this ambiguity.
        return action
    if condition == "spray":
        return action if re.search(r"スプレー|エアゾール|エアロゾル|spray|aerosol", context) else None
    if condition == "mask":
        cosmetic = re.search(r"ヘアマスク|シートマスク|フェイスパック|hair mask|sheet mask|face pack|トリートメント", context)
        hair_category = re.search(r"ヘアケア|ヘアトリートメント|フェイスパック|シートマスク", category)
        positive = re.search(r"不織布|立体マスク|防塵|防じん|医療用マスク|サージカル|n95|respirator|surgical|口と鼻|口鼻", context)
        if positive:
            return "BLOCK"
        if cosmetic or hair_category:
            return None
        return "REVIEW"
    if condition == "ph_weapon_decoration":
        # PH lists weapon keychains, pendants and figures as prohibited
        # imports, so the shared decoration REVIEW becomes BLOCK there.
        return action if decoration else None
    if condition == "weapon_attachment":
        if not decoration:
            return None
        attached = re.search(r"(?:剣|刀|銃|武器|ナイフ)(?:の模型)?(?:パーツ)?(?:付き|付属|同梱|型|装備|を持つ)"
                             r"|(?:剣|刀|銃|武器|ナイフ).{0,12}(?:付属|同梱|装備|セット)"
                             r"|(?:with|includes?|equipped with)\s+(?:a\s+)?(?:sword|gun|weapon|knife)"
                             r"|(?:gun|sword)[- ](?:shaped|keychain|pendant)", context)
        return "BLOCK" if attached else "REVIEW"
    if condition in {"food", "food_review"}:
        food_context = re.search(r"食品|フード|飲料|スナック|肉|ジャーキー|ソーセージ|ベーコン|ハム|卵|豆腐|アイスクリーム|乳製品|牛乳|食用油|野生キノコ|粉ミルク|food|snack|jerky|sausage|bacon|dairy|milk|tofu|seafood", context)
        cosmetic = re.search(r"シャンプー|トリートメント|化粧|美容|石鹸|石けん|ソープ|ヘア|shampoo|cosmetic|soap|hair", title)
        if group != "category" and cosmetic and not re.search(r"食品|食用|飲料|snack|food", title):
            return None
        food_category = re.search(r"食品|食品・飲料|food|grocery|飲料", category)
        return action if food_context or food_category else "REVIEW"
    if condition == "laser":
        power = re.search(r"(\d+(?:\.\d+)?)\s*mw", context)
        return ("BLOCK" if float(power[1]) >= 5 else None) if power else "REVIEW"
    if condition == "certification":
        return "BLOCK" if re.search(r"(?:ps|icc).{0,12}(?:なし|無し|未認証|未取得|without|no mark)", context) else "REVIEW"
    if condition == "sample":
        if re.search(r"詰め?替え|つめかえ|つめ替え|詰替|レフィル|リフィル|refill", value) and not re.search(r"試供品|小分け|非売品|量り売り|sample", value):
            return None
        return "REVIEW"
    if condition == "used":
        return action if re.search(r"中古|使用済|used|second[- ]hand", context) else None
    raise SafetyPolicyError("未対応の保安ルール条件です。")


def _policy_pattern(term, rule):
    if rule["id"] == "COMMON-SLS-PLANT-OTHER" and term == "種子":
        return r"種子(?!油|エキス|オイル)"
    if term == "アルコール":
        return r"(?<![ァ-ヴー])アルコール"
    if term == "ライター":
        return r"(?<!ハイ)ライター"
    if term == "マッチ":
        return r"マッチ(?!ング|ャ)"
    if rule["id"] == "COMMON-SLS-PERFUME" and term == "フレグランス":
        return r"フレグランス(?!フリー|不使用|無添加)"
    if rule["id"] == "COMMON-SLS-PERFUME" and term in {"perfume", "perfumes", "fragrance", "fragrances"}:
        return rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9]|[ -]?free\b)"
    if rule["id"] == "COMMON-DRUG" and term == "hemp":
        return re.escape(term)
    medical = (rule["condition"] in {"medical", "ph_contact_lens"}
               or (rule["condition"] == "general" and rule["risk"] == "medical_or_therapeutic"))
    if re.fullmatch(r"[a-z0-9]+(?: [a-z0-9]+)*", term) or (medical and re.fullmatch(r"[a-z0-9 -]+", term)):
        return rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    if re.search(r"[^a-z0-9 -].*[a-z0-9]$", term):
        return re.escape(term) + r"(?![a-z0-9])"
    return re.escape(term)


def _mask_usage_cautions(value, field, rule_id):
    """Exclude only an explicit usage instruction in the safety-warning field."""
    if field != "safetyWarning":
        return value
    pattern = None
    if rule_id == "COMMON-TRANSPORT-OXIDIZER":
        pattern = (r"漂白剤\s*(?:の)?(?:ご)?(?:使用|利用)(?:は|を)?(?:おやめ(?:ください|下さい)|しない(?:で)?(?:ください|下さい)?)"
                   r"|漂白剤\s*(?:を|は)(?:使わない|使用しない|使用しないで)(?:で)?(?:ください|下さい)?")
    elif rule_id == "COMMON-CONTACT-LENSES":
        pattern = (r"コンタクトレンズを(?:はずして|外して|外し(?:てから|た上で))"
                   r"|コンタクトレンズ(?:を)?(?:着用|装用|使用)(?:している|中の|の)?方は"
                   r"|コンタクトレンズ(?:\s*[、,]\s*(?:メガネ|眼鏡|アクセサリー))*\s*(?:等|など)?\s*は[、,\s]*"
                   r"(?:使用する|ご使用|使用)前に(?:は)?\s*必ず(?:はずし|外し)(?=[、,\s]|て|$)")
    return re.sub(pattern, lambda match: " " * len(match[0]), value) if pattern else value


def _mask_other_person_perfume(value):
    """Mask only a perfume occurrence explicitly referring to the user's other perfume."""
    patterns = (
        r"お手持ちの(?:スキンケア[・、,]\s*)?香水"
        r"(?!タイプ|です|である|(?:を|が)?(?:同梱|付属|入って|配合|含む))",
        r"香水(?=や他のフレグランスを(?:ご)?使用する方)",
        r"香水(?=の香りを邪魔(?:したくない|しない|しません))",
    )
    for pattern in patterns:
        value = re.sub(pattern, lambda m: m[0][:-2] + "  " if m[0].endswith("香水") else "  ", value)
    return value


def _mask_perfume_comparisons(value):
    """A smell comparison is not a perfume; an affirmative product remains one."""
    return re.sub(r"香水(?=のような(?:(?!商品|香水|フレグランス|コロン)[^。.!?！？]){0,16}"
                  r"(?:香り|香調|香気|匂い|におい))",
                  lambda m: " " * len(m[0]), value)


def _mask_nonperfume_fragrance(value, row, group):
    """Only generic fragrance wording on an identifiable wash/softener product."""
    if group != "title":
        return value
    from modules.guardrails import normalize_text
    product = normalize_text(row.get("product_title", ""))
    # Require the title itself to identify the product.  A conflicting
    # category alone must not turn a product explicitly named fragrance into SAFE.
    if not re.search(r"シャンプー|トリートメント|コンディショナー|ボディソープ|洗顔|柔軟剤|"
                     r"shampoo|conditioner|body wash|fabric softener", product):
        return value
    pattern = r"フレグランス|(?<![a-z0-9])fragrance(?![a-z0-9])"
    product_word = r"シャンプー|トリートメント|コンディショナー|ボディソープ|洗顔|柔軟剤|shampoo|conditioner|body wash|fabric softener"
    size = r"\d+(?:\.\d+)?\s*(?:ml|l|mg|g|kg|個|本)(?:\s*[x×]\s*\d+)?"
    separator = r"(?:と|[+＆&・/])"

    def mask_only_scent(match):
        prefix, suffix = value[:match.start()], value[match.end():]
        # A separately listed fragrance and wash product can be a bundle, not
        # merely a description of the wash product's scent.
        if (re.match(rf"\s*(?:{size})?\s*{separator}\s*(?:{product_word})", suffix)
                or re.search(rf"(?:{product_word})\s*(?:{size})?\s*{separator}\s*$", prefix)
                or re.match(rf"\s*{size}\s*{separator}\s*[^。.!?！？]{{0,32}}?(?:{product_word})", suffix)
                or (re.match(rf"\s*{size}", suffix)
                    and re.search(rf"(?:{product_word})\s*{size}\s*{separator}\s*[^。.!?！？]{{0,32}}$", prefix))
                or (re.search(r"セット|(?<![a-z])set(?![a-z])", value)
                    and re.match(rf"\s*{size}\s*(?:{product_word})\s*{size}", suffix))):
            return match.group()
        return " " * len(match.group())

    return re.sub(pattern, mask_only_scent, value)


def _category_is_toy(row):
    from modules.guardrails import normalize_text
    nodes = [n.strip() for n in normalize_text(row.get("category", "")).split(">")]
    return any(re.fullmatch(r"おもちゃ|玩具|人形・ドール|ドール・人形|人形|ドール|ままごと|"
                            r"ままごと・ごっこ遊び|おままごと|toys(?: & games)?|dolls|pretend play",
                            node) for node in nodes)


def _nail_tool(row):
    from modules.guardrails import normalize_text
    product = normalize_text(row.get("product_title", ""))
    category = normalize_text(row.get("category", ""))
    return bool(re.search(r"爪切り|つめ切り|爪やすり|爪ヤスリ|ネイルファイル|"
                          r"nail clipper|nail file", product + " " + category))


def _cosmetic_product(row):
    from modules.guardrails import normalize_text
    product = normalize_text(row.get("product_title", ""))
    category = normalize_text(row.get("category", ""))
    return bool(re.search(r"化粧|洗顔|美容液|シャンプー|スキンケア|cosmetic|skin care",
                          product + " " + category))


def _mask_makeup_wine_colors(value, row):
    """Recognize explicit color names only when the category is makeup."""
    from modules.guardrails import normalize_text
    category = normalize_text(row.get("category", ""))
    nodes = (node.strip() for node in category.split(">"))
    if not any(re.match(r"^(?:メイクアップ|口紅|リップ|アイシャドウ|アイライナー|チーク|makeup)(?:$|[・/、,\s])", node)
               for node in nodes):
        return value
    return re.sub(r"(?:パンプキンワイン|ワイン(?:レッド|ピンク|ブラウン|パープル|色))"
                  r"(?!\s*(?:入り|付き|同梱|付属|配合|含有|を含む|を使用))",
                  lambda match: " " * len(match[0]), value)


def _fragrance_text_describes_product(value, occurrence):
    """The newly recognized generic word in prose needs an affirmative product expression."""
    prefix = value[max(0, occurrence.start() - 40):occurrence.start()]
    return bool(re.match(r"(?:です|である|タイプ|そのもの)", value[occurrence.end():])
                or re.search(r"\b(?:this|the|our)\s+(?:(?:product|item)\s+)?is\s+(?:an?\s+)?$", prefix))


def _mask_official_gap_exclusions(value, rule_id, row):
    """Mask only the specified occurrence, preserving independent positive hits."""
    patterns = []
    if rule_id in {"COMMON-TOBACCO", "COMMON-GENERAL-TITLE-tobacco_or_vape",
                   "COMMON-GENERAL-TEXT-tobacco_or_vape"}:
        # DEC-0181 follow-up: a smell or stain being removed is not tobacco,
        # in the product title as well as in the description.
        patterns.append(r"シガーソケット|(?:タバコ|たばこ|煙草)(?:臭|ヤニ|の\s*(?:におい|匂い|臭い|ニオイ|ヤニ))")
    if rule_id == "COMMON-ALCOHOL-DRINK":
        drink = (r"梅酒|焼酎|ウイスキー|ウィスキー|ブランデー|ウォッカ|リキュール|果実酒|洋酒|"
                 r"清酒|紹興酒|泡盛|チューハイ|酎ハイ|ハイボール|シャンパン")
        patterns.append(rf"(?:{drink})\s*(?:用(?:の)?\s*)?(?:グラス|コップ|カップ|瓶|びん|ボトル|容器)")
        # Colour names such as champagne gold describe a colour, not a drink.
        patterns.append(r"シャンパン(?=\s*(?:ゴールド|ピンク|ベージュ|シルバー|ブラウン|カラー|色))")
    if rule_id == "SG-GENERAL-KNIFE":
        patterns.append(r"バターナイフ|butter[ -]+knife|(?:kitchen|chef|cook)(?:['’]s)?[ -]+knife[ -]+"
                        r"(?:sharpener|case|sheath|holder|storage)\b")
        # Sharpening tools are not knives; another knife occurrence still blocks.
        patterns.append(r"ナイフ(?=\s*(?:用(?:の)?\s*)?(?:研ぎ器|研ぎ|シャープナー|砥石))"
                        r"|knife[ -]+sharpener")
        from modules.guardrails import normalize_text
        kind = normalize_text(row.get("product_title", "")) + " " + normalize_text(row.get("category", "")) + " " + value
        if re.search(r"飾り|装飾|雑貨|フィギュア|キーホルダー|ペンダント|figure|keychain|pendant", kind):
            patterns.append(r"ナイフ(?:型|柄|の形)|knife[ -]+(?:shaped|pattern)")
    if rule_id == "COMMON-TRANSPORT-PESTICIDE":
        # "No insecticide ingredient" describes the absence of the product.
        patterns.append(r"殺虫(?:成分|剤)?\s*(?:は|が)?\s*(?:不使用|無配合|ゼロ|なし|無し|フリー)")
    if rule_id == "COMMON-TRANSPORT-PESTICIDE":
        # DEC-0182: a mosquito-coil holder or case is not the coil itself.
        patterns.append(r"蚊取り?線香(?=\s*(?:用(?:の)?\s*)?(?:ケース|ホルダー|皿|スタンド|入れ|立て|容器))"
                        r"|蚊とり線香(?=\s*(?:用(?:の)?\s*)?(?:ケース|ホルダー|皿|スタンド|入れ|立て|容器))")
    if rule_id == "COMMON-MEDICAL-DISPLAY":
        # DEC-0182: a case or holder for eye drops / plasters is an accessory.
        patterns.append(r"(?:目薬|点眼薬|絆創膏|ばんそうこう|バンソウコウ)"
                        r"(?=\s*(?:用(?:の)?\s*)?(?:ケース|ホルダー|ポーチ|入れ|容器|スタンド|ディスペンサー|補助))")
    if rule_id == "COMMON-COLD-FOOD":
        patterns.append(r"チルドレン")
    if rule_id == "PH-OUTDOOR-KNIFE":
        # DEC-0182: sharpening tools are not knives (same as SG-GENERAL-KNIFE).
        patterns.append(r"ナイフ(?=\s*(?:用(?:の)?\s*)?(?:研ぎ器|研ぎ|シャープナー|砥石))|knife[ -]+sharpener")
    if rule_id == "SG-GUM":
        patterns.append(r"ガムテープ|ガムシロップ|アラビアガム")
    if rule_id == "SG-WEAPON-PART":
        patterns.append(r"マガジンラック")
    if rule_id == "SG-ANIMAL-FAT":
        patterns.append(r"(?:ラード|牛脂|ヘット)\s*(?:は|が)?\s*(?:不使用|無添加|未使用)")
    if rule_id == "SG-MUSHROOM":
        patterns.append(r"きのこの山(?=$|[\s(、,.。!！?？+＆&]|と|セット|チョコレート|チョコ|お菓子|菓子)")
        # A truffle chocolate is a confection, not a mushroom.
        patterns.append(r"トリュフ(?=\s*(?:チョコ|ショコラ))|(?<=チョコ)\s*トリュフ|(?<=チョコレート)\s*トリュフ"
                        r"|(?<=ショコラ)\s*トリュフ")
        from modules.guardrails import normalize_text
        kind = normalize_text(row.get("product_title", "")) + " " + normalize_text(row.get("category", "")) + " " + value
        if re.search(r"おもちゃ|玩具|雑貨|飾り|装飾|フィギュア|キーホルダー|ぬいぐるみ|toy|figure", kind):
            patterns.append(r"(?:きのこ|キノコ)(?:型|形|の形)")
    if rule_id == "PH-TOY-WEAPON-CONTEXT":
        patterns.append(r"グルーガン|ヒートガン|マッサージガン|スプレーガン|エアダスターガン|ガンダム")
    for pattern in patterns:
        value = re.sub(pattern, lambda match: " " * len(match[0]), value)
    return value


def evaluate_policy(row, marketplace, rules=None):
    # Future-market data never enables its UI, credentials, or operations.
    from modules.guardrails import normalize_text, _contains_rule_term, GuardrailRule
    rules = load_policy_rules() if rules is None else rules
    hits = []
    for rule in rules:
        if "ALL" not in rule["markets"] and marketplace not in rule["markets"]:
            continue
        for group, field, raw in _values(row, rule["fields"]):
            is_ingredient_policy_text = rule["id"] == "COMMON-COSMETIC-INGREDIENT" and group == "text"
            # Section boundaries need their original line/HTML structure.  The
            # other policies keep their existing whitespace normalization.
            original = (unicodedata.normalize("NFKC", raw).strip().lower()
                        if is_ingredient_policy_text else normalize_text(raw))
            value = mask_harmless_phrases(original) if rule["condition"] == "general" else original
            value = _mask_official_gap_exclusions(value, rule["id"], row)
            exclusions = {"SG-AMULET": r"お守り(?:ください|下さい)",
                          "COMMON-SLS-PLANT": r"植物(?:由来|性|エキス|オイル|アロマ)"}
            if rule["id"] in exclusions:
                value = re.sub(exclusions[rule["id"]], lambda m: " " * len(m[0]), value)
            if rule["id"] == "COMMON-FINANCE":
                value = re.sub(r"株式会社|\(株\)", lambda m: " " * len(m[0]), value)
            if rule["id"] == "COMMON-SLS-PLANT" and _cosmetic_product(row):
                value = re.sub(r"(?<!観葉)和漢植物(?![の\s]{0,2}(?:本体|苗|種|鉢|栽培|生体|盆栽))",
                               lambda m: " " * len(m[0]), value)
            if rule["id"] == "COMMON-SLS-HAIRCOLOR":
                value = re.sub(r"ヘアカラー(?=\s*(?:ラスティング|の色落ち))",
                               lambda m: " " * len(m[0]), value)
            if rule["id"] == "PH-SLS":
                from modules.guardrails import normalize_text
                category = normalize_text(row.get("category", ""))
                if re.search(r"入浴剤|バスソルト|bath salts?", category):
                    value = re.sub(r"(?:食添|食品添加物)\s*[→⇒>]\s*(?:特号|特級)\s*[→⇒>]\s*肥料",
                                   lambda m: m[0][:-2] + "  ", value)
            value = _mask_usage_cautions(value, field, rule["id"])
            if rule["id"] == "COMMON-SLS-PERFUME":
                if group == "text":
                    value = _mask_other_person_perfume(value)
                if group in {"title", "text"}:
                    value = _mask_perfume_comparisons(value)
                value = _mask_nonperfume_fragrance(value, row, group)
                value = re.sub(r"コロンビア|セミコロン|コロン記号|コロンと(?=$|した|丸|転が|かわい|可愛)",
                               lambda m: " " * len(m[0]), value)
            if rule["id"] == "COMMON-ALCOHOL-DRINK" and group in {"title", "text"}:
                value = _mask_makeup_wine_colors(value, row)
            sections = ingredient_spans(original) if is_ingredient_policy_text else ()
            for term in rule["terms"]:
                normalized = normalize_text(term)
                toy_terms = {"PH-ORAL": {"歯ブラシ", "ハブラシ", "toothbrush"},
                             "COMMON-SLS-COIN": {"コイン", "coin", "coins"},
                             "COMMON-SLS-FOOD": {"牛乳", "milk"}}
                if normalized in toy_terms.get(rule["id"], ()) and _category_is_toy(row):
                    continue
                if (rule["id"] == "COMMON-SLS-NAIL"
                        and normalized in {"ネイル", "ネイルケア", "ネイル用具", "nail care"}
                        and _nail_tool(row)):
                    continue
                if rule["id"] == "COMMON-SLS-PLANT-OTHER" and term == "種子" and group not in {"title", "category"}:
                    continue
                cologne_category = (rule["id"] == "COMMON-SLS-PERFUME"
                                    and ("コロン" in normalized or "cologne" in normalized))
                softener_category = (rule["id"] == "COMMON-SLS-LAUNDRY"
                                     and normalized in {"柔軟剤", "柔軟仕上げ剤", "fabric softener"})
                if (group == "category" and rule["id"] not in {"SG-AMULET", "COMMON-SLS-PLANT"}
                        and not cologne_category and not softener_category):
                    if not (normalized == value if ">" in normalized else normalized in [n.strip() for n in value.split(">")]):
                        continue
                if group in {"brand", "asin"} and value != normalized:
                    continue
                # Every pattern requires this literal term.  Avoid compiling
                # hundreds of no-hit Japanese patterns on every reassessment.
                if normalized not in value:
                    continue
                occurrences = list(re.finditer(_policy_pattern(normalized, rule), value))
                if not occurrences:
                    continue
                medical = (rule["condition"] in {"medical", "ph_contact_lens"}
                           or (rule["condition"] == "general" and rule["risk"] == "medical_or_therapeutic"))
                probe = (GuardrailRule(term, normalized, rule["action"], "medical_or_therapeutic",
                                       "title", "contains", rule["source"], rule["note"], "rules.json", 0, "policy")
                         if medical else None)
                seen_actions = set()
                for index, occurrence in enumerate(occurrences):
                    if (rule["id"] == "COMMON-SLS-PERFUME"
                            and term in {"フレグランス", "perfume", "perfumes", "fragrance", "fragrances"} and group == "text"
                            and not _fragrance_text_describes_product(value, occurrence)):
                        continue
                    if medical:
                        # Isolate this occurrence so a later positive cannot make
                        # a negated occurrence appear to be the matching evidence.
                        start = occurrences[index - 1].end() if index else 0
                        end = occurrences[index + 1].start() if index + 1 < len(occurrences) else len(value)
                        if not _contains_rule_term(value[start:end], probe):
                            continue
                    action = _condition(rule, value, row, group)
                    ingredient_list = any(start <= occurrence.start() and occurrence.end() <= end
                                          for start, end in sections)
                    if ingredient_list:
                        action = "REVIEW"
                    if not action or action in seen_actions:
                        continue
                    seen_actions.add(action)
                    note = rule["note"]
                    if ingredient_list:
                        note += "; 見出しで確認した成分一覧の区間に記載（要確認）"
                    note += f"; 該当箇所[{field}]: 「{excerpt_at(original, occurrence.start(), occurrence.end())}」"
                    hits.append(PolicyHit(rule["id"], term, action, rule["risk"], field, note, rule["source"]))
    return hits
