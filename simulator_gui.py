#!/usr/bin/env python3
"""
simulator_gui.py — 食堂智能取餐器模拟器控制面板
================================================
双击 .pyw 启动 (无控制台) | 命令行: python simulator_gui.py --interval 0.5
"""

import csv
import logging
import math
import os
import queue
import random
import sys
import threading
import time
import argparse
from datetime import datetime
from pathlib import Path
from tkinter import (
    Tk, Toplevel, Frame, Label, Button, Canvas, Entry, StringVar,
    DoubleVar, scrolledtext, messagebox,
)
from tkinter import ttk

# ===================== 路径 =====================
BASE_DIR = Path(__file__).resolve().parent
CONFIG_CSV = BASE_DIR / "config" / "devices_config.csv"
OUTPUT_DIR = BASE_DIR / "sample_data"
LOG_DIR = BASE_DIR / "logs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ===================== 固定参数 =====================
FIXED_STATUS_COUNTS = {"online": 21, "offline": 1, "alert": 3, "maintenance": 1}
FIXED_TOTAL = sum(FIXED_STATUS_COUNTS.values())

FAULT_TYPES = ["温度过高", "CPU满载", "网络超时", "内存不足", "磁盘异常", "进程僵死"]

STATUS_COLOR_MAP = {
    "online": "#22C55E", "offline": "#EF4444",
    "alert": "#F59E0B", "maintenance": "#3B82F6",
}

# CPU 各状态高斯参数 (mu, sigma, 权重)
CPU_DIST = {
    "online": (38, 15, 21/26), "offline": (90, 8, 1/26),
    "alert": (65, 15, 3/26), "maintenance": (15, 8, 1/26),
}
# RAM 各状态高斯参数
RAM_DIST = {
    "online": (52, 12, 21/26), "offline": (92, 6, 1/26),
    "alert": (70, 12, 3/26), "maintenance": (25, 10, 1/26),
}

THEME = {
    "bg_dark": "#0d1117", "bg_card": "#161b22", "bg_input": "#21262d",
    "border": "#30363d", "text_primary": "#e6edf3", "text_secondary": "#8b949e",
    "text_muted": "#6e7681", "green": "#22C55E", "red": "#EF4444",
    "orange": "#F59E0B", "blue": "#58a6ff",
}

# ===================== 日志 =====================
def setup_logging():
    logger = logging.getLogger("simulator")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    log_file = LOG_DIR / f"simulator_{datetime.now():%Y%m%d}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8", mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(fh)
    return logger

logger = setup_logging()

# ===================== 数学工具 =====================
def gaussian_pdf(x, mu, sigma):
    if sigma <= 0: return 0.0
    return (1.0 / (sigma * math.sqrt(2 * math.pi))) * math.exp(-0.5 * ((x - mu) / sigma) ** 2)

def cpu_mixture_pdf(x):
    return sum(w * gaussian_pdf(x, mu, sigma) for mu, sigma, w in CPU_DIST.values())

def ram_mixture_pdf(x):
    return sum(w * gaussian_pdf(x, mu, sigma) for mu, sigma, w in RAM_DIST.values())

