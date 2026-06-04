#!/usr/bin/env python3
"""
simulator_web - 食堂智能取餐器设备数据模拟器
==============================================
读取 devices_config.csv 设备定义 → 写入 MySQL cafeteria_next → 生成前端 CSV

用法:
  ./generator.py [--once] [--interval 30]

  --once      单次生成后退出
  --interval  循环模式刷新间隔（默认30秒）

前端 CSV 输出:
  /opt/CafeteriaNext/web/dist/data/devices_list.csv  设备清单（列表模式）
  /opt/CafeteriaNext/web/dist/data/device_status.csv  状态分布（地图+统计卡片）
  /opt/CafeteriaNext/web/dist/data/fault_devices.csv  故障设备（告警面板）
"""

import csv
import os
import random
import sys
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ── MySQL ──────────────────────────────────────────────────────
import pymysql

DB_CONFIG = {
    "host": "localhost",
    "user": "cafeteria_app",
    "password": "CafeteriaApp2026!",
    "database": "cafeteria_next",
    "charset": "utf8mb4",
}

# ── 路径 ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
CONFIG_CSV = BASE_DIR / "config" / "devices_config.csv"
OUTPUT_DIR = Path("/opt/CafeteriaNext/web/dist/data")
for d in [OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── 状态离散表（模拟真实设备行为）─────────────────────────────
STATUS_WEIGHTS = {
    "online":       72,   # 大部分在线
    "alert":        10,   # 偶尔告警
    "offline":       8,   # 少量离线
    "maintenance":  10,   # 部分维护
}

FAULT_TYPES = ["温度过高", "CPU满载", "网络超时", "内存不足", "磁盘异常", "进程僵死"]
FAULT_MSGS = {
    "温度过高": "主板温度超85℃阈值",
    "CPU满载":   "CPU持续满载超5分钟",
    "网络超时": "连续3次心跳超时",
    "内存不足": "内存使用率超95%",
    "磁盘异常": "磁盘I/O延迟异常",
    "进程僵死": "主进程无响应超60s",
}


def db():
    """获取 MySQL 连接"""
    return pymysql.connect(**DB_CONFIG)


def load_devices() -> list[dict]:
    """读取设备配置 CSV"""
    devices = []
    with open(CONFIG_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            devices.append(row)
    print(f"📋 加载设备配置: {len(devices)} 台")
    return devices


def seed_devices(devices: list[dict]):
    """初始化 MySQL devices 表"""
    conn = db()
    cur = conn.cursor()
    existing = set()
    cur.execute("SELECT device_id FROM devices")
    for row in cur.fetchall():
        existing.add(row[0])

    inserted = 0
    for d in devices:
        if d["device_id"] in existing:
            continue
        cur.execute(
            """INSERT INTO devices (device_id, device_name, model, canteen, `window`, status, cpu, ram, uptime, alert)
               VALUES (%s, %s, %s, %s, %s, 'online', 30, 50, '100.0', '')""",
            (d["device_id"], d["device_name"], d["model"], d["canteen"], d["window"]),
        )
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()
    if inserted:
        print(f"🌱 新增设备: {inserted} 台 → MySQL")
    else:
        print(f"✅ 设备已存在于 MySQL ({len(existing)} 台)")


def simulate_device(device: dict) -> dict:
    """给一台设备生成运行时模拟数据"""
    status = random.choices(
        list(STATUS_WEIGHTS.keys()),
        weights=list(STATUS_WEIGHTS.values()),
        k=1,
    )[0]

    cpu = round(random.gauss(38, 15), 1) if status == "online" else round(random.gauss(85, 10), 1)
    cpu = min(100, max(5, cpu))
    ram = round(random.gauss(52, 12), 1) if status == "online" else round(random.gauss(90, 8), 1)
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


def update_mysql(devices: list[dict], simulated: list[dict]):
    """将模拟状态写回 MySQL"""
    conn = db()
    cur = conn.cursor()

    for sim in simulated:
        cur.execute(
            """UPDATE devices
               SET status=%s, cpu=%s, ram=%s, uptime=%s, alert=%s, heartbeat=%s
               WHERE device_id=%s""",
            (sim["status"], sim["cpu"], sim["ram"], sim["uptime"], sim["alert"],
             sim["heartbeat"], sim["id"]),
        )

    # 记录故障日志
    for sim in simulated:
        if sim["status"] in ("alert", "offline") and sim["alert"]:
            cur.execute(
                """INSERT INTO device_fault_logs (device_id, fault_type, fault_msg)
                   SELECT %s, %s, %s
                   WHERE NOT EXISTS (
                     SELECT 1 FROM device_fault_logs
                     WHERE device_id=%s AND fault_type=%s AND resolved_at IS NULL
                   )""",
                (sim["id"], sim["alert"], FAULT_MSGS.get(sim["alert"], ""),
                 sim["id"], sim["alert"]),
            )

    conn.commit()
    cur.close()
    conn.close()


def generate_csvs(simulated: list[dict]):
    """生成 3 个前端 CSV"""

    # ── 1. devices_list.csv ──
    with open(OUTPUT_DIR / "devices_list.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "model", "canteen", "window",
                                           "status", "cpu", "ram", "uptime", "alert", "heartbeat"])
        w.writeheader()
        for s in sorted(simulated, key=lambda x: (x["canteen"], x["window"])):
            w.writerow(s)

    # ── 2. device_status.csv ──
    status_counts = {
        "online":      0,
        "offline":     0,
        "alert":       0,
        "maintenance": 0,
    }
    for s in simulated:
        st = s["status"]
        if st in status_counts:
            status_counts[st] += 1
        elif st == "alert":
            status_counts["alert"] += 1
        elif st == "offline":
            status_counts["offline"] += 1
        else:
            status_counts["online"] += 1

    status_color_map = {
        "online":       "#22C55E",
        "offline":      "#EF4444",
        "alert":        "#F59E0B",
        "maintenance":  "#3B82F6",
    }
    with open(OUTPUT_DIR / "device_status.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["status", "count", "color"])
        w.writeheader()
        for st in ["online", "offline", "alert", "maintenance"]:
            w.writerow({"status": st, "count": status_counts[st], "color": status_color_map[st]})

    # ── 3. fault_devices.csv ──
    fault_devices = [s for s in simulated if s["status"] in ("alert", "offline")]
    with open(OUTPUT_DIR / "fault_devices.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["device_id", "school", "fault_type",
                                           "offline_time", "status", "action"])
        w.writeheader()
        for fd in fault_devices:
            w.writerow({
                "device_id":    fd["id"],
                "school":       fd["canteen"],
                "fault_type":   fd["alert"],
                "offline_time": fd["heartbeat"],
                "status":       fd["status"],
                "action":       "重启" if fd["alert"] == "CPU满载" else ("降温" if fd["alert"] == "温度过高" else "检修"),
            })

    total = len(simulated)
    online = status_counts["online"]
    offline = status_counts["offline"]
    alert = status_counts["alert"]
    maint = status_counts["maintenance"]
    print(f"📊 [{datetime.now().strftime('%H:%M:%S')}] {total}台 | "
          f"在线:{online} 离线:{offline} 告警:{alert} 维护:{maint} → CSV 已刷新")


def run_once():
    """单次运行"""
    config_devices = load_devices()
    seed_devices(config_devices)
    simulated = [simulate_device(d) for d in config_devices]
    update_mysql(config_devices, simulated)
    generate_csvs(simulated)
    print("✅ 单次生成完成")


def run_loop(interval: int = 30):
    """循环运行模式"""
    print(f"🔄 循环模式 | 刷新间隔: {interval}s | Ctrl+C 退出")
    config_devices = load_devices()
    seed_devices(config_devices)

    while True:
        try:
            simulated = [simulate_device(d) for d in config_devices]
            update_mysql(config_devices, simulated)
            generate_csvs(simulated)
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n👋 已停止")
            break
        except Exception as e:
            print(f"⚠️ 错误: {e}")
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="食堂取餐器设备模拟器")
    parser.add_argument("--once", action="store_true", help="单次运行")
    parser.add_argument("--interval", type=int, default=30, help="刷新间隔(秒), 默认30")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        run_loop(args.interval)
