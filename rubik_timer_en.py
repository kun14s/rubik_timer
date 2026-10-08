import json
import os
import random
import sys
import time
import tkinter as tk
import tkinter.font as tkfont

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

INSPECTION_SECONDS = 15.0
PENALTY_SECONDS    = 2.0

SCRAMBLE_LENGTH = 20
SCRAMBLE_AXIS_FACES = {
    0: ("R", "L"),
    1: ("U", "D"),
    2: ("F", "B"),
}
SCRAMBLE_MODS = ("", "'", "2")

TICK_FAST = 20
TICK_SLOW = 30

HIST_RENDER_LIMIT = 200
SAVE_DEBOUNCE_MS  = 500

BG        = "#0e0e12"
FG        = "#f5f5f7"
FG_DIM    = "#8a8a99"
FG_WARN   = "#ffb020"
FG_DANGER = "#ff3b30"
SEL_BG    = "#ffffff"
SEL_FG    = "#0e0e12"
PB_BG     = "#1e5f34"
WORST_BG  = "#7a2222"

ACTION_KEY = "space"
IGNORED_KEYS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
    "Meta_L", "Meta_R", "Super_L", "Super_R",
    "Caps_Lock", "Num_Lock", "Scroll_Lock",
}

DNF_VALUE = float("inf")

SOUND_ENABLED = True

SOUND_ALIAS = {
    "inspect": "SystemAsterisk",
    "warn8":   "SystemExclamation",
    "warn3":   "SystemHand",
    "go":      "SystemNotification",
    "stop":    ".Default",
    "pb":      "SystemAsterisk",
    "dnf":     "SystemHand",
}


def play_sound(name):
    if not SOUND_ENABLED or not HAS_WINSOUND:
        return
    alias = SOUND_ALIAS.get(name)
    if alias is None:
        return
    try:
        winsound.PlaySound(
            alias,
            winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
    except RuntimeError:
        pass


if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        BASE_DIR = os.getcwd()
HISTORY_FILE = os.path.join(BASE_DIR, "cube_times.json")

if sys.platform.startswith("win"):
    NUM_FAMILY, UI_FAMILY = "Consolas", "Segoe UI"
elif sys.platform == "darwin":
    NUM_FAMILY, UI_FAMILY = "Menlo", "Helvetica Neue"
else:
    NUM_FAMILY, UI_FAMILY = "DejaVu Sans Mono", "DejaVu Sans"


def value_to_seconds(value):
    if not value or value == "DNF":
        return None
    try:
        return float(value.rstrip("+"))
    except ValueError:
        return None


def average_of_n(values, n):
    if len(values) < n:
        return "-"
    window = sorted(DNF_VALUE if v is None else v for v in values[-n:])
    trimmed = window[1:-1]
    if trimmed and trimmed[-1] == DNF_VALUE:
        return None
    return sum(trimmed) / len(trimmed)


def fmt_avg(v):
    if v == "-":
        return "-"
    if v is None:
        return "DNF"
    return f"{v:.2f}"


def load_history():
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


def save_history(records):
    tmp = HISTORY_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"records": records}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, HISTORY_FILE)
    except OSError:
        pass


def gen_scramble(length=SCRAMBLE_LENGTH):
    moves = []
    last_axis = -1
    for _ in range(length):
        axis = random.choice([a for a in SCRAMBLE_AXIS_FACES if a != last_axis])
        face = random.choice(SCRAMBLE_AXIS_FACES[axis])
        last_axis = axis
        moves.append(face + random.choice(SCRAMBLE_MODS))
    return " ".join(moves)


