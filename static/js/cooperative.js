const API = '/api';

let farmersData = [];

function getToken() {
    return localStorage.getItem('access_token');
}

function authHeaders() {
    return {
        'Authorization': `Bearer ${getToken()}`
    };
}

function showToast(msg, type = 'success') {
    const t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'coop-toast show ' + type;
    setTimeout(() => {
        t.className = 'coop-toast';
    }, 4000);
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

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
}

function cap(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function phoneLinkHTML(phone) {
    if (!phone || phone.trim() === '') {
        return '<span style="color:#aaa;font-size:11px;">No phone</span>';
    }
    const clean = phone.replace(/[^0-9+]/g, '');
    return `<a href="tel:${clean}" style="color:#2E7D32;text-decoration:none;font-weight:600;font-size:12px;">📞 ${phone}</a>`;
}

function stockText(stock) {
    const items = Object.entries(stock || {})
        .map(([c, q]) => `${cap(c)}: ${fmtMoney(q)}kg`);
    return items.length
        ? items.join(', ')
        : 'No active stock';
}

document.getElementById('logoutBtnCoop')?.addEventListener('click', () => {
    localStorage.clear();
    window.location.href = '/login';
});

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
    const notifList = document.getElementById('notifList');
    const notifBadge = document.getElementById('notifBadge');
    if (!notifList) return;
    try {
        const res = await fetch(`${API}/notifications`, {
            headers: authHeaders()
        });
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
                <div>${esc(n.message)}</div>
                <div class="notif-time">${timeAgo(n.timestamp)}</div>
            </div>
        `).join('');
    } catch (err) {
        notifList.innerHTML = '<div class="notif-empty">Error loading notifications.</div>';
    }
}

document.getElementById('notifBellBtn')?.addEventListener('click', async () => {
    const notifPanel = document.getElementById('notifPanel');
    const notifBadge = document.getElementById('notifBadge');
    if (!notifPanel) return;
    const isOpening = !notifPanel.classList.contains('show');
    notifPanel.classList.toggle('show');
    if (isOpening) {
        await loadNotifications();
        fetch(`${API}/notifications/read-all`, {
            method: 'POST',
            headers: authHeaders()
        });
        if (notifBadge) notifBadge.style.display = 'none';
    }
});

document.addEventListener('click', (e) => {
    if (!e.target.closest('.notif-wrapper')) {
        document.getElementById('notifPanel')?.classList.remove('show');
    }
});

function getSelectedFarmers() {
    const ids = Array.from(
        document.querySelectorAll(
            '.coop-farmer-option input[type="checkbox"]:checked'
        )
    ).map(cb => parseInt(cb.value));
    return farmersData.filter(f => ids.includes(f.farmerId));
}

function refreshCropOptions() {
    const sel = document.getElementById('cropType');
    if (!sel) return;
    const prev = sel.value;
    const selected = getSelectedFarmers();
    let common = null;
    selected.forEach(f => {
        const crops = Object.keys(f.stock || {});
        common = common === null
            ? crops
            : common.filter(c => crops.includes(c));
    });
    common = common || [];
    sel.innerHTML =
        '<option value="">-- Select crop --</option>' +
        common.map(
            c => `<option value="${esc(c)}">${esc(cap(c))}</option>`
        ).join('');
    if (common.includes(prev)) {
        sel.value = prev;
    }
    if (selected.length > 0 && common.length === 0) {
        showToast('Selected farmers have no crop in common.', 'error');
    }
}

async function loadFarmers() {
    const grid = document.getElementById('farmerGrid');
    if (!grid) return;
    try {
        const res = await fetch(
            `${API}/cooperative/farmers`,
            { headers: authHeaders() }
        );
        if (res.status === 401 || res.status === 403) {
            window.location.href = '/login';
            return;
        }
        const data = await res.json();
        if (!Array.isArray(data) || data.length === 0) {
            grid.innerHTML =
                '<p style="grid-column:1/-1; color:#999; text-align:center;">' +
                'No farmers available.' +
                '</p>';
            return;
        }
        farmersData = data;
        grid.innerHTML = '';
        data.forEach(f => {
            const hasStock = Object.keys(f.stock || {}).length > 0;
            const label = document.createElement('label');
            label.className = 'coop-farmer-option unchecked';
            label.innerHTML = `
                <input
                    type="checkbox"
                    value="${f.farmerId}"
                    ${hasStock ? '' : 'disabled'}
                >
                <span>
                    ${esc(f.name)}
                    (${esc(f.location || 'Punjab')})
                    <small class="coop-stock ${hasStock ? '' : 'none'}">
                        ${esc(stockText(f.stock))}
                    </small>
                </span>
            `;
            const cb = label.querySelector('input[type="checkbox"]');
            cb.addEventListener('change', function () {
                label.classList.toggle('checked', this.checked);
                label.classList.toggle('unchecked', !this.checked);
                refreshCropOptions();
                updatePreview();
            });
            grid.appendChild(label);
        });
        refreshCropOptions();
        updatePreview();
    } catch (e) {
        console.error('Error loading farmers:', e);
        grid.innerHTML =
            '<p style="color:red; grid-column:1/-1;">' +
            'Error loading farmers.' +
            '</p>';
    }
}

function updatePreview() {
    const container = document.getElementById('previewContainer');
    if (!container) return;
    const selected = getSelectedFarmers();
    const crop = document.getElementById('cropType')?.value;
    const totalQty = parseFloat(
        document.getElementById('totalQty')?.value
    ) || 0;
    if (selected.length === 0 || !crop) {
        container.innerHTML =
            '<p style="color:#999; text-align:center;">' +
            'Select farmers and a crop to see preview.' +
            '</p>';
        return;
    }
    const totalAvail = selected.reduce(
        (sum, f) => sum + (f.stock[crop] || 0), 0
    );
    let html = `
        <p class="coop-avail">
            <b>
                Total available (${esc(cap(crop))}):
                ${fmtMoney(totalAvail)} kg
            </b>
        </p>
    `;
    if (totalQty > totalAvail) {
        html += `
            <p class="coop-warn">
                Requested quantity is more than the available stock.
            </p>
        `;
    }
    html += `
        <table class="coop-table">
            <thead>
                <tr>
                    <th>Farmer</th>
                    <th>Available (kg)</th>
                    <th>Contribution (kg)</th>
                </tr>
            </thead>
            <tbody>
    `;
    selected.forEach(f => {
        const avail = f.stock[crop] || 0;
        const share = (totalQty > 0 && totalAvail > 0)
            ? ((avail / totalAvail) * totalQty).toFixed(1) + ' kg'
            : '—';
        html += `
            <tr>
                <td>${esc(f.name)}</td>
                <td>${fmtMoney(avail)}</td>
                <td class="qty-highlight">${share}</td>
            </tr>
        `;
    });
    html += `</tbody></table>`;
    container.innerHTML = html;
}

async function loadMyListings() {
    const container = document.getElementById('myListingsContainer');
    if (!container) return;
    try {
        const res = await fetch(
            `${API}/cooperative/combined-listings`,
            { headers: authHeaders() }
        );
        if (res.status === 401 || res.status === 403) {
            window.location.href = '/login';
            return;
        }
        const data = await res.json();
        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML =
                '<p style="color:#9ca3af; text-align:center;">' +
                'No combined listings yet.' +
                '</p>';
            return;
        }
        let html = `
            <table class="coop-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Crop</th>
                        <th>Total Qty</th>
                        <th>Price/kg</th>
                        <th>Expiry</th>
                        <th>Status</th>
                        <th>Farmers</th>
                    </tr>
                </thead>
                <tbody>
        `;
        data.forEach(cl => {
            const farmerNames = cl.farmers
                .map(f => `${esc(f.name)} (${fmtMoney(f.contribution)}kg)`)
                .join(', ');
            const expiry = cl.shelfLife
                ? cl.shelfLife.split('T')[0]
                : 'N/A';
            html += `
                <tr>
                    <td>#${cl.combinedListingId}</td>
                    <td>${esc(cl.cropType)}</td>
                    <td>${fmtMoney(cl.totalQuantity)} kg</td>
                    <td>Rs. ${fmtMoney(cl.price)}</td>
                    <td>${esc(expiry)}</td>
                    <td>${esc(prettyStatus(cl.status))}</td>
                    <td>${farmerNames || '—'}</td>
                </tr>
            `;
        });
        html += `</tbody></table>`;
        container.innerHTML = html;
    } catch (e) {
        console.error('Error loading combined listings:', e);
        container.innerHTML =
            '<p style="color:red; text-align:center;">' +
            'Error loading your listings.' +
            '</p>';
    }
}

async function loadCooperativeOrders() {
    const container = document.getElementById('coopOrdersContainer');
    if (!container) return;
    try {
        const res = await fetch(
            `${API}/cooperative/orders`,
            { headers: authHeaders() }
        );
        if (res.status === 401 || res.status === 403) {
            window.location.href = '/login';
            return;
        }
        const data = await res.json();
        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML =
                '<p style="color:#9ca3af; text-align:center;">' +
                'No orders yet.' +
                '</p>';
            return;
        }
        let html = `
            <table class="coop-table">
                <thead>
                    <tr>
                        <th>Order</th>
                        <th>Crop</th>
                        <th>Qty</th>
                        <th>Amount</th>
                        <th>Buyer</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
        `;
        data.forEach(o => {
            const buyerCell = `
                <div>${esc(o.buyerName)}</div>
                <div style="margin-top:2px;">${phoneLinkHTML(o.buyerPhone)}</div>
            `;
            html += `
                <tr>
                    <td>#${o.orderId}</td>
                    <td>${esc(o.cropType)}</td>
                    <td>${fmtMoney(o.quantity)} kg</td>
                    <td>Rs. ${fmtMoney(o.totalAmount)}</td>
                    <td>${buyerCell}</td>
                    <td>${esc(prettyStatus(o.status))}</td>
                </tr>
            `;
        });
        html += `</tbody></table>`;
        container.innerHTML = html;
    } catch (e) {
        console.error('Error loading cooperative orders:', e);
        container.innerHTML =
            '<p style="color:red; text-align:center;">' +
            'Error loading orders.' +
            '</p>';
    }
}

document
    .getElementById('submitBtn')
    ?.addEventListener('click', async function () {
        const selected = getSelectedFarmers();
        if (selected.length === 0) {
            showToast('Select at least one farmer.', 'error');
            return;
        }
        const farmer_ids = selected.map(f => f.farmerId);
        const cropType = document.getElementById('cropType').value;
        const totalQty = parseFloat(
            document.getElementById('totalQty').value
        );
        const price = parseFloat(
            document.getElementById('pricePerKg').value
        );
        const expiryDate = document.getElementById('expiryDate').value;
        if (!cropType) {
            showToast('Select a crop type.', 'error');
            return;
        }
        if (!totalQty || totalQty <= 0) {
            showToast('Enter a valid total quantity.', 'error');
            return;
        }
        if (!price || price <= 0) {
            showToast('Enter a valid price per kg.', 'error');
            return;
        }
        if (!expiryDate) {
            showToast('Please select an expiry date.', 'error');
            return;
        }
        const today = new Date().toISOString().split('T')[0];
        if (expiryDate < today) {
            showToast('Expiry date cannot be in the past.', 'error');
            return;
        }
        const totalAvail = selected.reduce(
            (sum, f) => sum + (f.stock[cropType] || 0), 0
        );
        if (totalQty > totalAvail) {
            showToast(
                `Only ${fmtMoney(totalAvail)} kg available for this crop.`,
                'error'
            );
            return;
        }
        this.disabled = true;
        this.textContent = 'Creating...';
        try {
            const res = await fetch(
                `${API}/cooperative/combined-listing`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...authHeaders()
                    },
                    body: JSON.stringify({
                        farmer_ids: farmer_ids,
                        crop_type: cropType,
                        total_quantity: totalQty,
                        price_per_kg: price,
                        expiry_date: expiryDate
                    })
                }
            );
            const data = await res.json();
            if (res.ok) {
                showToast(
                    `✅ Combined listing created! ID: ${data.combinedListingId}`,
                    'success'
                );
                document.getElementById('totalQty').value = '';
                document.getElementById('pricePerKg').value = '';
                document.getElementById('expiryDate').value = '';
                document
                    .querySelectorAll(
                        '.coop-farmer-option input[type="checkbox"]'
                    )
                    .forEach(cb => {
                        cb.checked = false;
                        const opt = cb.closest('.coop-farmer-option');
                        opt.classList.remove('checked');
                        opt.classList.add('unchecked');
                    });
                refreshCropOptions();
                updatePreview();
                loadFarmers();
                loadMyListings();
            } else {
                showToast(
                    '❌ ' + (data.error || 'Failed'),
                    'error'
                );
            }
        } catch (e) {
            console.error('Create combined listing error:', e);
            showToast('❌ Network error', 'error');
        } finally {
            this.disabled = false;
            this.textContent = '🚜 Create Combined Listing';
        }
    });

document
    .getElementById('totalQty')
    ?.addEventListener('input', updatePreview);

document
    .getElementById('cropType')
    ?.addEventListener('change', updatePreview);

function createFlashSaleSection() {
    if (document.getElementById('coopFlashSaleSection')) {
        return;
    }
    const mainCard = document.querySelector('.coop-card');
    if (!mainCard) {
        return;
    }
    const section = document.createElement('div');
    section.id = 'coopFlashSaleSection';
    section.innerHTML = `
        <h2 class="coop-section-title">
            🔥 Flash Sale Alerts
        </h2>
        <div id="coopFlashSaleContainer">
            <p style="color:#9ca3af; text-align:center;">
                Loading flash sale alerts...
            </p>
        </div>
    `;
    const footerNote = mainCard.querySelector('.coop-footer-note');
    if (footerNote) {
        mainCard.insertBefore(section, footerNote);
    } else {
        mainCard.appendChild(section);
    }
}

async function loadCooperativeFlashSales() {
    const container = document.getElementById('coopFlashSaleContainer');
    if (!container) {
        return;
    }
    try {
        const res = await fetch(
            `${API}/cooperative/flash-sale/my-alerts`,
            { headers: authHeaders() }
        );
        if (res.status === 401 || res.status === 403) {
            window.location.href = '/login';
            return;
        }
        const data = await res.json();
        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML = `
                <p style="color:#9ca3af; text-align:center; padding:15px;">
                    No active flash sale alerts.
                </p>
            `;
            return;
        }
        let html = '';
        data.forEach(fs => {
            const expiry = fs.expiryDate
                ? fs.expiryDate.split('T')[0]
                : 'N/A';
            html += `
                <div style="
                    border:1px solid #f59e0b;
                    border-radius:10px;
                    padding:18px;
                    margin-bottom:14px;
                    background:#fffbeb;
                ">
                    <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                        gap:10px;
                        flex-wrap:wrap;
                    ">
                        <h3 style="margin:0; color:#92400e;">
                            🔥 ${esc(fs.cropType)}
                        </h3>
                        <span style="font-weight:600; color:#92400e;">
                            ${esc(prettyStatus(fs.status))}
                        </span>
                    </div>
                    <p style="margin:10px 0 5px;">
                        <b>Quantity:</b> ${fmtMoney(fs.quantity)} kg
                    </p>
                    <p style="margin:5px 0;">
                        <b>Original Price:</b> Rs. ${fmtMoney(fs.originalPrice)}/kg
                    </p>
                    <p style="margin:5px 0; color:#15803d; font-weight:700;">
                        <b>Flash Sale Price:</b> Rs. ${fmtMoney(fs.discountedPrice)}/kg
                    </p>
                    <p style="margin:5px 0;">
                        <b>Expiry:</b> ${esc(expiry)}
                    </p>
                    <p style="margin:8px 0; font-size:13px; color:#6b7280;">
                        This flash sale is for your cooperative listing.
                    </p>
                    <div style="
                        display:flex;
                        gap:10px;
                        margin-top:15px;
                        flex-wrap:wrap;
                    ">
                        <button
                            type="button"
                            class="coop-submit-btn"
                            onclick="respondCooperativeFlashSale(
                                ${fs.listingId},
                                true
                            )"
                        >
                            ✓ Accept Flash Sale
                        </button>
                        <button
                            type="button"
                            onclick="respondCooperativeFlashSale(
                                ${fs.listingId},
                                false
                            )"
                            style="
                                padding:10px 16px;
                                border:none;
                                border-radius:7px;
                                background:#dc2626;
                                color:white;
                                cursor:pointer;
                                font-weight:600;
                            "
                        >
                            ✕ Decline
                        </button>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    } catch (e) {
        console.error('Error loading cooperative flash sales:', e);
        container.innerHTML = `
            <p style="color:red; text-align:center;">
                Error loading flash sale alerts.
            </p>
        `;
    }
}

