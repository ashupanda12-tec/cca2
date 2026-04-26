// frontend/register.js
document.getElementById('register-form').addEventListener('submit', async function(event) {
    event.preventDefault();

    // Grab the values from the input fields
    let email = document.getElementById('email').value;
    let username = document.getElementById('username').value;
    let password = document.getElementById('password').value;
    let msgDiv = document.getElementById('message');

    try {
        let registerUrl = API_BASE_URL + '/auth/register';
        
        let response = await fetch(registerUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                "email": email, 
                "user_name": username, 
                "password": password 
            })
        });

        let data = await response.json();

        if (response.status == 201) {
            // Green text and redirect after 2 seconds
            msgDiv.style.color = 'green';
            msgDiv.textContent = "Registration successful. Redirecting to login...";
            msgDiv.style.display = 'block';
            
            setTimeout(function() {
                window.location.href = 'login.html';
            }, 2000);
            
        } else if (response.status == 409) {
            msgDiv.style.color = 'red';
            // display error
            msgDiv.textContent = "The email already exists";
            msgDiv.style.display = 'block';
            
        } else {
            msgDiv.style.color = 'red';
            // Fallback to another message if data.error doesn't exist
            if (data.error) {
                msgDiv.textContent = data.error;
            } else {
                msgDiv.textContent = "Registration failed.";
            }
            msgDiv.style.display = 'block';
        }
    } catch (error) {
        console.log('Error connecting to the API:', error);
        msgDiv.style.color = 'red';
        msgDiv.textContent = "Could not connect to the server.";
        msgDiv.style.display = 'block';
    }
});