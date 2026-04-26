// 1. On page load, verify login
window.onload = function() {
    let userEmail = sessionStorage.getItem('userEmail');
    
    // Security check
    if (userEmail == null || userEmail == "") {
        window.location.href = 'login.html'; 
        return;
    }

    // Split the email at the '@' symbol, and grab the first part (index 0)
    let username = userEmail.split('@')[0];
    document.getElementById('display-email').textContent = username;
    loadSubscriptions(userEmail);
};

// Helper function to fix the apostrophe bug for songs like "Don't Stop Believin'"
function escapeApostrophe(text) {
    return text.split("'").join("\\'"); 
}

// 2. Load Subscriptions
async function loadSubscriptions(email) {
    let listDiv = document.getElementById('subscription-list');
    listDiv.innerHTML = 'Loading...';

    try {
        // Add a timestamp to stop the browser from keeping old data
        let timestamp = new Date().getTime();
        let url = API_BASE_URL + '/subscriptions?email=' + email + '&t=' + timestamp;
        
        let response = await fetch(url);
        let data = await response.json();

        // Check if list is empty
        if (data.subscriptions == null || data.subscriptions.length == 0) {
            listDiv.innerHTML = '<p>No subscriptions found.</p>';
            return;
        }

        listDiv.innerHTML = ''; 
        
        // Loop through each song using a standard loop
        for (let i = 0; i < data.subscriptions.length; i++) {
            let song = data.subscriptions[i];
            let card = document.createElement('div');
            card.className = 'song-card';
            
            // Pick the S3 image if we have it, otherwise use the normal one
            let imgSource = song.image_url;
            if (song.presigned_url) {
                imgSource = song.presigned_url;
            }

            // Make the text safe for the button click
            let safeTitle = escapeApostrophe(song.title);
            let safeArtist = escapeApostrophe(song.artist);

            card.innerHTML = `
                <img src="${imgSource}" alt="${song.artist}">
                <div>
                    <strong>${song.title}</strong><br>
                    ${song.artist} (${song.year}) - ${song.album}<br>
                    <button onclick="removeSubscription('${safeTitle}', '${safeArtist}', '${song.year}')">Remove</button>
                </div>
            `;
            listDiv.appendChild(card);
        }
    } catch (error) {
        listDiv.innerHTML = '<p style="color:red;">Error loading subscriptions.</p>';
        console.log("Error:", error);
    }
}

// 3. Remove Subscription
async function removeSubscription(title, artist, year) {
    let email = sessionStorage.getItem('userEmail');
    
    try {
        let response = await fetch(API_BASE_URL + '/subscriptions', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                "email": email, 
                "title": title, 
                "artist": artist, 
                "year": year 
            })
        });

        if (response.ok == true) {
            loadSubscriptions(email); 
        } else {
            alert("Failed to remove subscription.");
        }
    } catch (error) {
        console.log("Error:", error);
    }
}

// 4. Search Query
document.getElementById('query-form').addEventListener('submit', async function(event) {
    event.preventDefault();

    let msgDiv = document.getElementById('query-message');
    let resultsDiv = document.getElementById('query-results');
    
    msgDiv.textContent = '';
    resultsDiv.innerHTML = 'Searching...';

    let title = document.getElementById('q-title').value.trim();
    let artist = document.getElementById('q-artist').value.trim();
    let year = document.getElementById('q-year').value.trim();
    let album = document.getElementById('q-album').value.trim();

    // Check if they left everything blank
    if (title == "" && artist == "" && year == "" && album == "") {
        resultsDiv.innerHTML = '';
        msgDiv.textContent = "Please fill in at least one field to search.";
        return;
    }

    // Build the query parameters
    let params = new URLSearchParams();
    if (title != "") params.append('title', title);
    if (artist != "") params.append('artist', artist);
    if (year != "") params.append('year', year);
    if (album != "") params.append('album', album);

    let searchUrl = API_BASE_URL + '/music/query?' + params.toString();

    try {
        let response = await fetch(searchUrl);
        let data = await response.json();

        if (data.message && data.message.includes("No result is retrieved")) {
            resultsDiv.innerHTML = '';
            msgDiv.textContent = "No result is retrieved. Please query again";
            return;
        }

        resultsDiv.innerHTML = ''; 

        if (data.results && data.results.length > 0) {
            for (let i = 0; i < data.results.length; i++) {
                let song = data.results[i];
                let card = document.createElement('div');
                card.className = 'song-card';
                
                let imgSource = song.image_url;
                if (song.presigned_url) {
                    imgSource = song.presigned_url;
                }

                let safeTitle = escapeApostrophe(song.title);
                let safeArtist = escapeApostrophe(song.artist);
                let safeAlbum = escapeApostrophe(song.album);

                card.innerHTML = `
                    <img src="${imgSource}" alt="${song.artist}">
                    <div>
                        <strong>${song.title}</strong>
                        <span>${song.artist} (${song.year}) - ${song.album}</span>
                        <button onclick="addSubscription('${safeTitle}', '${safeArtist}', '${song.year}', '${safeAlbum}', '${song.image_url}')">Subscribe</button>
                    </div>
                `;
                resultsDiv.appendChild(card);
            }
        }

    } catch (error) {
        resultsDiv.innerHTML = '';
        msgDiv.textContent = "Error connecting to the search service.";
        console.log("Error:", error);
    }
});

// 5. Add Subscription
window.addSubscription = async function(title, artist, year, album, image_url) {
    let email = sessionStorage.getItem('userEmail');
    
    try {
        let response = await fetch(API_BASE_URL + '/subscriptions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                "email": email, 
                "title": title, 
                "artist": artist, 
                "year": year, 
                "album": album, 
                "image_url": image_url 
            })
        });

        if (response.status == 201) {
            loadSubscriptions(email); 
        } else {
            let data = await response.json();
            alert("Failed to subscribe: " + data.error);
        }
    } catch (error) {
         alert("Error subscribing to song.");
         console.log("Error:", error);
    }
};