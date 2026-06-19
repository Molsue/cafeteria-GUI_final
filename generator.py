#!/usr/bin/env python3
"""
simulator_web - 食堂智能取餐器设备数据模拟器（纯CSV版）
========================================================
读取 devices_config.csv → 固定状态分配22台设备 → 输出 3 个 CSV

用法:
  python3 generator.py [--once] [--interval 0.125]

  --once      单次生成后退出
  --interval  循环模式刷新间隔（默认30秒）
"""

import csv
import logging
import os
import random
import sys
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ── 路径 ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
CONFIG_CSV = BASE_DIR / "config" / "devices_config.csv"
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", BASE_DIR / "output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = OUTPUT_DIR / "simulator.log"

# ── 日志 ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("simulator")

# ── 固定状态分配（22台）─────────────────────────────────────────
FIXED_STATUS = {
    "online":      17,  # 正常运行
    "offline":      1,  # 离线
    "alert":        3,  # 在线但告警
    "maintenance":  1,  # 在线但维护中
}
# 在线(广义)=17+3+1=21, 离线=1, 总22

FAULT_TYPES = ["温度过高", "CPU满载", "网络超时", "内存不足", "磁盘异常", "进程僵死"]


# ═══════════════════════════════════════════════════════════════
#  核心逻辑
# ═══════════════════════════════════════════════════════════════

def load_devices() -> list[dict]:
    """读取设备配置 CSV"""
    devices = []
    with open(CONFIG_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            devices.append(row)
    logger.info("📋 加载设备配置: %d 台", len(devices))
    return devices


def assign_statuses(device_count: int) -> list[str]:
    """按固定配额分配状态，返回打乱后的状态列表"""
    statuses = []
    for st, count in FIXED_STATUS.items():
        statuses.extend([st] * count)
    random.shuffle(statuses)
    return statuses


def simulate_device(device: dict, status: str) -> dict:
    """给一台设备按指定状态生成随机运行指标"""
    if status == "online":
        cpu = round(random.gauss(38, 15), 1)
        ram = round(random.gauss(52, 12), 1)
    else:
        cpu = round(random.gauss(85, 10), 1)
        ram = round(random.gauss(90, 8), 1)

    cpu = min(100, max(5, cpu))
    ram = min(100, max(20, ram))
    uptime = f"{round(random.gauss(98.5, 1.2), 1)}%" if status != "offline" else "0.0%"

    alert = ""
    if status in ("alert", "offline"):
        alert = random.choice(FAULT_TYPES)

    heartbeat = (datetime.now() - timedelta(seconds=random.randint(5, 120))).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "id":        device["device_id"],
        "name":      device["device_name"],
        "model":     device["model"],
        "canteen":   device["canteen"],
        "window":    device["window"],
        "status":    status,
        "cpu":       cpu,
        "ram":       ram,
        "uptime":    uptime,
        "alert":     alert,
        "heartbeat": heartbeat,
    }


def simulate_all(config_devices: list[dict]) -> list[dict]:
    """按固定状态分配，生成全部22台设备数据"""
    statuses = assign_statuses(len(config_devices))
    return [simulate_device(dev, st) for dev, st in zip(config_devices, statuses)]


def generate_csvs(simulated: list[dict]) -> dict:
    """生成 3 个 CSV 文件，返回状态统计"""

    # ── 1. devices_list.csv ──
    with open(OUTPUT_DIR / "devices_list.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name", "model", "canteen", "window",
            "status", "cpu", "ram", "uptime", "alert", "heartbeat"
        ])
        w.writeheader()
        for s in sorted(simulated, key=lambda x: (x["canteen"], x["window"])):
            w.writerow(s)

    # ── 2. device_status.csv ──
    status_counts = {"online": 0, "offline": 0, "alert": 0, "maintenance": 0}
    for s in simulated:
        st = s["status"]
        status_counts[st if st in status_counts else "online"] += 1

    color_map = {
        "online": "#22C55E", "offline": "#EF4444",
        "alert": "#F59E0B", "maintenance": "#3B82F6",
    }
    with open(OUTPUT_DIR / "device_status.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["status", "count", "color"])
        w.writeheader()
        for st in ["online", "offline", "alert", "maintenance"]:
            w.writerow({"status": st, "count": status_counts[st], "color": color_map[st]})

    # ── 3. fault_devices.csv ──
    fault_devices = [s for s in simulated if s["status"] in ("alert", "offline")]
    with open(OUTPUT_DIR / "fault_devices.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "device_id", "school", "fault_type", "offline_time", "status", "action"
        ])
        w.writeheader()
        for fd in fault_devices:
            action = "检修"
            if fd["alert"] == "CPU满载":
                action = "重启"
            elif fd["alert"] == "温度过高":
                action = "降温"
            w.writerow({
                "device_id":    fd["id"],
                "school":       fd["canteen"],
                "fault_type":   fd["alert"],
                "offline_time": fd["heartbeat"],
                "status":       fd["status"],
                "action":       action,
            })

    return status_counts


