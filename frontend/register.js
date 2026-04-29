document.getElementById('register-form').addEventListener('submit', async function(e) {
    e.preventDefault();

    const email    = document.getElementById('email').value;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const msgEl    = document.getElementById('message');

    msgEl.className = 'message-box';
    msgEl.style.display = 'none';

    try {
        const res = await fetch(API_BASE_URL + '/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, user_name: username, password })
        });

        const data = await res.json();

        if (res.status === 201) {
            msgEl.className = 'message-box success';
            msgEl.textContent = 'Account created! Redirecting to sign in…';
            msgEl.style.display = 'block';
            setTimeout(() => { window.location.href = 'login.html'; }, 2000);

        } else if (res.status === 409) {
            msgEl.className = 'message-box error';
            msgEl.textContent = 'The email already exists';
            msgEl.style.display = 'block';

        } else {
            msgEl.className = 'message-box error';
            msgEl.textContent = data.error || 'Registration failed.';
            msgEl.style.display = 'block';
        }
    } catch (err) {
        msgEl.className = 'message-box error';
        msgEl.textContent = 'Could not connect to the server.';
        msgEl.style.display = 'block';
        console.error(err);
    }
});
