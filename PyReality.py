# PyReality v3.2 — Cognitive Rift (VSCode-like editor + Jedi + Smart Indent, 800x600)
# Editor: رنگی، شماره‌خط، auto-indent، Smart Enter/Tab/Shift-Tab/Backspace، Autocomplete (Ctrl+Space + تایپ)
# Runtime: اجرای ایزوله در subprocess، Trace خط‌به‌خط، گراف بلاک‌های کنترلی

from __future__ import annotations

import ast
import json
import math
import os
import re
import subprocess
import tempfile
import threading
import time
import traceback
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Tuple

import sys

try:
    import tkinter as tk
except Exception as exc:
    print("Tkinter در دسترس نیست:", exc)
    sys.exit(1)

# ادیتور شبیه VS Code
try:
    from tkcode import CodeEditor  # pip install tkcode
except Exception:
    print("کتابخانه tkcode نصب نیست. ابتدا اجرا کنید: pip install tkcode")
    raise

# تکمیل خودکار پایتون
try:
    import jedi  # pip install jedi
except Exception:
    print("کتابخانه jedi نصب نیست. ابتدا اجرا کنید: pip install jedi")
    raise

# ============================================================================
# Constants & Utilities
# ============================================================================

APP_TITLE = "PyReality v3.2 — Cognitive Rift"
WINDOW_SIZE = "800x600"
CANVAS_BOUNDS: Tuple[int, int, int, int] = (20, 20, 780, 580)
TRACE_TAG = "__PYREALITY_TRACE__"

RNG_SEED = 1337
INDENT_WIDTH = 4
DEDENT_HEADS = ("elif", "else", "except", "finally")

_seed = RNG_SEED


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def random_uniform() -> float:
    global _seed
    _seed = (1103515245 * _seed + 12345) & 0x7FFFFFFF
    return (_seed % 10000) / 10000.0


# ============================================================================
# Cognitive Profile
# ============================================================================


class CognitiveProfile:
    """مدل ساده وضعیت شناختی کاربر."""

    __slots__ = ("focus_level", "anxiety_level", "code_confidence", "history")

    def __init__(self) -> None:
        self.focus_level: float = 0.7
        self.anxiety_level: float = 0.3
        self.code_confidence: float = 0.5
        self.history: Deque[Dict[str, float]] = deque(maxlen=300)

    def update(self, typing_speed: float, error_rate: float, code_depth: float) -> None:
        drift = (typing_speed / 100.0) - error_rate + (code_depth / 10.0)
        self.focus_level = clamp(self.focus_level + drift * 0.05, 0.0, 1.0)
        self.anxiety_level = clamp(1.0 - self.focus_level, 0.0, 1.0)
        self.code_confidence = clamp((1.0 - error_rate) * 0.85 + (code_depth * 0.15), 0.0, 1.0)
        self.history.append(
            {
                "focus": self.focus_level,
                "anxiety": self.anxiety_level,
                "confidence": self.code_confidence,
            }
        )


# ============================================================================
# MetaCognitive Engine
# ============================================================================


