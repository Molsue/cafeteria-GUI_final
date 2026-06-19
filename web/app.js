/* ============================================
   食堂智能取餐器 · 设备监控大屏
   数据读取 + 渲染逻辑
   ============================================ */

(function () {
  'use strict';

  // ===================== 常量 =====================
  const CSV_PATHS = {
    devices: '../sample_data/devices_list.csv',
    status: '../sample_data/device_status.csv',
    faults: '../sample_data/fault_devices.csv',
  };
  const REFRESH_INTERVAL = 5000; // 5秒刷新
  const STATUS_COLORS = {
    online: '#22C55E',
    offline: '#EF4444',
    alert: '#F59E0B',
    maintenance: '#3B82F6',
  };
  const STATUS_LABELS = {
    online: '在线',
    offline: '离线',
    alert: '告警',
    maintenance: '维护',
  };

  // ===================== 全局状态 =====================
  let devices = [];
  let statusData = [];
  let faultDevices = [];
  let refreshTimer = null;
  let isLoading = false;

  // ===================== DOM 引用 =====================
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const dom = {
    loadingOverlay: $('#loadingOverlay'),
    toastContainer: $('#toastContainer'),
    lastUpdateTime: $('#lastUpdateTime'),
    btnRefresh: $('#btnRefresh'),
    refreshIcon: $('.refresh-icon'),
    // Stat cards
    countOnline: $('#countOnline'),
    countOffline: $('#countOffline'),
    countAlert: $('#countAlert'),
    countMaintenance: $('#countMaintenance'),
    percentOnline: $('#percentOnline'),
    percentOffline: $('#percentOffline'),
    percentAlert: $('#percentAlert'),
    percentMaintenance: $('#percentMaintenance'),
    // Table
    tableBody: $('#tableBody'),
    deviceCountBadge: $('#deviceCountBadge'),
    emptyState: $('#emptyState'),
    searchInput: $('#searchInput'),
    filterCanteen: $('#filterCanteen'),
    filterStatus: $('#filterStatus'),
    btnClearFilter: $('#btnClearFilter'),
    // Alert panel
    alertList: $('#alertList'),
    alertCountBadge: $('#alertCountBadge'),
    alertEmpty: $('#alertEmpty'),
    // Drawer
    drawerOverlay: $('#drawerOverlay'),
    deviceDrawer: $('#deviceDrawer'),
    drawerBody: $('#drawerBody'),
    drawerClose: $('#drawerClose'),
  };

  // ===================== 粒子背景 =====================
  function initParticles() {
    const canvas = $('#particleCanvas');
    const ctx = canvas.getContext('2d');
    let particles = [];
    let animId;

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    const COUNT = 80;
    for (let i = 0; i < COUNT; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        r: Math.random() * 1.5 + 0.5,
        alpha: Math.random() * 0.5 + 0.15,
      });
    }

    function animate() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(148,163,184,${p.alpha})`;
        ctx.fill();
      }

      // 画连线
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(148,163,184,${0.08 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }
      animId = requestAnimationFrame(animate);
    }
    animate();
  }

  // ===================== CSV 解析 =====================
  function parseCSV(text) {
    const lines = text.trim().split('\n');
    if (lines.length < 2) return [];
    const headers = lines[0].split(',').map((h) => h.trim());
    return lines.slice(1).map((line) => {
      // 支持逗号分隔，处理带引号字段
      const cols = [];
      let current = '';
      let inQuotes = false;
      for (const ch of line) {
        if (ch === '"') { inQuotes = !inQuotes; continue; }
        if (ch === ',' && !inQuotes) { cols.push(current.trim()); current = ''; continue; }
        current += ch;
      }
      cols.push(current.trim());
      const obj = {};
      headers.forEach((h, i) => { obj[h] = cols[i] || ''; });
      return obj;
    });
  }

  // ===================== 数据加载 =====================
  async function fetchCSV(path) {
    const resp = await fetch(path, { cache: 'no-cache' });
    if (!resp.ok) throw new Error(`无法加载 ${path} (HTTP ${resp.status})`);
    return resp.text();
  }

  async function loadAllData() {
    const [devicesText, statusText, faultsText] = await Promise.all([
      fetchCSV(CSV_PATHS.devices),
      fetchCSV(CSV_PATHS.status),
      fetchCSV(CSV_PATHS.faults),
    ]);
    devices = parseCSV(devicesText);
    statusData = parseCSV(statusText);
    faultDevices = parseCSV(faultsText);
  }

  // ===================== Toast =====================
  function showToast(message, type) {
    type = type || 'error';
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    dom.toastContainer.appendChild(toast);
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 4000);
  }

  // ===================== 数字过渡动画 =====================
  function animateCount(el, target) {
    const current = parseInt(el.textContent, 10) || 0;
    if (current === target) return;
    const duration = 600;
    const start = performance.now();
    const diff = target - current;
    function step(ts) {
      const elapsed = ts - start;
      const progress = Math.min(elapsed / duration, 1);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(current + diff * eased);
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function animatePercent(el, target) {
    const text = el.textContent.replace('%', '');
    const current = parseFloat(text) || 0;
    if (Math.abs(current - target) < 0.1) {
      el.textContent = target.toFixed(1) + '%';
      return;
    }
    const duration = 600;
    const start = performance.now();
    const diff = target - current;
    function step(ts) {
      const elapsed = ts - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = (current + diff * eased).toFixed(1) + '%';
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // ===================== 渲染统计卡片 =====================
  function renderStatCards() {
    const total = devices.length || 22;
    const statusMap = {};
    statusData.forEach((s) => { statusMap[s.status] = parseInt(s.count, 10) || 0; });

    const online = statusMap.online || 0;
    const offline = statusMap.offline || 0;
    const alert = statusMap.alert || 0;
    const maintenance = statusMap.maintenance || 0;

    animateCount(dom.countOnline, online);
    animateCount(dom.countOffline, offline);
    animateCount(dom.countAlert, alert);
    animateCount(dom.countMaintenance, maintenance);

    animatePercent(dom.percentOnline, total > 0 ? (online / total) * 100 : 0);
    animatePercent(dom.percentOffline, total > 0 ? (offline / total) * 100 : 0);
    animatePercent(dom.percentAlert, total > 0 ? (alert / total) * 100 : 0);
    animatePercent(dom.percentMaintenance, total > 0 ? (maintenance / total) * 100 : 0);

    // 底部进度条
    document.querySelectorAll('.stat-card').forEach((card) => {
      const status = card.dataset.status;
      const count = statusMap[status] || 0;
      const bar = card.querySelector('.stat-card-bar');
      if (bar) bar.style.width = total > 0 ? (count / total) * 100 + '%' : '0%';
    });
  }

  // ===================== 获取当前筛选条件 =====================
  function getFilters() {
    const search = dom.searchInput.value.trim().toLowerCase();
    const canteen = dom.filterCanteen.value;
    const status = dom.filterStatus.value;
    return { search, canteen, status };
  }

  function getFilteredDevices() {
    const { search, canteen, status } = getFilters();
    return devices.filter((d) => {
      if (canteen && d.canteen !== canteen) return false;
      if (status && d.status !== status) return false;
      if (search) {
        const idMatch = d.id.toLowerCase().includes(search);
        const nameMatch = d.name.toLowerCase().includes(search);
        if (!idMatch && !nameMatch) return false;
      }
      return true;
    });
  }

  // ===================== 渲染表格 =====================
  function renderTable() {
    const filtered = getFilteredDevices();
    dom.deviceCountBadge.textContent = filtered.length + ' 台';
    dom.tableBody.innerHTML = '';

    if (filtered.length === 0) {
      dom.emptyState.style.display = 'flex';
    } else {
      dom.emptyState.style.display = 'none';
    }

    // 按食堂分组
    const grouped = {};
    filtered.forEach((d) => {
      const key = d.canteen || '未知';
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(d);
    });

    Object.keys(grouped).forEach((canteen) => {
      // 分组标题行
      const groupRow = document.createElement('tr');
      groupRow.className = 'group-row';
      groupRow.innerHTML = `<td colspan="11" style="padding:10px 14px;background:rgba(59,130,246,0.06);color:var(--blue);font-weight:700;font-size:0.82rem;letter-spacing:0.03em;border-bottom:1px solid rgba(59,130,246,0.12);">📌 ${canteen} (${grouped[canteen].length} 台)</td>`;
      dom.tableBody.appendChild(groupRow);

      grouped[canteen].forEach((d) => {
        const tr = document.createElement('tr');
        tr.dataset.deviceId = d.id;
        tr.innerHTML = buildRowHTML(d);
        tr.addEventListener('click', () => openDrawer(d));
        dom.tableBody.appendChild(tr);
      });
    });
  }

  function buildRowHTML(d) {
    const cpuVal = parseFloat(d.cpu) || 0;
    const ramVal = parseFloat(d.ram) || 0;
    const cpuHigh = cpuVal >= 80 ? ' cell-high' : '';
    const ramHigh = ramVal >= 80 ? ' cell-high' : '';
    const statusLabel = STATUS_LABELS[d.status] || d.status;
    const alertText = d.alert || '—';

    return `
      <td class="cell-id">${escHtml(d.id)}</td>
      <td class="cell-name" title="${escHtml(d.name)}">${escHtml(d.name)}</td>
      <td>${escHtml(d.canteen)}</td>
      <td>${escHtml(d.window)}</td>
      <td>${escHtml(d.model)}</td>
      <td class="cell-metric${cpuHigh}">${d.cpu}%</td>
      <td class="cell-metric${ramHigh}">${d.ram}%</td>
      <td>${d.uptime}</td>
      <td><span class="status-indicator status-${d.status}"><span class="status-dot"></span>${statusLabel}</span></td>
      <td style="color:${alertText !== '—' ? 'var(--orange)' : 'var(--text-muted)'}">${escHtml(alertText)}</td>
      <td style="font-family:var(--font-mono);font-size:0.78rem;">${d.heartbeat}</td>
    `;
  }

  function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ===================== 渲染告警面板 =====================
  function renderAlertPanel() {
    dom.alertList.innerHTML = '';
    const faults = faultDevices.filter((f) => f.status === 'offline' || f.status === 'alert');
    const count = faults.length;

    dom.alertCountBadge.textContent = count;
    dom.alertCountBadge.className = count === 0 ? 'alert-count-badge zero' : 'alert-count-badge';

    if (count === 0) {
      dom.alertList.style.display = 'none';
      dom.alertEmpty.style.display = 'flex';
    } else {
      dom.alertList.style.display = 'flex';
      dom.alertEmpty.style.display = 'none';

      // 排序：offline 优先
      faults.sort((a, b) => {
        const order = { offline: 0, alert: 1 };
        return (order[a.status] || 2) - (order[b.status] || 2);
      });

      faults.forEach((f) => {
        const card = document.createElement('div');
        card.className = `alert-item status-${f.status}`;
        const statusLabel = STATUS_LABELS[f.status] || f.status;
        card.innerHTML = `
          <div class="alert-item-header">
            <span class="alert-item-id">${escHtml(f.device_id)}</span>
            <span class="alert-item-status">${statusLabel}</span>
          </div>
          <div class="alert-item-school">📍 ${escHtml(f.school)}</div>
          <div class="alert-item-row">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            ${escHtml(f.fault_type)}
          </div>
          <div class="alert-item-row">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            ${escHtml(f.offline_time)}
          </div>
          <span class="alert-item-action">🔧 建议操作：${escHtml(f.action)}</span>
        `;
        dom.alertList.appendChild(card);
      });
    }
  }

  // ===================== 筛选器 =====================
  function populateCanteenFilter() {
    const canteens = [...new Set(devices.map((d) => d.canteen).filter(Boolean))].sort();
    const currentValue = dom.filterCanteen.value;
    dom.filterCanteen.innerHTML = '<option value="">全部食堂</option>';
    canteens.forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      dom.filterCanteen.appendChild(opt);
    });
    dom.filterCanteen.value = currentValue;
  }

  function onFilterChange() {
    renderTable();
  }

  function clearFilters() {
    dom.searchInput.value = '';
    dom.filterCanteen.value = '';
    dom.filterStatus.value = '';
    renderTable();
  }

  // ===================== 抽屉（设备详情） =====================
  function openDrawer(device) {
    dom.drawerBody.innerHTML = buildDetailHTML(device);
    dom.drawerOverlay.classList.add('visible');
    dom.deviceDrawer.classList.add('visible');
    document.body.style.overflow = 'hidden';

    // 延迟渲染进度条动画
    setTimeout(() => {
      const cpu = parseFloat(device.cpu) || 0;
      const ram = parseFloat(device.ram) || 0;
      const uptime = parseFloat(device.uptime) || 0;
      const cpuFill = dom.drawerBody.querySelector('.detail-chart-fill.cpu');
      const ramFill = dom.drawerBody.querySelector('.detail-chart-fill.ram');
      const uptimeFill = dom.drawerBody.querySelector('.detail-chart-fill.uptime');
      if (cpuFill) cpuFill.style.width = cpu + '%';
      if (ramFill) ramFill.style.width = ram + '%';
      if (uptimeFill) uptimeFill.style.width = uptime + '%';
    }, 100);
  }

  function closeDrawer() {
    dom.drawerOverlay.classList.remove('visible');
    dom.deviceDrawer.classList.remove('visible');
    document.body.style.overflow = '';
  }

  function buildDetailHTML(d) {
    const statusLabel = STATUS_LABELS[d.status] || d.status;
    const cpuVal = parseFloat(d.cpu) || 0;
    const ramVal = parseFloat(d.ram) || 0;
    const uptimeVal = parseFloat(d.uptime) || 0;
    const alertText = d.alert || '无';
    const cpuColor = cpuVal >= 80 ? 'var(--red)' : cpuVal >= 60 ? 'var(--orange)' : 'var(--green)';
    const ramColor = ramVal >= 80 ? 'var(--red)' : ramVal >= 60 ? 'var(--orange)' : 'var(--green)';

    return `
      <div class="detail-grid">
        <div class="detail-item">
          <div class="detail-item-label">设备ID</div>
          <div class="detail-item-value mono">${escHtml(d.id)}</div>
        </div>
        <div class="detail-item">
          <div class="detail-item-label">运行状态</div>
          <div class="detail-item-value" style="color:${STATUS_COLORS[d.status]}">${statusLabel}</div>
        </div>
        <div class="detail-item full">
          <div class="detail-item-label">设备名称</div>
          <div class="detail-item-value">${escHtml(d.name)}</div>
        </div>
        <div class="detail-item">
          <div class="detail-item-label">所属食堂</div>
          <div class="detail-item-value">${escHtml(d.canteen)}</div>
        </div>
        <div class="detail-item">
          <div class="detail-item-label">所在区域</div>
          <div class="detail-item-value">${escHtml(d.window)}</div>
        </div>
        <div class="detail-item">
          <div class="detail-item-label">设备型号</div>
          <div class="detail-item-value mono">${escHtml(d.model)}</div>
        </div>
        <div class="detail-item">
          <div class="detail-item-label">告警信息</div>
          <div class="detail-item-value" style="color:${alertText !== '无' ? 'var(--orange)' : 'var(--text-muted)'}">${escHtml(alertText)}</div>
        </div>

        <div class="detail-item full">
          <div class="detail-item-label">CPU 使用率</div>
          <div class="detail-item-value" style="color:${cpuColor}">${d.cpu}%</div>
          <div class="detail-chart-bar"><div class="detail-chart-fill cpu" style="width:0%"></div></div>
        </div>
        <div class="detail-item full">
          <div class="detail-item-label">内存使用率</div>
          <div class="detail-item-value" style="color:${ramColor}">${d.ram}%</div>
          <div class="detail-chart-bar"><div class="detail-chart-fill ram" style="width:0%"></div></div>
        </div>
        <div class="detail-item full">
          <div class="detail-item-label">在线率</div>
          <div class="detail-item-value" style="color:${uptimeVal >= 95 ? 'var(--green)' : uptimeVal >= 80 ? 'var(--orange)' : 'var(--red)'}">${d.uptime}</div>
          <div class="detail-chart-bar"><div class="detail-chart-fill uptime" style="width:0%"></div></div>
        </div>
        <div class="detail-item full">
          <div class="detail-item-label">最后心跳</div>
          <div class="detail-item-value mono">${d.heartbeat}</div>
        </div>
      </div>
    `;
  }

  // ===================== 更新时间 =====================
  function updateTime() {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0');
    dom.lastUpdateTime.textContent = `${hh}:${mm}:${ss}`;
  }

  // ===================== 主刷新流程 =====================
  async function refreshData(showLoading) {
    if (isLoading) return;
    isLoading = true;

    if (showLoading) {
      dom.loadingOverlay.classList.remove('hidden');
    }

    try {
      await loadAllData();
      renderAll();
      updateTime();

      // 旋转刷新图标
      dom.refreshIcon.classList.add('spinning');
      setTimeout(() => dom.refreshIcon.classList.remove('spinning'), 800);

      if (showLoading) {
        dom.loadingOverlay.classList.add('hidden');
      }
    } catch (err) {
      console.error('数据加载失败:', err);
      dom.loadingOverlay.classList.add('hidden');
      showToast('数据加载失败，请检查 sample_data/ 目录是否存在', 'error');
    } finally {
      isLoading = false;
    }
  }

  function renderAll() {
    populateCanteenFilter();
    renderStatCards();
    renderTable();
    renderAlertPanel();
  }

  // ===================== 事件绑定 =====================
  function bindEvents() {
    dom.btnRefresh.addEventListener('click', () => refreshData(false));
    dom.searchInput.addEventListener('input', onFilterChange);
    dom.filterCanteen.addEventListener('change', onFilterChange);
    dom.filterStatus.addEventListener('change', onFilterChange);
    dom.btnClearFilter.addEventListener('click', clearFilters);

    dom.drawerClose.addEventListener('click', closeDrawer);
    dom.drawerOverlay.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeDrawer();
    });
  }

  // ===================== 启动 =====================
  function init() {
    bindEvents();
    initParticles();
    updateTime();

    // 初始加载（显示loading）
    refreshData(true);

    // 5秒自动刷新
    refreshTimer = setInterval(() => refreshData(false), REFRESH_INTERVAL);

    // 每秒更新时间
    setInterval(updateTime, 1000);
  }

  // DOM 就绪后启动
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
