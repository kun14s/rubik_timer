import json
import math
import os
import sys
import tkinter as tk
import tkinter.font as tkfont


BG        = "#0e0e12"
FG        = "#f5f5f7"
FG_DIM    = "#8a8a99"
FG_WARN   = "#ffb020"
FG_DANGER = "#ff3b30"
GRID      = "#22222a"
AXIS      = "#55555f"
LINE      = "#4ea1ff"
PB_COLOR  = "#34c759"
DNF_COLOR = "#ff3b30"

DNF_VALUE = float("inf")

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        BASE_DIR = os.getcwd()
HISTORY_FILE = os.path.join(BASE_DIR, "cube_times.json")

if sys.platform.startswith("win"):
    NUM_FAMILY, UI_FAMILY = "Consolas", "Microsoft YaHei"
elif sys.platform == "darwin":
    NUM_FAMILY, UI_FAMILY = "Menlo", "PingFang SC"
else:
    NUM_FAMILY, UI_FAMILY = "DejaVu Sans Mono", "Noto Sans CJK SC"


TEXT = {
    "title":      "魔方成绩图表 · Rubik's Cube Chart",
    "solves":     "次数 / Solves",
    "best":       "最佳 / Best",
    "worst":      "最差 / Worst",
    "no_data":    "暂无成绩数据，请先运行计时器\nNo solve data yet. Run the timer first.",
    "reload":     "R  重新加载 / Reload",
    "close":      "Esc  关闭 / Close",
    "time_axis":  "时间 / Time (s)",
    "index_axis": "序号 / Index",
    "load_err":   "读取 cube_times.json 失败 / Failed to read cube_times.json",
}


def value_to_seconds(value):
    if not value or value == "DNF":
        return None
    try:
        return float(value.rstrip("+"))
    except ValueError:
        return None


def nice_step(v):
    if v <= 0:
        return 1.0
    exp = math.floor(math.log10(v))
    f = v / (10 ** exp)
    if f <= 1:
        nf = 1.0
    elif f <= 2:
        nf = 2.0
    elif f <= 2.5:
        nf = 2.5
    elif f <= 5:
        nf = 5.0
    else:
        nf = 10.0
    return nf * (10 ** exp)


