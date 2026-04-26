// frontend/login.js
document.getElementById('login-form').addEventListener('submit', async function(event) {
    event.preventDefault(); 

    let email = document.getElementById('email').value;
    let password = document.getElementById('password').value;
    let errorMsg = document.getElementById('message');

    try {
        let loginUrl = API_BASE_URL + '/auth/login';
        
        let response = await fetch(loginUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                "email": email, 
                "password": password 
            })
        });

        if (response.ok == true) {
            sessionStorage.setItem('userEmail', email);
            window.location.href = 'index.html'; 
        } else {
            // Use backend error
            let errorData = await response.json();
            
            if (errorData.error) {
                errorMsg.textContent = errorData.error;
            } else {
                errorMsg.textContent = "email or password is invalid";
            }
            
            // Add red styling so it looks like an error
            errorMsg.style.color = "#d93025";
            errorMsg.style.backgroundColor = "#fce8e6";
            errorMsg.style.display = 'block';
        }
    } catch (error) {
        console.log('Error connecting to the API:', error);
        errorMsg.textContent = "Could not connect to the server.";
        errorMsg.style.color = "#d93025";
        errorMsg.style.backgroundColor = "#fce8e6";
        errorMsg.style.display = 'block';
    }
});