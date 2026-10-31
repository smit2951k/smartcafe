/**
 * AROMA CAFE — MODERN ADMIN WORKSPACE CONTROLLER
 * Features:
 * - 5-second live feed polling with Web Audio chime
 * - Live clock updating every second
 * - Native HTML5 Canvas 7-Day Revenue Velocity Chart
 * - Dynamic Kanban board with per-second elapsed timer badge (amber >10m, red >20m)
 * - Order Detail Drawer & 80mm Kitchen Ticket printing
 * - Visual Floor Grid with Table Status and QR Code download
 * - Instant 86 Menu availability toggling & bulk controls
 * - Customer Directory with aggregated history drawer (No email)
 * - Settings & Staff account controls
 */

// Global State
const AdminApp = {
  soundEnabled: true,
  audioCtx: null,
  activeSection: 'overview',
  ordersViewMode: 'board', // 'board' or 'table'
  activeFilter: 'active',  // 'active', 'pending', 'prep', 'ready', 'completed', 'cancelled'
  tableFilter: 'all',
  searchQuery: '',
  liveFeedData: null,
  knownOrderIds: new Set(),
  pollTimer: null,
  clockTimer: null,
  elapsedTimer: null
};

// -------------------------------------------------------------
// WEB AUDIO SYNTHESIZER (NO EXTERNAL AUDIO FILES NEEDED)
// -------------------------------------------------------------
function playOrderChime() {
  if (!AdminApp.soundEnabled) return;
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    if (!AdminApp.audioCtx) {
      AdminApp.audioCtx = new AudioContext();
    }
    const ctx = AdminApp.audioCtx;
    if (ctx.state === 'suspended') {
      ctx.resume();
    }

    const now = ctx.currentTime;
    // Dual tone chime: E5 (659.25Hz) followed by B5 (987.77Hz)
    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gainNode = ctx.createGain();

    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(659.25, now);
    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(987.77, now + 0.12);

    gainNode.gain.setValueAtTime(0.01, now);
    gainNode.gain.exponentialRampToValueAtTime(0.25, now + 0.04);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.6);

    osc1.connect(gainNode);
    osc2.connect(gainNode);
    gainNode.connect(ctx.destination);

    osc1.start(now);
    osc1.stop(now + 0.15);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.6);
  } catch (e) {
    console.warn("Audio chime unavailable:", e);
  }
}

// -------------------------------------------------------------
// TOAST NOTIFICATIONS
// -------------------------------------------------------------
function showAdminToast(message, type = 'info') {
  const container = document.getElementById('adminToastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `admin-toast ${type}`;
  toast.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px;">
      <span style="font-size:16px;">${type === 'success' ? '✓' : type === 'error' ? '⚠' : '🔔'}</span>
      <span style="font-size:12.5px;font-weight:500;">${message}</span>
    </div>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// -------------------------------------------------------------
// LIVE CLOCK
// -------------------------------------------------------------
function initLiveClock() {
  const clockEl = document.getElementById('adminLiveClock');
  if (!clockEl) return;
  const update = () => {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  };
  update();
  AdminApp.clockTimer = setInterval(update, 1000);
}

// -------------------------------------------------------------
// SECTION NAVIGATION (SINGLE SIDEBAR NAVIGATION)
// -------------------------------------------------------------
function switchSection(sectionId) {
  AdminApp.activeSection = sectionId;

  // Update sidebar active link
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
    if (link.getAttribute('data-section') === sectionId) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });

  // Switch active section DOM
  document.querySelectorAll('.admin-section').forEach(sec => {
    if (sec.id === `section-${sectionId}`) {
      sec.classList.add('active');
    } else {
      sec.classList.remove('active');
    }
  });

  // Update Page Title
  const titles = {
    overview: 'Operations Overview',
    orders: 'Kitchen & Floor Orders',
    reservations: 'Table Reservations',
    tables: 'Visual Floor Grid',
    menu: 'Culinary Menu & 86 Controls',
    customers: 'Patron Directory',
    settings: 'Cafe Sanctuary Settings'
  };
  const titleEl = document.getElementById('adminPageTitle');
  if (titleEl) {
    titleEl.textContent = titles[sectionId] || 'Workspace';
  }

  // Close mobile sidebar if open
  closeMobileSidebar();

  // If switched to overview, redraw canvas
  if (sectionId === 'overview' && AdminApp.liveFeedData) {
    renderRevenueChart(AdminApp.liveFeedData.seven_day_revenue);
  }
}

function toggleMobileSidebar() {
  const sidebar = document.getElementById('adminSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (sidebar && backdrop) {
    sidebar.classList.toggle('open');
    backdrop.classList.toggle('open');
  }
}

function closeMobileSidebar() {
  const sidebar = document.getElementById('adminSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (sidebar && backdrop) {
    sidebar.classList.remove('open');
    backdrop.classList.remove('open');
  }
}