class RubikTimer:

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Rubik's Cube Timer")
        root.geometry("920x580")
        root.minsize(680, 480)
        root.configure(bg=BG)

        self.font_num      = tkfont.Font(family=NUM_FAMILY, size=120, weight="bold")
        self.font_num_xl   = tkfont.Font(family=NUM_FAMILY, size=150, weight="bold")
        self.font_small    = tkfont.Font(family=UI_FAMILY,  size=20)
        self.font_hist     = tkfont.Font(family=NUM_FAMILY, size=15)
        self.font_scramble = tkfont.Font(family=NUM_FAMILY, size=22)

        self.scramble_label = tk.Label(root, text=gen_scramble(),
                                       font=self.font_scramble, bg=BG, fg=FG_DIM)
        self.scramble_label.pack(side="top", fill="x", padx=20, pady=(20, 0))

        self.session_label = tk.Label(root, text="", font=self.font_hist,
                                      bg=BG, fg=FG_DIM)
        self.session_label.pack(side="bottom", fill="x", pady=(0, 12))

        self.big = tk.Label(root, text="", font=self.font_num, bg=BG, fg=FG)
        self.big.pack(expand=True, fill="both", padx=20, pady=(24, 0))

        self.small = tk.Label(root, text="", font=self.font_small, bg=BG, fg=FG_DIM)
        self.small.pack(side="bottom", fill="x", pady=(0, 8))

        self.hist_frame = tk.Frame(root, bg=BG)
        self.hist_text = tk.Text(self.hist_frame, bg=BG, fg=FG, font=self.font_hist,
                                 bd=0, highlightthickness=0, wrap="none",
                                 insertwidth=0, takefocus=0, padx=28, pady=22)
        self.hist_text.tag_configure("pb", background=PB_BG, foreground=FG)
        self.hist_text.tag_configure("worst", background=WORST_BG, foreground=FG)
        self.hist_text.tag_configure("sel", background=SEL_BG, foreground=SEL_FG)
        scroll = tk.Scrollbar(self.hist_frame, command=self.hist_text.yview,
                              bg=BG, troughcolor=BG, bd=0, highlightthickness=0)
        self.hist_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.hist_text.pack(side="left", fill="both", expand=True)

        self.state         = "idle"
        self.job           = None
        self.phase_start   = 0.0
        self.plus2         = False
        self.lock_until    = 0.0
        self.held_key      = None
        self.hist_visible  = False
        self.hist_pos      = 0
        self.confirm_clear = False
        self.current_scramble = ""
        self._warned_8 = False
        self._warned_3 = False
        self._base_hint = ""
        self._hint_color = FG_DIM
        self._sel_lineno = None
        self._save_job = None
        self._parsed_cache = None

        self.records = load_history()
        self._refresh_stats()

        root.bind("<KeyPress>",   self.on_key_press)
        root.bind("<KeyRelease>", self.on_key_release)
        root.bind("<Button-1>",   lambda _e: root.focus_force())
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(50, root.focus_force)

        self.to_idle()

    def _on_close(self):
        if self._save_job is not None:
            try:
                self.root.after_cancel(self._save_job)
            except tk.TclError:
                pass
            self._save_job = None
            save_history(self.records)
        self.root.destroy()

    def _parsed_values(self):
        if self._parsed_cache is None:
            self._parsed_cache = [value_to_seconds(r["value"]) for r in self.records]
        return self._parsed_cache

    def _invalidate_cache(self):
        self._parsed_cache = None

    def _schedule_save(self):
        if self._save_job is not None:
            return
        self._save_job = self.root.after(SAVE_DEBOUNCE_MS, self._flush_save)

    def _flush_save(self):
        self._save_job = None
        save_history(self.records)

    def _cancel(self):
        if self.job is not None:
            try:
                self.root.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None

    def _sound_tag(self):
        return "Sound on" if SOUND_ENABLED else "Sound off"

    def _render_hint(self):
        text = self._base_hint
        if text:
            text = f"{text} · {self._sound_tag()}"
        self.small.config(text=text, fg=self._hint_color)

    def _show(self, text, color=FG, font=None, hint="", hint_color=FG_DIM):
        if self._base_hint != hint or self._hint_color != hint_color:
            self._base_hint = hint
            self._hint_color = hint_color
            full = f"{hint} · {self._sound_tag()}" if hint else ""
            self.small.config(text=full, fg=hint_color)
        if self.big.cget("text") != text or self.big.cget("fg") != color:
            self.big.config(text=text, fg=color, font=font or self.font_num)

    def _set_hint(self, text, color=FG_DIM):
        if self._base_hint != text or self._hint_color != color:
            self._base_hint = text
            self._hint_color = color
            full = f"{text} · {self._sound_tag()}" if text else ""
            self.small.config(text=full, fg=color)

    def _refresh_stats(self):
        values = self._parsed_values()
        valid = [v for v in values if v is not None]

        parts = [f"Solves {len(values)}"]
        parts.append(f"Best {min(valid):.2f}" if valid else "Best -")
        parts.append(f"ao5 {fmt_avg(average_of_n(values, 5))}")
        parts.append(f"ao12 {fmt_avg(average_of_n(values, 12))}")
        self.session_label.config(text="        ".join(parts))

    def _record(self, value):
        self.records.append({
            "value": value,
            "scramble": self.current_scramble,
        })
        self._invalidate_cache()
        self._schedule_save()
        self._refresh_stats()

    def to_idle(self, new_scramble=False):
        self._cancel()
        self.state = "idle"
        self.plus2 = False
        self.confirm_clear = False
        if new_scramble:
            self.scramble_label.config(text=gen_scramble())
        self._show("0.00", FG, self.font_num,
                   "Space to inspect · H history · C clear history · M mute")

    def start_inspection(self):
        self._cancel()
        self._hide_history()
        self.state = "inspect"
        self.plus2 = False
        self._warned_8 = False
        self._warned_3 = False
        self.current_scramble = self.scramble_label.cget("text")
        self.phase_start = time.perf_counter()
        self.lock_until = self.phase_start + 0.5
        play_sound("inspect")
        self.tick_inspection()

    def tick_inspection(self):
        remain = INSPECTION_SECONDS - (time.perf_counter() - self.phase_start)
        if remain <= 0.0:
            self.start_penalty()
            return

        if remain > 8.0:
            color, tag = FG, ""
        elif remain > 3.0:
            color, tag = FG_WARN, " (8s left)"
            if not self._warned_8:
                self._warned_8 = True
                play_sound("warn8")
        else:
            color, tag = FG_DANGER, " (3s left)"
            if not self._warned_3:
                self._warned_3 = True
                play_sound("warn3")

        self._show(f"{remain:.1f}", color, self.font_num,
                   f"Inspecting{tag} · Space to start", color)
        self.job = self.root.after(TICK_SLOW, self.tick_inspection)

    def start_penalty(self):
        self._cancel()
        self.state = "penalty"
        self.plus2 = True
        self.phase_start = time.perf_counter()
        self.tick_penalty()

    def tick_penalty(self):
        remain = PENALTY_SECONDS - (time.perf_counter() - self.phase_start)
        if remain <= 0.0:
            self.show_dnf()
            return
        self._show(f"+2  {remain:.1f}", FG_WARN, self.font_num,
                   "Inspection overtime +2 · Space to confirm, timeout gives DNF", FG_WARN)
        self.job = self.root.after(TICK_SLOW, self.tick_penalty)

    def show_dnf(self):
        self._cancel()
        self.state = "dnf"
        self._record("DNF")
        play_sound("dnf")
        self._show("DNF", FG_DANGER, self.font_num_xl,
                   "DNF · Space for new scramble", FG_DANGER)

    def start_run(self):
        self._cancel()
        self._hide_history()
        self.state = "run"
        self.current_scramble = self.scramble_label.cget("text")
        self.phase_start = time.perf_counter()
        self.lock_until = self.phase_start + 0.2
        play_sound("go")
        self.tick_run()

    def tick_run(self):
        elapsed = time.perf_counter() - self.phase_start
        self._show(f"{elapsed:.2f}", FG, self.font_num, "Running · any key to stop")
        self.job = self.root.after(TICK_FAST, self.tick_run)

    def stop_run(self):
        self._cancel()
        elapsed = time.perf_counter() - self.phase_start
        self.state = "done"
        self.lock_until = time.perf_counter() + 0.35

        if self.plus2:
            total = elapsed + PENALTY_SECONDS
            value = f"{total:.2f}+"
        else:
            total = elapsed
            value = f"{elapsed:.2f}"

        previous = [v for v in self._parsed_values() if v is not None]
        is_pb = (not previous) or (total < min(previous))

        self._record(value)
        play_sound("pb" if is_pb else "stop")

        if self.plus2:
            self._show(f"{total:.2f}", FG_WARN, self.font_num,
                       f"{elapsed:.2f} + 2.00 = {total:.2f}s · Space for new scramble", FG_WARN)
        else:
            self._show(f"{elapsed:.2f}", FG, self.font_num,
                       f"{elapsed:.2f}s · Space for new scramble")

    def toggle_history(self):
        if self.hist_visible:
            self._hide_history()
        else:
            self.hist_pos = 0
            self.confirm_clear = False
            self._sel_lineno = None
            self._render_history()
            self.hist_frame.place(x=0, y=0, relwidth=1, relheight=1)
            self.hist_frame.lift()
            self.hist_visible = True

    def _hide_history(self):
        if self.hist_visible:
            self.hist_frame.place_forget()
            self.hist_visible = False
        self.confirm_clear = False
        self.root.focus_force()

    @staticmethod
    def _pb_worst_indices(values):
        if not values:
            return None, set()

        valid = [(i, v) for i, v in enumerate(values) if v is not None]
        pb_idx = min(valid, key=lambda iv: iv[1])[0] if valid else None

        worst = {i for i, v in enumerate(values) if v is None}
        if valid:
            worst.add(max(valid, key=lambda iv: iv[1])[0])
        if pb_idx is not None:
            worst.discard(pb_idx)

        return pb_idx, worst

    def _render_history(self):
        total = len(self.records)
        values = self._parsed_values()
        valid = [v for v in values if v is not None]

        head = f"Solves {total}"
        if valid:
            head += (f"        Best {min(valid):.2f}"
                     f"        ao5 {fmt_avg(average_of_n(values, 5))}"
                     f"        ao12 {fmt_avg(average_of_n(values, 12))}")

        pb_idx, worst_idxs = self._pb_worst_indices(values)
        show_n = min(total, HIST_RENDER_LIMIT)

        self.hist_text.config(state="normal")
        self.hist_text.delete("1.0", "end")
        self.hist_text.insert("end", head + "\n")
        self.hist_text.insert("end", "─" * 58 + "\n\n")

        if total == 0:
            self.hist_text.insert("end", "No solves yet\n")
        else:
            for pos in range(show_n):
                idx = total - 1 - pos
                rec = self.records[idx]
                lineno = 4 + pos
                self.hist_text.insert(
                    "end", f"{idx + 1:>5}.  {rec['value']:>8}    {rec['scramble']}\n"
                )
                if idx == pb_idx:
                    self.hist_text.tag_add("pb", f"{lineno}.0", f"{lineno}.end")
                elif idx in worst_idxs:
                    self.hist_text.tag_add("worst", f"{lineno}.0", f"{lineno}.end")
            if total > show_n:
                self.hist_text.insert(
                    "end", f"\n…… {total - show_n} older solves not shown ……\n"
                )

        if self.confirm_clear:
            self.hist_text.insert("end",
                                  "\nPress C again to clear all history · any other key cancels")
        else:
            self.hist_text.insert("end", "\n↑↓ select · D delete · C clear · H / Esc back")
        self.hist_text.config(state="disabled")

        self._sel_lineno = None
        if show_n:
            self.hist_pos = max(0, min(self.hist_pos, show_n - 1))
            self._highlight(self.hist_pos)

    def _highlight(self, pos):
        if self._sel_lineno is not None:
            self.hist_text.tag_remove(
                "sel", f"{self._sel_lineno}.0", f"{self._sel_lineno}.end"
            )
        lineno = 4 + pos
        self.hist_text.tag_add("sel", f"{lineno}.0", f"{lineno}.end")
        self.hist_text.see(f"{lineno}.0")
        self._sel_lineno = lineno

    def _move_hist(self, delta):
        total = len(self.records)
        if total == 0:
            return
        limit = min(total, HIST_RENDER_LIMIT)
        new_pos = max(0, min(self.hist_pos + delta, limit - 1))
        if new_pos == self.hist_pos:
            return
        self.hist_pos = new_pos
        self._highlight(new_pos)

    def _delete_hist(self):
        total = len(self.records)
        if total == 0:
            return
        idx = total - 1 - self.hist_pos
        if not (0 <= idx < total):
            return
        removed = self.records.pop(idx)
        self._invalidate_cache()
        self._schedule_save()
        self._refresh_stats()

        new_total = len(self.records)
        if new_total:
            limit = min(new_total, HIST_RENDER_LIMIT)
            self.hist_pos = min(self.hist_pos, limit - 1)
        else:
            self.hist_pos = 0
        self._sel_lineno = None
        self._render_history()
        return removed

    def _clear_history(self):
        self.records = []
        self._invalidate_cache()
        save_history(self.records)
        self._refresh_stats()
        self.confirm_clear = False
        self.hist_pos = 0
        self._sel_lineno = None
        if self.hist_visible:
            self._render_history()
        else:
            self._show("0.00", FG, self.font_num,
                       "History cleared · Space to inspect · H history · C clear history · M mute")

    def on_key_press(self, event):
        global SOUND_ENABLED

        ks = event.keysym
        if ks in IGNORED_KEYS:
            return
        if ks == self.held_key and ks not in ("Up", "Down"):
            return
        self.held_key = ks

        if self.state == "run":
            if time.perf_counter() < self.lock_until:
                return
            self.stop_run()
            return

        if self.hist_visible:
            if self.confirm_clear:
                if ks in ("c", "C"):
                    self._clear_history()
                else:
                    self.confirm_clear = False
                    self._render_history()
                return

            if ks in ("h", "H", "Escape"):
                self._hide_history()
            elif ks == "Up":
                self._move_hist(-1)
            elif ks == "Down":
                self._move_hist(1)
            elif ks in ("d", "D"):
                self._delete_hist()
            elif ks in ("c", "C"):
                self.confirm_clear = True
                self._render_history()
            return

        if self.confirm_clear:
            if ks in ("c", "C"):
                self._clear_history()
            else:
                self.confirm_clear = False
                self._set_hint("Space to inspect · H history · C clear history · M mute")
            return

        if ks in ("m", "M"):
            SOUND_ENABLED = not SOUND_ENABLED
            self._render_hint()
            if SOUND_ENABLED:
                play_sound("go")
            return

        if ks == "Escape":
            self.to_idle(new_scramble=True)
            return

        if ks in ("h", "H"):
            self.toggle_history()
            return

        if ks in ("c", "C"):
            self.confirm_clear = True
            self._set_hint("Press C again to clear history · any other key cancels", FG_DANGER)
            return

        if time.perf_counter() < self.lock_until:
            return
        if ks != ACTION_KEY:
            return

        st = self.state
        if st == "idle":
            self.start_inspection()
        elif st in ("inspect", "penalty"):
            self.start_run()
        elif st in ("done", "dnf"):
            self.to_idle(new_scramble=True)

    def on_key_release(self, event):
        if event.keysym == self.held_key:
            self.held_key = None


def main():
    root = tk.Tk()
    RubikTimer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
