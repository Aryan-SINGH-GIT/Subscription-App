// Authentication Module

// Check if user is authenticated
function isAuthenticated() {
    return !!api.getToken();
}

// Require authentication (redirect to login if not authenticated)
function requireAuth() {
    if (!isAuthenticated()) {
        // Use replace to prevent back button issues
        window.location.replace('index.html');
        return false;
    }
    return true;
}

// Logout
function logout() {
    // Remove tokens from storage
    api.removeToken();
    
    // Clear any cached user data
    try {
        localStorage.removeItem('user_data');
        sessionStorage.clear();
    } catch (e) {
        // Ignore storage errors
    }
    
    // Show logout message if toast function is available
    if (typeof showToast === 'function') {
        showToast('Logged out successfully', 'success');
        // Wait a moment for toast to show, then redirect
        setTimeout(() => {
            window.location.replace('index.html');
        }, 500);
    } else {
        // If no toast function, redirect immediately
        window.location.replace('index.html');
    }
}

// Login
async function login(username, password) {
    try {
        const data = await api.post('/auth/token/', { username, password }, { auth: false });
        api.setToken(data.access);
        api.setRefreshToken(data.refresh);
        return { success: true };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

// Register
async function register(username, email, password) {
    try {
        const data = await api.post('/auth/register/', {
            username,
            email,
            password,
            password_confirm: password
        }, { auth: false });

        // Auto-login after registration
        const loginResult = await login(username, password);
        return loginResult;
    } catch (error) {
        return { success: false, error: error.message };
    }
}

// Get current user info
async function getCurrentUser() {
    try {
        return await api.get('/auth/profile/');
    } catch (error) {
        console.error('Failed to get user:', error);
        return null;
    }
}
