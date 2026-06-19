# 食堂智能取餐器 · 设备监控 GUI

## 项目简介

22台食堂智能取餐器设备的实时监控大屏。模拟器每30秒刷新设备状态，输出CSV文件供前端GUI直接读取。

## 数据文件

`sample_data/` 目录下是模拟器生成的示例数据，共 3 个 CSV：

| 文件 | 用途 |
|------|------|
| `devices_list.csv` | 22台设备完整信息（主表） |
| `device_status.csv` | 在线/离线/告警/维护数量统计 |
| `fault_devices.csv` | 故障设备详情 + 建议操作 |

### devices_list.csv 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| id | 设备编号 | DEV-2001-0001 |
| name | 设备名称 | 第一食堂1F-A区-01号机 |
| model | 设备型号 | SCS-800/900/1000 |
| canteen | 所属食堂 | 第一食堂/第二食堂/第三食堂/教工餐厅 |
| window | 所在区域 | 1F-A区/1F-B区/2F-C区/2F-D区 |
| status | 运行状态 | online/offline/alert/maintenance |
| cpu | CPU使用率(%) | 35.2 |
| ram | 内存使用率(%) | 48.7 |
| uptime | 在线率(%) | 99.1%（offline为0.0%） |
| alert | 告警类型 | 空字符串=正常，否则为故障类型 |
| heartbeat | 最后心跳时间 | 2026-06-19 15:36:56 |

### 状态颜色映射

| 状态 | 颜色 | 含义 |
|------|------|------|
| online | #22C55E 绿色 | 正常运行 |
| offline | #EF4444 红色 | 已离线 |
| alert | #F59E0B 橙色 | 运行中但触发告警 |
| maintenance | #3B82F6 蓝色 | 维护中 |

## GUI 开发指南

### 本地运行

```bash
git clone git@github.com:Molsue/cafeteria-GUI_final.git
cd cafeteria-GUI_final
npx live-server .   # 或用 VSCode Live Server 插件
```

### 数据读取方式

纯前端，直接从 `sample_data/` 读取 CSV 文件（或部署后从 `data/` 目录读取线上实时CSV）：

```javascript
fetch('sample_data/devices_list.csv')
  .then(r => r.text())
  .then(csv => {
    // 用 PapaParse 或手写解析
    const rows = csv.trim().split('\n').slice(1).map(line => {
      const cols = line.split(',');
      return { id: cols[0], name: cols[1], ... };
    });
  });
```

## 目录结构

```
cafeteria-GUI_final/
├── README.md
├── generator.py          # 模拟器（服务器运行，GUI不需要管）
├── generate.sh
├── config/
│   └── devices_config.csv
├── sample_data/          # ← GUI开发用示例数据
│   ├── devices_list.csv
│   ├── device_status.csv
│   └── fault_devices.csv
└── web/                  # ← 你的GUI代码放这里
    ├── index.html
    ├── style.css
    └── app.js
```
