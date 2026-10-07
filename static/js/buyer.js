const API = '/api';

function getToken() {
    return localStorage.getItem('access_token');
}
function authHeaders() {
    return { 'Authorization': `Bearer ${getToken()}` };
}
function requireAuth() {
    if (!getToken()) window.location.href = '/login';
}
function logout() {
    localStorage.clear();
    window.location.href = '/login';
}
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toastMessage');
    if (!toast) return;
    toastMsg.textContent = message;
    toast.className = 'toast align-items-center text-white border-0 show';
    toast.classList.add(type === 'success' ? 'bg-success' : 'bg-danger');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 4000);
}
function fmtMoney(val) {
    const n = parseFloat(val);
    return isNaN(n) ? '0.00' : n.toFixed(2);
}
function phoneLinkHTML(phone, label = '📞') {
    if (!phone || phone.trim() === '') {
        return '<span style="color:#aaa;font-size:11px;">No phone</span>';
    }
    const clean = phone.replace(/[^0-9+]/g, '');
    return `<a href="tel:${clean}" style="color:#2E7D32;text-decoration:none;font-weight:600;font-size:12px;">${label} ${phone}</a>`;
}
const notifBellBtn = document.getElementById('notifBellBtn');
const notifPanel = document.getElementById('notifPanel');
const notifBadge = document.getElementById('notifBadge');
const notifList = document.getElementById('notifList');
function timeAgo(isoString) {
    const diffMs = Date.now() - new Date(isoString).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}