def compute_stats(simulated: list[dict]) -> dict:
    """计算本轮模拟的 CPU/内存/在线率 统计"""
    all_online = [s for s in simulated if s["status"] != "offline"]
    all_devices = simulated

    cpu_vals = [s["cpu"] for s in all_devices]
    ram_vals = [s["ram"] for s in all_devices]
    uptime_vals = [
        float(s["uptime"].replace("%", ""))
        for s in all_online if s["uptime"] != "0.0%"
    ]

    return {
        "cpu_avg":   round(sum(cpu_vals) / len(cpu_vals), 1),
        "cpu_max":   max(cpu_vals),
        "ram_avg":   round(sum(ram_vals) / len(ram_vals), 1),
        "ram_max":   max(ram_vals),
        "uptime_avg": round(sum(uptime_vals) / len(uptime_vals), 1) if uptime_vals else 0,
    }


def log_cycle(status_counts: dict, stats: dict):
    """记录本周期摘要到日志"""
    fault_count = status_counts["offline"] + status_counts["alert"]
    logger.info(
        "📊 设备: 在线%d(正常%d+告警%d+维护%d) 离线%d 故障%d | "
        "CPU均值%.1f%%(峰值%.0f%%) 内存均值%.1f%%(峰值%.0f%%) 平均在线率%.1f%% | CSV已刷新",
        status_counts["online"] + status_counts["alert"] + status_counts["maintenance"],
        status_counts["online"],
        status_counts["alert"],
        status_counts["maintenance"],
        status_counts["offline"],
        fault_count,
        stats["cpu_avg"], stats["cpu_max"],
        stats["ram_avg"], stats["ram_max"],
        stats["uptime_avg"],
    )


def log_device_details(simulated: list[dict]):
    """记录每台设备的 CPU/内存/状态 详情"""
    for s in simulated:
        if s["status"] in ("alert", "offline"):
            logger.warning(
                "⚠️ %s | %s | %s | CPU:%.1f%% RAM:%.1f%% 在线:%s 故障:%s",
                s["id"], s["name"], s["status"],
                s["cpu"], s["ram"], s["uptime"], s["alert"]
            )
        else:
            logger.info(
                "   %s | %s | %s | CPU:%.1f%% RAM:%.1f%% 在线:%s",
                s["id"], s["name"], s["status"],
                s["cpu"], s["ram"], s["uptime"]
            )


# ═══════════════════════════════════════════════════════════════
#  运行入口
# ═══════════════════════════════════════════════════════════════

def run_once():
    config_devices = load_devices()
    simulated = simulate_all(config_devices)
    status_counts = generate_csvs(simulated)
    stats = compute_stats(simulated)
    log_cycle(status_counts, stats)
    log_device_details(simulated)
    logger.info("✅ 单次生成完成")


def run_loop(interval: float = 30):
    logger.info("🔄 循环模式启动 | 刷新间隔: %.3fs (每秒%.0f次)", interval, 1/interval if interval > 0 else 0)
    config_devices = load_devices()

    cycle = 0
    while True:
        try:
            cycle += 1
            simulated = simulate_all(config_devices)
            status_counts = generate_csvs(simulated)
            stats = compute_stats(simulated)
            log_cycle(status_counts, stats)
            log_device_details(simulated)
            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("👋 收到停止信号，已退出（共运行 %d 轮）", cycle)
            break
        except Exception as e:
            logger.error("⚠️ 第 %d 轮异常: %s", cycle, e)
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="食堂取餐器设备模拟器（纯CSV）")
    parser.add_argument("--once", action="store_true", help="单次运行")
    parser.add_argument("--interval", type=float, default=30, help="刷新间隔(秒), 默认30")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        run_loop(args.interval)