# ===================== 设备加载 =====================
def load_devices():
    devices = []
    with open(CONFIG_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            devices.append(row)
    real = len(devices)
    if real < FIXED_TOTAL:
        canteens = list({d["canteen"] for d in devices})
        models = list({d["model"] for d in devices})
        windows = ["1F-A区", "1F-B区", "2F-C区", "2F-D区"]
        for i in range(FIXED_TOTAL - real):
            idx = real + i + 1
            src = devices[i % real]
            devices.append({
                "device_id": f"DEV-{2000 + idx // 10}-{idx % 10:04d}",
                "device_name": f"{src['canteen']}{windows[i % 4]}-{idx:02d}号机",
                "model": models[i % len(models)],
                "canteen": canteens[i % len(canteens)],
                "window": windows[i % 4],
            })
    return devices

def build_status_list():
    pool = []
    for st, cnt in FIXED_STATUS_COUNTS.items():
        pool.extend([st] * cnt)
    random.shuffle(pool)
    return pool

def simulate_device(device, status):
    if status == "online":
        cpu = round(random.gauss(38, 15), 1)
        ram = round(random.gauss(52, 12), 1)
        uptime = f"{round(random.gauss(98.5, 1.2), 1)}%"
    elif status == "maintenance":
        cpu = round(random.gauss(15, 8), 1)
        ram = round(random.gauss(25, 10), 1)
        uptime = f"{round(random.gauss(95, 2), 1)}%"
    elif status == "alert":
        cpu = round(random.gauss(65, 15), 1)
        ram = round(random.gauss(70, 12), 1)
        uptime = f"{round(random.gauss(97, 2), 1)}%"
    else:
        cpu = round(random.gauss(90, 8), 1)
        ram = round(random.gauss(92, 6), 1)
        uptime = "0.0%"
    cpu = min(100, max(1, cpu))
    ram = min(100, max(5, ram))
    alert = random.choice(FAULT_TYPES) if status in ("alert", "offline") else ""
    heartbeat = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "id": device.get("device_id", ""), "name": device.get("device_name", ""),
        "model": device.get("model", ""), "canteen": device.get("canteen", ""),
        "window": device.get("window", ""), "status": status,
        "cpu": cpu, "ram": ram, "uptime": uptime, "alert": alert, "heartbeat": heartbeat,
    }

# ===================== CSV 写入 =====================
def write_csvs(simulated):
    # devices_list.csv
    with open(OUTPUT_DIR / "devices_list.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name", "model", "canteen", "window",
            "status", "cpu", "ram", "uptime", "alert", "heartbeat",
        ])
        w.writeheader()
        for s in sorted(simulated, key=lambda x: (x["canteen"], x["window"])):
            w.writerow(s)
    # device_status.csv
    counts = {"online": 0, "offline": 0, "alert": 0, "maintenance": 0}
    for s in simulated:
        st = s["status"]
        if st in counts: counts[st] += 1
        else: counts["online"] += 1
    with open(OUTPUT_DIR / "device_status.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["status", "count", "color"])
        w.writeheader()
        for st in ["online", "offline", "alert", "maintenance"]:
            w.writerow({"status": st, "count": counts[st], "color": STATUS_COLOR_MAP[st]})
    # fault_devices.csv
    faults = [s for s in simulated if s["status"] in ("alert", "offline")]
    with open(OUTPUT_DIR / "fault_devices.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "device_id", "school", "fault_type", "offline_time", "status", "action",
        ])
        w.writeheader()
        for fd in faults:
            action = "重启" if fd["alert"] == "CPU满载" else (
                "降温" if fd["alert"] == "温度过高" else "检修")
            w.writerow({
                "device_id": fd["id"], "school": fd["canteen"],
                "fault_type": fd["alert"], "offline_time": fd["heartbeat"],
                "status": fd["status"], "action": action,
            })
    return counts

# ===================== 数据收集器 (滑动窗口) =====================
class DataCollector:
    def __init__(self, window_size=1000):
        self.lock = threading.Lock()
        self.window_size = window_size
        self.cpu_vals = []
        self.ram_vals = []
        self.ticks = 0

    def add_batch(self, simulated):
        with self.lock:
            for d in simulated:
                self.cpu_vals.append(float(d["cpu"]))
                self.ram_vals.append(float(d["ram"]))
            # 滑动窗口：只保留最近 N 条
            if len(self.cpu_vals) > self.window_size:
                self.cpu_vals = self.cpu_vals[-self.window_size:]
                self.ram_vals = self.ram_vals[-self.window_size:]
            self.ticks += 1

    def get_snapshot(self):
        with self.lock:
            return list(self.cpu_vals), list(self.ram_vals), self.ticks

