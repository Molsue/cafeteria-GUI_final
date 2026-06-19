# VSCode AI 开发提示词

## 使用方式

把这个文件内容全部复制，粘贴到 VSCode 里的 AI 对话窗口（Copilot / Cursor / Cody 等），AI 就会根据你的数据和需求生成 GUI 代码。

---

## 📋 提示词正文（直接复制下面全部）

```

你是一个前端开发专家。请根据以下需求，帮我创建一个「食堂智能取餐器设备监控大屏」的完整前端页面。

## 项目背景

这是一个22台食堂智能取餐器设备的实时监控系统。设备部署在4个食堂（第一食堂、第二食堂、第三食堂、教工餐厅），每台设备上报CPU、内存、在线率、心跳等运行数据。

## 数据源

页面纯静态，数据从3个CSV文件读取（同目录下 sample_data/ 文件夹）。你需要用 JavaScript fetch 读取并解析CSV。

### 1. sample_data/devices_list.csv（设备主表）

字段：id, name, model, canteen, window, status, cpu, ram, uptime, alert, heartbeat

示例数据：
```
id,name,model,canteen,window,status,cpu,ram,uptime,alert,heartbeat
DEV-2001-0001,第一食堂1F-A区-01号机,SCS-800,第一食堂,1F-A区,online,34.6,57.6,97.5%,,2026-06-19 15:35:37
DEV-2003-0001,第三食堂1F-A区-01号机,SCS-1000,第三食堂,1F-A区,alert,88.8,87.2,98.5%,网络超时,2026-06-19 15:36:41
DEV-2002-0002,第二食堂1F-A区-02号机,SCS-900,第二食堂,1F-A区,offline,100,89.6,0.0%,CPU满载,2026-06-19 15:36:54
```

### 2. sample_data/device_status.csv（状态统计）

字段：status, count, color

示例数据：
```
status,count,color
online,16,#22C55E
offline,4,#EF4444
alert,2,#F59E0B
maintenance,0,#3B82F6
```

### 3. sample_data/fault_devices.csv（故障设备）

字段：device_id, school, fault_type, offline_time, status, action

示例数据：
```
device_id,school,fault_type,offline_time,status,action
DEV-2002-0002,第二食堂,CPU满载,2026-06-19 15:36:54,offline,重启
DEV-2003-0001,第三食堂,网络超时,2026-06-19 15:36:41,alert,检修
```

## GUI 页面要求

### 布局结构（从上到下）

1. **顶部导航栏**
   - 标题：「食堂智能取餐器 · 设备监控大屏」
   - 右上角显示「最后更新: HH:MM:SS」，每5秒刷新一次

2. **统计卡片区（4个卡片横排）**
   - 在线设备：绿色背景，显示 online 数量
   - 离线设备：红色背景，显示 offline 数量
   - 告警设备：橙色背景，显示 alert 数量
   - 维护设备：蓝色背景，显示 maintenance 数量
   - 每个卡片显示数量和百分比

3. **设备列表表格（主区域）**
   - 列：设备ID、设备名称、食堂、区域、型号、CPU%、内存%、在线率、状态、告警、心跳时间
   - 状态列用彩色圆点+文字显示
   - CPU和内存超过80%的用红色高亮
   - 按食堂分组，支持搜索和按状态筛选
   - 点击行可以展开查看设备详情

4. **告警面板（右侧或底部）**
   - 显示所有故障设备（alert + offline）
   - 每一条显示：设备ID、学校、故障类型、离线时间、建议操作（重启/降温/检修）
   - 告警设备用红色/橙色边框高亮
   - 标题旁显示故障数量角标

### 技术栈

- 纯 HTML + CSS + JavaScript（单个 index.html 文件即可，或者拆成 index.html / style.css / app.js）
- 不依赖任何框架，可以用 fetch API 读 CSV
- CSS 用现代风格（深色主题更好看），响应式布局
- 用 CSS Grid 或 Flexbox 布局

### 功能要求

1. 页面加载时自动读取3个CSV文件
2. 每5秒自动刷新数据（实际部署后CSV会由后端实时更新）
3. 设备表格支持按食堂筛选、按状态筛选、关键词搜索
4. 统计卡片数字变化时加一个过渡动画
5. 加载数据时显示 loading 状态
6. 数据读取失败时显示错误提示

### 状态颜色规范

- online: #22C55E (绿)
- offline: #EF4444 (红)
- alert: #F59E0B (橙)
- maintenance: #3B82F6 (蓝)

### 输出要求

请生成3个文件：
1. index.html - 页面结构
2. style.css - 样式（深色科技风主题）
3. app.js - 数据读取+渲染逻辑

CSV文件在 sample_data/ 目录下，请直接fetch该目录下的文件作为数据源。

```
