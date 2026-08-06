// Utility Functions
// Shared utility functions for time, date, and storage operations

// localStorage keys constants
const STORAGE_KEYS = {
    LESSON_PLAN: 'currentLessonPlan',
    COURSE: 'currentCourse',
    METHOD_OPTIONS: 'methodOptions',
    TOOLS_OPTIONS: 'toolsOptions'
};

const TimeUtils = {
    /**
     * Convert HH:MM string to minutes since midnight
     * @param {string} timeString - Time in HH:MM format
     * @returns {number} Minutes since midnight, or 0 if invalid
     */
    parseTime(timeString) {
        if (!timeString || typeof timeString !== 'string') return 0;

        const parts = timeString.split(':');
        if (parts.length !== 2) return 0;

        const [hours, minutes] = parts.map(n => parseInt(n, 10));
        if (isNaN(hours) || isNaN(minutes)) return 0;

        return hours * 60 + minutes;
    },

    /**
     * Convert minutes since midnight to HH:MM string
     * @param {number} totalMinutes - Minutes since midnight
     * @returns {string} Time in HH:MM format
     */
    formatTime(totalMinutes) {
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    },

    /**
     * Convert YYYY-MM-DD date string to DD.MM.YYYY format
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @returns {string} Date in DD.MM.YYYY format, or empty string if invalid
     */
    formatDate(dateString) {
        if (!dateString || typeof dateString !== 'string') return '';

        const parts = dateString.split('-');
        if (parts.length !== 3) return dateString; // Fallback: return as-is if invalid format

        const [year, month, day] = parts;
        return `${day}.${month}.${year}`;
    },

    /**
     * Get current date formatted as DD.MM.YYYY
     * @returns {string} Current date in DD.MM.YYYY format
     */
    formatCurrentDate() {
        const today = new Date();
        const day = today.getDate().toString().padStart(2, '0');
        const month = (today.getMonth() + 1).toString().padStart(2, '0');
        const year = today.getFullYear();
        return `${day}.${month}.${year}`;
    },

    /**
     * Load and parse data from localStorage
     * @param {string} key - localStorage key to retrieve
     * @param {string} errorMessage - Error message to show if key not found
     * @returns {Object|null} Parsed JSON object, or null if error/not found
     */
    loadFromLocalStorage(key, errorMessage) {
        const stored = localStorage.getItem(key);
        if (!stored) {
            alert(errorMessage);
            window.close();
            return null;
        }

        try {
            return JSON.parse(stored);
        } catch (e) {
            console.error(`Error parsing localStorage key "${key}":`, e);
            alert('Errore nel caricamento dei dati');
            window.close();
            return null;
        }
    }
};
