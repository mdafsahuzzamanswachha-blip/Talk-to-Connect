// =======================
// AUTH.JS
// =======================

// Login form submit
document.getElementById('login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value.trim();

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();
        if (res.ok) {
            // Store token if using JWT
            if (data.token) {
                localStorage.setItem('authToken', data.token);
            }
            window.location.href = '/chat';
        } else {
            alert(data.error || 'Login failed');
        }
    } catch (err) {
        console.error(err);
        alert('Network error');
    }
});

// Logout
document.getElementById('logout-btn')?.addEventListener('click', () => {
    localStorage.removeItem('authToken');
    fetch('/api/logout', { method: 'POST' }).finally(() => {
        window.location.href = '/login';
    });
});

// Auto‑redirect if already logged in
if (localStorage.getItem('authToken') && window.location.pathname === '/login') {
    window.location.href = '/chat';
}