class MetaCognitiveEngine:
    """تحلیل AST و تولید معیارهای شناختی برای UI."""

    ICON_MAP: Dict[str, str] = {
        "function": "🌀",
        "class": "⚡",
        "loop": "∞",
        "condition": "Δ",
        "variable": "○",
        "comprehension": "◎",
        "call_or_deco": "✷",
        "import": "⇢",
        "exception": "‼",
    }

    def __init__(self) -> None:
        self.concept_graph: Dict[str, int] = defaultdict(int)
        self.profile = CognitiveProfile()
        self._syntax_error_counter = 0

    def analyze(self, code: str) -> Dict[str, object]:
        if not code.strip():
            self.concept_graph.clear()
            return self._state(status="empty", suggestion="کد بنویسید")
        try:
            tree = ast.parse(code)
            self._syntax_error_counter = max(0, self._syntax_error_counter - 1)
            self._extract_concepts(tree)
            depth = self.measure_concept_depth(code)
            err_rate = self.estimate_error_rate()
            return self._state(
                status="parsed",
                suggestion=self._summary_text(),
                depth=depth,
                error_rate=err_rate,
            )
        except Exception:
            self._syntax_error_counter += 1
            return self._state(
                status="syntax_error", suggestion="خطای نحوی. ساده‌تر کنید یا پرانتزها را ببندید."
            )

    def measure_concept_depth(self, code: str) -> float:
        try:
            tree = ast.parse(code)
        except Exception:
            return 0.2
        depths: List[int] = []

        def _depth(node: ast.AST, d: int = 0) -> None:
            depths.append(d)
            for child in ast.iter_child_nodes(node):
                _depth(child, d + 1)

        _depth(tree, 0)
        if not depths:
            return 0.2
        return clamp(sum(depths) / (len(depths) * 10.0), 0.0, 1.0)

    def estimate_error_rate(self) -> float:
        return clamp(self._syntax_error_counter / 5.0, 0.0, 1.0)

    def _extract_concepts(self, tree: ast.AST) -> None:
        self.concept_graph.clear()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.concept_graph["function"] += 1
            elif isinstance(node, ast.ClassDef):
                self.concept_graph["class"] += 1
            elif isinstance(node, (ast.For, ast.While)):
                self.concept_graph["loop"] += 1
            elif isinstance(node, ast.If):
                self.concept_graph["condition"] += 1
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                self.concept_graph["variable"] += 1
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                self.concept_graph["comprehension"] += 1
            elif isinstance(node, (ast.Call, ast.keyword)):
                self.concept_graph["call_or_deco"] += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self.concept_graph["import"] += 1
            elif isinstance(node, (ast.Raise, ast.Try, ast.ExceptHandler)):
                self.concept_graph["exception"] += 1

    def _summary_text(self) -> str:
        if not self.concept_graph:
            return "الگویی یافت نشد."
        parts = [f"{k}:{v}" for k, v in sorted(self.concept_graph.items())]
        return "الگوهای کشف‌شده: " + ", ".join(parts)

    def _state(
        self,
        *,
        status: str,
        suggestion: str,
        depth: Optional[float] = None,
        error_rate: Optional[float] = None,
    ) -> Dict[str, object]:
        total = sum(self.concept_graph.values())
        if total <= 3:
            load = 0
        elif total <= 8:
            load = 1
        elif total <= 16:
            load = 2
        else:
            load = 3
        return {
            "concepts": dict(self.concept_graph),
            "cognitive_load": load,
            "metrics": {"status": status, "suggestion": suggestion},
            "depth": 0.5 if depth is None else depth,
            "error_rate": 0.0 if error_rate is None else error_rate,
        }


# ============================================================================
# Execution Sandbox
# ============================================================================


