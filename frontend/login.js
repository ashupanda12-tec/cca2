document.getElementById('login-form').addEventListener('submit', async function(e) {
    e.preventDefault();

    const email    = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const msgEl    = document.getElementById('message');

    // Reset
    msgEl.style.display = 'none';

    try {
        const res = await fetch(API_BASE_URL + '/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        if (res.ok) {
            sessionStorage.setItem('userEmail', email);
            window.location.href = 'index.html';
        } else {
            const data = await res.json();
            msgEl.textContent = data.error || 'email or password is invalid';
            msgEl.style.display = 'block';
        }
    } catch (err) {
        msgEl.textContent = 'Could not connect to the server.';
        msgEl.style.display = 'block';
        console.error(err);
    }
});
