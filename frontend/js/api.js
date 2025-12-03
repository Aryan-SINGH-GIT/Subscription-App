// API Client Module
// Auto-detect API base URL (works for both localhost and production)
const getBaseURL = () => {
    // If running on same domain, use relative URL
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:8000/api';
    }
    // Production: use same origin
    return `${window.location.origin}/api`;
};

const API_BASE_URL = getBaseURL();

class APIClient {
    constructor() {
        this.baseURL = API_BASE_URL;
        this.token = this.getToken();
    }

    // Token management
    getToken() {
        return localStorage.getItem('access_token');
    }

    setToken(token) {
        localStorage.setItem('access_token', token);
        this.token = token;
    }

    removeToken() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        this.token = null;
    }

    getRefreshToken() {
        return localStorage.getItem('refresh_token');
    }

    setRefreshToken(token) {
        localStorage.setItem('refresh_token', token);
    }

    // Build headers
    getHeaders(includeAuth = true) {
        const headers = {
            'Content-Type': 'application/json',
        };

        if (includeAuth && this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        return headers;
    }

    // Generic request method
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            ...options,
            headers: {
                ...this.getHeaders(options.auth !== false),
                ...options.headers,
            },
        };

        try {
            const response = await fetch(url, config);

            // Handle 401 - Token expired
            if (response.status === 401 && this.token) {
                // Try to refresh token
                const refreshed = await this.refreshAccessToken();
                if (refreshed) {
                    // Retry the original request
                    config.headers['Authorization'] = `Bearer ${this.token}`;
                    const retryResponse = await fetch(url, config);
                    return this.handleResponse(retryResponse);
                } else {
                    // Refresh failed, redirect to login
                    this.removeToken();
                    window.location.href = '/index.html';
                    throw new Error('Session expired. Please login again.');
                }
            }

            return this.handleResponse(response);
        } catch (error) {
            console.error('API Request Error:', error);
            throw error;
        }
    }

    async handleResponse(response) {
        const contentType = response.headers.get('content-type');

        // Handle PDF downloads and other binary responses
        if (contentType && contentType.includes('application/pdf')) {
            return response.blob();
        }

        // Handle JSON responses
        if (contentType && contentType.includes('application/json')) {
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || data.message || 'Request failed');
            }

            return data;
        }

        // Handle empty responses
        if (response.status === 204) {
            return null;
        }

        // Handle other response types
        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }

        return response.text();
    }

    async refreshAccessToken() {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) return false;

        try {
            const response = await fetch(`${this.baseURL}/auth/token/refresh/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh: refreshToken }),
            });

            if (response.ok) {
                const data = await response.json();
                this.setToken(data.access);
                return true;
            }
            return false;
        } catch (error) {
            console.error('Token refresh failed:', error);
            return false;
        }
    }

    // HTTP Methods
    get(endpoint, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'GET',
        });
    }

    post(endpoint, data, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    put(endpoint, data, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    patch(endpoint, data, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    delete(endpoint, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'DELETE',
        });
    }

    // Download file (for PDFs)
    async downloadFile(endpoint, filename) {
        const blob = await this.get(endpoint);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }
}

// Create singleton instance
const api = new APIClient();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
}
