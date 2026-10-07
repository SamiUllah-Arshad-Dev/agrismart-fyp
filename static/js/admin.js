const API = '/api';

function getToken() { return localStorage.getItem('access_token'); }
function authHeaders() { return { 'Authorization': `Bearer ${getToken()}` }; }

function showToast(msg, type = 'success') {
    const t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'coop-toast show ' + type;
    setTimeout(() => t.className = 'coop-toast', 4000);
}

function fmtMoney(val) {
    const n = parseFloat(val);
    return isNaN(n) ? '0.00' : n.toFixed(2);
}

function prettyStatus(status) {
    return String(status || '')
        .toLowerCase()
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}

function cap(s) {
    return String(s || '').charAt(0).toUpperCase() + String(s || '').slice(1);
}

document.getElementById('logoutBtnAdmin')?.addEventListener('click', () => {
    localStorage.clear();
    window.location.href = '/login';
});

document.querySelectorAll('.admin-tab').forEach(tab => {
    tab.addEventListener('click', function() {
        document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.admin-tab-content').forEach(c => c.classList.remove('active'));
        this.classList.add('active');
        const tabName = this.dataset.tab;
        document.getElementById('tab-' + tabName).classList.add('active');
        if (tabName === 'users') loadPendingUsers();
        else if (tabName === 'disputes') loadDisputes();
        else if (tabName === 'flash') loadFlashSales();
        else if (tabName === 'offline') loadOfflineStatus();
    });
});

async function loadStats() {
    try {
        const res = await fetch(`${API}/admin/dashboard`, { headers: authHeaders() });
        if (res.status === 401 || res.status === 403) { window.location.href = '/login'; return; }
        const data = await res.json();
        document.getElementById('statOrders').textContent = data.total_orders || 0;
        document.getElementById('statDisputes').textContent = data.disputed_orders || 0;
        document.getElementById('statFlash').textContent = data.active_flash_sales || 0;
    } catch (e) { console.error('Stats error:', e); }
    loadUserStats();
}

async function loadUserStats() {
    try {
        const res = await fetch(`${API}/admin/users/stats`, { headers: authHeaders() });
        if (res.status === 401 || res.status === 403) { window.location.href = '/login'; return; }
        const data = await res.json();
        document.getElementById('statTotalUsers').textContent = data.total || 0;
        document.getElementById('statVerified').textContent = data.verified || 0;
        document.getElementById('statUnverified').textContent = data.unverified || 0;
    } catch (e) {
        console.error('User stats error:', e);
        document.getElementById('statTotalUsers').textContent = '?';
    }
}

document.getElementById('userSearchInput')?.addEventListener('input', async function() {
    const query = this.value.trim();
    const resultsDiv = document.getElementById('searchResults');
    if (query.length < 2) {
        resultsDiv.innerHTML = '';
        return;
    }
    try {
        const res = await fetch(`${API}/admin/users/search?q=${encodeURIComponent(query)}`, {
            headers: authHeaders()
        });
        if (res.status === 401 || res.status === 403) { window.location.href = '/login'; return; }
        const data = await res.json();
        if (data.length === 0) {
            resultsDiv.innerHTML = '<p style="color:#999; margin:8px 0;">No users found.</p>';
            return;
        }
        let html = `<table>
            <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>CNIC</th><th>Role</th><th>Status</th></tr></thead><tbody>`;
        data.forEach(u => {
            const status = u.isVerified ? '✅ Verified' : '⏳ Pending';
            html += `<tr>
                <td>${u.userId}</td>
                <td>${u.name}</td>
                <td>${u.email}</td>
                <td>${u.cnic}</td>
                <td>${cap(u.role)}</td>
                <td>${status}</td>
            </tr>`;
        });
        resultsDiv.innerHTML = html + '</tbody></table>';
    } catch (e) {
        console.error('Search error:', e);
        resultsDiv.innerHTML = '<p style="color:red;">Network error while searching.</p>';
    }
});

