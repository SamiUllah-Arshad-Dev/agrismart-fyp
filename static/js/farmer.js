function getToken() {
    return localStorage.getItem('access_token');
}

function authHeaders() {
    return {
        'Authorization': `Bearer ${getToken()}`
    };
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = 'toast show ' + type;
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => {
        toast.classList.remove('show');
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

function escapeHTML(str) {
    return String(str || '').replace(
        /[&<>"']/g,
        m => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        }[m])
    );
}

function listingThumbHTML(photos) {
    const src = (photos && photos.length > 0) ? photos[0] : null;
    if (src) {
        return `
            <img
                src="${src}"
                alt="crop"
                style="
                    width:40px;
                    height:40px;
                    object-fit:cover;
                    border-radius:6px;
                    display:block;
                "
                onerror="
                    this.parentElement.innerHTML=
                    '<span style=font-size:12px;color:#aaa;>📷</span>'
                "
            >
        `;
    }
    return `
        <span style="
            display:flex;
            align-items:center;
            justify-content:center;
            width:40px;
            height:40px;
            background:#f5f5f5;
            border-radius:6px;
            color:#ccc;
            font-size:10px;
            border:1px solid #eee;
        ">
            No<br>Img
        </span>
    `;
}

const form = document.getElementById('createListingForm');
const cropType = document.getElementById('cropType');
const quantity = document.getElementById('quantity');
const pricePerKg = document.getElementById('pricePerKg');
const expiryDate = document.getElementById('expiryDate');
const photoInput = document.getElementById('photoInput');
const mlBtn = document.getElementById('mlForecastBtn');
const forecastResult = document.getElementById('forecastResult');
const forecastPrice = document.getElementById('forecastPrice');
const forecastDemand = document.getElementById('forecastDemand');
const listingContainer = document.getElementById('listingsContainer');
const escrowContainer = document.getElementById('escrowContainer');
const flashContainer = document.getElementById('flashAlertsContainer');
const logoutBtn = document.getElementById('logoutBtn');

const name = localStorage.getItem('user_name') || 'Farmer';
document.getElementById('farmerNameDisplay').textContent = name;
document.getElementById('farmerInitials').textContent =
    name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

logoutBtn.addEventListener('click', () => {
    localStorage.clear();
    window.location.href = '/login';
});

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
        const res = await fetch('/api/notifications', { headers: authHeaders() });
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
                <div>${escapeHTML(n.message)}</div>
                <div class="notif-time">${timeAgo(n.timestamp)}</div>
            </div>
        `).join('');
    } catch (err) {
        notifList.innerHTML = '<div class="notif-empty">Error loading notifications.</div>';
    }
}

notifBellBtn.addEventListener('click', async () => {
    const isOpening = !notifPanel.classList.contains('show');
    notifPanel.classList.toggle('show');
    if (isOpening) {
        await loadNotifications();
        fetch('/api/notifications/read-all', {
            method: 'POST',
            headers: authHeaders()
        });
        notifBadge.style.display = 'none';
    }
});

document.addEventListener('click', (e) => {
    if (!e.target.closest('.notif-wrapper')) {
        notifPanel.classList.remove('show');
    }
});

mlBtn.addEventListener('click', async () => {
    const crop = cropType.value.trim();
    if (!crop) {
        showToast('Please enter a crop type first.', 'error');
        return;
    }
    try {
        const res = await fetch('/api/ml/forecast', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders()
            },
            body: JSON.stringify({ crop_type: crop })
        });
        const data = await res.json();
        if (res.ok) {
            forecastPrice.textContent = `Rs. ${fmtMoney(data.recommended_price)}`;
            forecastDemand.textContent = data.demand_forecast;
            forecastResult.style.display = 'block';
            showToast('ML Forecast fetched!', 'success');
        } else {
            showToast('Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
});

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('crop_type', cropType.value.trim());
    formData.append('quantity', quantity.value);
    formData.append('price', pricePerKg.value || '');
    formData.append('expiry_date', expiryDate.value);
    for (let file of photoInput.files) {
        formData.append('photos', file);
    }
    try {
        const res = await fetch('/api/listings', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${getToken()}` },
            body: formData
        });
        const data = await res.json();
        if (res.status === 201) {
            showToast(`Listing created! ID: ${data.listingId}`, 'success');
            quantity.value = '';
            pricePerKg.value = '';
            expiryDate.value = '';
            photoInput.value = '';
            forecastResult.style.display = 'none';
            loadListings();
            loadEscrowHistory();
        } else {
            showToast('Error: ' + (data.error || 'Failed'), 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
});

