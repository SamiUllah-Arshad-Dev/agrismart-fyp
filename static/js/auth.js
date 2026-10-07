const API_BASE = '/api';

async function apiPost(path, payload, fallbackError) {
    let res;
    try {
        res = await fetch(`${API_BASE}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    } catch (netErr) {
        throw new Error('Server se connection nahi ban raha. Kya Flask chal raha hai?');
    }
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
    console.log(`[api] POST ${path} ->`, res.status, data);
    if (!res.ok) {
        throw new Error(data.error || data.message ||
                        `${fallbackError} (HTTP ${res.status})`);
    }
    return data;
}

export async function registerUser(userData) {
    return apiPost('/register', userData, 'Registration failed');
}

export async function loginUser(credentials) {
    return apiPost('/login', credentials, 'Login failed');
}

export async function getCurrentUser(token) {
    const res = await fetch(`${API_BASE}/me`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch (_) { data = {}; }
    if (!res.ok) throw new Error(data.error || 'Failed to fetch user');
    return data;
}

export async function forgotPassword(email) {
    return apiPost('/forgot-password', { email }, 'Request failed');
}

export async function resetPassword(token, newPassword) {
    return apiPost('/reset-password',
                   { token: token, new_password: newPassword },
                   'Reset failed');
}