// -------------------------------------------------------------
// DATA POLLING LOOP
// -------------------------------------------------------------
async function fetchLiveFeed() {
  const statusDot = document.getElementById('liveStatusDot');
  try {
    const res = await fetch('/api/admin/live-feed');
    if (!res.ok) {
      if (res.status === 401 || res.status === 403) {
        window.location.href = '/admin/login';
        return;
      }
      throw new Error(`Feed error: ${res.status}`);
    }
    const data = await res.json();
    if (data.success) {
      processLiveFeed(data);
      if (statusDot) statusDot.style.backgroundColor = '#10B981';
    }
  } catch (err) {
    console.error("Live feed sync failed:", err);
    if (statusDot) statusDot.style.backgroundColor = '#EF4444';
  }
}

function processLiveFeed(data) {
  const previousData = AdminApp.liveFeedData;
  AdminApp.liveFeedData = data;

  // Delta detection for new incoming orders
  const currentOrders = data.orders || [];
  let newOrderDetected = false;

  currentOrders.forEach(order => {
    if (AdminApp.knownOrderIds.size > 0 && !AdminApp.knownOrderIds.has(order.id)) {
      newOrderDetected = true;
      showAdminToast(`New order #${order.id} received for Table ${order.table_number}!`, 'success');
    }
    AdminApp.knownOrderIds.add(order.id);
  });

  if (newOrderDetected) {
    playOrderChime();
  }

  // Render components
  renderKPIs(data.kpi);
  if (AdminApp.activeSection === 'overview') {
    renderRevenueChart(data.seven_day_revenue);
    renderOverviewMiniBoards(data);
  }
  renderOrders(data.orders);
  renderReservations(data.reservations);
  renderTables(data.tables);
  renderCustomers(data.customers);
}

// -------------------------------------------------------------
// RENDER KPIS
// -------------------------------------------------------------
function renderKPIs(kpi) {
  if (!kpi) return;
  const setEl = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };
  setEl('kpiTodayRev', kpi.today_revenue);
  setEl('kpiRevTrend', kpi.today_revenue_trend);
  setEl('kpiOrdersToday', kpi.orders_today);
  setEl('kpiOrderTrend', kpi.orders_today_trend);
  setEl('kpiAvgTicket', kpi.avg_ticket);
  setEl('kpiAvgTicketTrend', kpi.avg_ticket_trend);
  setEl('kpiKitchenActive', kpi.kitchen_active);
  setEl('kpiReadyPass', kpi.ready_on_pass);
  setEl('kpiTablesOccupied', kpi.tables_occupied);
  setEl('kpiResToday', kpi.reservations_today);
  setEl('kpiResTrend', kpi.reservations_trend);

  // Update sidebar counter badge
  const pendingOrders = (AdminApp.liveFeedData?.orders || []).filter(o => o.status === 'PENDING').length;
  const badgeEl = document.getElementById('ordersNavBadge');
  if (badgeEl) {
    badgeEl.textContent = pendingOrders;
    badgeEl.style.display = pendingOrders > 0 ? 'inline-block' : 'none';
  }
}

// -------------------------------------------------------------
// NATIVE HTML5 CANVAS 7-DAY REVENUE VELOCITY CHART
// -------------------------------------------------------------
function renderRevenueChart(daysData) {
  const canvas = document.getElementById('revenueChart');
  if (!canvas || !daysData || daysData.length === 0) return;

  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();

  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = rect.height;
  const paddingBottom = 30;
  const paddingTop = 20;
  const chartHeight = h - paddingBottom - paddingTop;

  ctx.clearRect(0, 0, w, h);

  const maxRev = Math.max(...daysData.map(d => d.revenue), 1000);
  const barWidth = Math.min(36, (w / daysData.length) * 0.45);
  const step = w / daysData.length;

  daysData.forEach((item, idx) => {
    const x = idx * step + (step - barWidth) / 2;
    const barH = (item.revenue / maxRev) * chartHeight;
    const y = h - paddingBottom - barH;

    // Draw background track
    ctx.fillStyle = '#F5F5F4';
    ctx.beginPath();
    ctx.roundRect(x, paddingTop, barWidth, chartHeight, 4);
    ctx.fill();

    // Draw revenue bar (gold gradient)
    const grad = ctx.createLinearGradient(0, y, 0, y + barH);
    grad.addColorStop(0, '#C5A880');
    grad.addColorStop(1, '#8C6D45');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.roundRect(x, y, barWidth, barH, 4);
    ctx.fill();

    // Draw day label
    ctx.fillStyle = '#78716C';
    ctx.font = '500 11.5px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(item.day, x + barWidth / 2, h - 8);

    // Draw revenue above bar
    ctx.fillStyle = '#1C1917';
    ctx.font = '600 11px Inter, sans-serif';
    ctx.fillText(`₹${Math.round(item.revenue)}`, x + barWidth / 2, Math.max(16, y - 6));
  });
}

