export function showToast(message, type = 'success', ms = 3500) {
    let t = document.getElementById('toast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'toast';
        t.className = 'toast';
        document.body.appendChild(t);
    }
    t.textContent = message;
    t.className = 'toast show ' + type;
    t.style.position = 'fixed';
    t.style.top = '20px';
    t.style.left = '50%';
    t.style.transform = 'translateX(-50%)';
    t.style.zIndex = '9999';
    t.style.padding = '12px 20px';
    t.style.borderRadius = '8px';
    t.style.color = '#fff';
    t.style.fontSize = '14px';
    t.style.maxWidth = '90vw';
    t.style.textAlign = 'center';
    t.style.boxShadow = '0 4px 14px rgba(0,0,0,.18)';
    t.style.background = type === 'error' ? '#e53935'
                       : type === 'info' ? '#1e88e5' : '#2E7D32';
    t.style.display = 'block';
    clearTimeout(t._hideTimer);
    t._hideTimer = setTimeout(() => {
        t.style.display = 'none';
        t.className = 'toast';
    }, ms);
}

export function setError(input, errorEl, hasError) {
    if (errorEl) errorEl.style.display = hasError ? 'block' : 'none';
    if (input) {
        input.style.borderColor = hasError ? '#e53935' : '';
        input.classList.toggle('input-error', !!hasError);
    }
}

export function clearError(input, errorEl) {
    setError(input, errorEl, false);
}

export function clearAllErrors(root = document) {
    root.querySelectorAll('.error-msg').forEach(el => { el.style.display = 'none'; });
    root.querySelectorAll('input, select, textarea').forEach(el => {
        el.style.borderColor = '';
        el.classList.remove('input-error');
    });
}

export function isValidEmail(value) {
    return /^[^@]+@[^@]+.[^@]+$/.test(String(value || '').trim());
}

export function setLoading(btn, loading, loadingText = 'Please wait...') {
    if (!btn) return;
    if (loading) {
        btn.dataset._label = btn.textContent;
        btn.disabled = true;
        btn.textContent = loadingText;
    } else {
        btn.disabled = false;
        if (btn.dataset._label) btn.textContent = btn.dataset._label;
    }
}