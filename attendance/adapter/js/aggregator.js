'use strict';

/**
 * Aggregator
 *
 * Groups multiple Zoom connection segments (same person, same meeting)
 * into a single attendance record with total minutes per meeting-half.
 *
 * Accepts optional maps to override break points and effective start times.
 */
const Aggregator = {

    /**
     * @param {Array} meetings
     * @param {Map<number, Date>} [breakPoints]
     * @param {Map<number, Date>} [effectiveStarts]
     * @returns {Array}
     */
    aggregate(meetings, breakPoints, effectiveStarts) {
        const records = [];

        for (let i = 0; i < meetings.length; i++) {
            const meeting = meetings[i];
            if (meeting.segments.length === 0) continue;

            const effStart = (effectiveStarts && effectiveStarts.get(i)) || meeting.startTime;

            const bp = breakPoints ? breakPoints.get(i) : null;
            let firstEnd, secondStart;

            if (bp) {
                firstEnd = bp;
                secondStart = bp;
            } else {
                const breakInfo = BreakDetector.detect(meeting);
                if (breakInfo) {
                    firstEnd = breakInfo.breakStart;
                    secondStart = breakInfo.breakEnd;
                } else {
                    const mid = new Date(
                        (effStart.getTime() + meeting.endTime.getTime()) / 2
                    );
                    firstEnd = mid;
                    secondStart = mid;
                }
            }

            const durationFirst = (firstEnd - effStart) / 60000;
            const durationSecond = (meeting.endTime - secondStart) / 60000;

            const groups = this._groupByParticipant(meeting.segments);

            for (const [, segments] of groups) {
                const first = segments[0];

                let minFirst = 0;
                let minSecond = 0;

                for (const seg of segments) {
                    minFirst += this._overlap(seg.joinTime, seg.leaveTime, effStart, firstEnd);
                    minSecond += this._overlap(seg.joinTime, seg.leaveTime, secondStart, meeting.endTime);
                }

                records.push({
                    course: meeting.course,
                    meetingId: meeting.meetingId,
                    date: meeting.startTime,
                    meetingStart: meeting.startTime,
                    meetingEnd: meeting.endTime,
                    meetingDuration: meeting.durationMinutes,
                    firstName: first.firstName,
                    lastName: first.lastName,
                    email: first.email,
                    minutesFirstHalf: this._round1(minFirst),
                    minutesSecondHalf: this._round1(minSecond),
                    durationFirstHalf: this._round1(durationFirst),
                    durationSecondHalf: this._round1(durationSecond),
                    totalMinutes: this._round1(minFirst + minSecond),
                    segmentCount: segments.length,
                    _segments: segments.map(s => ({
                        joinTime: s.joinTime,
                        leaveTime: s.leaveTime
                    })),
                    _meetingIndex: i,
                    _firstHalfEnd: firstEnd,
                    _secondHalfStart: secondStart
                });
            }
        }

        return records;
    },

    // ------------------------------------------------------------------

    _groupByParticipant(segments) {
        const groups = new Map();
        for (const seg of segments) {
            const key = seg.email || seg.fullName;
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(seg);
        }
        return groups;
    },

    _overlap(segStart, segEnd, rangeStart, rangeEnd) {
        const start = Math.max(segStart.getTime(), rangeStart.getTime());
        const end = Math.min(segEnd.getTime(), rangeEnd.getTime());
        return Math.max(0, (end - start) / 60000);
    },

    _round1(n) {
        return Math.round(n * 10) / 10;
    }
};
