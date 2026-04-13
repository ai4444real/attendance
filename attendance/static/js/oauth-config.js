/**
 * Google OAuth Configuration
 *
 * Loads OAuth configuration from backend to avoid hardcoding credentials.
 * The backend provides the client ID and OAuth endpoints.
 */

let GOOGLE_OAUTH_CONFIG = null;

/**
 * Load OAuth configuration from backend
 * @returns {Promise<Object>} OAuth configuration
 */
async function loadOAuthConfig() {
    if (GOOGLE_OAUTH_CONFIG) {
        return GOOGLE_OAUTH_CONFIG;
    }

    try {
        const response = await fetch('/api/oauth/config');
        if (!response.ok) {
            throw new Error('Failed to load OAuth config from backend');
        }

        const config = await response.json();

        // Add dynamic redirect URI
        config.redirectUri = window.location.origin + config.redirectUri;

        GOOGLE_OAUTH_CONFIG = config;
        return config;
    } catch (error) {
        console.error('Error loading OAuth config:', error);
        throw error;
    }
}

// Export per uso in altri module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { loadOAuthConfig };
}
