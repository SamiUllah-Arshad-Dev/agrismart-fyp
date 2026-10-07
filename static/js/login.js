import { loginUser, forgotPassword } from './auth.js';
import { showToast, setError, clearAllErrors } from './utils.js';

export function initLogin() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('verified') === 'true') {
        setTimeout(() => {
            showToast('✅ Email verified! Your account is pending admin approval. Please try logging in after some time.', 'success');
        }, 500);
        window.history.replaceState({}, document.title, '/login');
    }
    const form = document.getElementById('loginForm');
    const email = document.getElementById('email');
    const password = document.getElementById('password');
    const btn = document.getElementById('loginBtn');
    const emailErr = document.getElementById('emailError');
    const passErr = document.getElementById('passwordError');
    email.setAttribute('readonly', true);
    password.setAttribute('readonly', true);
    email.value = '';
    password.value = '';
    setTimeout(() => {
        email.removeAttribute('readonly');
        password.removeAttribute('readonly');
        email.focus();
    }, 300);
    document.getElementById('togglePassword')?.addEventListener('click', function() {
        password.type = password.type === 'password' ? 'text' : 'password';
        this.classList.toggle('slashed', password.type === 'password');
    });
    function validateEmail() {
        const val = email.value.trim();
        const valid = /^[^@]+@[^@]+\.[^@]+$/.test(val);
        setError(email, emailErr, !valid);
        return valid;
    }
    function validatePassword() {
        const valid = password.value.length > 0;
        setError(password, passErr, !valid);
        return valid;
    }
    email.addEventListener('blur', validateEmail);
    password.addEventListener('blur', validatePassword);
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        if (!validateEmail() || !validatePassword()) {
            showToast('Please fix the errors in red.', 'error');
            return;
        }
        btn.disabled = true;
        btn.textContent = 'Logging in...';
        const payload = {
            email: email.value.trim().toLowerCase(),
            password: password.value
        };
        try {
            const data = await loginUser(payload);
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user_role', data.role);
            localStorage.setItem('user_id', data.userId);
            localStorage.setItem('user_name', data.name);
            showToast(`✅ Welcome, ${data.name}! Logged in as ${data.role}.`, 'success');
            setTimeout(() => {
                const role = data.role;
                if (role === 'farmer') {
                    window.location.href = '/farmer/dashboard';
                } else if (role === 'buyer') {
                    window.location.href = '/buyer/dashboard';
                } else if (role === 'admin') {
                    window.location.href = '/admin-panel';
                } else if (role === 'cooperative') {
                    window.location.href = '/cooperative-ui';
                } else {
                    alert(`Login Successful!\nName: ${data.name}\nRole: ${data.role}`);
                }
            }, 600);
        } catch (err) {
            showToast('❌ ' + err.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Login';
        }
    });
    document.getElementById('registerLink')?.addEventListener('click', function(e) {
        e.preventDefault();
        window.location.href = '/register';
    });
    document.getElementById('forgotLink')?.addEventListener('click', async function(e) {
        e.preventDefault();
        const emailInput = document.getElementById('email').value.trim();
        if (!emailInput) {
            showToast('Please enter your email address first.', 'error');
            return;
        }
        if (!/^[^@]+@[^@]+\.[^@]+$/.test(emailInput)) {
            showToast('Please enter a valid email address.', 'error');
            return;
        }
        try {
            await forgotPassword(emailInput);
            showToast('✅ If email exists, reset link sent to terminal.', 'success');
        } catch (err) {
            showToast('❌ ' + err.message, 'error');
        }
    });
}