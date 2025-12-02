/**
 * Google OAuth Module - PKCE Flow
 *
 * Professional, reusable OAuth 2.0 implementation with PKCE.
 * Can be used for any Google API (Calendar, Drive, Gmail, etc.)
 * by changing scopes in config.
 *
 * Features:
 * - PKCE flow (no client secret needed)
 * - Token auto-refresh
 * - localStorage persistence
 * - Event-driven architecture
 *
 * Usage:
 *   const auth = new GoogleOAuth(GOOGLE_OAUTH_CONFIG);
 *   await auth.authorize();
 *   const token = await auth.getAccessToken();
 */

class GoogleOAuth {
    constructor(config) {
        this.config = config;
        this.tokenKey = 'google_oauth_token';
        this.listeners = {
            'authorized': [],
            'unauthorized': [],
            'error': []
        };

        // Check if already authorized on init
        this._checkStoredToken();
    }

    /**
     * Check if user is currently authorized
     */
    isAuthorized() {
        const token = this._getStoredToken();
        return token && token.access_token && !this._isTokenExpired(token);
    }

    /**
     * Start OAuth authorization flow
     * Opens popup window for user to authorize
     */
    async authorize() {
        try {
            // Generate PKCE challenge
            const codeVerifier = this._generateCodeVerifier();
            const codeChallenge = await this._generateCodeChallenge(codeVerifier);

            // Store code verifier for later
            sessionStorage.setItem('pkce_code_verifier', codeVerifier);

            // Build authorization URL
            const authUrl = this._buildAuthorizationUrl(codeChallenge);

            // Open popup for authorization
            const popup = window.open(authUrl, 'Google Authorization',
                'width=500,height=600,left=100,top=100');

            // Wait for authorization code
            const code = await this._waitForAuthorizationCode(popup);

            // Exchange code for tokens
            await this._exchangeCodeForTokens(code, codeVerifier);

            this._emit('authorized');
            return true;

        } catch (error) {
            console.error('Authorization error:', error);
            this._emit('error', error);
            throw error;
        }
    }

    /**
     * Get valid access token (auto-refresh if needed)
     */
    async getAccessToken() {
        const token = this._getStoredToken();

        if (!token || !token.access_token) {
            throw new Error('Not authorized. Please call authorize() first.');
        }

        // If token is expired, refresh it
        if (this._isTokenExpired(token)) {
            if (token.refresh_token) {
                await this._refreshAccessToken(token.refresh_token);
                return this._getStoredToken().access_token;
            } else {
                // No refresh token, need to re-authorize
                this._clearStoredToken();
                this._emit('unauthorized');
                throw new Error('Token expired and no refresh token available. Please re-authorize.');
            }
        }

        return token.access_token;
    }

    /**
     * Revoke authorization and clear tokens
     */
    async logout() {
        const token = this._getStoredToken();

        if (token && token.access_token) {
            // Revoke token at Google
            try {
                await fetch(`https://oauth2.googleapis.com/revoke?token=${token.access_token}`, {
                    method: 'POST'
                });
            } catch (error) {
                console.error('Error revoking token:', error);
            }
        }

        this._clearStoredToken();
        this._emit('unauthorized');
    }