async function loadListings() {
    try {
        const res = await fetch('/api/listings', { headers: authHeaders() });
        if (res.status === 401 || res.status === 403) {
            window.location.href = '/login';
            return;
        }
        const data = await res.json();
        if (!data || data.length === 0) {
            listingContainer.innerHTML = '<div class="empty-state">No listings yet.</div>';
            return;
        }
        let html = `
            <table class="listings-table">
                <thead>
                    <tr>
                        <th>Photo</th>
                        <th>Crop</th>
                        <th>Qty</th>
                        <th>Price</th>
                        <th>Expiry</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;
        data.forEach(l => {
            if (l.listingType === 'cooperative') {
                const cooperativeExpiry = l.shelfLife ? l.shelfLife.split('T')[0] : 'N/A';
                html += `
                    <tr>
                        <td>${listingThumbHTML(l.photos)}</td>
                        <td>
                            <strong>${escapeHTML(l.cropType)}</strong>
                            <div style="font-size:11px; color:#777; margin-top:3px;">
                                Cooperative Combined Listing
                            </div>
                        </td>
                        <td>
                            ${l.quantity} kg
                            <div style="font-size:11px; color:#777;">contribution</div>
                        </td>
                        <td>Rs. ${fmtMoney(l.price)}</td>
                        <td>${escapeHTML(cooperativeExpiry)}</td>
                        <td>
                            <span style="
                                background:#E8F5E9;
                                color:#2E7D32;
                                font-weight:700;
                                padding:4px 12px;
                                border-radius:20px;
                                font-size:12px;
                                display:inline-block;
                            ">
                                ${prettyStatus(l.status || 'ACTIVE')}
                            </span>
                        </td>
                        <td>
                            <span style="color:#666; font-size:12px; font-weight:600;">
                                Managed by Cooperative
                            </span>
                        </td>
                    </tr>
                `;
                return;
            }
            const photosJson = JSON.stringify(l.photos || []).replace(/"/g, '&quot;');
            const status = (l.status || 'ACTIVE').toUpperCase();
            let bgColor;
            let textColor;
            switch (status) {
                case 'ACTIVE':
                    bgColor = '#E8F5E9';
                    textColor = '#2E7D32';
                    break;
                case 'SOLD':
                    bgColor = '#ECEFF1';
                    textColor = '#607D8B';
                    break;
                case 'EXPIRED':
                    bgColor = '#FFEBEE';
                    textColor = '#C62828';
                    break;
                case 'ON_FLASH_SALE':
                case 'FLASH':
                    bgColor = '#FFF3E0';
                    textColor = '#E65100';
                    break;
                default:
                    bgColor = '#f5f5f5';
                    textColor = '#333';
            }
            const statusBadge = `
                <span style="
                    background:${bgColor};
                    color:${textColor};
                    font-weight:700;
                    padding:4px 12px;
                    border-radius:20px;
                    font-size:12px;
                    display:inline-block;
                    letter-spacing:0.3px;
                    border:1px solid rgba(0,0,0,0.04);
                ">
                    ${prettyStatus(status)}
                </span>
            `;
            const expireBtn = (
                status === 'ACTIVE' ||
                status === 'ON_FLASH_SALE' ||
                status === 'FLASH'
            ) ? `
                <button class="btn-expire"
                        onclick="markExpired(${l.listingId})"
                        title="Mark as Expired">📦</button>
            ` : '';
            const startFlashBtn = (status === 'ACTIVE') ? `
                <button class="btn-flash"
                        onclick="startFlashSale(${l.listingId})"
                        title="Start Flash Sale">🔥</button>
            ` : '';
            const flashManageBtns = (
                status === 'ON_FLASH_SALE' ||
                status === 'FLASH'
            ) ? `
                <button class="btn-flash-edit"
                        onclick="editFlashSale(${l.listingId})"
                        title="Edit Discount">✏️🔥</button>
                <button class="btn-flash-end"
                        onclick="endFlashSale(${l.listingId})"
                        title="End Flash Sale">⏹️</button>
            ` : '';
            html += `
                <tr>
                    <td>${listingThumbHTML(l.photos)}</td>
                    <td><strong>${escapeHTML(l.cropType)}</strong></td>
                    <td>${l.quantity} kg</td>
                    <td>Rs. ${fmtMoney(l.price)}</td>
                    <td>${l.shelfLife?.split('T')[0] || 'N/A'}</td>
                    <td>${statusBadge}</td>
                    <td>
                        <button class="btn-edit"
                                title="Edit Listing"
                                onclick="editListing(
                                    '${l.listingId}',
                                    '${escapeHTML(l.cropType)}',
                                    ${l.quantity},
                                    ${l.price},
                                    '${l.shelfLife?.split('T')[0] || ''}',
                                    '${photosJson}'
                                )">✏️</button>
                        <button class="btn-delete"
                                title="Delete Listing"
                                onclick="deleteListing(${l.listingId})">🗑️</button>
                        ${expireBtn}
                        ${startFlashBtn}
                        ${flashManageBtns}
                    </td>
                </tr>
            `;
        });
        html += `
                </tbody>
            </table>
        `;
        listingContainer.innerHTML = html;
    } catch (err) {
        console.error('Error loading listings:', err);
        listingContainer.innerHTML = '<div class="empty-state">Error loading listings.</div>';
    }
}

window.deleteListing = async function(listingId) {
    if (!confirm('Delete this listing?')) return;
    try {
        const res = await fetch(`/api/listings/${listingId}`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        const data = await res.json();
        if (res.ok) {
            showToast('Listing deleted.', 'success');
            loadListings();
            loadEscrowHistory();
        } else {
            showToast(data.error || 'Delete failed.', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
};

window.markExpired = async function(listingId) {
    if (!confirm('Mark this listing as EXPIRED? It will be hidden from buyers.')) return;
    try {
        const res = await fetch(`/api/listings/${listingId}/mark-expired`, {
            method: 'POST',
            headers: authHeaders()
        });
        const data = await res.json();
        if (res.ok) {
            showToast('Listing marked as EXPIRED.', 'success');
            loadListings();
            loadFlashAlerts();
        } else {
            showToast(data.error || 'Failed to mark expired.', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
};

window.startFlashSale = async function(listingId) {
    const discountStr = prompt(
        'Enter discount percentage (5-90):\nExample: 20 for 20% off',
        '20'
    );
    if (!discountStr) return;
    const discount = parseFloat(discountStr) / 100;
    if (isNaN(discount) || discount < 0.05 || discount > 0.90) {
        showToast('Discount must be between 5% and 90%', 'error');
        return;
    }
    try {
        const res = await fetch(`/api/listings/${listingId}/start-flash-sale`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders()
            },
            body: JSON.stringify({ discount })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(
                `🔥 Flash sale started! Rs.${fmtMoney(data.originalPrice)} → Rs.${fmtMoney(data.discountedPrice)}`,
                'success'
            );
            loadListings();
            loadFlashAlerts();
        } else {
            showToast(data.error || 'Failed to start flash sale', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
};

window.editFlashSale = async function(listingId) {
    const discountStr = prompt('Enter new discount percentage (5-90):', '20');
    if (!discountStr) return;
    const discount = parseFloat(discountStr) / 100;
    if (isNaN(discount) || discount < 0.05 || discount > 0.90) {
        showToast('Discount must be between 5% and 90%', 'error');
        return;
    }
    try {
        const res = await fetch(`/api/listings/${listingId}/edit-flash-sale`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders()
            },
            body: JSON.stringify({ discount })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(
                `✏️ Discount updated! New price: Rs.${fmtMoney(data.discountedPrice)}`,
                'success'
            );
            loadListings();
            loadFlashAlerts();
        } else {
            showToast(data.error || 'Failed to update discount', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
};

window.endFlashSale = async function(listingId) {
    if (!confirm('End flash sale and restore original price?')) return;
    try {
        const res = await fetch(`/api/listings/${listingId}/end-flash-sale`, {
            method: 'POST',
            headers: authHeaders()
        });
        const data = await res.json();
        if (res.ok) {
            showToast('⏹️ Flash sale ended, price restored', 'success');
            loadListings();
            loadFlashAlerts();
        } else {
            showToast(data.error || 'Failed to end flash sale', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
};

async function loadEscrowHistory() {
    try {
        const res = await fetch('/api/escrow/history', { headers: authHeaders() });
        const data = await res.json();
        if (!data || data.length === 0) {
            escrowContainer.innerHTML = '<div class="empty-state">No escrow history.</div>';
            return;
        }
        let html = `
            <table class="escrow-table">
                <thead>
                    <tr>
                        <th>Order</th>
                        <th>Buyer</th>
                        <th>Location</th>
                        <th>Crop</th>
                        <th>Amount</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
        `;
        data.forEach(e => {
            const cls = e.escrowStatus === 'RELEASED' ? 'status-released' : 'status-held';
            const buyerCell = `
                <div>${escapeHTML(e.buyerName || 'N/A')}</div>
                ${
                    e.buyerPhone && e.buyerPhone !== 'N/A'
                        ? `<div style="margin-top:2px;"><a href="tel:${e.buyerPhone.replace(/[^0-9+]/g, '')}" style="color:#2E7D32;text-decoration:none;font-weight:600;font-size:12px;">📞 ${escapeHTML(e.buyerPhone)}</a></div>`
                        : ''
                }
            `;
            html += `
                <tr>
                    <td>#${e.orderId}</td>
                    <td>${buyerCell}</td>
                    <td>${escapeHTML(e.buyerLocation || 'N/A')}</td>
                    <td>${escapeHTML(e.cropType || 'N/A')}</td>
                    <td>Rs. ${fmtMoney(e.amount)}</td>
                    <td>
                        <span class="${cls}">
                            ${e.escrowStatus || 'HELD'}
                        </span>
                    </td>
                </tr>
            `;
        });
        html += `
                </tbody>
            </table>
        `;
        escrowContainer.innerHTML = html;
    } catch (err) {
        escrowContainer.innerHTML = '<div class="empty-state">Error loading escrow.</div>';
    }
}

async function loadFlashAlerts() {
    try {
        const res = await fetch('/api/flash-sale/my-alerts', { headers: authHeaders() });
        const data = await res.json();
        if (!data || data.length === 0) {
            flashContainer.innerHTML = '<div class="empty-state">No flash alerts.</div>';
            return;
        }
        let html = '';
        data.forEach(a => {
            const responded = a.farmerResponse === 'accepted';
            const actionHTML = responded ? `
                <div style="
                    text-align:center;
                    padding:10px;
                    color:#2E7D32;
                    font-weight:600;
                    background:#E8F5E9;
                    border-radius:8px;
                    margin-top:8px;
                ">
                    ✓ Flash sale accepted
                </div>
            ` : `
                <button class="btn-respond"
                        onclick="respondFlash(${a.listingId})">
                    Respond
                </button>
            `;
            html += `
                <div class="flash-alert-card">
                    <div class="flash-alert-title">
                        ${escapeHTML(a.cropType)}
                        <span class="flash-alert-expiry">Expiring soon!</span>
                    </div>
                    <div class="flash-alert-desc">
                        Discounted price: Rs. ${fmtMoney(a.discountedPrice)}/kg
                        (was Rs. ${fmtMoney(a.originalPrice)})
                    </div>
                    ${actionHTML}
                </div>
            `;
        });
        flashContainer.innerHTML = html;
    } catch (err) {
        flashContainer.innerHTML = '<div class="empty-state">Error loading alerts.</div>';
    }
}

window.respondFlash = async function(listingId) {
    const accept = confirm(
        'Accept flash sale?\n\n' +
        'OK = Accept (keep on flash sale)\n' +
        'Cancel = Decline (return to normal price)'
    );
    try {
        const res = await fetch('/api/flash-sale/respond', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders()
            },
            body: JSON.stringify({ listing_id: listingId, accept })
        });
        if (res.ok) {
            const msg = accept
                ? 'Flash sale accepted!'
                : 'Flash sale declined, listing active again';
            showToast(msg, 'success');
            loadListings();
            loadFlashAlerts();
        } else {
            showToast('Failed to respond.', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
};

window.editListing = function(listingId, cropType, quantity, price, expiry, photosJson) {
    let photos = [];
    try {
        photos = JSON.parse(photosJson);
    } catch (e) {
        photos = [];
    }
    document.getElementById('editListingId').value = listingId;
    document.getElementById('editCropType').value = cropType || '';
    document.getElementById('editQuantity').value = quantity || '';
    document.getElementById('editPrice').value = price || '';
    document.getElementById('editExpiry').value = expiry || '';
    const photoImg = document.getElementById('editCurrentPhoto');
    const photoContainer = document.getElementById('editCurrentPhotoContainer');
    const noPhotoSpan = document.getElementById('editNoPhotoMsg');
    if (photos && photos.length > 0 && photoImg) {
        photoImg.src = photos[0];
        photoImg.style.display = 'block';
        if (noPhotoSpan) noPhotoSpan.style.display = 'none';
    } else if (photoImg) {
        photoImg.style.display = 'none';
        if (noPhotoSpan) noPhotoSpan.style.display = 'inline';
    }
    document.getElementById('editPhotoInput').value = '';
    const modal = new bootstrap.Modal(document.getElementById('editModal'));
    modal.show();
};

document.getElementById('editForm')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    const listingId = document.getElementById('editListingId').value;
    const formData = new FormData();
    formData.append('crop_type', document.getElementById('editCropType').value.trim());
    formData.append('quantity', document.getElementById('editQuantity').value);
    formData.append('price', document.getElementById('editPrice').value);
    formData.append('expiry_date', document.getElementById('editExpiry').value);
    const photoFile = document.getElementById('editPhotoInput').files[0];
    if (photoFile) {
        formData.append('photo', photoFile);
    }
    const submitBtn = document.getElementById('editSubmitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Updating...';
    try {
        const res = await fetch(`/api/listings/${listingId}`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${getToken()}` },
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            showToast('Listing updated successfully!', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('editModal'));
            if (modal) modal.hide();
            loadListings();
            loadEscrowHistory();
        } else {
            showToast(data.error || 'Failed to update', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Update Listing';
    }
});

export function initFarmerDashboard() {
    if (!getToken()) {
        window.location.href = '/login';
        return;
    }
    const expiryInput = document.getElementById('expiryDate');
    if (expiryInput) {
        const today = new Date().toISOString().split('T')[0];
        expiryInput.setAttribute('min', today);
    }
    loadListings();
    loadEscrowHistory();
    loadFlashAlerts();
    loadNotifications();
}