# ===================== 历史 CSV =====================
class HistoryWriter:
    def __init__(self, filepath, flush_interval=8):
        self.filepath = filepath
        self.flush_interval = flush_interval
        self.lock = threading.Lock()
        self._buf = []
        self._hdr = [
            "timestamp", "tick", "device_id", "device_name", "model",
            "canteen", "window", "status", "cpu", "ram", "uptime", "alert", "heartbeat",
        ]
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(self._hdr)

    def append_batch(self, ts, tick, simulated):
        with self.lock:
            for d in simulated:
                self._buf.append([
                    ts, tick, d["id"], d["name"], d["model"],
                    d["canteen"], d["window"], d["status"],
                    d["cpu"], d["ram"], d["uptime"], d["alert"], d["heartbeat"],
                ])
            if tick % self.flush_interval == 0:
                self._flush()

    def _flush(self):
        if not self._buf: return
        with open(self.filepath, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(self._buf)
        self._buf.clear()

    def flush_now(self):
        with self.lock: self._flush()

# ===================== 消息类型 =====================
class Msg:
    LOG = "log"; STATS = "stats"; TICK = "tick"; ERROR = "error"; STOPPED = "stopped"

# ===================== 统计弹窗 =====================
class StatsWindow(Toplevel):
    def __init__(self, parent, collector):
        super().__init__(parent)
        self.collector = collector
        self.title("统计分布验证 — CPU & RAM")
        self.geometry("820x880")
        self.minsize(640, 700)
        self.configure(bg="#0d1117")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        hdr = Frame(self, bg="#161b22", height=40, highlightbackground="#30363d", highlightthickness=1)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        Label(hdr, text="实际数据分布 vs 理论统计分布", font=("Microsoft YaHei UI", 11, "bold"),
              fg="#e6edf3", bg="#161b22").pack(side="left", padx=16, pady=10)
        self._info = StringVar(value="...")
        Label(hdr, textvariable=self._info, font=("Consolas", 10),
              fg="#8b949e", bg="#161b22").pack(side="right", padx=16, pady=10)

        self.cpu_cv = Canvas(self, bg="#0d1117", highlightthickness=0)
        self.cpu_cv.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        self.ram_cv = Canvas(self, bg="#0d1117", highlightthickness=0)
        self.ram_cv.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        leg = Frame(self, bg="#161b22", height=26); leg.pack(fill="x"); leg.pack_propagate(False)
        Label(leg, text="  ██ 实际频率  ", fg="#58a6ff", bg="#161b22", font=("Microsoft YaHei UI", 9)).pack(side="left", padx=8)
        Label(leg, text="  ── 理论混合高斯  ", fg="#f85149", bg="#161b22", font=("Microsoft YaHei UI", 9)).pack(side="left", padx=8)
        Label(leg, text="  ··· 状态均值  ", fg="#22C55E", bg="#161b22", font=("Microsoft YaHei UI", 9)).pack(side="left", padx=8)

        self._draw()
        self._loop()

    def _loop(self):
        if self.winfo_exists():
            self._draw()
            self.after(2000, self._loop)

    def _draw_chart(self, cv, data, title, dist_params, pdf_func):
        cv.delete("all")
        n = len(data)
        W, H = cv.winfo_width() or 800, cv.winfo_height() or 400
        ml, mr, mt, mb = 60, 30, 28, 40
        pw, ph = W - ml - mr, H - mt - mb
        if pw < 100 or ph < 100: return

        def xp(v): return ml + (v / 100.0) * pw
        def yp(v, ymax): return mt + ph - (v / max(ymax, 1)) * ph

        cv.create_text(ml + pw / 2, 8, text=title, fill="#e6edf3",
                       font=("Microsoft YaHei UI", 10, "bold"))

        for pct in range(0, 101, 20):
            cx = xp(pct)
            cv.create_line(cx, mt, cx, mt + ph, fill="#21262d", dash=(2, 4))
            cv.create_text(cx, mt + ph + 14, text=f"{pct}%", fill="#8b949e", font=("Consolas", 8))

        BINS, bin_w = 20, 5.0
        hist = [0] * BINS
        for v in data:
            idx = min(int(v / bin_w), BINS - 1)
            hist[idx] += 1

        # ── 理论曲线用固定 scale = 窗口大小 × 桶宽 ──
        FIXED_N = 1000.0
        scale = FIXED_N * bin_w
        # 理论最大期望计数 → Y 轴上限定死不变
        pdf_max = max(pdf_func(x / 10.0) for x in range(0, 1001))
        ymax = pdf_max * scale * 1.3

        # Y 轴刻度 (计数)
        for i in range(0, 6):
            v = ymax * i / 5.0
            cy = yp(v, ymax)
            cv.create_line(ml - 4, cy, ml, cy, fill="#8b949e")
            cv.create_text(ml - 8, cy, text=str(int(v)), fill="#8b949e",
                           font=("Consolas", 8), anchor="e")

        # ── 蓝色直方图 (实际计数) ──
        for i in range(BINS):
            x0, x1 = xp(i * bin_w), xp((i + 1) * bin_w)
            bar_h = (hist[i] / ymax) * ph
            cv.create_rectangle(x0, mt + ph - bar_h, x1, mt + ph,
                                fill="#58a6ff", outline="#1f6feb", width=1)

        # ── 红色理论曲线 (期望计数 = PDF × scale，固定不动) ──
        pts = []
        for px in range(int(ml), int(ml + pw), 2):
            v = (px - ml) / pw * 100.0
            pts.append((px, yp(pdf_func(v) * scale, ymax)))
        if len(pts) >= 2:
            for i in range(len(pts) - 1):
                cv.create_line(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1],
                               fill="#f85149", width=2.5)

        # ── 状态均值线 ──
        for st, (mu, sigma, w) in dist_params.items():
            cx = xp(mu)
            cv.create_line(cx, mt, cx, mt + ph, fill="#22C55E", dash=(6, 8), width=1)
            cv.create_text(cx, mt + ph + 26, text=f"{st[:4]}\nμ={mu}",
                           fill="#22C55E", font=("Microsoft YaHei UI", 6), anchor="n")

        cv.create_line(ml, mt, ml, mt + ph, fill="#30363d", width=1)
        cv.create_line(ml, mt + ph, ml + pw, mt + ph, fill="#30363d", width=1)

    def _draw(self):
        cpu, ram, ticks = self.collector.get_snapshot()
        self._info.set(f"样本: {len(cpu)}  |  轮次: {ticks}")
        self._draw_chart(self.cpu_cv, cpu, "CPU 使用率分布 (%)", CPU_DIST, cpu_mixture_pdf)
        self._draw_chart(self.ram_cv, ram, "RAM 使用率分布 (%)", RAM_DIST, ram_mixture_pdf)