// -------------------------------------------------------------
// OVERVIEW MINI BOARDS
// -------------------------------------------------------------
function renderOverviewMiniBoards(data) {
  // Mini live orders
  const miniOrdersList = document.getElementById('overviewLiveOrdersList');
  if (miniOrdersList) {
    const activeOrders = (data.orders || []).filter(o => ['PENDING', 'PREPARING', 'READY'].includes(o.status)).slice(0, 5);
    if (activeOrders.length === 0) {
      miniOrdersList.innerHTML = `
        <div style="text-align:center;padding:24px;color:#78716C;font-size:12.5px;">
          No active orders in preparation.
        </div>`;
    } else {
      miniOrdersList.innerHTML = activeOrders.map(o => `
        <div onclick="openOrderDetail('${o.id}')" style="display:flex;justify-content:space-between;align-items:center;padding:12px 14px;border-bottom:1px solid #F0EEE9;cursor:pointer;">
          <div style="display:flex;align-items:center;gap:10px;">
            <span class="table-tag">T${o.table_number}</span>
            <div>
              <strong style="font-size:13px;display:block;">#${o.id} &bull; ${o.customer_name}</strong>
              <span style="font-size:11.5px;color:#78716C;">${(o.items || []).map(i => `${i.quantity}x ${i.name}`).join(', ')}</span>
            </div>
          </div>
          <div style="text-align:right;">
            <strong style="font-size:13px;display:block;font-family:var(--font-serif);">₹${o.total}</strong>
            <span class="status-badge status-${o.status.toLowerCase()}" style="font-size:10px;padding:1px 6px;border-radius:99px;">${o.status}</span>
          </div>
        </div>
      `).join('');
    }
  }

  // Top selling items
  const topSellingEl = document.getElementById('overviewTopSellingList');
  if (topSellingEl && data.top_selling) {
    topSellingEl.innerHTML = data.top_selling.map((item, idx) => `
      <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #F0EEE9;">
        <div style="display:flex;align-items:center;gap:10px;">
          <span style="width:22px;height:22px;border-radius:50%;background:#F5F5F4;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;">${idx + 1}</span>
          <span style="font-size:13px;font-weight:500;">${item.name}</span>
        </div>
        <span style="font-size:12px;font-weight:600;color:var(--admin-gold);">${item.count} ordered</span>
      </div>
    `).join('');
  }
}

// -------------------------------------------------------------
// ORDERS KANBAN & TABLE RENDERING
// -------------------------------------------------------------
function setOrdersViewMode(mode) {
  AdminApp.ordersViewMode = mode;
  document.getElementById('viewModeBoardBtn')?.classList.toggle('active', mode === 'board');
  document.getElementById('viewModeTableBtn')?.classList.toggle('active', mode === 'table');
  document.getElementById('kanbanBoardWrapper')?.classList.toggle('hidden', mode !== 'board');
  document.getElementById('ordersTableWrapper')?.classList.toggle('hidden', mode !== 'table');
  if (AdminApp.liveFeedData) {
    renderOrders(AdminApp.liveFeedData.orders);
  }
}

function setOrdersFilter(filter) {
  AdminApp.activeFilter = filter;
  document.querySelectorAll('.segmented-control .segmented-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-filter') === filter);
  });
  if (AdminApp.liveFeedData) {
    renderOrders(AdminApp.liveFeedData.orders);
  }
}

