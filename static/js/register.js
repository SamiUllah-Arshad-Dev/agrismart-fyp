import { registerUser } from './auth.js';
import { showToast, setError, clearAllErrors } from './utils.js';

export function initRegister() {
    const form = document.getElementById('registerForm');
    const cnic = document.getElementById('cnic');
    const fullName = document.getElementById('fullName');
    const email = document.getElementById('email');
    const phone = document.getElementById('phone');
    const password = document.getElementById('password');
    const confirmPass = document.getElementById('confirmPassword');
    const role = document.getElementById('role');
    const location = document.getElementById('location');
    const btn = document.getElementById('registerBtn');
    const cnicErr = document.getElementById('cnicError');
    const nameErr = document.getElementById('nameError');
    const emailErr = document.getElementById('emailError');
    const phoneErr = document.getElementById('phoneError');
    const passErr = document.getElementById('passwordError');
    const confirmErr = document.getElementById('confirmError');
    const locationErr = document.getElementById('locationError');
    const card = document.querySelector('.card');
    window.addEventListener('load', function() {
        setTimeout(function() {
            form.reset();
        }, 50);
    });
    document.getElementById('togglePassword1')?.addEventListener('click', function() {
        password.type = password.type === 'password' ? 'text' : 'password';
        this.classList.toggle('slashed', password.type === 'password');
    });
    document.getElementById('togglePassword2')?.addEventListener('click', function() {
        confirmPass.type = confirmPass.type === 'password' ? 'text' : 'password';
        this.classList.toggle('slashed', confirmPass.type === 'password');
    });
    function validateCnic() {
        const val = cnic.value.trim();
        const valid = /^\d{13}$/.test(val);
        setError(cnic, cnicErr, !valid);
        return valid;
    }
    function validateName() {
        const valid = fullName.value.trim().length > 0;
        setError(fullName, nameErr, !valid);
        return valid;
    }
    function validateEmail() {
        const valid = /^[^@]+@[^@]+\.[^@]+$/.test(email.value.trim());
        setError(email, emailErr, !valid);
        return valid;
    }
    function validatePhone() {
        const val = phone.value.trim();
        const valid = /^03\d{9}$/.test(val);
        setError(phone, phoneErr, !valid);
        return valid;
    }
    function validatePassword() {
        const val = password.value;
        const errors = [];
        if (val.length < 8) errors.push("at least 8 characters");
        if (!/[a-z]/.test(val)) errors.push("one lowercase letter (a-z)");
        if (!/[A-Z]/.test(val)) errors.push("one uppercase letter (A-Z)");
        if (!/\d/.test(val)) errors.push("one digit (0-9)");
        if (!/[!@#$%^&*(),.?":{}|<>]/.test(val)) {
            errors.push("one special character (!@#$ etc)");
        }
        if (errors.length > 0) {
            passErr.textContent = "❌ Password must contain " + errors.join(", ") + ".";
            setError(password, passErr, true);
            return false;
        } else {
            passErr.textContent = "✅ Strong password!";
            setError(password, passErr, false);
            return true;
        }
    }
    function validateConfirm() {
        const valid = confirmPass.value === password.value && confirmPass.value !== '';
        setError(confirmPass, confirmErr, !valid);
        return valid;
    }
    function validateLocation() {
        const valid = location.value.trim().length > 0;
        setError(location, locationErr, !valid);
        return valid;
    }
    cnic.addEventListener('blur', validateCnic);
    fullName.addEventListener('blur', validateName);
    email.addEventListener('blur', validateEmail);
    phone.addEventListener('blur', validatePhone);
    password.addEventListener('blur', validatePassword);
    confirmPass.addEventListener('blur', validateConfirm);
    location.addEventListener('blur', validateLocation);
    function validateForm() {
        return validateCnic() &&
               validateName() &&
               validateEmail() &&
               validatePhone() &&
               validatePassword() &&
               validateConfirm() &&
               validateLocation();
    }
    function showSuccessPanel(verificationLink) {
        form.style.display = 'none';
        const panel = document.createElement('div');
        panel.id = 'successPanel';
        panel.innerHTML = `
            <div style="text-align:center; padding: 10px 0;">
                <div style="font-size:40px; margin-bottom:8px;">✅</div>
                <h3 style="margin-bottom:6px;">Registration Successful!</h3>
                <p style="color:#555; font-size:14px; margin-bottom:20px;">
                    Click below to verify your email address.
                </p>
                <button type="button" id="verifyNowBtn" class="btn-register">
                    Verify My Email
                </button>
                <div id="verifyResultBox" style="margin-top:16px;"></div>
            </div>
        `;
        card.appendChild(panel);
        document.getElementById('verifyNowBtn').addEventListener('click', async function() {
            this.disabled = true;
            this.textContent = 'Verifying...';
            try {
                const res = await fetch(verificationLink);
                const data = await res.json();
                const resultBox = document.getElementById('verifyResultBox');
                if (res.ok) {
                    this.style.display = 'none';
                    resultBox.innerHTML = `
                        <div class="notice" style="background:#f1f8f1; color:#1b5e20; margin-bottom:14px;">
                            ✅ ${data.message}
                        </div>

                        <p style="color:#555; font-size:13px; margin-bottom:14px;">
                            An admin will approve your account shortly. Once approved, you can log in.
                        </p>

                        <p style="color:#666; font-size:13px;">
                            Redirecting to login page in 2 seconds...
                        </p>
                    `;
                    setTimeout(() => {
                        window.location.href = '/login?verified=true';
                    }, 2000);
                } else {
                    resultBox.innerHTML = `
                        <div class="error-msg show">
                            ❌ ${data.error || 'Verification failed'}
                        </div>
                    `;
                    this.disabled = false;
                    this.textContent = 'Verify My Email';
                }
            } catch (e) {
                showToast('❌ Could not verify. Check server connection.', 'error');
                this.disabled = false;
                this.textContent = 'Verify My Email';
            }
        });
    }
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        if (!validateForm()) {
            showToast('Please fix the errors in red.', 'error');
            return;
        }
        btn.disabled = true;
        btn.textContent = 'Registering...';
        const payload = {
            name: fullName.value.trim(),
            email: email.value.trim().toLowerCase(),
            password: password.value,
            cnic: cnic.value.trim(),
            phone: phone.value.trim(),
            role: role.value,
            location: location.value.trim()
        };
        try {
            const data = await registerUser(payload);
            showToast('✅ Registration Successful!', 'success');
            clearAllErrors();
            if (data && data.verification_link) {
                showSuccessPanel(data.verification_link);
            }
        } catch (err) {
            showToast('❌ Failed: ' + err.message, 'error');
            if (err.message.includes('CNIC')) {
                setError(cnic, cnicErr, true, err.message);
            } else if (err.message.includes('Email')) {
                setError(email, emailErr, true, err.message);
            } else if (err.message.includes('Phone')) {
                setError(phone, phoneErr, true, err.message);
            } else if (err.message.toLowerCase().includes('location')) {
                setError(location, locationErr, true, err.message);
            }
        } finally {
            btn.disabled = false;
            btn.textContent = 'Register';
        }
    });
    document.getElementById('loginLink')?.addEventListener('click', function(e) {
        e.preventDefault();
        window.location.href = '/login';
    });
}