# ===================== Worker 线程 =====================
class SimulatorWorker(threading.Thread):
    def __init__(self, msg_queue, collector, history_writer, interval=0.125):
        super().__init__(daemon=True)
        self.mq = msg_queue
        self.collector = collector
        self.hw = history_writer
        self.interval = interval
        self._stop = threading.Event()

    def stop(self): self._stop.set()

    @property
    def stopped(self): return self._stop.is_set()

    def _push(self, msg):
        self.mq.put({"type": Msg.LOG, "message": msg})

    def _push_err(self, msg):
        self.mq.put({"type": Msg.ERROR, "message": msg})

    def run(self):
        logger.info("Worker started | interval=%.3fs", self.interval)
        self._push(f"Worker started | {1/self.interval:.0f}Hz")

        try:
            devices = load_devices()
            self._push(f"Loaded {len(devices)} devices")
        except Exception as e:
            self._push_err(f"Load failed: {e}")
            return

        tick = 0
        while not self.stopped:
            t0 = time.monotonic()
            tick += 1
            ts = datetime.now().strftime("%H:%M:%S")

            try:
                statuses = build_status_list()
                simulated = [simulate_device(d, s) for d, s in zip(devices, statuses)]
                counts = write_csvs(simulated)
                self.hw.append_batch(ts, tick, simulated)
                self.collector.add_batch(simulated)

                # ── 日志文件：全字段 ──
                logger.info("ROUND %d | online=%d offline=%d alert=%d maint=%d",
                            tick, counts["online"], counts["offline"],
                            counts["alert"], counts["maintenance"])
                for d in simulated:
                    a = d["alert"] or "-"
                    logger.info("  %s | %s | %s | %s | CPU=%.1f%% RAM=%.1f%% UP=%s | %s | HB=%s",
                                d["id"], d["name"], d["canteen"], d["status"],
                                d["cpu"], d["ram"], d["uptime"], a, d["heartbeat"])

                # ── GUI 日志：仅 id / model / cpu / ram / uptime ──
                for d in simulated:
                    self._push(
                        f"{ts} | {d['id']} | {d['model']} | "
                        f"CPU:{d['cpu']:5.1f}% | RAM:{d['ram']:5.1f}% | UP:{d['uptime']}"
                    )

                # 统计
                faults = [s for s in simulated if s["status"] in ("alert", "offline")]
                self.mq.put({"type": Msg.STATS, "counts": counts, "tick": tick,
                             "timestamp": ts, "total": len(simulated), "faults": len(faults)})
                self.mq.put({"type": Msg.TICK, "tick": tick})

            except Exception as e:
                logger.error("Error: %s", e, exc_info=True)
                self._push_err(f"Error: {e}")

            elapsed = time.monotonic() - t0
            remaining = self.interval - elapsed
            while remaining > 0 and not self.stopped:
                time.sleep(min(0.05, remaining))
                remaining -= 0.05

        self.hw.flush_now()
        logger.info("Worker stopped")
        self._push("Worker stopped")
        self.mq.put({"type": Msg.STOPPED})

