'use strict';

/**
 * Break Detector
 *
 * ISOLATED MODULE - Detects the main break/split in a meeting.
 *
 * Two strategies (tried in order):
 *
 *   1. Valley: look for a period where most people are disconnected.
 *      Works when there's a real break (everyone leaves Zoom).
 *
 *   2. Boundary: look for a moment where many segments end simultaneously.
 *      Works when Zoom stays open but the host splits the session
 *      (breakout rooms, pause, etc.) — people get new segments instantly.
 *
 * If neither strategy finds anything → returns null → aggregator uses midpoint.
 *
 * !! MODIFY THIS FILE to tune break detection !!
 */
const BreakDetector = {

    /** Strategy 1 config */
    valleyDropThreshold: 0.15,  // count must drop below 15% of peak
    valleyMinMinutes: 5,        // valley must last at least 5 min

    /** Strategy 2 config */
    boundaryWindowSec: 60,      // cluster leave-times within 60 seconds
    boundaryMinParticipants: 0.4, // cluster must include 40%+ of participants

    /**
     * Detect the break in a meeting.
     *
     * @param {Object} meeting - Parsed meeting with .segments[], .startTime, .endTime
     * @returns {{ breakStart: Date, breakEnd: Date } | null}
     */
    detect(meeting) {
        const segs = meeting.segments;
        if (!segs || segs.length === 0) return null;

        // Strategy 1: real disconnection valley
        const valley = this._detectValley(meeting);
        if (valley) return valley;

        // Strategy 2: synchronous segment boundary
        const boundary = this._detectBoundary(meeting);
        if (boundary) return boundary;

        return null;
    },

    // ------------------------------------------------------------------
    // Strategy 1: Connection count valley
    // ------------------------------------------------------------------

    _detectValley(meeting) {
        const segs = meeting.segments;
        const startMs = meeting.startTime.getTime();
        const endMs = meeting.endTime.getTime();
        const step = 60000;

        const timeline = [];
        for (let t = startMs; t <= endMs; t += step) {
            let count = 0;
            for (const seg of segs) {
                if (seg.joinTime.getTime() <= t && seg.leaveTime.getTime() > t) {
                    count++;
                }
            }
            timeline.push({ time: t, count });
        }

        const peak = Math.max(...timeline.map(p => p.count));
        if (peak < 2) return null;

        const cutoff = peak * this.valleyDropThreshold;
        const duration = endMs - startMs;
        let best = null;
        let valleyStart = null;

        for (const point of timeline) {
            if (point.count <= cutoff) {
                if (valleyStart === null) valleyStart = point.time;
            } else {
                if (valleyStart !== null) {
                    const midValley = (valleyStart + point.time) / 2;
                    const relPos = (midValley - startMs) / duration;
                    if (relPos >= 0.15 && relPos <= 0.85) {
                        const dur = point.time - valleyStart;
                        if (!best || dur > (best.endMs - best.startMs)) {
                            best = { startMs: valleyStart, endMs: point.time };
                        }
                    }
                    valleyStart = null;
                }
            }
        }
        if (valleyStart !== null) {
            const midValley = (valleyStart + endMs) / 2;
            const relPos = (midValley - startMs) / duration;
            if (relPos >= 0.15 && relPos <= 0.85) {
                const dur = endMs - valleyStart;
                if (!best || dur > (best.endMs - best.startMs)) {
                    best = { startMs: valleyStart, endMs: endMs };
                }
            }
        }

        if (!best) return null;
        if ((best.endMs - best.startMs) / 60000 < this.valleyMinMinutes) return null;

        return {
            breakStart: new Date(best.startMs),
            breakEnd: new Date(best.endMs)
        };
    },

    // ------------------------------------------------------------------
    // Strategy 2: Synchronous segment boundary
    // ------------------------------------------------------------------

    _detectBoundary(meeting) {
        const segs = meeting.segments;
        const startMs = meeting.startTime.getTime();
        const endMs = meeting.endTime.getTime();
        const duration = endMs - startMs;

        // Unique participants
        const allParticipants = new Set();
        for (const seg of segs) {
            allParticipants.add(seg.email || seg.fullName);
        }
        if (allParticipants.size < 3) return null;

        // Collect leave events with participant identity
        const leaveEvents = segs
            .map(seg => ({
                time: seg.leaveTime.getTime(),
                who: seg.email || seg.fullName
            }))
            .sort((a, b) => a.time - b.time);

        // Sliding window: find the window with the most unique participants leaving
        const windowMs = this.boundaryWindowSec * 1000;
        let bestTime = null;
        let bestCount = 0;

        for (let i = 0; i < leaveEvents.length; i++) {
            const wStart = leaveEvents[i].time;

            // Skip if too close to meeting start or end (within 15%)
            const relPos = (wStart - startMs) / duration;
            if (relPos < 0.15 || relPos > 0.85) continue;

            // Count unique participants leaving within the window
            const inWindow = new Set();
            const times = [];
            for (let j = i; j < leaveEvents.length && leaveEvents[j].time <= wStart + windowMs; j++) {
                inWindow.add(leaveEvents[j].who);
                times.push(leaveEvents[j].time);
            }

            if (inWindow.size > bestCount) {
                bestCount = inWindow.size;
                // Use the median time in the cluster
                bestTime = times[Math.floor(times.length / 2)];
            }
        }

        // Must include a significant portion of participants
        if (bestCount < allParticipants.size * this.boundaryMinParticipants) return null;

        // Verify connection count actually drops around this time.
        // If people just reconnect immediately, it's not a real break.
        const checkMs = bestTime;
        const beforeMs = checkMs - 2 * 60000;
        const afterMs = checkMs + 2 * 60000;
        let countBefore = 0, countAfter = 0;
        for (const seg of segs) {
            const jt = seg.joinTime.getTime(), lt = seg.leaveTime.getTime();
            if (jt <= beforeMs && lt > beforeMs) countBefore++;
            if (jt <= afterMs && lt > afterMs) countAfter++;
        }
        const peakCount = allParticipants.size;
        // Connection count must drop to below 50% of participants in the 2 min after
        if (countAfter > peakCount * 0.5 && countBefore > peakCount * 0.5) return null;

        // This is a point-in-time boundary (zero-duration "break")
        return {
            breakStart: new Date(bestTime),
            breakEnd: new Date(bestTime)
        };
    }
};
