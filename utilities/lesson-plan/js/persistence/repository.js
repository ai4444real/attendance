/**
 * Abstract base class for persistence repositories
 * Defines the contract for all persistence implementations
 */
class Repository {
    /**
     * Save an entity to the persistence layer
     * @param {Object} entity - The entity to save (LessonPlan or Course)
     * @param {string} type - Entity type ('lesson_plan' or 'course')
     * @returns {Promise<void>}
     */
    async save(entity, type) {
        throw new Error('Method save() must be implemented');
    }

    /**
     * Load an entity by ID from the persistence layer
     * @param {string} id - The entity ID
     * @param {string} type - Entity type ('lesson_plan' or 'course')
     * @returns {Promise<Object>} The loaded entity
     */
    async load(id, type) {
        throw new Error('Method load() must be implemented');
    }

    /**
     * Delete an entity by ID
     * @param {string} id - The entity ID
     * @param {string} type - Entity type ('lesson_plan' or 'course')
     * @returns {Promise<void>}
     */
    async delete(id, type) {
        throw new Error('Method delete() must be implemented');
    }

    /**
     * Load all entities of a given type
     * @param {string} type - Entity type ('lesson_plan' or 'course')
     * @returns {Promise<Array>} Array of entities
     * @note Not all repositories support this (e.g., filesystem doesn't)
     */
    async loadAll(type) {
        throw new Error('Method loadAll() not supported by this repository');
    }

    /**
     * Search entities by query
     * @param {Object} query - Search criteria
     * @param {string} type - Entity type ('lesson_plan' or 'course')
     * @returns {Promise<Array>} Array of matching entities
     * @note Not all repositories support this (e.g., filesystem doesn't)
     */
    async search(query, type) {
        throw new Error('Method search() not supported by this repository');
    }

    /**
     * Get repository capabilities
     * @returns {Object} Capabilities object { browse: boolean, search: boolean }
     */
    get capabilities() {
        return {
            browse: false,
            search: false
        };
    }

    /**
     * Get repository type identifier
     * @returns {string} Repository type ('filesystem', 'supabase', etc.)
     */
    get type() {
        throw new Error('Property type must be implemented');
    }
}
