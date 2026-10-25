"""把游戏自带的汉化 json 转成「能查的牌表 / 遗物表 / 能力表」。

输入（先用 pck.py 从游戏里提出来）：
  <loc>/cards.json / relics.json / powers.json / potions.json / card_keywords.json / enchantments.json
输出：
  <out>/cards.md  relics.md  powers.md  potions.md  enchantments.md
  <out>/index.tsv   —— 每行 名称 \\t 类型 \\t 效果 \\t ID，给 sts2_lookup / lookup.py 用

注意：效果里的 {Damage:diff()} 这类是占位符，具体数值随卡牌等级/力量变化，这里只保留变量名。

用法:
  python build-db.py [--loc <localization/zhs 目录>] [--out <输出目录>]
  默认 --loc ./localization/zhs  --out ./data
"""
import argparse
import json
import re
from pathlib import Path

VAR_ZH = {
    "Damage": "伤害",
    "Block": "格挡",
    "Cards": "抽牌数",
    "Energy": "能量",
    "Hp": "生命",
    "HP": "生命",
    "Heal": "回复",
    "Strength": "力量",
    "Dexterity": "敏捷",
    "Vulnerable": "易伤",
    "Weak": "虚弱",
    "Poison": "中毒",
    "Gold": "金币",
    "MaxHp": "最大生命",
}


def clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\{([A-Za-z0-9_]+)(?::[^}]*)?\}", lambda m: "{" + VAR_ZH.get(m.group(1), m.group(1)) + "}", text)
    text = text.replace("[gold]", "").replace("[/gold]", "")
    text = text.replace("\\n", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def load(loc: Path, name):
    p = loc / name
    return json.load(open(p, encoding="utf-8")) if p.exists() else {}


def collect(data, kind):
    out = {}
    for k, v in data.items():
        if not k.endswith(".title"):
            continue
        cid = k[: -len(".title")]
        desc = clean(data.get(cid + ".description", ""))
        if v and (desc or kind != "card"):
            out[cid] = (v, desc)
    return out


def write_md(path, title, rows):
    rows = sorted(rows, key=lambda r: r[1])
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n（共 {len(rows)} 条。{{伤害}} 这类是占位符，实际数值看游戏里牌面。）\n\n")
        for cid, name, desc in rows:
            f.write(f"- **{name}**（`{cid}`）：{desc}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loc", default="localization/zhs", help="游戏汉化 json 所在目录")
    ap.add_argument("--out", default="data", help="输出的牌表目录")
    args = ap.parse_args()
    loc, out = Path(args.loc), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cards = collect(load(loc, "cards.json"), "card")
    relics = collect(load(loc, "relics.json"), "relic")
    powers = collect(load(loc, "powers.json"), "power")
    potions = collect(load(loc, "potions.json"), "potion")
    ench = collect(load(loc, "enchantments.json"), "enchant")
    keywords = load(loc, "card_keywords.json")

    write_md(out / "cards.md", "卡牌", [(c, n, d) for c, (n, d) in cards.items()])
    write_md(out / "relics.md", "遗物", [(c, n, d) for c, (n, d) in relics.items()])
    write_md(out / "powers.md", "能力 / 状态", [(c, n, d) for c, (n, d) in powers.items()])
    write_md(out / "potions.md", "药水", [(c, n, d) for c, (n, d) in potions.items()])
    write_md(out / "enchantments.md", "附魔", [(c, n, d) for c, (n, d) in ench.items()])

    with open(out / "index.tsv", "w", encoding="utf-8") as f:
        for kind, data in (("卡牌", cards), ("遗物", relics), ("能力", powers), ("药水", potions), ("附魔", ench)):
            for cid, (n, d) in data.items():
                f.write(f"{n}\t{kind}\t{d}\t{cid}\n")
        for k, v in keywords.items():
            if k.endswith(".description"):
                f.write(f"{k[: -len('.description')]}\t关键词\t{v}\t\n")

    print(f"cards={len(cards)} relics={len(relics)} powers={len(powers)} potions={len(potions)} ench={len(ench)}")


if __name__ == "__main__":
    main()
