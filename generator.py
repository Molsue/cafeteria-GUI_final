#!/usr/bin/env python3
"""
simulator_web - 食堂智能取餐器设备数据模拟器（纯CSV版）
========================================================
读取 devices_config.csv → 随机生成22台设备状态 → 输出 3 个 CSV

用法:
  python3 generator.py [--once] [--interval 30]

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

# ── 状态权重 ────────────────────────────────────────────────────
STATUS_WEIGHTS = {
    "online":       72,
    "alert":        10,
    "offline":       8,
    "maintenance":  10,
}

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


def simulate_device(device: dict) -> dict:
    """给一台设备生成随机运行时数据"""
    status = random.choices(
        list(STATUS_WEIGHTS.keys()),
        weights=list(STATUS_WEIGHTS.values()),
        k=1,
    )[0]

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


def generate_csvs(simulated: list[dict]) -> dict:
    """
    生成 3 个 CSV 文件
    返回状态统计 dict
    """

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


def log_cycle(status_counts: dict, fault_count: int):
    """记录本周期摘要到日志"""
    logger.info(
        "📊 22台 | 在线:%d 离线:%d 告警:%d 维护:%d 故障设备:%d → CSV 已刷新",
        status_counts["online"],
        status_counts["offline"],
        status_counts["alert"],
        status_counts["maintenance"],
        fault_count,
    )


def log_fault_details(simulated: list[dict]):
    """记录故障设备详情到日志"""
    for s in simulated:
        if s["status"] in ("alert", "offline"):
            logger.warning(
                "⚠️ 故障设备 | ID:%s 名称:%s 状态:%s 故障:%s",
                s["id"], s["name"], s["status"], s["alert"]
            )


# ═══════════════════════════════════════════════════════════════
#  运行入口
# ═══════════════════════════════════════════════════════════════

def run_once():
    config_devices = load_devices()
    simulated = [simulate_device(d) for d in config_devices]
    status_counts = generate_csvs(simulated)
    fault_count = status_counts["offline"] + status_counts["alert"]
    log_cycle(status_counts, fault_count)
    if fault_count > 0:
        log_fault_details(simulated)
    logger.info("✅ 单次生成完成")


def run_loop(interval: float = 30):
    logger.info("🔄 循环模式启动 | 刷新间隔: %ds", interval)
    config_devices = load_devices()

    cycle = 0
    while True:
        try:
            cycle += 1
            simulated = [simulate_device(d) for d in config_devices]
            status_counts = generate_csvs(simulated)
            fault_count = status_counts["offline"] + status_counts["alert"]
            log_cycle(status_counts, fault_count)
            if fault_count > 0:
                log_fault_details(simulated)
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