async function loadNotifications() {
    try {
        const res = await fetch(`${API}/notifications`, { headers: authHeaders() });
        if (!res.ok) return;
        const data = await res.json();
        if (data.unreadCount > 0) {
            notifBadge.textContent = data.unreadCount;
            notifBadge.style.display = 'inline-block';
        } else {
            notifBadge.style.display = 'none';
        }
        if (!data.notifications || data.notifications.length === 0) {
            notifList.innerHTML = '<div class="notif-empty">No notifications yet.</div>';
            return;
        }
        notifList.innerHTML = data.notifications.map(n => `
            <div class="notif-item ${n.isRead ? '' : 'unread'}">
                <div>${n.message}</div>
                <div class="notif-time">${timeAgo(n.timestamp)}</div>
            </div>
        `).join('');
    } catch (err) {
        notifList.innerHTML = '<div class="notif-empty">Error loading notifications.</div>';
    }
}
notifBellBtn?.addEventListener('click', async () => {
    const isOpening = !notifPanel.classList.contains('show');
    notifPanel.classList.toggle('show');
    if (isOpening) {
        await loadNotifications();
        fetch(`${API}/notifications/read-all`, { method: 'POST', headers: authHeaders() });
        notifBadge.style.display = 'none';
    }
});
document.addEventListener('click', (e) => {
    if (!e.target.closest('.notif-wrapper')) {
        notifPanel?.classList.remove('show');
    }
});
function cropImageHTML(cropType, height = '90px', photos = null) {
    const uploaded = (photos && photos.length > 0) ? photos[0] : null;
    if (uploaded) {
        return `<img src="${uploaded}" alt="${cropType}" style="width:100%; height:${height}; object-fit:cover; display:block;" 
                     onerror="this.parentElement.innerHTML='<div style=display:flex;flex-direction:column;align-items:center;justify-content:center;height:${height};background:#f5f5f5;color:#bbb;font-size:12px;border-radius:4px;><span style=font-size:24px;>🖼️</span><span style=margin-top:4px;>No Photo</span></div>'">`;
    }
    return `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:${height};background:#f8f9fa;color:#bbb;font-size:12px;border-radius:4px;border:1px solid #eee;">
        <span style="font-size:24px;">🖼️</span>
        <span style="margin-top:4px;">No Photo</span>
    </div>`;
}
function statusBadge(status) {
    const map = {
        'paid': 'status-paid', 'delivered': 'status-delivered',
        'pending': 'status-pending', 'disputed': 'status-disputed',
        'completed': 'status-completed', 'cancelled': 'status-cancelled'
    };
    const label = status.charAt(0).toUpperCase() + status.slice(1);
    return `<span class="status-badge ${map[status]||''}">${label}</span>`;
}
async function fetchListings(crop = '') {
    try {
        const url = crop ? `${API}/listings/active?crop_type=${encodeURIComponent(crop)}` : `${API}/listings/active`;
        const res = await fetch(url, { headers: authHeaders() });
        if (res.status === 401 || res.status === 403) { logout(); return []; }
        return await res.json();
    } catch { return []; }
}
async function fetchFlashSales() {
    try {
        const res = await fetch(`${API}/flash-sale/alerts`, { headers: authHeaders() });
        if (!res.ok) return [];
        return await res.json();
    } catch { return []; }
}
async function fetchOrders() {
    try {
        const res = await fetch(`${API}/orders`, { headers: authHeaders() });
        if (!res.ok) return [];
        return await res.json();
    } catch { return []; }
}
async function fetchMe() {
    try {
        const res = await fetch(`${API}/me`, { headers: authHeaders() });
        if (!res.ok) return null;
        return await res.json();
    } catch { return null; }
}
function renderFlashSales(items) {
    const c = document.getElementById('flashSaleContainer');
    if (!items || items.length === 0) {
        c.innerHTML = '<div class="text-muted" style="padding:10px;">No flash sales right now.</div>';
        return;
    }
    c.innerHTML = items.map(item => {
        const discount = item.originalPrice > 0 ? Math.round((1 - item.discountedPrice / item.originalPrice) * 100) : 0;
        return `
        <div class="flash-card">
            <div class="card-img">${cropImageHTML(item.cropType, '100px', item.photos)}</div>
            <div class="card-body">
                <div class="crop-name">${item.cropType}</div>
                <div class="price-discount">
                    <span class="price-current">Rs.${fmtMoney(item.discountedPrice)}</span>
                    ${item.originalPrice > item.discountedPrice ? `<span class="price-original">Rs.${fmtMoney(item.originalPrice)}</span>` : ''}
                    ${discount > 0 ? `<span class="discount-badge">-${discount}%</span>` : ''}
                </div>
                <div class="qty">Qty: ${item.quantity}kg</div>
                <div class="rating">⭐ ${item.farmerRating || 'N/A'}</div>
                <div style="margin:4px 0;">${phoneLinkHTML(item.farmerPhone)}</div>
                <button class="btn-buy-now" data-listing-id="${item.listingId}" data-crop="${item.cropType}" data-price="${item.discountedPrice}" data-qty="${item.quantity}" data-farmer="${item.farmerName || 'Unknown'}">Buy Now</button>
            </div>
        </div>`;
    }).join('');
    c.querySelectorAll('.btn-buy-now').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const listingId = this.dataset.listingId;
            const crop = this.dataset.crop;
            const price = parseFloat(this.dataset.price);
            const qty = parseInt(this.dataset.qty);
            const farmerName = this.dataset.farmer;
            openBuyModal(listingId, crop, price, qty, farmerName);
        });
    });
}
function renderListings(listings) {
    const c = document.getElementById('listingsContainer');
    const countEl = document.getElementById('listingsCount');
    if (!listings || listings.length === 0) {
        c.innerHTML = '<div class="text-muted">No active listings.</div>';
        if (countEl) countEl.textContent = '0';
        return;
    }
    if (countEl) countEl.textContent = `(${listings.length})`;
    c.innerHTML = listings.map(l => {
        const rating = l.farmerRating > 0 ? `⭐ ${l.farmerRating}` : '⭐ New';
        return `
        <div class="listing-card">
            <div class="card-img">${cropImageHTML(l.cropType, '90px', l.photos)}</div>
            <div class="card-body">
                <div class="crop-name">${l.cropType}</div>
                <div class="price">Rs.${fmtMoney(l.price)}/kg</div>
                <div class="stock">Stock: ${l.quantity}kg</div>
                <div class="rating">${rating}</div>
                <div style="font-size:11px;color:#666;margin:2px 0;">👨‍🌾 ${l.farmerName || 'Unknown'}</div>
                <div style="margin:4px 0;">${phoneLinkHTML(l.farmerPhone)}</div>
                <button class="btn-buy-now" data-listing-id="${l.listingId}" data-crop="${l.cropType}" data-price="${l.price}" data-qty="${l.quantity}" data-farmer="${l.farmerName || 'Unknown'}">Buy Now</button>
            </div>
        </div>`;
    }).join('');
    c.querySelectorAll('.btn-buy-now').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const listingId = this.dataset.listingId;
            const crop = this.dataset.crop;
            const price = parseFloat(this.dataset.price);
            const qty = parseInt(this.dataset.qty);
            const farmerName = this.dataset.farmer;
            openBuyModal(listingId, crop, price, qty, farmerName);
        });
    });
}
function renderRecentOrders(orders) {
    const c = document.getElementById('recentOrdersContainer');
    if (!orders || orders.length === 0) {
        c.innerHTML = '<div class="text-muted">No orders yet.</div>';
        return;
    }
    const recent = orders.slice(-3).reverse();
    c.innerHTML = recent.map(o => {
        let actionBtn = '';
        if (o.status === 'paid') {
            actionBtn = `
                <button class="btn-action-sm btn-confirm" data-order="${o.orderId}">✅ Confirm</button>
                <button class="btn-action-sm btn-dispute" data-order="${o.orderId}">⚠️ Dispute</button>`;
        } else if (o.status === 'delivered') {
            actionBtn = `<button class="btn-action-sm btn-rate" data-order="${o.orderId}">⭐ Rate</button>`;
        } else if (o.status === 'disputed') {
            actionBtn = `<button class="btn-action-sm btn-view" data-order="${o.orderId}">View Case</button>`;
        }
        return `
        <div class="order-item">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <span class="order-id">Order #${o.orderId}</span>
                    <span class="order-crop">${o.cropType || 'N/A'}</span>
                </div>
                ${statusBadge(o.status)}
            </div>
            <div style="font-size:11px;color:#666;margin-top:4px;">
                👨‍🌾 ${o.farmerName || 'Unknown'} &nbsp; ${phoneLinkHTML(o.farmerPhone)}
            </div>
            <div class="mt-1">
                ${actionBtn}
            </div>
        </div>`;
    }).join('');
    c.querySelectorAll('.btn-confirm').forEach(btn => {
        btn.addEventListener('click', () => confirmDelivery(btn.dataset.order));
    });
    c.querySelectorAll('.btn-dispute').forEach(btn => {
        btn.addEventListener('click', () => raiseDispute(btn.dataset.order));
    });
    c.querySelectorAll('.btn-rate').forEach(btn => {
        btn.addEventListener('click', () => rateFarmer(btn.dataset.order));
    });
    c.querySelectorAll('.btn-view').forEach(btn => {
        btn.addEventListener('click', () => showToast('Your dispute is under review by admin.', 'success'));
    });
}
function renderEscrow(orders) {
    const c = document.getElementById('escrowContainer');
    const escrows = orders.filter(o => o.escrow && o.escrow.status && ['held','released'].includes(o.escrow.status));
    if (escrows.length === 0) {
        c.innerHTML = '<div class="text-muted">No escrow records.</div>';
        return;
    }
    c.innerHTML = escrows.slice(-3).reverse().map(o => {
        const cls = o.escrow.status === 'released' ? 'escrow-released' : 'escrow-held';
        const label = o.escrow.status === 'released' ? 'RELEASED' : 'HELD';
        const date = new Date(o.orderDate).toLocaleDateString('en-PK', { day:'2-digit', month:'short' });
        return `
        <div class="escrow-item">
            <div>
                <div style="font-size:13px; font-weight:600;">Order #${o.orderId}</div>
                <div style="font-size:11px; color:#aaa;">${date}</div>
            </div>
            <div style="text-align:right;">
                <div class="escrow-amount">Rs. ${fmtMoney(o.escrow.amount)}</div>
                <div class="${cls}">${label}</div>
            </div>
        </div>`;
    }).join('');
}
function renderOrderHistory(orders) {
    const tbody = document.getElementById('orderHistoryBody');
    if (!orders || orders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-muted text-center">No orders yet.</td></tr>';
        return;
    }
    tbody.innerHTML = orders.map(o => {
        let actions = '';
        if (o.status === 'paid' || o.status === 'pending') {
            actions = `
                <button class="btn-action-sm btn-confirm" data-order="${o.orderId}">Confirm</button>
                <button class="btn-action-sm btn-dispute" data-order="${o.orderId}">Dispute</button>`;
        } else if (o.status === 'delivered') {
            actions = `<button class="btn-action-sm btn-rate" data-order="${o.orderId}">Rate</button>`;
        } else if (o.status === 'disputed') {
            actions = `<button class="btn-action-sm btn-view" data-order="${o.orderId}">View</button>`;
        } else {
            actions = `<span class="text-muted small">${o.status}</span>`;
        }
        const farmerCell = `
            <div>${o.farmerName || 'Unknown'}</div>
            <div style="margin-top:2px;">${phoneLinkHTML(o.farmerPhone)}</div>
        `;
        return `
        <tr>
            <td><strong>#${o.orderId}</strong></td>
            <td>${o.cropType || 'N/A'}</td>
            <td>${farmerCell}</td>
            <td>${o.quantity || '—'}</td>
            <td>Rs. ${fmtMoney(o.totalAmount)}</td>
            <td>${statusBadge(o.status)}</td>
            <td>${actions}</td>
        </tr>`;
    }).join('');
    tbody.querySelectorAll('.btn-confirm').forEach(btn => {
        btn.addEventListener('click', () => confirmDelivery(btn.dataset.order));
    });
    tbody.querySelectorAll('.btn-dispute').forEach(btn => {
        btn.addEventListener('click', () => raiseDispute(btn.dataset.order));
    });
    tbody.querySelectorAll('.btn-rate').forEach(btn => {
        btn.addEventListener('click', () => rateFarmer(btn.dataset.order));
    });
    tbody.querySelectorAll('.btn-view').forEach(btn => {
        btn.addEventListener('click', () => showToast('Your dispute is under review by admin.', 'success'));
    });
}
let _currentListing = null;
let buyModalInstance = null;
function openBuyModal(listingId, cropType, price, maxQty, farmerName) {
    _currentListing = { listingId, cropType, price, maxQty, farmerName };
    document.getElementById('modalListingInfo').innerHTML = `
        <div style="font-size:13px; color:#2E7D32; font-weight:600; margin-bottom:4px;">
            👨‍🌾 Farmer: ${farmerName || 'Unknown'}
        </div>
        <strong>${cropType}</strong> — Rs.${fmtMoney(price)}/kg<br>
        <span style="color:#888; font-size:12px;">Available: ${maxQty}kg</span>
    `;
    document.getElementById('modalQty').value = '';
    document.getElementById('modalTotal').textContent = `Total: Rs. 0`;
    if (!buyModalInstance) {
        buyModalInstance = new bootstrap.Modal(document.getElementById('buyModal'));
    }
    buyModalInstance.show();
}
document.getElementById('modalQty').addEventListener('input', function() {
    if (!_currentListing) return;
    const qty = parseFloat(this.value) || 0;
    const total = qty * _currentListing.price;
    document.getElementById('modalTotal').textContent = `Total: Rs. ${total.toFixed(2)}`;
});
document.getElementById('modalConfirmBtn').addEventListener('click', async function() {
    if (!_currentListing) return;
    const qty = parseFloat(document.getElementById('modalQty').value);
    if (!qty || qty <= 0) {
        showToast('Please enter a valid quantity.', 'error');
        return;
    }
    if (qty > _currentListing.maxQty) {
        showToast(`Max available: ${_currentListing.maxQty}kg`, 'error');
        return;
    }
    this.disabled = true;
    this.textContent = '⏳ Placing...';
    try {
        const res = await fetch(`${API}/orders`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders()
            },
            body: JSON.stringify({
                listing_id: _currentListing.listingId,
                quantity: qty
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Order failed');
        showToast(`✅ Order placed! Total: Rs.${fmtMoney(data.total)}. Escrow held.`, 'success');
        buyModalInstance.hide();
        await refreshAll();
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    } finally {
        this.disabled = false;
        this.textContent = '✅ Confirm Order';
    }
});
async function confirmDelivery(orderId) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async () => {
        if (!input.files[0]) return;
        const formData = new FormData();
        formData.append('photo', input.files[0]);
        try {
            const res = await fetch(`${API}/orders/${orderId}/confirm`, {
                method: 'POST',
                headers: authHeaders(),
                body: formData
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed');
            showToast('✅ Delivery confirmed! Escrow released.', 'success');
            await refreshAll();
        } catch (err) {
            showToast('❌ ' + err.message, 'error');
        }
    };
    input.click();
}
async function raiseDispute(orderId) {
    const reason = prompt('Please describe the issue:');
    if (!reason || !reason.trim()) return;
    try {
        const res = await fetch(`${API}/orders/${orderId}/dispute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders()
            },
            body: JSON.stringify({ reason: reason.trim() })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed');
        showToast('⚠️ Dispute raised. Admin will review.', 'success');
        await refreshAll();
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}
async function rateFarmer(orderId) {
    const score = prompt('Rate this farmer (1-5):');
    if (!score) return;
    const num = parseFloat(score);
    if (isNaN(num) || num < 1 || num > 5) {
        showToast('Please enter a score between 1 and 5.', 'error');
        return;
    }
    const comment = prompt('Add a comment (optional):') || '';
    try {
        const res = await fetch(`${API}/ratings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders()
            },
            body: JSON.stringify({
                order_id: orderId,
                score: num,
                comment
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed');
        showToast('⭐ Rating submitted! Order completed.', 'success');
        await refreshAll();
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}
async function addFunds() {
    const amountStr = prompt('Enter amount to add (Rs.):');
    if (!amountStr) return;
    const amount = parseFloat(amountStr);
    if (isNaN(amount) || amount <= 0) {
        showToast('Please enter a valid positive amount.', 'error');
        return;
    }
    try {
        const res = await fetch(`${API}/wallet/add-funds`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders()
            },
            body: JSON.stringify({ amount })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to add funds');
        showToast(`💰 ${data.message}`, 'success');
        document.getElementById('walletBalance').textContent = fmtMoney(data.newBalance);
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}
async function refreshAll() {
    const [listings, flashSales, orders] = await Promise.all([
        fetchListings(),
        fetchFlashSales(),
        fetchOrders()
    ]);
    renderFlashSales(flashSales);
    renderListings(listings);
    renderRecentOrders(orders);
    renderEscrow(orders);
    renderOrderHistory(orders);
}
export function initBuyerDashboard() {
    requireAuth();
    const role = localStorage.getItem('user_role');
    if (role && role !== 'buyer') {
        showToast('⚠️ This page is for buyers only.', 'error');
        setTimeout(() => window.location.href = '/login', 1500);
        return;
    }
    const name = localStorage.getItem('user_name') || 'Buyer';
    document.getElementById('buyerNameDisplay').textContent = name;
    fetchMe().then(user => {
        if (user) {
            document.getElementById('walletBalance').textContent = fmtMoney(user.walletBalance);
        }
    });
    document.getElementById('logoutBtn').addEventListener('click', logout);
    document.getElementById('searchBtn').addEventListener('click', async () => {
        const crop = document.getElementById('searchInput').value.trim();
        const listings = await fetchListings(crop);
        renderListings(listings);
    });
    document.getElementById('searchInput').addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            const crop = e.target.value.trim();
            const listings = await fetchListings(crop);
            renderListings(listings);
        }
    });
    const addFundsBtn = document.getElementById('addFundsBtn');
    if (addFundsBtn) {
        addFundsBtn.addEventListener('click', addFunds);
    }
    refreshAll();
    loadNotifications();
}