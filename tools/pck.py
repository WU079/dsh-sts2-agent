"""从《杀戮尖塔 2》的 .pck 里把游戏自带的汉化提取出来（只读，不碰游戏目录）。

Godot 4.5 的 PCK v3 布局：
  0   magic 'GDPC'
  4   pack_version
  8   ver_major / ver_minor / ver_patch
  20  pack_flags
  24  uint64 file_base
  32  uint64 dir_offset     ← 目录表从这里开始
  40  16 字节保留
  dir_offset: uint32 count，然后每条：uint32 路径长度（含 4 字节对齐填充）、
              路径、uint64 偏移、uint64 大小、16 字节 md5、uint32 flags

用法:
  python pck.py list <SlayTheSpire2.pck> [过滤子串]
  python pck.py extract <SlayTheSpire2.pck> localization/zhs/ ./data
"""
import struct
import sys
from pathlib import Path


def parse(path):
    f = open(path, "rb")
    if f.read(4) != b"GDPC":
        raise SystemExit("不是 PCK 文件")
    f.read(4)
    f.read(12)
    f.read(4)
    file_base = struct.unpack("<Q", f.read(8))[0]
    dir_offset = struct.unpack("<Q", f.read(8))[0]
    f.seek(dir_offset)
    (count,) = struct.unpack("<I", f.read(4))
    entries = []
    for _ in range(count):
        (plen,) = struct.unpack("<I", f.read(4))
        raw = f.read(plen)
        p = raw.rstrip(b"\x00").decode("utf-8", "replace")
        off, size = struct.unpack("<QQ", f.read(16))
        f.read(16)
        (eflags,) = struct.unpack("<I", f.read(4))
        entries.append({"path": p, "offset": off, "size": size, "flags": eflags})
    return f, {"file_base": file_base, "dir_offset": dir_offset, "entries": entries}


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    pck = sys.argv[2]
    f, info = parse(pck)
    if cmd == "list":
        needle = sys.argv[3].lower() if len(sys.argv) > 3 else ""
        hits = [e for e in info["entries"] if needle in e["path"].lower()]
        print(f"# files={len(info['entries'])} base={info['file_base']} dir={info['dir_offset']}")
        for e in hits[:500]:
            print(f"{e['size']:>9}  {e['path']}")
        print(f"# matched={len(hits)}")
        return
    if cmd == "extract":
        needle = sys.argv[3].lower() if len(sys.argv) > 3 else ""
        outdir = Path(sys.argv[4] if len(sys.argv) > 4 else "data")
        base = info["file_base"]
        n = 0
        for e in info["entries"]:
            if needle not in e["path"].lower():
                continue
            f.seek(base + e["offset"])
            out = outdir / e["path"]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(f.read(e["size"]))
            n += 1
        print(f"extracted {n} files -> {outdir}")
        return
    raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
