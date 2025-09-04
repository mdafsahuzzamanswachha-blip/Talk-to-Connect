// =======================
// AUTH.JS (Professional)
// =======================

/**
 * Utility: Show error/success messages
 */
function showMessage(msg, type = 'error') {
    const msgBox = document.getElementById('auth-message');
    if (!msgBox) return alert(msg); // fallback

    msgBox.textContent = msg;
    msgBox.style.color = type === 'error' ? '#ff4d4f' : '#4caf50';
    msgBox.style.display = 'block';
}

/**
 * Utility: Set loading state on button
 */
function setLoading(button, isLoading) {
    if (!button) return;
    button.disabled = isLoading;
    button.textContent = isLoading ? 'Please wait...' : button.dataset.label || 'Submit';
}

/**
 * Save token with optional expiry
 */
function saveToken(token, expiresIn = 3600) {
    const expiry = Date.now() + expiresIn * 1000;
    localStorage.setItem('authToken', token);
    localStorage.setItem('authExpiry', expiry);
}

/**
 * Check if user is authenticated
 */
function isAuthenticated() {
    const token = localStorage.getItem('authToken');
    const expiry = localStorage.getItem('authExpiry');
    return token && expiry && Date.now() < expiry;
}

/**
 * Login handler
 */
document.getElementById('login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = document.getElementById('email')?.value.trim();
    const password = document.getElementById('password')?.value.trim();
    const btn = e.target.querySelector('button[type="submit"]');

    if (!email || !password) {
        showMessage('Please enter both email and password');
        return;
    }

    try {
        setLoading(btn, true);

        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();

        if (res.ok) {
            if (data.token) {
                saveToken(data.token, data.expiresIn || 3600);
            }
            window.location.href = '/chat';
        } else {
            showMessage(data.error || 'Invalid email or password');
        }
    } catch (err) {
        console.error('Login error:', err);
        showMessage('Network error, please try again.');
    } finally {
        setLoading(btn, false);
    }
});

/**
 * Logout handler
 */
document.getElementById('logout-btn')?.addEventListener('click', async () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('authExpiry');

    try {
        await fetch('/api/logout', { method: 'POST' });
    } catch (err) {
        console.warn('Logout request failed, clearing token anyway.');
    } finally {
        window.location.href = '/login';
    }
});

/**
 * Auto-redirects
 */
if (isAuthenticated() && window.location.pathname === '/login') {
    window.location.href = '/chat';
}
if (!isAuthenticated() && window.location.pathname.startsWith('/chat')) {
    window.location.href = '/login';
}
