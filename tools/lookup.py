"""查本地牌表（命令行版，等价于插件里的 sts2_lookup）。

用法:
  python lookup.py 打击
  python lookup.py 力量 --type 能力
  python lookup.py 群星之子 --limit 3 --index data/index.tsv
"""
import argparse
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("words", nargs="+", help="名字或效果关键词")
    ap.add_argument("--type", "-t", default=None, help="只看某一类：卡牌 / 遗物 / 能力 / 药水 / 附魔")
    ap.add_argument("--limit", "-n", type=int, default=8)
    ap.add_argument("--index", default="data/index.tsv", help="牌表路径")
    args = ap.parse_args()

    index = Path(args.index)
    if not index.exists():
        raise SystemExit(f"找不到牌表 {index}，先跑 build-db.py 生成")
    needle = " ".join(args.words)
    rows = []
    for line in index.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name, typ, desc = parts[0], parts[1], parts[2]
        cid = parts[3] if len(parts) > 3 else ""
        if args.type and args.type not in typ:
            continue
        if needle.lower() in f"{name} {desc} {cid}".lower():
            rows.append((name, typ, desc, cid))
    rows.sort(key=lambda r: 0 if r[0] == needle else 1)
    for name, typ, desc, cid in rows[: args.limit]:
        print(f"[{typ}] {name}（{cid}）\n    {desc}")
    if not rows:
        print(f"没找到「{needle}」")
    elif len(rows) > args.limit:
        print(f"……共 {len(rows)} 条，只显示前 {args.limit} 条")


if __name__ == "__main__":
    main()
