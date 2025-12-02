/**
 * Google Calendar API Wrapper
 *
 * Professional wrapper for Google Calendar API v3.
 * Handles authentication, error handling, and data transformation.
 *
 * Usage:
 *   const auth = new GoogleOAuth(GOOGLE_OAUTH_CONFIG);
 *   const calendar = new GoogleCalendarAPI(auth);
 *   const events = await calendar.getEvents('primary', startDate, endDate);
 */

class GoogleCalendarAPI {
    constructor(googleAuth) {
        this.auth = googleAuth;
        this.baseUrl = 'https://www.googleapis.com/calendar/v3';
    }

    /**
     * Get list of user's calendars
     * @returns {Promise<Array>} Array of calendar objects
     */
    async listCalendars() {
        const token = await this.auth.getAccessToken();

        const response = await fetch(`${this.baseUrl}/users/me/calendarList`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error(`Failed to list calendars: ${response.statusText}`);
        }

        const data = await response.json();
        return data.items || [];
    }

    /**
     * Get events from a calendar within date range
     * @param {string} calendarId - Calendar ID ('primary' for main calendar)
     * @param {Date} startDate - Start date
     * @param {Date} endDate - End date
     * @param {Object} options - Additional options
     * @returns {Promise<Array>} Array of event objects
     */
    async getEvents(calendarId = 'primary', startDate, endDate, options = {}) {
        const token = await this.auth.getAccessToken();

        // Build query parameters
        const params = new URLSearchParams({
            timeMin: startDate.toISOString(),
            timeMax: endDate.toISOString(),
            singleEvents: 'true',  // Expand recurring events
            orderBy: 'startTime',
            maxResults: options.maxResults || 2500,  // Max allowed by API
            ...options
        });

        const response = await fetch(
            `${this.baseUrl}/calendars/${encodeURIComponent(calendarId)}/events?${params}`,
            {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            }
        );

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(`Failed to get events: ${error.error?.message || response.statusText}`);
        }

        const data = await response.json();
        return data.items || [];
    }

    /**
     * Get events and extract lesson information
     * Transforms Calendar events into lesson objects for attendance system
     *
     * @param {string} calendarId - Calendar ID
     * @param {Date} startDate - Start date
     * @param {Date} endDate - End date
     * @returns {Promise<Array>} Array of lesson objects
     */
    async getLessons(calendarId = 'primary', startDate, endDate) {
        const events = await this.getEvents(calendarId, startDate, endDate);

        return events.map(event => ({
            id: event.id,
            date: event.start.dateTime || event.start.date,
            title: event.summary || 'Untitled',
            description: event.description || '',
            location: event.location || '',

            // Extract course name from title (customize parsing logic as needed)
            courseName: this._extractCourseName(event.summary),

            // Extract lesson topic from description
            topic: this._extractTopic(event.description),

            // Full event data for reference
            rawEvent: event
        }));
    }

    /**
     * Get events matching a specific course name pattern
     * @param {string} calendarId - Calendar ID
     * @param {string} coursePattern - Course name or pattern to match
     * @param {Date} startDate - Start date
     * @param {Date} endDate - End date
     * @returns {Promise<Array>} Filtered events matching course
     */
    async getCourseEvents(calendarId, coursePattern, startDate, endDate) {
        const lessons = await this.getLessons(calendarId, startDate, endDate);

        return lessons.filter(lesson =>
            lesson.courseName &&
            lesson.courseName.toLowerCase().includes(coursePattern.toLowerCase())
        );
    }

    /**
     * Get unique course names from calendar events
     * Useful for populating course dropdowns
     */
    async getUniqueCourses(calendarId = 'primary', startDate, endDate) {
        const lessons = await this.getLessons(calendarId, startDate, endDate);

        const courseNames = new Set(
            lessons
                .map(l => l.courseName)
                .filter(name => name && name.trim())
        );

        return Array.from(courseNames).sort();
    }

    // ============================================================================
    // PRIVATE METHODS - Customize these based on your calendar structure
    // ============================================================================

    /**
     * Extract course name from event title
     * Customize this logic based on how courses are named in your calendar
     *
     * Examples:
     * - "_Coaching 25 - Lezione 1" → "_Coaching 25"
     * - "FSEA 02.25: Presentazione" → "FSEA 02.25"
     * - "Master - Modulo 1" → "Master"
     *
     * @private
     */
    _extractCourseName(title) {
        if (!title) return '';

        // Try common patterns (customize as needed)

        // Pattern 1: Course name before " - " or ": "
        const match1 = title.match(/^([^:-]+)[\s]*[-:]/);
        if (match1) return match1[1].trim();

        // Pattern 2: If starts with underscore, take until first space and number
        const match2 = title.match(/^(_[A-Za-z\s]+\d+)/);
        if (match2) return match2[1].trim();

        // Default: return full title
        return title.trim();
    }

    /**
     * Extract lesson topic from description
     * Customize based on how topics are formatted in event descriptions
     *
     * @private
     */
    _extractTopic(description) {
        if (!description) return '';

        // Remove HTML tags if present
        const text = description.replace(/<[^>]*>/g, '');

        // Take first line or first 200 chars
        const firstLine = text.split('\n')[0];
        return firstLine.substring(0, 200).trim();
    }

    /**
     * Format event date for display
     * @private
     */
    _formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('it-IT', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GoogleCalendarAPI;
}
