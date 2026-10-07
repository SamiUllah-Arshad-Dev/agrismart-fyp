import { showToast, setLoading, isValidEmail } from './utils.js';

export function initForgotPassword() {
    const form = document.getElementById('forgotForm');
    const email = document.getElementById('email');
    const sendBtn = document.getElementById('sendBtn');
    const emailError = document.getElementById('emailError');
    if (!form || !email || !sendBtn) return;
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const emailVal = email.value.trim().toLowerCase();
        if (emailError) emailError.style.display = 'none';
        if (!emailVal || !isValidEmail(emailVal)) {
            if (emailError) emailError.style.display = 'block';
            return;
        }
        setLoading(sendBtn, true);
        try {
            const response = await fetch('/api/forgot-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: emailVal })
            });
            const data = await response.json();
            if (response.ok) {
                showToast(data.message || 'If the email exists, a reset link was sent.', 'success');
                form.style.display = 'none';
                const panel = document.createElement('div');
                panel.id = 'resetPanel';
                panel.style.marginTop = '20px';
                panel.style.padding = '20px';
                panel.style.background = '#e8f5e9';
                panel.style.borderRadius = '8px';
                panel.style.textAlign = 'center';
                panel.innerHTML = `
                    <p style="font-weight:bold; color:#2E7D32;">Check the console</p>
                    <p style="color:#555;">If that email is registered, a reset link has been printed to the server console (this simulates an email in development).</p>
                `;
                form.parentNode.appendChild(panel);
            } else {
                showToast(data.error || data.message || 'Something went wrong.', 'error');
            }
        } catch (err) {
            showToast('Network error. Please try again.', 'error');
        } finally {
            setLoading(sendBtn, false);
        }
    });
}