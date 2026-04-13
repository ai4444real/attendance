'use strict';

/**
 * Presence Rules
 *
 * ISOLATED MODULE - Business rules for determining attendance status.
 *
 * Current rule:
 *   The meeting is split in two halves (midpoint).
 *   If a participant was present >= 80% of a half, they count as "present" for that half.
 *
 * !! MODIFY THIS FILE when attendance rules change !!
 * !! Nothing else in the codebase depends on HOW the decision is made, only on the result !!
 */
const PresenceRules = {

    /** Minimum fraction of a half to be considered "present" for that half */
    threshold: 0.8,

    /**
     * Determine attendance status for a participant.
     *
     * @param {number} minutesFirstHalf  - Minutes present in first half
     * @param {number} minutesSecondHalf - Minutes present in second half
     * @param {number} durationFirstHalf - Total duration of first half (minutes)
     * @param {number} durationSecondHalf - Total duration of second half (minutes)
     * @returns {string} "presente" | "prima_meta" | "seconda_meta" | "assente"
     */
    determine(minutesFirstHalf, minutesSecondHalf, durationFirstHalf, durationSecondHalf, threshold) {
        const t = (threshold !== undefined) ? threshold : this.threshold;

        const firstOk = durationFirstHalf > 0 &&
            (minutesFirstHalf / durationFirstHalf) >= t;

        const secondOk = durationSecondHalf > 0 &&
            (minutesSecondHalf / durationSecondHalf) >= t;

        if (firstOk && secondOk) return 'presente';
        if (firstOk) return 'prima_meta';
        if (secondOk) return 'seconda_meta';
        return 'assente';
    }
};