function renderOrders(orders = []) {
  const query = AdminApp.searchQuery.toLowerCase();
  const tableVal = AdminApp.tableFilter;

  // Filter orders
  let filtered = orders.filter(o => {
    // Search match
    if (query) {
      const matchId = (o.id || '').toLowerCase().includes(query);
      const matchName = (o.customer_name || '').toLowerCase().includes(query);
      const matchMobile = (o.customer_mobile || '').toLowerCase().includes(query);
      const matchTable = String(o.table_number || '').toLowerCase().includes(query);
      if (!matchId && !matchName && !matchMobile && !matchTable) return false;
    }
    // Table filter
    if (tableVal !== 'all' && String(o.table_number) !== tableVal) {
      return false;
    }
    // Segment filter
    if (AdminApp.activeFilter === 'pending' && o.status !== 'PENDING') return false;
    if (AdminApp.activeFilter === 'prep' && o.status !== 'PREPARING') return false;
    if (AdminApp.activeFilter === 'ready' && o.status !== 'READY') return false;
    if (AdminApp.activeFilter === 'completed' && o.status !== 'COMPLETED') return false;
    if (AdminApp.activeFilter === 'cancelled' && o.status !== 'CANCELLED') return false;
    if (AdminApp.activeFilter === 'active' && ['COMPLETED', 'CANCELLED'].includes(o.status)) return false;

    return true;
  });

  // Render Kanban Columns
  const cols = {
    PENDING: document.getElementById('colPendingOrders'),
    PREPARING: document.getElementById('colPrepOrders'),
    READY: document.getElementById('colReadyOrders'),
    COMPLETED: document.getElementById('colCompletedOrders')
  };

  const counts = { PENDING: 0, PREPARING: 0, READY: 0, COMPLETED: 0 };

  // Clear columns
  Object.values(cols).forEach(col => { if (col) col.innerHTML = ''; });

  filtered.forEach(o => {
    if (cols[o.status]) {
      counts[o.status]++;
      cols[o.status].appendChild(createOrderCardElement(o));
    }
  });

  // Update Column Badges
  Object.keys(counts).forEach(status => {
    const badge = document.getElementById(`countBadge-${status}`);
    if (badge) badge.textContent = counts[status];
    // Empty state
    if (counts[status] === 0 && cols[status]) {
      cols[status].innerHTML = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 14 14"></polyline></svg>
          <h4>No ${status.toLowerCase()} orders</h4>
          <p>Orders in this queue will appear here live.</p>
        </div>
      `;
    }
  });

  // Render Table View if active
  const tableBody = document.getElementById('ordersTableBody');
  if (tableBody) {
    if (filtered.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:32px;color:#78716C;">No orders matching current filter criteria.</td></tr>`;
    } else {
      tableBody.innerHTML = filtered.map(o => `
        <tr onclick="openOrderDetail('${o.id}')" style="cursor:pointer;border-bottom:1px solid #F0EEE9;">
          <td style="padding:12px 16px;font-family:var(--font-mono);font-weight:600;">#${o.id}</td>
          <td style="padding:12px 16px;"><span class="table-tag">T${o.table_number}</span></td>
          <td style="padding:12px 16px;">
            <strong>${o.customer_name}</strong>
            <span style="font-size:11px;color:#78716C;display:block;">${o.customer_mobile || 'Walk-in'}</span>
          </td>
          <td style="padding:12px 16px;font-size:12.5px;">${(o.items || []).map(i => `${i.quantity}x ${i.name}`).join(', ')}</td>
          <td style="padding:12px 16px;font-family:var(--font-serif);font-size:1.15rem;font-weight:700;">₹${o.total}</td>
          <td style="padding:12px 16px;">
            <span class="timer-badge ${getTimerClass(o.elapsed_minutes)}">
              ⏱ ${o.elapsed_minutes || 0}m
            </span>
          </td>
          <td style="padding:12px 16px;">
            <span class="status-badge status-${o.status.toLowerCase()}">${o.status}</span>
          </td>
        </tr>
      `).join('');
    }
  }
}

function createOrderCardElement(order) {
  const card = document.createElement('div');
  card.className = 'order-card';
  card.setAttribute('data-order-id', order.id);
  card.onclick = (e) => {
    if (!e.target.closest('button')) {
      openOrderDetail(order.id);
    }
  };

  const timerClass = getTimerClass(order.elapsed_minutes);

  // Next status action button configuration
  let actionBtnHtml = '';
  if (order.status === 'PENDING') {
    actionBtnHtml = `<button onclick="updateOrderStatus('${order.id}', 'PREPARING')" class="action-btn-sm btn-primary-action">Start Prep &rarr;</button>`;
  } else if (order.status === 'PREPARING') {
    actionBtnHtml = `<button onclick="updateOrderStatus('${order.id}', 'READY')" class="action-btn-sm btn-primary-action">Mark Ready &check;</button>`;
  } else if (order.status === 'READY') {
    actionBtnHtml = `<button onclick="updateOrderStatus('${order.id}', 'COMPLETED')" class="action-btn-sm btn-primary-action">Complete Order &check;</button>`;
  }

  card.innerHTML = `
    <div class="card-top">
      <div style="display:flex;align-items:center;gap:6px;">
        <span class="order-id">#${order.id}</span>
        <span class="timer-badge ${timerClass}" id="timer-${order.id}">⏱ ${order.elapsed_minutes || 0}m</span>
      </div>
      <span class="table-tag">T${order.table_number}</span>
    </div>

    <div class="customer-row">
      <span class="customer-name">${order.customer_name}</span>
      <span style="font-family:var(--font-mono);font-size:11px;">${order.customer_mobile || ''}</span>
    </div>

    <div class="items-preview">
      ${(order.items || []).map(i => `<strong>${i.quantity}x</strong> ${i.name}`).join('<br/>')}
    </div>

    ${order.notes ? `<div style="font-size:11.5px;color:#92400E;background:#FEF3C7;padding:4px 8px;border-radius:4px;"><strong>Note:</strong> ${order.notes}</div>` : ''}

    <div class="card-bottom">
      <span class="order-amount">₹${order.total}</span>
      <div class="card-actions">
        ${actionBtnHtml}
      </div>
    </div>
  `;

  return card;
}

function getTimerClass(minutes) {
  if (!minutes) return 'normal';
  if (minutes >= 20) return 'red';
  if (minutes >= 10) return 'amber';
  return 'normal';
}

// -------------------------------------------------------------
// ORDER STATUS MUTATION
// -------------------------------------------------------------
async function updateOrderStatus(orderId, newStatus) {
  try {
    const res = await fetch(`/api/admin/orders/${orderId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    const data = await res.json();
    if (data.success) {
      showAdminToast(`Order #${orderId} moved to ${newStatus}`, 'success');
      fetchLiveFeed();
      // If drawer is open, refresh drawer
      if (document.getElementById('orderDetailDrawer')?.classList.contains('active')) {
        openOrderDetail(orderId);
      }
    } else {
      showAdminToast(data.error || 'Failed to update order status', 'error');
    }
  } catch (err) {
    showAdminToast('Network error while updating status', 'error');
  }
}

async function cancelOrderWithReason(orderId) {
  const reason = prompt('Please specify the cancellation reason for the kitchen log:');
  if (!reason) return;

  try {
    const res = await fetch(`/api/admin/orders/${orderId}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason })
    });
    const data = await res.json();
    if (data.success) {
      showAdminToast(`Order #${orderId} cancelled.`, 'info');
      closeOrderDetail();
      fetchLiveFeed();
    } else {
      showAdminToast(data.error || 'Failed to cancel order', 'error');
    }
  } catch (err) {
    showAdminToast('Error cancelling order', 'error');
  }
}

// -------------------------------------------------------------
// ORDER DETAIL DRAWER & KITCHEN TICKET PRINTING
// -------------------------------------------------------------
function openOrderDetail(orderId) {
  const order = (AdminApp.liveFeedData?.orders || []).find(o => o.id === orderId);
  if (!order) return;

  const drawer = document.getElementById('orderDetailDrawer');
  const backdrop = document.getElementById('adminDrawerBackdrop');
  if (!drawer || !backdrop) return;

  document.getElementById('drawerOrderId').textContent = `#${order.id}`;
  document.getElementById('drawerOrderTable').textContent = `Table ${order.table_number}`;
  document.getElementById('drawerCustomerInfo').textContent = `${order.customer_name} (${order.customer_mobile || 'Walk-in'})`;
  document.getElementById('drawerOrderTime').textContent = new Date(order.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  document.getElementById('drawerOrderStatusPill').textContent = order.status;
  document.getElementById('drawerOrderStatusPill').className = `status-badge status-${order.status.toLowerCase()}`;

  // Items itemization
  const itemsList = document.getElementById('drawerItemsList');
  if (itemsList) {
    itemsList.innerHTML = (order.items || []).map(i => `
      <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #F0EEE9;">
        <div>
          <strong style="font-size:13px;">${i.quantity}x ${i.name}</strong>
          ${i.selected_options ? `<div style="font-size:11px;color:#78716C;">${i.selected_options.map(o => o.label || o.name).join(', ')}</div>` : ''}
        </div>
        <span style="font-family:var(--font-serif);font-size:1.15rem;font-weight:600;">₹${i.item_total || (i.unit_price * i.quantity)}</span>
      </div>
    `).join('');
  }

  // Financial summary
  document.getElementById('drawerSubtotal').textContent = `₹${order.subtotal || 0}`;
  document.getElementById('drawerTax').textContent = `₹${order.tax || 0}`;
  document.getElementById('drawerTotal').textContent = `₹${order.total || 0}`;

  // Timeline
  const timelineEl = document.getElementById('drawerTimeline');
  if (timelineEl) {
    timelineEl.innerHTML = (order.timeline || []).map(t => `
      <div class="timeline-item">
        <div class="timeline-dot">&bull;</div>
        <div>
          <strong style="font-size:12.5px;display:block;">${t.status}</strong>
          <span style="font-size:11px;color:#78716C;">${new Date(t.time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} &bull; by ${t.actor || 'System'}</span>
          ${t.notes ? `<p style="font-size:11.5px;color:#92400E;margin-top:2px;">${t.notes}</p>` : ''}
        </div>
      </div>
    `).join('');
  }

  // Setup buttons
  document.getElementById('drawerPrintBtn').onclick = () => printKitchenTicket(order);
  document.getElementById('drawerCancelBtn').onclick = () => cancelOrderWithReason(order.id);

  drawer.classList.add('active');
  backdrop.classList.add('active');
}

function closeOrderDetail() {
  const drawer = document.getElementById('orderDetailDrawer');
  const backdrop = document.getElementById('adminDrawerBackdrop');
  if (drawer) drawer.classList.remove('active');
  if (backdrop) backdrop.classList.remove('active');
}

function printKitchenTicket(order) {
  const printArea = document.getElementById('kitchenTicketPrintArea');
  if (!printArea) return;

  printArea.innerHTML = `
    <div style="text-align:center;border-bottom:2px dashed #000;padding-bottom:8px;margin-bottom:10px;">
      <h2 style="font-size:18px;margin:0 0 4px;font-weight:900;">AROMA CAFE</h2>
      <p style="font-size:11px;margin:0;">KITCHEN DISPATCH TICKET</p>
      <div style="font-size:22px;font-weight:900;margin:6px 0;">TABLE ${order.table_number}</div>
      <div style="font-size:12px;">ORDER #${order.id} &bull; ${new Date().toLocaleTimeString('en-IN')}</div>
    </div>

    <div style="margin-bottom:12px;">
      <div style="font-size:11px;">GUEST: <strong>${order.customer_name}</strong> (${order.customer_mobile || 'Walk-in'})</div>
    </div>

    <div style="border-bottom:2px dashed #000;padding-bottom:10px;margin-bottom:10px;">
      ${(order.items || []).map(i => `
        <div style="display:flex;justify-content:space-between;font-size:14px;font-weight:700;margin-bottom:4px;">
          <span>[ ] ${i.quantity} x ${i.name}</span>
        </div>
      `).join('')}
    </div>

    ${order.notes ? `
      <div style="background:#eee;padding:6px;font-size:12px;font-weight:bold;margin-bottom:10px;border:1px solid #000;">
        SPECIAL NOTE: ${order.notes}
      </div>
    ` : ''}

    <div style="text-align:center;font-size:10px;margin-top:14px;">
      *** EXPEDITE ON PASS ***
    </div>
  `;

  window.print();
}

// -------------------------------------------------------------
// TABLES FLOOR GRID & QR CODE DOWNLOAD
// -------------------------------------------------------------
function renderTables(tables = []) {
  const grid = document.getElementById('tablesFloorGrid');
  if (!grid) return;

  grid.innerHTML = tables.map(t => {
    const isTakeaway = String(t.number).toLowerCase() === 'takeaway';
    return `
      <div class="table-node status-${t.status}" onclick="handleTableClick('${t.number}')">
        <div class="table-header">
          <span class="table-num">${isTakeaway ? 'Takeaway' : `Table ${t.number}`}</span>
          <span class="table-status-pill status-${t.status}">${t.status.replace('_', ' ')}</span>
        </div>
        <div class="table-section-label">${t.section} &bull; ${t.capacity ? `${t.capacity} Seats` : 'Counter'}</div>
        ${t.active_order_id ? `
          <div style="margin-top:auto;padding-top:8px;border-top:1px dashed #E7E5E4;display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:11.5px;font-weight:600;color:var(--admin-gold);">Order #${t.active_order_id}</span>
            <button onclick="event.stopPropagation(); openOrderDetail('${t.active_order_id}')" class="action-btn-sm btn-secondary-action" style="padding:2px 8px;">View</button>
          </div>
        ` : `
          <div style="margin-top:auto;padding-top:8px;border-top:1px dashed #E7E5E4;display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:11px;color:#78716C;">No active ticket</span>
            <a href="/api/admin/tables/${t.number}/qrcode" download="table-${t.number}-qr.png" onclick="event.stopPropagation()" class="action-btn-sm btn-secondary-action" style="padding:2px 8px;text-decoration:none;">QR Code &darr;</a>
          </div>
        `}
      </div>
    `;
  }).join('');
}

function handleTableClick(tableNumber) {
  const table = (AdminApp.liveFeedData?.tables || []).find(t => String(t.number) === String(tableNumber));
  if (!table) return;

  if (table.active_order_id) {
    openOrderDetail(table.active_order_id);
    return;
  }

  // Table options: Toggle between free, needs_cleaning, reserved
  const nextStatus = table.status === 'free' ? 'needs_cleaning' : (table.status === 'needs_cleaning' ? 'free' : 'free');
  if (confirm(`Change status of Table ${table.number} to "${nextStatus}"?`)) {
    updateTableStatus(table.number, nextStatus);
  }
}

async function updateTableStatus(tableNumber, status) {
  try {
    const res = await fetch(`/api/admin/tables/${tableNumber}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    const data = await res.json();
    if (data.success) {
      showAdminToast(`Table ${tableNumber} marked as ${status}`, 'success');
      fetchLiveFeed();
    }
  } catch (e) {
    showAdminToast('Failed to update table status', 'error');
  }
}

// -------------------------------------------------------------
// MENU MANAGEMENT & 86 CONTROLS
// -------------------------------------------------------------
async function toggleItem86(itemId, isAvailable) {
  try {
    const res = await fetch(`/api/admin/menu/${itemId}/toggle-86`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ available: isAvailable })
    });
    const data = await res.json();
    if (data.success) {
      showAdminToast(data.message, 'info');
      // Update UI class immediately
      const card = document.getElementById(`menuCard-${itemId}`);
      if (card) card.classList.toggle('is-86', !isAvailable);
    }
  } catch (e) {
    showAdminToast('Failed to toggle item availability', 'error');
  }
}

async function bulkToggleMenu(makeAvailable) {
  const actionText = makeAvailable ? "Make ALL menu items AVAILABLE" : "86 (Deactivate) ALL menu items";
  if (!confirm(`Are you sure you want to ${actionText}?`)) return;

  try {
    const res = await fetch('/api/admin/menu/bulk-toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ available: makeAvailable })
    });
    const data = await res.json();
    if (data.success) {
      showAdminToast(data.message, 'success');
      setTimeout(() => window.location.reload(), 1000);
    }
  } catch (e) {
    showAdminToast('Failed to perform bulk toggle', 'error');
  }
}

// -------------------------------------------------------------
// RESERVATIONS MANAGEMENT
// -------------------------------------------------------------
function renderReservations(reservations = []) {
  const tbody = document.getElementById('reservationsTableBody');
  if (!tbody) return;

  if (reservations.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:32px;color:#78716C;">No reservations booked for today.</td></tr>`;
    return;
  }

  tbody.innerHTML = reservations.map(r => `
    <tr style="border-bottom:1px solid #F0EEE9;">
      <td style="padding:12px 16px;font-family:var(--font-mono);font-weight:600;">#${r.id}</td>
      <td style="padding:12px 16px;">
        <strong>${r.name}</strong>
        <span style="font-size:11px;color:#78716C;display:block;">${r.mobile}</span>
      </td>
      <td style="padding:12px 16px;">${r.party_size} Guests</td>
      <td style="padding:12px 16px;font-weight:600;color:var(--admin-gold);">${r.time} &bull; ${r.date}</td>
      <td style="padding:12px 16px;">${r.zone} (T${r.table_number || '--'})</td>
      <td style="padding:12px 16px;">
        <span class="status-badge status-${(r.status || 'confirmed').toLowerCase()}">${r.status || 'CONFIRMED'}</span>
      </td>
      <td style="padding:12px 16px;">
        <div style="display:flex;gap:6px;">
          ${r.status !== 'SEATED' ? `<button onclick="updateReservationStatus('${r.id}', 'SEATED')" class="action-btn-sm btn-primary-action" style="padding:4px 8px;">Seat</button>` : ''}
          ${r.status === 'CONFIRMED' ? `<button onclick="updateReservationStatus('${r.id}', 'NO_SHOW')" class="action-btn-sm btn-secondary-action" style="padding:4px 8px;">No Show</button>` : ''}
        </div>
      </td>
    </tr>
  `).join('');
}

async function updateReservationStatus(resId, status) {
  try {
    const res = await fetch(`/api/admin/reservations/${resId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    const data = await res.json();
    if (data.success) {
      showAdminToast(`Reservation #${resId} marked as ${status}`, 'success');
      fetchLiveFeed();
    }
  } catch (e) {
    showAdminToast('Failed to update reservation', 'error');
  }
}

// -------------------------------------------------------------
// CUSTOMERS DIRECTORY & HISTORY DRAWER (NO EMAIL)
// -------------------------------------------------------------
function renderCustomers(customers = []) {
  const tbody = document.getElementById('customersTableBody');
  if (!tbody) return;

  if (customers.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:32px;color:#78716C;">No customer accounts registered yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = customers.map(c => `
    <tr onclick="openCustomerDrawer('${c.mobile}')" style="cursor:pointer;border-bottom:1px solid #F0EEE9;">
      <td style="padding:12px 16px;font-weight:600;">${c.name}</td>
      <td style="padding:12px 16px;font-family:var(--font-mono);">${c.mobile}</td>
      <td style="padding:12px 16px;">${c.order_count || 0} Orders</td>
      <td style="padding:12px 16px;font-family:var(--font-serif);font-size:1.15rem;font-weight:700;color:var(--admin-gold);">₹${c.total_spend || 0}</td>
      <td style="padding:12px 16px;font-size:12px;color:#78716C;">${c.last_visit ? new Date(c.last_visit).toLocaleDateString('en-IN') : '--'}</td>
    </tr>
  `).join('');
}

function openCustomerDrawer(mobile) {
  const customer = (AdminApp.liveFeedData?.customers || []).find(c => c.mobile === mobile);
  if (!customer) return;

  const drawer = document.getElementById('customerDetailDrawer');
  const backdrop = document.getElementById('adminDrawerBackdrop');
  if (!drawer || !backdrop) return;

  document.getElementById('custDrawerName').textContent = customer.name;
  document.getElementById('custDrawerMobile').textContent = `+91 ${customer.mobile}`;
  document.getElementById('custDrawerSpend').textContent = `₹${customer.total_spend || 0}`;
  document.getElementById('custDrawerOrdersCount').textContent = customer.order_count || 0;

  // Filter orders for this customer
  const custOrders = (AdminApp.liveFeedData?.orders || []).filter(o => o.customer_mobile === mobile);
  const historyList = document.getElementById('custDrawerOrdersList');
  if (historyList) {
    if (custOrders.length === 0) {
      historyList.innerHTML = `<p style="color:#78716C;font-size:12.5px;padding:12px 0;">No previous orders recorded.</p>`;
    } else {
      historyList.innerHTML = custOrders.map(o => `
        <div onclick="openOrderDetail('${o.id}')" style="padding:10px 12px;border:1px solid #E7E5E4;border-radius:6px;margin-bottom:8px;cursor:pointer;background:#FAFAF9;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <strong>#${o.id} &bull; Table ${o.table_number}</strong>
            <span style="font-family:var(--font-serif);font-weight:700;">₹${o.total}</span>
          </div>
          <span style="font-size:11.5px;color:#78716C;">${new Date(o.created_at).toLocaleDateString('en-IN')} &bull; Status: ${o.status}</span>
        </div>
      `).join('');
    }
  }

  drawer.classList.add('active');
  backdrop.classList.add('active');
}

function closeCustomerDrawer() {
  const drawer = document.getElementById('customerDetailDrawer');
  const backdrop = document.getElementById('adminDrawerBackdrop');
  if (drawer) drawer.classList.remove('active');
  if (backdrop) backdrop.classList.remove('active');
}

// -------------------------------------------------------------
// SETTINGS & STAFF MANAGEMENT
// -------------------------------------------------------------
async function saveCafeSettings(e) {
  e.preventDefault();
  const opening_hours = document.getElementById('settingsOpeningHours').value;
  const gst_rate = parseFloat(document.getElementById('settingsGstRate').value);

  try {
    const res = await fetch('/api/admin/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ opening_hours, gst_rate })
    });
    const data = await res.json();
    if (data.success) {
      showAdminToast('Sanctuary settings updated successfully', 'success');
    }
  } catch (e) {
    showAdminToast('Failed to save settings', 'error');
  }
}

async function addStaffAccount(e) {
  e.preventDefault();
  const username = document.getElementById('newStaffUsername').value;
  const name = document.getElementById('newStaffName').value;
  const mobile = document.getElementById('newStaffMobile').value;
  const password = document.getElementById('newStaffPassword').value;
  const role = document.getElementById('newStaffRole').value;

  try {
    const res = await fetch('/api/admin/staff', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, name, mobile, password, role })
    });
    const data = await res.json();
    if (data.success) {
      showAdminToast(`Staff operator @${username} added.`, 'success');
      document.getElementById('addStaffModal')?.classList.add('hidden');
      fetchLiveFeed();
    } else {
      showAdminToast(data.error || 'Failed to add staff', 'error');
    }
  } catch (e) {
    showAdminToast('Error adding staff member', 'error');
  }
}

// -------------------------------------------------------------
// INITIALIZATION
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  initLiveClock();

  // Polling sound toggle
  const soundBtn = document.getElementById('soundToggleBtn');
  if (soundBtn) {
    soundBtn.onclick = () => {
      AdminApp.soundEnabled = !AdminApp.soundEnabled;
      soundBtn.classList.toggle('muted', !AdminApp.soundEnabled);
      showAdminToast(AdminApp.soundEnabled ? 'Chime sound enabled' : 'Chime sound muted', 'info');
    };
  }

  // Global search input
  const searchInput = document.getElementById('adminGlobalSearch');
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        AdminApp.searchQuery = e.target.value.trim();
        if (AdminApp.liveFeedData) {
          renderOrders(AdminApp.liveFeedData.orders);
        }
      }, 250);
    });

    // Keyboard shortcut '/' to search
    window.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement !== searchInput) {
        e.preventDefault();
        searchInput.focus();
      }
    });
  }

  // Live polling every 5 seconds
  fetchLiveFeed();
  AdminApp.pollTimer = setInterval(fetchLiveFeed, 5000);

  // Per-second elapsed timer update
  AdminApp.elapsedTimer = setInterval(() => {
    const cards = document.querySelectorAll('.order-card');
    cards.forEach(card => {
      const orderId = card.getAttribute('data-order-id');
      const order = (AdminApp.liveFeedData?.orders || []).find(o => o.id === orderId);
      if (order && order.created_at) {
        const orderDt = new Date(order.created_at);
        const elapsedMin = Math.floor((new Date() - orderDt) / 60000);
        order.elapsed_minutes = elapsedMin;
        const timerBadge = document.getElementById(`timer-${orderId}`);
        if (timerBadge) {
          timerBadge.textContent = `⏱ ${elapsedMin}m`;
          timerBadge.className = `timer-badge ${getTimerClass(elapsedMin)}`;
        }
      }
    });
  }, 1000);
});