    /**
     * Add event listener
     * Events: 'authorized', 'unauthorized', 'error'
     */
    on(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event].push(callback);
        }
    }

    // ============================================================================
    // PRIVATE METHODS
    // ============================================================================

    _checkStoredToken() {
        if (this.isAuthorized()) {
            this._emit('authorized');
        }
    }

    _buildAuthorizationUrl(codeChallenge) {
        const params = new URLSearchParams({
            client_id: this.config.clientId,
            redirect_uri: this.config.redirectUri,
            response_type: 'code',
            scope: this.config.scopes.join(' '),
            code_challenge: codeChallenge,
            code_challenge_method: 'S256',
            access_type: 'offline',  // Request refresh token
            prompt: 'consent'  // Force consent screen to get refresh token
        });

        return `${this.config.authorizationEndpoint}?${params.toString()}`;
    }

    async _waitForAuthorizationCode(popup) {
        return new Promise((resolve, reject) => {
            // Listen for redirect back to our app
            const checkClosed = setInterval(() => {
                if (popup.closed) {
                    clearInterval(checkClosed);
                    reject(new Error('Authorization cancelled'));
                }
            }, 1000);

            // Listen for message from popup
            const messageHandler = (event) => {
                // Verify origin
                if (event.origin !== window.location.origin) return;

                if (event.data.type === 'oauth_code') {
                    clearInterval(checkClosed);
                    window.removeEventListener('message', messageHandler);
                    popup.close();
                    resolve(event.data.code);
                } else if (event.data.type === 'oauth_error') {
                    clearInterval(checkClosed);
                    window.removeEventListener('message', messageHandler);
                    popup.close();
                    reject(new Error(event.data.error));
                }
            };

            window.addEventListener('message', messageHandler);

            // Timeout after 5 minutes
            setTimeout(() => {
                clearInterval(checkClosed);
                if (!popup.closed) popup.close();
                reject(new Error('Authorization timeout'));
            }, 5 * 60 * 1000);
        });
    }

    async _exchangeCodeForTokens(code, codeVerifier) {
        const response = await fetch(this.config.tokenEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: new URLSearchParams({
                client_id: this.config.clientId,
                code: code,
                code_verifier: codeVerifier,
                grant_type: 'authorization_code',
                redirect_uri: this.config.redirectUri
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Token exchange failed: ${error.error_description || error.error}`);
        }

        const tokens = await response.json();

        // Store tokens with expiry timestamp
        const tokenData = {
            access_token: tokens.access_token,
            refresh_token: tokens.refresh_token,
            expires_at: Date.now() + (tokens.expires_in * 1000),
            scope: tokens.scope
        };

        this._storeToken(tokenData);
    }

    async _refreshAccessToken(refreshToken) {
        const response = await fetch(this.config.tokenEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: new URLSearchParams({
                client_id: this.config.clientId,
                refresh_token: refreshToken,
                grant_type: 'refresh_token'
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Token refresh failed: ${error.error_description || error.error}`);
        }

        const tokens = await response.json();

        // Update stored token
        const currentToken = this._getStoredToken();
        const tokenData = {
            access_token: tokens.access_token,
            refresh_token: tokens.refresh_token || currentToken.refresh_token,  // Keep old if not provided
            expires_at: Date.now() + (tokens.expires_in * 1000),
            scope: tokens.scope
        };

        this._storeToken(tokenData);
    }

    _generateCodeVerifier() {
        const array = new Uint8Array(32);
        crypto.getRandomValues(array);
        return this._base64URLEncode(array);
    }

    async _generateCodeChallenge(verifier) {
        const encoder = new TextEncoder();
        const data = encoder.encode(verifier);
        const hash = await crypto.subtle.digest('SHA-256', data);
        return this._base64URLEncode(new Uint8Array(hash));
    }

    _base64URLEncode(buffer) {
        const base64 = btoa(String.fromCharCode(...buffer));
        return base64
            .replace(/\+/g, '-')
            .replace(/\//g, '_')
            .replace(/=/g, '');
    }

    _storeToken(tokenData) {
        localStorage.setItem(this.tokenKey, JSON.stringify(tokenData));
    }

    _getStoredToken() {
        const stored = localStorage.getItem(this.tokenKey);
        return stored ? JSON.parse(stored) : null;
    }

    _clearStoredToken() {
        localStorage.removeItem(this.tokenKey);
    }

    _isTokenExpired(token) {
        if (!token.expires_at) return true;
        // Consider expired if less than 5 minutes remaining
        return Date.now() >= (token.expires_at - 5 * 60 * 1000);
    }

    _emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => callback(data));
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GoogleOAuth;
}