async function loadPendingUsers() {
    try {
        const res = await fetch(`${API}/admin/users/pending`, { headers: authHeaders() });
        const data = await res.json();
        const container = document.getElementById('pendingUsersContainer');
        if (!data || data.length === 0) {
            container.innerHTML = '<p style="color:#999;">No pending users.</p>';
            return;
        }
        let html = `<table class="admin-table">
            <thead><tr><th>Name</th><th>Email</th><th>CNIC</th><th>Role</th><th>Action</th></tr></thead><tbody>`;
        data.forEach(u => {
            html += `<tr>
                <td>${u.name}</td>
                <td>${u.email}</td>
                <td>${u.cnic}</td>
                <td>${cap(u.role)}</td>
                <td><button class="btn-verify" data-id="${u.userId}">Verify</button></td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
        container.querySelectorAll('.btn-verify').forEach(btn => {
            btn.addEventListener('click', async function() {
                const userId = this.dataset.id;
                try {
                    const res = await fetch(`${API}/admin/verify/${userId}`, {
                        method: 'POST',
                        headers: authHeaders()
                    });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(data.message || 'User verified!', 'success');
                        loadPendingUsers();
                        loadStats();
                    } else {
                        showToast('Error: ' + (data.error || 'Failed'), 'error');
                    }
                } catch (e) {
                    showToast('Network error', 'error');
                }
            });
        });
    } catch (e) {
        document.getElementById('pendingUsersContainer').innerHTML = '<p style="color:red;">Error loading users.</p>';
    }
}

async function loadDisputes() {
    try {
        const res = await fetch(`${API}/admin/disputes`, { headers: authHeaders() });
        const data = await res.json();
        const container = document.getElementById('disputesContainer');
        if (!data || data.length === 0) {
            container.innerHTML = '<p style="color:#999;">No disputes.</p>';
            return;
        }
        let html = `<table class="admin-table">
            <thead><tr><th>Order ID</th><th>Amount</th><th>Action</th></tr></thead><tbody>`;
        data.forEach(d => {
            html += `<tr>
                <td>#${d.orderId}</td>
                <td>Rs. ${fmtMoney(d.amount)}</td>
                <td>
                    <select id="action_${d.orderId}">
                        <option value="release">Release</option>
                        <option value="hold">Hold</option>
                        <option value="cancel_refund">Cancel/Refund</option>
                    </select>
                    <button class="btn-resolve" data-id="${d.orderId}">Resolve</button>
                </td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
        container.querySelectorAll('.btn-resolve').forEach(btn => {
            btn.addEventListener('click', async function() {
                const orderId = this.dataset.id;
                const action = document.getElementById(`action_${orderId}`).value;
                try {
                    const res = await fetch(`${API}/admin/disputes/${orderId}/resolve`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', ...authHeaders() },
                        body: JSON.stringify({ action })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(data.message || 'Dispute resolved!', 'success');
                        loadDisputes();
                        loadStats();
                    } else {
                        showToast('Error: ' + (data.error || 'Failed'), 'error');
                    }
                } catch (e) {
                    showToast('Network error', 'error');
                }
            });
        });
    } catch (e) {
        document.getElementById('disputesContainer').innerHTML = '<p style="color:red;">Error loading disputes.</p>';
    }
}

async function loadFlashSales() {
    try {
        const res = await fetch(`${API}/admin/flash-sales`, { headers: authHeaders() });
        const data = await res.json();
        const container = document.getElementById('flashSalesContainer');
        if (!data || data.length === 0) {
            container.innerHTML = '<p style="color:#999;">No active flash sales.</p>';
            return;
        }
        let html = `<table class="admin-table">
            <thead><tr><th>Crop</th><th>Discounted Price</th><th>Action</th></tr></thead><tbody>`;
        data.forEach(f => {
            html += `<tr>
                <td>${prettyStatus(f.cropType)}</td>
                <td>Rs. ${fmtMoney(f.discountedPrice)}</td>
                <td><button class="btn-override" data-id="${f.flashSaleId}">Override</button></td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
        container.querySelectorAll('.btn-override').forEach(btn => {
            btn.addEventListener('click', async function() {
                const flashId = this.dataset.id;
                try {
                    const res = await fetch(`${API}/admin/flash-sales/${flashId}/override`, {
                        method: 'POST',
                        headers: authHeaders()
                    });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(data.message || 'Flash sale overridden!', 'success');
                        loadFlashSales();
                        loadStats();
                    } else {
                        showToast('Error: ' + (data.error || 'Failed'), 'error');
                    }
                } catch (e) {
                    showToast('Network error', 'error');
                }
            });
        });
    } catch (e) {
        document.getElementById('flashSalesContainer').innerHTML = '<p style="color:red;">Error loading flash sales.</p>';
    }
}

async function loadOfflineStatus() {
    try {
        const res = await fetch(`${API}/admin/offline-mode/status`, { headers: authHeaders() });
        const data = await res.json();
        document.getElementById('offlineStatusText').textContent = data.offline_mode ? 'Offline' : 'Online';
    } catch (e) {
        console.error('Offline status error:', e);
    }
}

document.getElementById('toggleOfflineBtn')?.addEventListener('click', async function() {
    const current = document.getElementById('offlineStatusText').textContent === 'Online' ? false : true;
    try {
        const res = await fetch(`${API}/admin/offline-mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...authHeaders() },
            body: JSON.stringify({ enable: !current })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message || 'Offline mode toggled!', 'success');
            loadOfflineStatus();
        } else {
            showToast('Error: ' + (data.error || 'Failed'), 'error');
        }
    } catch (e) {
        showToast('Network error', 'error');
    }
});