async function respondCooperativeFlashSale(listingId, accept) {
    try {
        const res = await fetch(
            `${API}/cooperative/flash-sale/respond`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...authHeaders()
                },
                body: JSON.stringify({
                    listing_id: listingId,
                    accept: accept
                })
            }
        );
        const data = await res.json();
        if (res.status === 401 || res.status === 403) {
            window.location.href = '/login';
            return;
        }
        if (res.ok) {
            showToast(
                data.message || (
                    accept
                        ? 'Flash sale accepted.'
                        : 'Flash sale declined.'
                ),
                'success'
            );
            loadCooperativeFlashSales();
            loadMyListings();
        } else {
            showToast(
                '❌ ' + (data.error || 'Flash sale response failed.'),
                'error'
            );
        }
    } catch (e) {
        console.error('Cooperative flash sale response error:', e);
        showToast('❌ Network error.', 'error');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (!getToken()) {
        window.location.href = '/login';
        return;
    }
    const expiryInput = document.getElementById('expiryDate');
    if (expiryInput) {
        const today = new Date().toISOString().split('T')[0];
        expiryInput.setAttribute('min', today);
    }
    loadFarmers();
    loadMyListings();
    loadCooperativeOrders();
    createFlashSaleSection();
    loadCooperativeFlashSales();
    loadNotifications();
});