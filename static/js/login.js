    (() => {
        'use strict';

        // DOM Elements
        const loginForm      = document.getElementById('loginForm');
        const registerForm   = document.getElementById('registerForm');
        const alertError     = document.getElementById('alertError');
        const alertErrorText = document.getElementById('alertErrorText');
        const alertSuccess   = document.getElementById('alertSuccess');
        const alertSuccessText = document.getElementById('alertSuccessText');
        const authSubtitle   = document.getElementById('authSubtitle');

        // API Base URL
        const API_BASE = '/api/auth';

        // Toggle Login / Register

        document.getElementById('showRegister').addEventListener('click', (e) => {
            e.preventDefault();
            loginForm.classList.add('hidden');
            registerForm.classList.remove('hidden');
            registerForm.classList.remove('auth-form'); // reset animation
            void registerForm.offsetWidth; // force reflow
            registerForm.classList.add('auth-form');
            authSubtitle.textContent = 'Buat akun baru';
            hideAlerts();
        });

        document.getElementById('showLogin').addEventListener('click', (e) => {
            e.preventDefault();
            registerForm.classList.add('hidden');
            loginForm.classList.remove('hidden');
            loginForm.classList.remove('auth-form');
            void loginForm.offsetWidth;
            loginForm.classList.add('auth-form');
            authSubtitle.textContent = 'Masuk ke akun Anda';
            hideAlerts();
        });

        // Toggle Password Visibility

        document.querySelectorAll('.toggle-password').forEach(btn => {
            btn.addEventListener('click', () => {
                const target = document.getElementById(btn.dataset.target);
                const icon = btn.querySelector('i');
                if (target.type === 'password') {
                    target.type = 'text';
                    icon.classList.replace('bi-eye', 'bi-eye-slash');
                } else {
                    target.type = 'password';
                    icon.classList.replace('bi-eye-slash', 'bi-eye');
                }
            });
        });

        // Alert Helpers

        function showError(msg) {
            alertSuccess.classList.remove('show');
            alertErrorText.textContent = msg;
            alertError.classList.add('show');
        }

        function showSuccess(msg) {
            alertError.classList.remove('show');
            alertSuccessText.textContent = msg;
            alertSuccess.classList.add('show');
        }

        function hideAlerts() {
            alertError.classList.remove('show');
            alertSuccess.classList.remove('show');
        }

        // Password Strength Meter

        const regPassword = document.getElementById('regPassword');

        regPassword.addEventListener('input', () => {
            const val = regPassword.value;
            let score = 0;
            if (val.length >= 8) score++;
            if (/[a-z]/.test(val) && /[A-Z]/.test(val)) score++;
            if (/\d/.test(val)) score++;
            if (/[^a-zA-Z0-9]/.test(val)) score++;

            const bars = [
                document.getElementById('str1'),
                document.getElementById('str2'),
                document.getElementById('str3'),
                document.getElementById('str4'),
            ];
            const strengthText = document.getElementById('strengthText');

            bars.forEach((bar, i) => {
                bar.className = 'strength-bar';
                if (i < score) {
                    if (score <= 1) bar.classList.add('weak');
                    else if (score <= 2) bar.classList.add('medium');
                    else bar.classList.add('strong');
                }
            });

            const labels = ['', 'Lemah', 'Sedang', 'Kuat', 'Sangat Kuat'];
            strengthText.textContent = val.length > 0 ? labels[score] || '' : '';
        });

        // Client-side Validation (Register)

        function validateRegister() {
            const username  = document.getElementById('regUsername');
            const email     = document.getElementById('regEmail');
            const password  = document.getElementById('regPassword');
            const confirm   = document.getElementById('regConfirmPassword');
            let valid = true;

            // Reset
            [username, email, password, confirm].forEach(el => {
                el.classList.remove('is-invalid', 'is-valid');
            });

            // Username
            if (username.value.trim().length < 3) {
                username.classList.add('is-invalid');
                document.getElementById('regUsernameFeedback').textContent = 'Username minimal 3 karakter';
                valid = false;
            } else {
                username.classList.add('is-valid');
            }

            // Email
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email.value.trim())) {
                email.classList.add('is-invalid');
                document.getElementById('regEmailFeedback').textContent = 'Format email tidak valid';
                valid = false;
            } else {
                email.classList.add('is-valid');
            }

            // Password
            if (password.value.length < 8) {
                password.classList.add('is-invalid');
                document.getElementById('regPasswordFeedback').textContent = 'Password minimal 8 karakter';
                valid = false;
            } else {
                password.classList.add('is-valid');
            }

            // Confirm
            if (confirm.value !== password.value) {
                confirm.classList.add('is-invalid');
                document.getElementById('regConfirmFeedback').textContent = 'Password tidak cocok';
                valid = false;
            } else if (confirm.value.length > 0) {
                confirm.classList.add('is-valid');
            }

            return valid;
        }

        // Button Loading State

        function setLoading(btn, loading) {
            if (loading) {
                btn.classList.add('loading');
                btn.disabled = true;
            } else {
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        }

        // LOGIN Submit

        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideAlerts();

            const identifier = document.getElementById('loginIdentifier').value.trim();
            const password   = document.getElementById('loginPassword').value;

            if (!identifier || !password) {
                showError('Semua field wajib diisi');
                return;
            }

            const btn = document.getElementById('btnLogin');
            setLoading(btn, true);

            try {
                const res = await fetch(`${API_BASE}/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: identifier,
                        password: password,
                    }),
                });

                const data = await res.json();

                if (!res.ok) {
                    showError(data.error || 'Login gagal. Periksa kembali kredensial Anda.');
                    return;
                }

                // Simpan JWT token
                localStorage.setItem('auth_token', data.access_token);
                localStorage.setItem('user', JSON.stringify(data.user));

                showSuccess('Login berhasil! Mengalihkan...');

                // Redirect ke dashboard
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 800);

            } catch (err) {
                showError('Tidak dapat terhubung ke server. Coba lagi nanti.');
                console.error('Login error:', err);
            } finally {
                setLoading(btn, false);
            }
        });

        // REGISTER Submit

        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideAlerts();

            if (!validateRegister()) return;

            const username = document.getElementById('regUsername').value.trim();
            const email    = document.getElementById('regEmail').value.trim();
            const password = document.getElementById('regPassword').value;
            
            const api_id   = document.getElementById('regApiId').value.trim();
            const api_hash = document.getElementById('regApiHash').value.trim();
            const chat_id  = document.getElementById('regChatId').value.trim();

            if (!api_id || !api_hash || !chat_id) {
                showError('Telegram API ID, API Hash, dan Chat ID wajib diisi');
                return;
            }

            const btn = document.getElementById('btnRegister');
            setLoading(btn, true);

            try {
                const res = await fetch(`${API_BASE}/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, email, password, api_id, api_hash, chat_id }),
                });

                const data = await res.json();

                if (!res.ok) {
                    showError(data.error || 'Registrasi gagal. Coba lagi.');
                    return;
                }

                showSuccess('Akun berhasil dibuat! Silakan login.');

                // Switch ke login form setelah delay
                setTimeout(() => {
                    document.getElementById('showLogin').click();
                    // Pre-fill username
                    document.getElementById('loginIdentifier').value = username;
                    document.getElementById('loginPassword').focus();
                }, 1500);

            } catch (err) {
                showError('Tidak dapat terhubung ke server. Coba lagi nanti.');
                console.error('Register error:', err);
            } finally {
                setLoading(btn, false);
            }
        });

        // Auto-redirect jika sudah login

        if (localStorage.getItem('auth_token')) {
            window.location.href = '/dashboard';
        }

    })();