function loadDetails(type) {
    const section = document.getElementById('detailsSection');
    const title = document.getElementById('detailsTitle');
    const content = document.getElementById('detailsContent');
    if (!section) {
        console.warn('detailsSection element not found.');
        return;
    }
    section.style.display = 'block';

    if (type === 'users') {
        title.innerText = '👥 All Users';
        fetch(`${API}/admin/users/all`, { headers: authHeaders() })
            .then(r => {
                if (r.status === 401 || r.status === 403) { window.location.href = '/login'; return; }
                return r.json();
            })
            .then(data => {
                if (!data || data.error) {
                    content.innerHTML = '<p style="color:red;">' + (data?.error || 'Failed to load users.') + '</p>';
                    return;
                }
                let html = `<table class="admin-table">
                    <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Verified</th></tr></thead><tbody>`;
                data.forEach(u => {
                    html += `<tr><td>${u.userId}</td><td>${u.name}</td><td>${u.email}</td><td>${cap(u.role)}</td><td>${u.verified ? '✅' : '⏳'}</td></tr>`;
                });
                content.innerHTML = html + '</tbody></table>';
            })
            .catch(() => { content.innerHTML = '<p style="color:red;">Network error loading users.</p>'; });
    }
    else if (type === 'orders') {
        title.innerText = '📦 All Orders';
        fetch(`${API}/admin/orders/all`, { headers: authHeaders() })
            .then(r => {
                if (r.status === 401 || r.status === 403) { window.location.href = '/login'; return; }
                return r.json();
            })
            .then(data => {
                if (!data || data.error) {
                    content.innerHTML = '<p style="color:red;">' + (data?.error || 'Failed to load orders.') + '</p>';
                    return;
                }
                let html = `<table class="admin-table">
                    <thead><tr><th>Order ID</th><th>Buyer</th><th>Crop</th><th>Total</th><th>Status</th></tr></thead><tbody>`;
                data.forEach(o => {
                    html += `<tr><td>#${o.orderId}</td><td>${o.buyer}</td><td>${prettyStatus(o.crop)}</td><td>Rs. ${fmtMoney(o.total)}</td><td>${prettyStatus(o.status)}</td></tr>`;
                });
                content.innerHTML = html + '</tbody></table>';
            })
            .catch(() => { content.innerHTML = '<p style="color:red;">Network error loading orders.</p>'; });
    }
    else if (type === 'disputes') {
        title.innerText = '⚖️ All Disputes';
        fetch(`${API}/admin/disputes`, { headers: authHeaders() })
            .then(r => {
                if (r.status === 401 || r.status === 403) { window.location.href = '/login'; return; }
                return r.json();
            })
            .then(data => {
                if (!data || data.error) {
                    content.innerHTML = '<p style="color:red;">' + (data?.error || 'Failed to load disputes.') + '</p>';
                    return;
                }
                let html = `<table class="admin-table">
                    <thead><tr><th>Order</th><th>Buyer</th><th>Farmer</th><th>Amount</th><th>Status</th></tr></thead><tbody>`;
                data.forEach(d => {
                    html += `<tr><td>#${d.orderId}</td><td>${d.buyerName}</td><td>${d.farmerName}</td><td>Rs. ${fmtMoney(d.amount)}</td><td>${prettyStatus(d.orderStatus)}</td></tr>`;
                });
                content.innerHTML = html + '</tbody></table>';
            })
            .catch(() => { content.innerHTML = '<p style="color:red;">Network error loading disputes.</p>'; });
    }
}

function loadFilteredUsers(type) {
    const section = document.getElementById('detailsSection');
    const title = document.getElementById('detailsTitle');
    const content = document.getElementById('detailsContent');
    if (!section) {
        console.warn('detailsSection element not found.');
        return;
    }
    section.style.display = 'block';
    fetch(`${API}/admin/users/all`, { headers: authHeaders() })
        .then(r => {
            if (r.status === 401 || r.status === 403) { window.location.href = '/login'; return; }
            return r.json();
        })
        .then(data => {
            if (!data || data.error) {
                content.innerHTML = '<p style="color:red;">' + (data?.error || 'Failed to load users.') + '</p>';
                return;
            }
            let filteredData = [];
            let titleText = '';
            if (type === 'verified') {
                filteredData = data.filter(u => u.verified === true);
                titleText = '✅ Verified Users';
            } else if (type === 'unverified') {
                filteredData = data.filter(u => u.verified === false);
                titleText = '⏳ Unverified Users (Pending)';
            }
            if (filteredData.length === 0) {
                content.innerHTML = `<p style="color:#999;">No ${type} users found.</p>`;
                return;
            }
            title.innerText = titleText;
            let html = `<table class="admin-table">
                <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Status</th></tr></thead><tbody>`;
            filteredData.forEach(u => {
                const status = u.verified ? '✅ Verified' : '⏳ Pending';
                html += `<tr><td>${u.userId}</td><td>${u.name}</td><td>${u.email}</td><td>${cap(u.role)}</td><td>${status}</td></tr>`;
            });
            content.innerHTML = html + '</tbody></table>';
        })
        .catch(() => { content.innerHTML = '<p style="color:red;">Network error loading users.</p>'; });
}

document.addEventListener('DOMContentLoaded', () => {
    if (!getToken()) {
        window.location.href = '/login';
        return;
    }
    const role = localStorage.getItem('user_role');
    if (role && role !== 'admin') {
        showToast('⚠️ This page is for admins only.', 'error');
        setTimeout(() => window.location.href = '/login', 1500);
        return;
    }
    loadStats();
    loadPendingUsers();
});