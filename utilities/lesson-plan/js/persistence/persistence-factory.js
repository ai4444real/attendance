/**
 * Factory for creating persistence repository instances
 * Handles repository creation based on configuration
 */
class PersistenceFactory {
    /**
     * Configuration key for localStorage
     */
    static STORAGE_KEY = 'persistence_type';

    /**
     * Default repository type
     */
    static DEFAULT_TYPE = 'filesystem';

    /**
     * Create repository instance based on type
     * @param {string} type - Repository type ('filesystem', 'supabase', etc.)
     * @returns {Repository} Repository instance
     * @throws {Error} If repository type is not supported
     */
    static create(type = null) {
        // Use provided type, or get from config, or use default
        const repositoryType = type || this.getConfiguredType();

        switch (repositoryType) {
            case 'filesystem':
                return new FileSystemRepository();

            case 'supabase':
                // Future implementation
                throw new Error('Supabase repository not yet implemented. Coming soon!');

            default:
                console.warn(`Unknown repository type: ${repositoryType}, falling back to filesystem`);
                return new FileSystemRepository();
        }
    }

    /**
     * Get configured repository type from localStorage
     * @returns {string} Repository type
     */
    static getConfiguredType() {
        try {
            return localStorage.getItem(this.STORAGE_KEY) || this.DEFAULT_TYPE;
        } catch (e) {
            console.warn('Could not access localStorage, using default repository type');
            return this.DEFAULT_TYPE;
        }
    }

    /**
     * Set repository type in localStorage
     * @param {string} type - Repository type to save
     */
    static setConfiguredType(type) {
        try {
            localStorage.setItem(this.STORAGE_KEY, type);
        } catch (e) {
            console.error('Could not save repository type to localStorage:', e);
        }
    }

    /**
     * Get list of available repository types
     * @returns {Array<Object>} Array of {type, name, available} objects
     */
    static getAvailableTypes() {
        return [
            {
                type: 'filesystem',
                name: 'Locale (File sul tuo computer)',
                available: true,
                capabilities: {
                    browse: false,
                    search: false
                }
            },
            {
                type: 'supabase',
                name: 'Remoto (Database cloud)',
                available: false,  // Not yet implemented
                capabilities: {
                    browse: true,
                    search: true
                }
            }
        ];
    }
}