class ExecutionSandbox:
    """اجرای کد در subprocess ایزوله با ردیابی اختیاری."""

    def __init__(self, time_limit_sec: float = 3.0) -> None:
        self.time_limit = time_limit_sec
        self.process: Optional[subprocess.Popen] = None
        self.tempdir: Optional[str] = None

    def build_traced_script(self, code: str, enable_trace: bool) -> str:
        lines = [
            "import sys, os, linecache",
            "",
            "def _tracer(frame, event, arg):",
            "    if event == 'line':",
            f"        sys.stdout.write('{TRACE_TAG} ' + str(frame.f_lineno) + '\\n')",
            "        sys.stdout.flush()",
            "    return _tracer",
            "",
            f"if {str(bool(enable_trace))}:",
            "    sys.settrace(_tracer)",
            "",
        ]
        return "\n".join(lines) + "\n" + code

    def run(
        self, code: str, *, enable_trace: bool = False, stdin_data: str = ""
    ) -> Tuple[str, str, int]:
        self.tempdir = tempfile.mkdtemp(prefix="pyreality_")
        script_path = os.path.join(self.tempdir, "script.py")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(self.build_traced_script(code, enable_trace))

        env = {"PYTHONIOENCODING": "utf-8"}

        try:
            self.process = subprocess.Popen(
                [sys.executable, "-I", "-S", script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.tempdir,
                env=env,
                text=True,
            )
            try:
                out, err = self.process.communicate(stdin_data, timeout=self.time_limit)
            except subprocess.TimeoutExpired:
                self.process.kill()
                out, err = self.process.communicate()
                err += "\n[TimeLimitError] اجرای برنامه از حد زمان مجاز گذشت."
            rc = int(self.process.returncode or 0)
            return out, err, rc
        finally:
            self.cleanup()

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.kill()

    def cleanup(self) -> None:
        if self.tempdir and os.path.exists(self.tempdir):
            try:
                for name in os.listdir(self.tempdir):
                    path = os.path.join(self.tempdir, name)
                    try:
                        os.remove(path)
                    except IsADirectoryError:
                        pass
                os.rmdir(self.tempdir)
            except Exception:
                pass


# ============================================================================
# Line Analyzer & Block Graph
# ============================================================================


class LineAnalyzer:
    """نگاشت سادهٔ نوع نودهای AST به شماره‌خط برای هایلایت."""

    def __init__(self) -> None:
        self.line_map: Dict[int, List[str]] = {}

    def analyze(self, code: str) -> Dict[int, List[str]]:
        self.line_map.clear()
        try:
            tree = ast.parse(code)
        except Exception:
            return {}
        for node in ast.walk(tree):
            if hasattr(node, "lineno"):
                ln = int(getattr(node, "lineno"))
                label = type(node).__name__
                self.line_map.setdefault(ln, []).append(label)
        return self.line_map


class BlockGraphDrawer:
    """ترسیم سادهٔ بلاک‌های کنترلی روی Canvas."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas
        self.node_items: List[int] = []

    def clear(self) -> None:
        for item in self.node_items:
            self.canvas.delete(item)
        self.node_items.clear()

    def build_from_ast(self, code: str) -> None:
        self.clear()
        try:
            tree = ast.parse(code)
        except Exception:
            return
        blocks: List[Tuple[str, str, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                blocks.append(("Function", getattr(node, "name", ""), int(node.lineno)))
            elif isinstance(node, ast.ClassDef):
                blocks.append(("Class", getattr(node, "name", ""), int(node.lineno)))
            elif isinstance(node, ast.If):
                blocks.append(("If", "cond", int(node.lineno)))
            elif isinstance(node, ast.For):
                blocks.append(("For", "iter", int(node.lineno)))
            elif isinstance(node, ast.While):
                blocks.append(("While", "cond", int(node.lineno)))
            elif isinstance(node, ast.Try):
                blocks.append(("Try", "", int(node.lineno)))
        blocks.sort(key=lambda t: t[2])

        x, y = 640, 360
        dy = 56
        prev_rect: Optional[int] = None
        for kind, label, ln in blocks[:18]:
            rect = self._draw_node(x, y, f"{kind}\nL{ln} {label}")
            if prev_rect is not None:
                self._draw_arrow(prev_rect, rect)
            prev_rect = rect
            y += dy

    def _draw_node(self, x: int, y: int, text: str) -> int:
        w, h = 200, 60
        rect = self.canvas.create_rectangle(
            x - w // 2, y - h // 2, x + w // 2, y + h // 2, outline="#4ecdc4", width=2, fill=""
        )
        label = self.canvas.create_text(x, y, text=text, fill="#E6E6FA", font=("Cascadia Code", 10))
        self.node_items.extend([rect, label])
        return rect

    def _draw_arrow(self, src_rect: int, dst_rect: int) -> None:
        x1, y1, x2, y2 = self.canvas.coords(src_rect)
        sx, sy = (x1 + x2) / 2, y2
        x1b, y1b, x2b, y2b = self.canvas.coords(dst_rect)
        dx, dy = (x1b + x2b) / 2, y1b
        line = self.canvas.create_line(sx, sy, dx, dy, fill="#45b7d1", width=2, arrow=tk.LAST)
        self.node_items.append(line)


# ============================================================================
# Surreal Canvas (UI) with VSCode-like editor + Smart Indent
# ============================================================================


class SurrealCanvas:
    """UI: Canvas + CodeEditor (tkcode) + Console + Guide + Autocomplete + Smart Indent."""

    WORD_RE = re.compile(r"[A-Za-z0-9_]+")

    def __init__(self, root: tk.Tk, engine: MetaCognitiveEngine) -> None:
        self.root = root
        self.engine = engine

        # Background canvas
        self.canvas = tk.Canvas(root, bg="#0f0f23", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.bounds = CANVAS_BOUNDS
        self.items: List[Tuple[int, float, float]] = []
        self.speed_scale = 1.0
        self.density = 1
        self._bg_shift = 0.0

        # Editor panel (tkcode)
        self.text_frame = tk.Frame(self.root, bg="#1a1a2e")
        self.editor = CodeEditor(
            self.text_frame,
            width=80,
            height=22,
            language="python",
            highlighter="dracula",
            autofocus=True,
            blockcursor=True,
            insertwidth=2,
            padx=6,
            pady=6,
        )
        self.editor.pack(fill="both", expand=True)
        self.status_lbl = tk.Label(
            self.text_frame, text="", bg="#1a1a2e", fg="#8bd", anchor="w", font=("Cascadia Code", 9)
        )
        self.status_lbl.pack(fill="x", padx=8, pady=(2, 6))

        # Console panel
        self.console_frame = tk.Frame(self.root, bg="#0b0b18")
        self.console = tk.Text(
            self.console_frame, bg="#0b0b18", fg="#C8F7C5", insertbackground="#ffffff", font=("Cascadia Code", 10), height=6, relief="flat"
        )
        self.console.pack(fill="both", expand=True, padx=10, pady=10)
        self.console.tag_configure("stderr", foreground="#ff6b6b")
        self.console.tag_configure("trace", foreground="#feca57")
        self.stdin_entry = tk.Entry(self.console_frame, bg="#111125", fg="#E6E6FA", insertbackground="#fff", font=("Cascadia Code", 9))
        self.stdin_entry.pack(fill="x", padx=10, pady=(0, 10))

        # Run bar
        self.run_bar = tk.Frame(self.root, bg="#151528")
        self.run_btn = tk.Button(self.run_bar, text="▶ Run", command=self.on_run, bg="#1f1f38", fg="#E6E6FA", relief="flat")
        self.step_btn = tk.Button(self.run_bar, text="⤴ Trace", command=self.on_trace, bg="#1f1f38", fg="#E6E6FA", relief="flat")
        self.stop_btn = tk.Button(self.run_bar, text="■ Stop", command=self.on_stop, bg="#401b1b", fg="#E6E6FA", relief="flat")
        self.blocks_btn = tk.Button(self.run_bar, text="▦ Blocks", command=self.on_blocks, bg="#1f1f38", fg="#E6E6FA", relief="flat")
        for w in (self.run_btn, self.step_btn, self.stop_btn, self.blocks_btn):
            w.pack(side="left", padx=8, pady=6)

        # Guide
        self.guide_frame = tk.Frame(self.root, bg="#151528")
        self.guide_title = tk.Label(self.guide_frame, text="Vahid", fg="#4ecdc4", bg="#151528", font=("Cascadia Code", 12, "bold"))
        self.guide_msg = tk.Message(self.guide_frame, text="...", fg="#ddd", bg="#151528", font=("Cascadia Code", 9), width=240)
        self.guide_badge = tk.Label(self.guide_frame, text="Reality: 0", fg="#feca57", bg="#151528", font=("Cascadia Code", 9, "bold"))
        self.guide_title.pack(anchor="w", padx=8, pady=(8, 2))
        self.guide_badge.pack(anchor="w", padx=8)
        self.guide_msg.pack(anchor="w", padx=8, pady=8)

        # Layout on Canvas (800x600)
        self.text_win = self.canvas.create_window(270, 260, window=self.text_frame, width=480, height=360)
        self.runbar_win = self.canvas.create_window(270, 440, window=self.run_bar, width=480, height=34)
        self.console_win = self.canvas.create_window(270, 530, window=self.console_frame, width=480, height=120)
        self.guide_win = self.canvas.create_window(640, 160, window=self.guide_frame, width=260, height=180)

        # Tools
        self.block_drawer = BlockGraphDrawer(self.canvas)
        self.line_analyzer = LineAnalyzer()
        self.sandbox = ExecutionSandbox()

        # Autocomplete popup state
        self.ac_popup: Optional[tk.Toplevel] = None
        self.ac_list: Optional[tk.Listbox] = None
        self.ac_active = False

        # Seed code
        self.editor.insert(
            "1.0",
            (
                "def f(n: int) -> int:\n"
                "    s = 0\n"
                "    for i in range(n):\n"
                "        if i % 2 == 0:\n"
                "            s += i\n"
                "    return s\n\n"
                "print(f(10))\n"
            ),
        )

        # Events
        self.editor.bind("<KeyRelease>", self._on_change)

        # Autocomplete: خودکار + Ctrl+Space
        self.editor.bind("<KeyRelease>", self._autocomplete_trigger, add="+")
        self.editor.bind("<Control-space>", self._force_autocomplete)

        # Smart indent/outdent
        self.editor.bind("<Return>", self._smart_newline)          # Enter
        self.editor.bind("<BackSpace>", self._smart_backspace)     # Backspace
        self.editor.bind("<Tab>", self._smart_tab)                 # Tab
        self.editor.bind("<ISO_Left_Tab>", self._smart_shift_tab)  # Shift+Tab
        self.editor.bind("<Shift-Tab>", self._smart_shift_tab)     # Shift+Tab (alt)

        # ضد تایپو
        self._on_autocomplete_trigger = self._autocomplete_trigger

        self._highlight_reset()
        self.root.after(30, self._tick)
        self._on_change()

    # ---------- small utils ----------
    def _line_text(self, lineno: int) -> str:
        return self.editor.get(f"{lineno}.0", f"{lineno}.end")

    def _current_line_col(self) -> Tuple[int, int]:
        li, co = self.editor.index("insert").split(".")
        return int(li), int(co)

    def _leading_spaces(self, s: str) -> int:
        i = 0
        while i < len(s) and s[i] == " ":
            i += 1
        return i

    def _prev_nonempty_line(self, start_line: int) -> Optional[int]:
        ln = start_line
        while ln > 1:
            ln -= 1
            t = self._line_text(ln).rstrip()
            if t:
                return ln
        return None

    def _next_tab_stop(self, col: int) -> int:
        return ((col // INDENT_WIDTH) + 1) * INDENT_WIDTH

    def _is_dedent_head(self, stripped: str) -> bool:
        head = stripped.split(":")[0].strip().split()
        return bool(head) and head[0] in DEDENT_HEADS

    # ---------- change & animate ----------
    def _on_change(self, _event: Optional[tk.Event] = None) -> None:
        code = self.get_code()
        state = self.engine.analyze(code)
        level = int(state.get("cognitive_load", 0))
        msg = str(state["metrics"]["suggestion"])
        self.set_feedback(msg, level)
        self._populate(state.get("concepts", {}), 1 + level)
        self.line_analyzer.analyze(code)

        # live dedent برای سرخط‌های خاص
        line, col = self._current_line_col()
        text = self._line_text(line)
        lead = self._leading_spaces(text)
        stripped = text.strip()
        if stripped and self._is_dedent_head(stripped):
            want = max(0, lead - INDENT_WIDTH)
            if want < lead:
                self.editor.delete(f"{line}.0", f"{line}.{lead}")
                self.editor.insert(f"{line}.0", " " * want)
                if col <= lead:
                    self.editor.mark_set("insert", f"{line}.{max(0, col - (lead - want))}")

    def _populate(self, concepts: Dict[str, int], density: int) -> None:
        for item, _, _ in getattr(self, "items", []):
            self.canvas.delete(item)
        self.items = []
        x0, y0, x1, y1 = self.bounds
        for key, count in concepts.items():
            icon = MetaCognitiveEngine.ICON_MAP.get(key, "·")
            n_items = max(1, min(6, count * density))
            for _ in range(n_items):
                x = int(lerp(x0, x1, random_uniform()))
                y = int(lerp(y0, y1, random_uniform()))
                item = self.canvas.create_text(x, y, text=icon, fill="#E6E6FA", font=("Segoe UI Emoji", 20, "bold"))
                vx = (1 if random_uniform() > 0.5 else -1) * (1 + 2 * random_uniform())
                vy = (1 if random_uniform() > 0.5 else -1) * (1 + 2 * random_uniform())
                self.items.append((item, vx, vy))

    def _tick(self) -> None:
        x0, y0, x1, y1 = self.bounds
        for i, (item, vx, vy) in enumerate(self.items):
            dx = int(vx * self.speed_scale)
            dy = int(vy * self.speed_scale)
            self.canvas.move(item, dx, dy)
            x, y = self.canvas.coords(item)
            if x < x0 or x > x1:
                vx = -vx
            if y < y0 or y > y1:
                vy = -vy
            self.items[i] = (item, vx, vy)
        self.root.after(30, self._tick)

    # ---------- editor API ----------
    def get_code(self) -> str:
        return self.editor.get("1.0", "end-1c")

    def typing_speed(self) -> float:
        return clamp(len(self.get_code()) / 10.0, 0.0, 120.0)

    def set_feedback(self, text: str, level: int) -> None:
        self.guide_msg.configure(text=text)
        self.guide_badge.configure(text=f"Reality: {level}")
        self.status_lbl.configure(text=text)

    # ---------- environment ----------
    def adjust_environment(self, profile: CognitiveProfile) -> None:
        target_speed = 0.6 + 0.6 * (1.0 - profile.anxiety_level)
        self.speed_scale = lerp(self.speed_scale, target_speed, 0.2)
        self.density = int(round(lerp(self.density, 1 + int(3 * profile.code_confidence), 0.2)))
        self.density = max(1, min(4, self.density))
        self._bg_shift = (self._bg_shift + 0.02 + 0.02 * profile.focus_level) % (2 * math.pi)
        base = int(15 + 10 * math.sin(self._bg_shift))
        self.canvas.configure(bg=f"#{base:02x}{base:02x}{35:02x}")

    # ---------- Smart Indent ----------
    def _smart_newline(self, _event: Optional[tk.Event] = None) -> str:
        line, col = self._current_line_col()
        text = self._line_text(line)
        before = text[:col]
        after = text[col:]
        stripped = before.strip()

        base_indent = self._leading_spaces(text)

        # dedent-head مثل else/elif/except/finally
        if stripped and self._is_dedent_head(stripped) and base_indent >= INDENT_WIDTH:
            base_indent -= INDENT_WIDTH

        # اگر قبل از مکان‌نما ":" تمام شده، یک پله اضافه کن
        if before.rstrip().endswith(":"):
            base_indent += INDENT_WIDTH

        base_indent = max(0, base_indent)

        # بازنویسی خط و درج سطر جدید با فاصله
        self.editor.delete(f"{line}.0", f"{line}.end")
        self.editor.insert(f"{line}.0", before)
        self.editor.insert("insert", "\n" + (" " * base_indent) + after.lstrip())

        # جابه‌جایی مکان‌نما
        new_line = line + 1
        self.editor.mark_set("insert", f"{new_line}.{base_indent}")
        return "break"

    def _smart_backspace(self, _event: Optional[tk.Event] = None) -> str:
        line, col = self._current_line_col()
        if col == 0:
            return "break"

        text = self._line_text(line)
        lead = self._leading_spaces(text)

        # اگر در ناحیه فاصله‌های ابتدایی هستیم، به مرز ۴تایی قبلی برو
        if col <= lead and lead > 0:
            prev_stop = ((col - 1) // INDENT_WIDTH) * INDENT_WIDTH
            prev_stop = max(0, prev_stop)
            self.editor.delete(f"{line}.{prev_stop}", f"{line}.{col}")
            self.editor.mark_set("insert", f"{line}.{prev_stop}")
            return "break"

        # رفتار عادی
        self.editor.delete(f"{line}.{col-1}", f"{line}.{col}")
        self.editor.mark_set("insert", f"{line}.{col-1}")
        return "break"

    def _smart_tab(self, _event: Optional[tk.Event] = None) -> str:
        # اگر انتخابی هست، همهٔ خطوط انتخاب‌شده را ۴ اسپس جلو ببریم
        try:
            start = self.editor.index("sel.first")
            end = self.editor.index("sel.last")
            s_line = int(start.split(".")[0])
            e_line = int(end.split(".")[0])
            for ln in range(s_line, e_line + 1):
                self.editor.insert(f"{ln}.0", " " * INDENT_WIDTH)
            return "break"
        except Exception:
            # بدون انتخاب: تا مرز بعدی
            line, col = self._current_line_col()
            stop = self._next_tab_stop(col)
            self.editor.insert(f"{line}.{col}", " " * (stop - col))
            self.editor.mark_set("insert", f"{line}.{stop}")
            return "break"

    def _smart_shift_tab(self, _event: Optional[tk.Event] = None) -> str:
        # اگر انتخابی هست، همهٔ خطوط را یک پله بیرون بکش
        try:
            start = self.editor.index("sel.first")
            end = self.editor.index("sel.last")
            s_line = int(start.split(".")[0])
            e_line = int(end.split(".")[0])
            for ln in range(s_line, e_line + 1):
                text = self._line_text(ln)
                lead = self._leading_spaces(text)
                drop = min(INDENT_WIDTH, lead)
                if drop:
                    self.editor.delete(f"{ln}.0", f"{ln}.{drop}")
            return "break"
        except Exception:
            line, col = self._current_line_col()
            text = self._line_text(line)
            lead = self._leading_spaces(text)
            if lead > 0:
                drop = min(INDENT_WIDTH, lead)
                self.editor.delete(f"{line}.0", f"{line}.{drop}")
                if col <= lead:
                    self.editor.mark_set("insert", f"{line}.{max(0, col - drop)}")
            return "break"

    # ---------- run / trace ----------
    def on_run(self) -> None:
        self._execute(enable_trace=False)

    def on_trace(self) -> None:
        self._execute(enable_trace=True)

    def on_stop(self) -> None:
        self.sandbox.stop()
        self._append_console("[stopped]\n", tag="stderr")

    def _execute(self, *, enable_trace: bool) -> None:
        self.console.delete("1.0", tk.END)
        code = self.get_code()
        stdin_data = self.stdin_entry.get()
        self._highlight_reset()

        def worker() -> None:
            out, err, rc = self.sandbox.run(code, enable_trace=enable_trace, stdin_data=stdin_data)
            for line in out.splitlines():
                if line.startswith(TRACE_TAG):
                    try:
                        _, lineno = line.split(" ", 1)
                        self.root.after(0, lambda ln=int(lineno): self._highlight_line(ln))
                        self.root.after(0, lambda lno=lineno: self._append_console(f"[L{lno}]\n", tag="trace"))
                    except Exception:
                        self.root.after(0, lambda s=line: self._append_console(s + "\n"))
                else:
                    self.root.after(0, lambda s=line: self._append_console(s + "\n"))
            if err:
                self.root.after(0, lambda s=err: self._append_console(s, tag="stderr"))
            self.root.after(0, lambda: self._append_console(f"[exit {rc}]\n", tag="trace"))

        threading.Thread(target=worker, daemon=True).start()

    def _append_console(self, text: str, tag: Optional[str] = None) -> None:
        if tag:
            self.console.insert(tk.END, text, tag)
        else:
            self.console.insert(tk.END, text)
        self.console.see(tk.END)

    def _highlight_reset(self) -> None:
        try:
            self.editor.tag_delete("exec_line")
        except Exception:
            pass
        self.editor.tag_configure("exec_line", background="#2f2f55")

    def _highlight_line(self, lineno: int) -> None:
        try:
            start = f"{lineno}.0"
            end = f"{lineno}.end"
            self.editor.tag_remove("exec_line", "1.0", tk.END)
            self.editor.tag_add("exec_line", start, end)
        except Exception:
            pass

    # ---------- blocks ----------
    def on_blocks(self) -> None:
        self.block_drawer.build_from_ast(self.get_code())

    # ---------- autocomplete (Jedi) ----------
    def get_code(self) -> str:
        return self.editor.get("1.0", "end-1c")

    def _cursor_index(self) -> Tuple[int, int]:
        idx = self.editor.index("insert")
        line, col = idx.split(".")
        return int(line), int(col)

    def _word_start_index(self) -> str:
        pos = self.editor.index("insert")
        line, col = map(int, pos.split("."))
        start_col = col
        while start_col > 0:
            ch = self.editor.get(f"{line}.{start_col-1}", f"{line}.{start_col}")
            if not re.match(r"[A-Za-z0-9_]", ch):
                break
            start_col -= 1
        return f"{line}.{start_col}"

    def _show_ac_popup(self, items: List[str]) -> None:
        self._autocomplete_cancel()
        if not items:
            return
        bbox = self.editor.bbox("insert")
        if not bbox:
            return
        x, y, w, h = bbox
        x += self.editor.winfo_rootx()
        y += self.editor.winfo_rooty() + h + 2

        self.ac_popup = tk.Toplevel(self.editor)
        self.ac_popup.wm_overrideredirect(True)
        self.ac_popup.wm_geometry(f"+{x}+{y}")

        self.ac_list = tk.Listbox(self.ac_popup, height=min(8, len(items)), bg="#0b0b18", fg="#E6E6FA")
        for it in items:
            self.ac_list.insert(tk.END, it)
        self.ac_list.pack(fill="both", expand=True)
        self.ac_list.bind("<Double-Button-1>", self._autocomplete_accept)
        self.ac_list.bind("<Return>", self._autocomplete_accept)
        self.ac_list.focus_set()

        self.ac_active = True

    def _autocomplete_trigger(self, event: tk.Event) -> None:
        # کلیدهای مجاز برای تحریک خودکار + اندکی تاخیر برای آرامش اعصاب
        if event.keysym in ("BackSpace", "period", "underscore", "Return", "Tab") or re.match(
            r"^[A-Za-z0-9]$", event.keysym or ""
        ):
            self.root.after(30000, self._compute_completions)

    # alias ضد تایپو
    _on_autocomplete_trigger = _autocomplete_trigger

    def _force_autocomplete(self, _event: tk.Event) -> str:
        self._compute_completions(force=True)
        return "break"

    def _compute_completions(self, force: bool = False) -> None:
        src = self.get_code()
        line, col = self._cursor_index()
        try:
            script = jedi.Script(src, path="__main__.py")
            comps = script.complete(line=line, column=col)
            names = sorted({c.name for c in comps})
            if force or names:
                self._show_ac_popup(names[:100])
        except Exception:
            # autocomplete باید بی‌سروصدا باشد
            pass

    def _autocomplete_accept(self, _event: Optional[tk.Event] = None) -> str:
        if not self.ac_active or not self.ac_popup or not self.ac_list:
            return "break"
        sel = self.ac_list.curselection()
        if not sel:
            self.ac_list.selection_set(0)
            sel = (0,)
        word = self.ac_list.get(sel[0])
        start = self._word_start_index()
        self.editor.delete(start, "insert")
        self.editor.insert("insert", word)
        self._autocomplete_cancel()
        return "break"

    def _autocomplete_cancel(self, _event: Optional[tk.Event] = None) -> str:
        if self.ac_popup:
            try:
                self.ac_popup.destroy()
            except Exception:
                pass
        self.ac_popup = None
        self.ac_list = None
        self.ac_active = False
        return "break"


# ============================================================================
# Feedback Loop & App
# ============================================================================


class FeedbackLoop(threading.Thread):
    """حلقهٔ بازخورد شناختی سبک."""

    def __init__(self, ui: SurrealCanvas, engine: MetaCognitiveEngine) -> None:
        super().__init__(daemon=True)
        self.ui = ui
        self.engine = engine
        self._running = True

    def run(self) -> None:
        while self._running:
            try:
                code = self.ui.get_code()
                typing_speed = self.ui.typing_speed()
                error_rate = self.engine.estimate_error_rate()
                depth = self.engine.measure_concept_depth(code)
                self.engine.profile.update(typing_speed, error_rate, depth)
                self.ui.adjust_environment(self.engine.profile)
                # پیام راهنما ساده
                p = self.engine.profile
                if p.focus_level > 0.85 and p.code_confidence > 0.7:
                    msg = "تو داری با کد یکی می‌شی... ادامه بده."
                elif p.anxiety_level > 0.65 and p.code_confidence < 0.5:
                    msg = "نفس بکش. پایتون نمی‌خواد تو رو بکشه. فعلاً."
                elif p.code_confidence < 0.4:
                    msg = "شاید باید به کدت نگاه کنی، نه به خودت."
                elif p.focus_level < 0.4:
                    msg = "تمرکزت ریخته. پنج خط ساده بنویس، بعد برگرد."
                else:
                    msg = "الگو خوبه. برو ادامه."
                self.ui.root.after(0, lambda t=msg: self.ui.set_feedback(t, 0))
                time.sleep(1.0)
            except Exception:
                traceback.print_exc()
                time.sleep(1.0)

    def stop(self) -> None:
        self._running = False


class PyRealityApp:
    """راه‌انداز برنامهٔ PyReality."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.configure(bg="#0f0f23")

        self.engine = MetaCognitiveEngine()
        self.ui = SurrealCanvas(self.root, self.engine)
        self.loop = FeedbackLoop(self.ui, self.engine)

        self._build_menu()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self._new_file)
        filemenu.add_command(label="Save cognitive snapshot", command=self._save_snapshot)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Calm mode", command=lambda: self._set_mode("calm"))
        viewmenu.add_command(label="Focus mode", command=lambda: self._set_mode("focus"))
        viewmenu.add_command(label="Storm mode", command=lambda: self._set_mode("storm"))
        menubar.add_cascade(label="View", menu=viewmenu)

        self.root.config(menu=menubar)

    def _new_file(self) -> None:
        self.ui.editor.delete("1.0", tk.END)
        self.ui._on_change()

    def _save_snapshot(self) -> None:
        data = {
            "profile": {
                "focus": self.engine.profile.focus_level,
                "anxiety": self.engine.profile.anxiety_level,
                "confidence": self.engine.profile.code_confidence,
            },
            "concepts": self.engine.concept_graph,
            "time": time.time(),
        }
        with open("cognitive_profile.json", "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    def _set_mode(self, mode: str) -> None:
        p = self.engine.profile
        if mode == "calm":
            p.focus_level = clamp(p.focus_level + 0.2, 0, 1)
            p.anxiety_level = clamp(p.anxiety_level - 0.2, 0, 1)
        elif mode == "focus":
            p.focus_level = clamp(0.9, 0, 1)
            p.code_confidence = clamp(p.code_confidence + 0.1, 0, 1)
        elif mode == "storm":
            p.anxiety_level = clamp(0.8, 0, 1)
            p.focus_level = clamp(0.3, 0, 1)
        self.ui.adjust_environment(p)

    def run(self) -> None:
        self.loop.start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self) -> None:
        self.loop.stop()
        self.root.destroy()


# ============================================================================
# Entry
# ============================================================================

if __name__ == "__main__":
    app = PyRealityApp()
    app.run()