# ===================== 主 GUI =====================
class SimulatorApp(Tk):
    def __init__(self, interval=0.125):
        super().__init__()
        self.interval = interval
        self.worker = None
        self.mq = queue.Queue()
        self.running = False
        self.tick_count = 0
        self._aid = None
        self._stats_aid = None

        self.collector = DataCollector()
        self.hw = HistoryWriter(str(OUTPUT_DIR / "history_log.csv"))
        self.stats_win = None

        self.title("食堂智能取餐器 · 模拟器控制面板")
        self.geometry("820x720")
        self.minsize(640, 560)
        self.configure(bg=THEME["bg_dark"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._poller()
        logger.info("GUI ready")
        self._log("GUI ready", "info")

    # ── UI ──
    def _build_ui(self):
        style = ttk.Style(self); style.theme_use("clam")

        # 顶栏
        hdr = Frame(self, bg=THEME["bg_card"], height=56, highlightbackground=THEME["border"], highlightthickness=1)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        Label(hdr, text="食堂智能取餐器 · 模拟器控制面板", font=("Microsoft YaHei UI", 13, "bold"),
              fg=THEME["text_primary"], bg=THEME["bg_card"]).pack(side="left", padx=20, pady=14)
        self._dot = Label(hdr, text="●", font=("", 14), fg=THEME["text_muted"], bg=THEME["bg_card"])
        self._dot.pack(side="right", padx=(0, 6), pady=14)
        self._st_lbl = Label(hdr, text="已停止", font=("Microsoft YaHei UI", 10),
                             fg=THEME["text_muted"], bg=THEME["bg_card"])
        self._st_lbl.pack(side="right", padx=(0, 14), pady=14)

        main = Frame(self, bg=THEME["bg_dark"]); main.pack(fill="both", expand=True, padx=16, pady=(16, 0))

        # 配置 + 控制行
        row = Frame(main, bg=THEME["bg_dark"]); row.pack(fill="x", pady=(0, 12))

        c1 = self._card(row, "运行配置"); c1.pack(side="left", fill="x", expand=True, padx=(0, 6))
        inn = Frame(c1, bg=THEME["bg_card"]); inn.pack(fill="x", padx=16, pady=(8, 14))
        Label(inn, text="间隔(秒):", font=("Microsoft YaHei UI", 10),
              fg=THEME["text_secondary"], bg=THEME["bg_card"]).pack(side="left")
        self._iv = DoubleVar(value=self.interval)
        Entry(inn, textvariable=self._iv, width=6, font=("Consolas", 12), bg=THEME["bg_input"],
              fg=THEME["text_primary"], insertbackground=THEME["text_primary"],
              relief="flat", justify="center", highlightbackground=THEME["border"],
              highlightthickness=1).pack(side="left", padx=10)
        Label(inn, text=f"|  设备: {FIXED_TOTAL}台 (在线{FIXED_STATUS_COUNTS['online']} "
              f"离线{FIXED_STATUS_COUNTS['offline']} 告警{FIXED_STATUS_COUNTS['alert']} "
              f"维护{FIXED_STATUS_COUNTS['maintenance']})",
              font=("Microsoft YaHei UI", 9), fg=THEME["blue"], bg=THEME["bg_card"]).pack(side="left", padx=10)

        c2 = self._card(row, "操作"); c2.pack(side="left", fill="x", padx=(6, 0))
        inn2 = Frame(c2, bg=THEME["bg_card"]); inn2.pack(fill="x", padx=16, pady=(8, 14))
        self._btn1 = Button(inn2, text="▶  启动模拟器", font=("Microsoft YaHei UI", 10, "bold"),
                            bg="#238636", fg="#fff", relief="flat", activebackground="#2ea043",
                            activeforeground="#fff", cursor="hand2", padx=18, pady=6,
                            command=self._start)
        self._btn1.pack(side="left", padx=(0, 8))
        self._btn2 = Button(inn2, text="⏹  停止模拟器", font=("Microsoft YaHei UI", 10, "bold"),
                            bg="#da3633", fg="#fff", relief="flat", activebackground="#f85149",
                            activeforeground="#fff", cursor="hand2", padx=18, pady=6,
                            command=self._stop, state="disabled")
        self._btn2.pack(side="left")

        # 统计卡片
        srow = Frame(main, bg=THEME["bg_dark"]); srow.pack(fill="x", pady=(0, 12))
        self._sf = {}
        defs = [("online", "在线设备", THEME["green"]), ("offline", "离线设备", THEME["red"]),
                ("alert", "告警设备", THEME["orange"]), ("maintenance", "维护设备", THEME["blue"])]
        for key, lb, clr in defs:
            cd = self._card(srow, lb); cd.pack(side="left", fill="x", expand=True, padx=6)
            cd.config(highlightbackground=clr, highlightthickness=1)
            inn3 = Frame(cd, bg=THEME["bg_card"]); inn3.pack(fill="x", padx=16, pady=(6, 14))
            sv = StringVar(value=str(FIXED_STATUS_COUNTS[key]))
            Label(inn3, textvariable=sv, font=("Consolas", 26, "bold"),
                  fg=clr, bg=THEME["bg_card"]).pack()
            Label(inn3, text=lb, font=("Microsoft YaHei UI", 9),
                  fg=THEME["text_secondary"], bg=THEME["bg_card"]).pack()
            self._sf[key] = sv

        # 日志
        lc = self._card(main, "运行日志"); lc.pack(fill="both", expand=True, pady=(0, 12))
        lc.config(highlightbackground=THEME["border"], highlightthickness=1)
        li = Frame(lc, bg=THEME["bg_card"]); li.pack(fill="both", expand=True, padx=2, pady=2)
        self._log_w = scrolledtext.ScrolledText(
            li, font=("Consolas", 9), bg=THEME["bg_dark"], fg=THEME["text_primary"],
            insertbackground=THEME["text_primary"], relief="flat", wrap="word", state="disabled")
        self._log_w.pack(fill="both", expand=True)
        for tag, fg in [("info", THEME["text_secondary"]), ("success", THEME["green"]),
                         ("warning", THEME["orange"]), ("error", THEME["red"]),
                         ("highlight", THEME["blue"])]:
            self._log_w.tag_config(tag, foreground=fg)

        # 状态栏
        sb = Frame(self, bg=THEME["bg_card"], height=30, highlightbackground=THEME["border"], highlightthickness=1)
        sb.pack(fill="x", side="bottom"); sb.pack_propagate(False)
        self._sb_txt = StringVar(value="就绪 — 点击启动")
        Label(sb, textvariable=self._sb_txt, font=("Microsoft YaHei UI", 9),
              fg=THEME["text_muted"], bg=THEME["bg_card"], anchor="w").pack(side="left", padx=14, pady=6)
        self._sb_tick = StringVar(value="")
        Label(sb, textvariable=self._sb_tick, font=("Consolas", 9),
              fg=THEME["text_muted"], bg=THEME["bg_card"], anchor="e").pack(side="right", padx=14, pady=6)

    def _card(self, parent, title):
        c = Frame(parent, bg=THEME["bg_card"], highlightbackground=THEME["border"], highlightthickness=1)
        Label(c, text=title, font=("Microsoft YaHei UI", 9, "bold"),
              fg=THEME["text_secondary"], bg=THEME["bg_card"], anchor="w").pack(fill="x", padx=14, pady=(10, 0))
        return c

    # ── 队列 ──
    def _poller(self):
        try:
            while True:
                m = self.mq.get_nowait()
                t = m.get("type")
                if t == Msg.LOG: self._log(m["message"], "info")
                elif t == Msg.ERROR: self._log(m["message"], "error")
                elif t == Msg.STATS: self._upd_stats(m)
                elif t == Msg.TICK:
                    self.tick_count = m["tick"]
                    self._sb_tick.set(f"第 {m['tick']} 轮")
                elif t == Msg.STOPPED: self._on_stopped()
        except queue.Empty:
            pass
        self._aid = self.after(100, self._poller)

    def _log(self, msg, level="info"):
        self._log_w.config(state="normal")
        self._log_w.insert("end", f"[{datetime.now():%H:%M:%S}] ", "info")
        self._log_w.insert("end", f"{msg}\n", level)
        self._log_w.see("end")
        self._log_w.config(state="disabled")

    def _upd_stats(self, m):
        for k, v in m["counts"].items():
            if k in self._sf: self._sf[k].set(str(v))
        self._sb_txt.set(f"刷新: {m['timestamp']} | {m['total']}台 | 故障: {m['faults']}台")

    # ── 启停 ──
    def _start(self):
        if self.running:
            messagebox.showwarning("已在运行", "模拟器正在运行中")
            return
        self.interval = self._iv.get()
        if self.interval < 0.1:
            messagebox.showerror("参数错误", "间隔不能小于 0.1 秒")
            return
        self.running = True
        self.tick_count = 0
        self._btn1.config(state="disabled", bg="#21262d")
        self._btn2.config(state="normal", bg="#da3633")
        self._dot.config(fg=THEME["green"])
        self._st_lbl.config(text="运行中", fg=THEME["green"])
        self._sb_txt.set("运行中...")
        self._sb_tick.set("")
        for sv in self._sf.values(): sv.set("...")
        self.worker = SimulatorWorker(self.mq, self.collector, self.hw, self.interval)
        self.worker.start()
        self._stats_aid = self.after(10000, self._open_stats)
        self._log(f"Started | interval={self.interval}s | {FIXED_TOTAL}devs | stats in 10s", "success")

    def _stop(self):
        if not self.running or not self.worker: return
        self._log("Stopping...", "warning")
        self.worker.stop()
        self._btn2.config(state="disabled", bg="#21262d")
        self._dot.config(fg=THEME["orange"])
        self._st_lbl.config(text="停止中...", fg=THEME["orange"])
        self._sb_txt.set("等待线程退出...")

    def _on_stopped(self):
        self.running = False; self.worker = None
        if self._stats_aid: self.after_cancel(self._stats_aid); self._stats_aid = None
        self._btn1.config(state="normal", bg="#238636")
        self._btn2.config(state="disabled", bg="#21262d")
        self._dot.config(fg=THEME["text_muted"])
        self._st_lbl.config(text="已停止", fg=THEME["text_muted"])
        self._sb_txt.set("就绪 — 点击启动")
        self._sb_tick.set(f"共 {self.tick_count} 轮")
        self._log(f"Stopped ({self.tick_count} rounds)", "warning")

    def _open_stats(self):
        if not self.running: return
        if self.stats_win is None or not self.stats_win.winfo_exists():
            self.stats_win = StatsWindow(self, self.collector)
        else:
            self.stats_win.deiconify(); self.stats_win.lift()
        self._log("Stats window opened", "highlight")

    def _on_close(self):
        if self.running and self.worker:
            if messagebox.askokcancel("确认退出", "模拟器运行中，确定退出？"):
                self.worker.stop()
                self.after(200, self._force_close)
        else:
            self._force_close()

    def _force_close(self):
        if self._aid: self.after_cancel(self._aid)
        if self._stats_aid: self.after_cancel(self._stats_aid)
        if self.stats_win and self.stats_win.winfo_exists(): self.stats_win.destroy()
        logger.info("GUI closed")
        self.destroy()

# ===================== 入口 =====================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=0.125, help="间隔(秒), 默认0.125")
    args = parser.parse_args()
    SimulatorApp(interval=args.interval).mainloop()

if __name__ == "__main__":
    main()
