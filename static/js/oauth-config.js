/**
 * Google OAuth Configuration
 *
 * IMPORTANTE: Questo file contiene credenziali OAuth.
 * È incluso in .gitignore per sicurezza.
 *
 * Per usare in altro progetto: copia questo file e sostituisci clientId
 */

const GOOGLE_OAUTH_CONFIG = {
    // Client ID from Google Cloud Console
    clientId: '572268474022-54j1dba72gm26n00oi42ijrhv3ielep1.apps.googleusercontent.com',

    // Client Secret from Google Cloud Console
    clientSecret: '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Your',

    // Scopes richiesti (solo lettura calendario)
    scopes: [
        'https://www.googleapis.com/auth/calendar.readonly'
    ],

    // Redirect URI (deve matchare quello in Google Cloud Console)
    redirectUri: window.location.origin + '/oauth-callback',

    // Google OAuth endpoints
    authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
    tokenEndpoint: 'https://oauth2.googleapis.com/token',

    // PKCE settings
    usePKCE: true
};

// Export per uso in altri module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GOOGLE_OAUTH_CONFIG;
}