class ChartWindow:

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(TEXT["title"])
        root.geometry("1000x620")
        root.minsize(720, 480)
        root.configure(bg=BG)

        self.font_header = tkfont.Font(family=NUM_FAMILY, size=13)
        self.font_axis   = tkfont.Font(family=NUM_FAMILY, size=11)
        self.font_label  = tkfont.Font(family=UI_FAMILY,  size=14)
        self.font_dnf    = tkfont.Font(family=NUM_FAMILY, size=10, weight="bold")

        self.header = tk.Label(root, text="", font=self.font_header,
                               bg=BG, fg=FG, anchor="w", justify="left")
        self.header.pack(side="top", fill="x", padx=20, pady=(14, 0))

        self.footer = tk.Label(
            root,
            text=f"{TEXT['reload']}    ·    {TEXT['close']}",
            font=self.font_header, bg=BG, fg=FG_DIM,
        )
        self.footer.pack(side="bottom", fill="x", pady=(0, 12))

        self.canvas = tk.Canvas(root, bg=BG, bd=0, highlightthickness=0)
        self.canvas.pack(side="top", fill="both", expand=True,
                         padx=8, pady=(6, 4))

        self._resize_job = None
        self.canvas.bind("<Configure>", self._on_resize)

        self.records = []
        self.times = []

        root.bind("<KeyPress>", self.on_key)
        root.bind("<Button-1>", lambda _e: root.focus_force())
        root.after(50, root.focus_force)

        self.reload()

    def _on_resize(self, _event):
        if self._resize_job is not None:
            try:
                self.root.after_cancel(self._resize_job)
            except tk.TclError:
                pass
        self._resize_job = self.root.after(40, self.draw)

    @staticmethod
    def _read_history():
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return []
        if isinstance(data, dict):
            data = data.get("records", [])
        if not isinstance(data, list):
            return []
        records = []
        for item in data:
            if isinstance(item, dict) and "value" in item:
                records.append({
                    "value": str(item["value"]),
                    "scramble": str(item.get("scramble", "")),
                })
        return records

    def reload(self):
        self.records = self._read_history()
        self.times = [value_to_seconds(r["value"]) for r in self.records]
        self._update_header()
        self.draw()

    def _avg(self, n):
        if len(self.times) < n:
            return "-"
        window = sorted(DNF_VALUE if t is None else t for t in self.times[-n:])
        trimmed = window[1:-1]
        if trimmed and trimmed[-1] == DNF_VALUE:
            return None
        return sum(trimmed) / len(trimmed)

    @staticmethod
    def _fmt_avg(v):
        if v == "-":
            return "-"
        if v is None:
            return "DNF"
        return f"{v:.2f}"

    def _update_header(self):
        n = len(self.times)
        valid = [t for t in self.times if t is not None]
        dnf_count = n - len(valid)

        parts = [f"{TEXT['solves']}: {n}"]
        parts.append(f"{TEXT['best']}: {min(valid):.2f}" if valid else f"{TEXT['best']}: -")
        parts.append(f"{TEXT['worst']}: {max(valid):.2f}" if valid else f"{TEXT['worst']}: -")
        parts.append(f"ao5: {self._fmt_avg(self._avg(5))}")
        parts.append(f"ao12: {self._fmt_avg(self._avg(12))}")
        parts.append(f"DNF: {dnf_count}")
        self.header.config(text="      ".join(parts))

    def _reduce(self, n, plot_w):
        if n <= 1:
            return list(range(n))
        plot_w = max(int(plot_w), 1)
        if n <= plot_w * 2:
            return list(range(n))

        times = self.times

        def v(t):
            return 0.0 if t is None else t

        buckets = {}
        for i in range(n):
            b = int(i * plot_w / n)
            cur = buckets.get(b)
            if cur is None:
                buckets[b] = [i, i]
            else:
                if v(times[i]) < v(times[cur[0]]):
                    cur[0] = i
                if v(times[i]) > v(times[cur[1]]):
                    cur[1] = i

        idx_set = set()
        for lo, hi in buckets.values():
            idx_set.add(lo)
            idx_set.add(hi)
        return sorted(idx_set)

    def draw(self):
        self._resize_job = None
        c = self.canvas
        c.delete("all")

        w = c.winfo_width()
        h = c.winfo_height()
        if w < 80 or h < 80:
            return

        m_l, m_r, m_t, m_b = 80, 36, 48, 62
        plot_w = w - m_l - m_r
        plot_h = h - m_t - m_b
        if plot_w < 40 or plot_h < 40:
            return

        n = len(self.times)
        if n == 0:
            c.create_text(w / 2, h / 2, text=TEXT["no_data"],
                          fill=FG_DIM, font=self.font_label, justify="center")
            return

        valid = [t for t in self.times if t is not None]
        max_val = max(valid) if valid else 10.0
        max_val = max(max_val * 1.08, 1.0)

        step = nice_step(max_val / 5.0)
        y_max = step * 5
        while y_max < max_val:
            y_max += step
        ticks = int(round(y_max / step))

        def x_of(i):
            if n == 1:
                return m_l + plot_w / 2
            return m_l + plot_w * i / (n - 1)

        def y_of(t):
            return m_t + plot_h * (1 - t / y_max)

        for k in range(ticks + 1):
            val = step * k
            y = y_of(val)
            c.create_line(m_l, y, m_l + plot_w, y, fill=GRID)
            c.create_text(m_l - 10, y, text=f"{val:g}",
                          fill=FG_DIM, font=self.font_axis, anchor="e")

        c.create_line(m_l, m_t, m_l, m_t + plot_h, fill=AXIS)
        c.create_line(m_l, m_t + plot_h,
                      m_l + plot_w, m_t + plot_h, fill=AXIS)

        c.create_text(m_l, m_t - 26, text=TEXT["time_axis"],
                      fill=FG_DIM, font=self.font_axis, anchor="w")

        max_x_labels = max(2, int(plot_w // 70))
        if n <= max_x_labels:
            label_idxs = list(range(n))
        else:
            step_x = (n - 1) / (max_x_labels - 1)
            label_idxs = sorted({int(round(i * step_x))
                                 for i in range(max_x_labels)})

        for i in label_idxs:
            c.create_text(x_of(i), m_t + plot_h + 14, text=str(i + 1),
                          fill=FG_DIM, font=self.font_axis, anchor="n")

        c.create_text(m_l + plot_w, m_t + plot_h + 36,
                      text=TEXT["index_axis"], fill=FG_DIM,
                      font=self.font_axis, anchor="e")

        draw_idxs = self._reduce(n, plot_w)
        pts = []
        for i in draw_idxs:
            t = self.times[i]
            v = 0.0 if t is None else t
            pts.append((i, t, x_of(i), y_of(v)))

        if len(pts) >= 2:
            flat = []
            for _, _, x, y in pts:
                flat.append(x)
                flat.append(y)
            c.create_line(*flat, fill=LINE, width=1.6)

        if n <= 80:
            r = 3.5
        elif n <= 300:
            r = 2.5
        else:
            r = 0

        show_dnf_label = n <= 80
        for i, t, x, y in pts:
            if t is None:
                if r > 0:
                    c.create_oval(x - r - 1.5, y - r - 1.5,
                                  x + r + 1.5, y + r + 1.5,
                                  fill=DNF_COLOR, outline="")
                if show_dnf_label:
                    c.create_text(x, y - 9, text="DNF",
                                  fill=DNF_COLOR, font=self.font_dnf,
                                  anchor="s")
            else:
                if r > 0:
                    c.create_oval(x - r, y - r, x + r, y + r,
                                  fill=LINE, outline="")

        if valid:
            pb_val = min(valid)
            for i, t in enumerate(self.times):
                if t == pb_val:
                    x = x_of(i)
                    y = y_of(pb_val)
                    c.create_oval(x - 6, y - 6, x + 6, y + 6,
                                  outline=PB_COLOR, width=2)
                    c.create_text(x, y - 14, text=f"PB {pb_val:.2f}",
                                  fill=PB_COLOR, font=self.font_axis,
                                  anchor="s")
                    break

    def on_key(self, event):
        ks = event.keysym
        if ks in ("r", "R"):
            self.reload()
        elif ks == "Escape":
            self.root.destroy()


def main():
    root = tk.Tk()
    ChartWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
