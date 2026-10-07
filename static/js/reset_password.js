import { resetPassword } from './auth.js';
import { showToast, setError } from './utils.js';

export function initResetPassword() {
    const form = document.getElementById('resetForm');
    const newPassword = document.getElementById('newPassword');
    const confirmNew = document.getElementById('confirmNewPassword');
    const btn = document.getElementById('resetBtn');
    const newPassErr = document.getElementById('newPasswordError');
    const confirmErr = document.getElementById('confirmNewPasswordError');
    const invalidNotice = document.getElementById('invalidLinkNotice');
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    if (!token || token.trim() === '') {
        invalidNotice.style.display = 'block';
        form.style.display = 'none';
        return;
    }
    document.getElementById('toggleNew')?.addEventListener('click', function() {
        newPassword.type = newPassword.type === 'password' ? 'text' : 'password';
        this.classList.toggle('slashed', newPassword.type === 'password');
    });
    document.getElementById('toggleConfirm')?.addEventListener('click', function() {
        confirmNew.type = confirmNew.type === 'password' ? 'text' : 'password';
        this.classList.toggle('slashed', confirmNew.type === 'password');
    });
    function validateNewPassword() {
        const valid = newPassword.value.length >= 6;
        setError(newPassword, newPassErr, !valid);
        return valid;
    }
    function validateConfirm() {
        const valid = confirmNew.value === newPassword.value
                      && confirmNew.value !== '';
        setError(confirmNew, confirmErr, !valid);
        return valid;
    }
    newPassword.addEventListener('blur', validateNewPassword);
    confirmNew.addEventListener('blur', validateConfirm);
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        if (!validateNewPassword() || !validateConfirm()) {
            showToast('Please fix the errors in red.', 'error');
            return;
        }
        btn.disabled = true;
        btn.textContent = 'Resetting...';
        try {
            await resetPassword(token, newPassword.value);
            showToast('Password reset successful! Redirecting to login...', 'success');
            setTimeout(() => {
                window.location.href = '/login';
            }, 1500);
        } catch (err) {
            showToast('❌ ' + err.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Reset Password';
        }
    });
}