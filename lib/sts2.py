"""杀戮尖塔2 外部控制小工具（截图 + 鼠标键盘），给 AI 玩用。

用法:
  python sts2.py shot <png路径>
  python sts2.py click <x> <y>            # 屏幕绝对坐标（1922x1080 的全屏窗口）
  python sts2.py key <键名>               # enter/space/escape/tab/up/down/left/right/数字/字母
  python sts2.py info                     # 打印窗口位置尺寸
  python sts2.py activate                 # 把游戏窗口拉到前台
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time
from pathlib import Path

user32 = ctypes.windll.user32
try:
    user32.SetProcessDPIAware()
except Exception:
    pass

TITLE = "Slay the Spire 2"


def find_window():
    hwnd = user32.FindWindowW(None, TITLE)
    if hwnd:
        return hwnd
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, _l):
        n = user32.GetWindowTextLengthW(h)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(h, buf, n + 1)
            if TITLE.lower() in buf.value.lower():
                found.append(h)
                return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def window_rect(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def activate(hwnd):
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)


def shot(path):
    from PIL import ImageGrab

    hwnd = find_window()
    if not hwnd:
        raise SystemExit("找不到游戏窗口")
    activate(hwnd)
    left, top, w, h = window_rect(hwnd)
    img = ImageGrab.grab(bbox=(left, top, left + w, top + h), all_screens=True)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print(f"{path} {img.size[0]}x{img.size[1]} @ {left},{top}")


def move(x, y):
    """只把光标挪过去，不点（用来看卡片 tooltip）。"""
    hwnd = find_window()
    if hwnd:
        activate(hwnd)
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.5)
    print(f"moved {x},{y}")


def drag(x1, y1, x2, y2, steps=14):
    """按住鼠标从 (x1,y1) 拖到 (x2,y2)——杀戮尖塔出牌要拖到上方才打出去。"""
    hwnd = find_window()
    if hwnd:
        activate(hwnd)
    user32.SetCursorPos(int(x1), int(y1))
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # left down
    time.sleep(0.08)
    for i in range(1, steps + 1):
        x = int(x1 + (x2 - x1) * i / steps)
        y = int(y1 + (y2 - y1) * i / steps)
        user32.SetCursorPos(x, y)
        time.sleep(0.02)
    time.sleep(0.12)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # left up
    time.sleep(0.35)
    print(f"dragged {x1},{y1} -> {x2},{y2}")


def click(x, y):
    hwnd = find_window()
    if hwnd:
        activate(hwnd)
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.08)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # left down
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # left up
    time.sleep(0.2)
    print(f"clicked {x},{y}")


VK = {
    "enter": 0x0D, "escape": 0x1B, "esc": 0x1B, "space": 0x20, "tab": 0x09,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "backspace": 0x08, "delete": 0x2E, "home": 0x24, "end": 0x23,
}
for c in "0123456789":
    VK[c] = 0x30 + int(c)
for c in "abcdefghijklmnopqrstuvwxyz":
    VK[c] = ord(c) - 32


def key(name):
    hwnd = find_window()
    if hwnd:
        activate(hwnd)
    code = VK.get(name.lower())
    if code is None:
        raise SystemExit(f"不认识的键: {name}")
    user32.keybd_event(code, 0, 0, 0)
    time.sleep(0.04)
    user32.keybd_event(code, 0, 2, 0)
    time.sleep(0.15)
    print(f"key {name}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "info"
    if cmd == "shot":
        shot(sys.argv[2])
    elif cmd == "click":
        click(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "move":
        move(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "drag":
        drag(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
    elif cmd == "key":
        key(sys.argv[2])
    elif cmd == "info":
        hwnd = find_window()
        print(f"hwnd={hwnd} rect={window_rect(hwnd) if hwnd else 'not found'}")
    elif cmd == "activate":
        activate(find_window())
        print("activated")
    else:
        raise SystemExit(__doc__)
