// Segment Manager
// Handles all segment-related operations: add, remove and time calculations

class SegmentManager {
    constructor(methodOptions, toolsOptions) {
        this.segmentCounter = 0;
        this.methodOptions = methodOptions;
        this.toolsOptions = toolsOptions;
    }

    renumberSegments() {
        const segments = document.querySelectorAll('.segment-item');
        segments.forEach((segment, index) => {
            const segmentNumber = index + 1;

            // Update segment number display
            const numberSpan = segment.querySelector('.segment-number');
            numberSpan.textContent = `Segmento ${segmentNumber}`;

            // Update segment data attribute for consistency
            segment.dataset.segmentId = segmentNumber;

            // Update time display IDs to ensure they're unique and sequential
            const startTimeSpan = segment.querySelector('.start-time');
            const endTimeSpan = segment.querySelector('.end-time');
            if (startTimeSpan) startTimeSpan.id = `startTime_${segmentNumber}`;
            if (endTimeSpan) endTimeSpan.id = `endTime_${segmentNumber}`;

            const moveUpButton = segment.querySelector('.segment-move-up');
            const moveDownButton = segment.querySelector('.segment-move-down');
            const removeButton = segment.querySelector('.segment-remove');
            moveUpButton.disabled = index === 0;
            moveDownButton.disabled = index === segments.length - 1;
            moveUpButton.onclick = () => lessonPlanManager.moveSegment(segmentNumber, -1);
            moveDownButton.onclick = () => lessonPlanManager.moveSegment(segmentNumber, 1);
            removeButton.onclick = () => lessonPlanManager.removeSegment(segmentNumber);
        });
    }

    updateSegmentTimes() {
        const startTimeInput = document.getElementById('startTime');
        const startTime = startTimeInput.value;

        if (!startTime) {
            // Hide all time displays if no start time
            document.querySelectorAll('.time-display').forEach(display => {
                display.style.display = 'none';
            });
            return;
        }

        const segments = document.querySelectorAll('.segment-item');
        let currentTime = TimeUtils.parseTime(startTime);

        segments.forEach((segment, index) => {
            const durationInput = segment.querySelector('input[name="duration_min"]');
            const timeDisplay = segment.querySelector('.time-display');
            const startTimeSpan = segment.querySelector('.start-time');
            const endTimeSpan = segment.querySelector('.end-time');
            const duration = parseInt(durationInput.value, 10) || 0;

            // Show the time display
            timeDisplay.style.display = 'flex';

            // Set start time (current time before adding duration)
            startTimeSpan.textContent = TimeUtils.formatTime(currentTime);

            // Add duration to get end time
            currentTime += duration;
            endTimeSpan.textContent = TimeUtils.formatTime(currentTime);
        });
    }

    removeSegment(segmentId) {
        const segment = document.querySelector(`[data-segment-id="${segmentId}"]`);
        if (segment) {
            // Cleanup pulldown components to prevent memory leak
            if (segment.methodPulldown && typeof segment.methodPulldown.destroy === 'function') {
                segment.methodPulldown.destroy();
            }
            if (segment.toolsPulldown && typeof segment.toolsPulldown.destroy === 'function') {
                segment.toolsPulldown.destroy();
            }

            segment.remove();
        }

        // Rinumera i segmenti rimanenti
        this.renumberSegments();

        // Update times after removing segment
        this.updateSegmentTimes();
    }

    moveSegment(segmentId, direction) {
        const segment = document.querySelector(`[data-segment-id="${segmentId}"]`);
        if (!segment) return;

        const sibling = direction < 0
            ? segment.previousElementSibling
            : segment.nextElementSibling;
        if (!sibling) return;

        if (direction < 0) {
            segment.parentElement.insertBefore(segment, sibling);
        } else {
            segment.parentElement.insertBefore(sibling, segment);
        }

        this.renumberSegments();
        this.updateSegmentTimes();
    }

    addInitialSegment() {
        this.addSegment();
    }

    addSegment(segmentData = null) {
        this.segmentCounter++;
        const container = document.getElementById('segmentsContainer');

        // Se non ci sono dati forniti, prova a copiare dall'ultimo segmento
        if (!segmentData) {
            const lastSegment = container.querySelector('.segment-item:last-child');
            if (lastSegment && lastSegment.methodPulldown && lastSegment.toolsPulldown) {
                const lastMethod = lastSegment.methodPulldown.getValue();
                const lastTools = lastSegment.toolsPulldown.getValue();

                if (lastMethod || lastTools) {
                    segmentData = {
                        method: lastMethod,
                        tools: lastTools ? lastTools.split(',').map(t => t.trim()) : []
                    };
                }
            }
        }

        const segmentDiv = document.createElement('div');
        segmentDiv.className = 'segment-item';
        segmentDiv.dataset.segmentId = this.segmentCounter;

        segmentDiv.innerHTML = `
            <div class="segment-header">
                <span class="segment-number">Segmento ${this.segmentCounter}</span>
                <div class="segment-actions">
                    <span class="reorder-controls" aria-label="Riordina segmento">
                        <button type="button" class="reorder-btn segment-move-up" title="Sposta su" aria-label="Sposta segmento su">↑</button>
                        <button type="button" class="reorder-btn segment-move-down" title="Sposta giù" aria-label="Sposta segmento giù">↓</button>
                    </span>
                    <button type="button" class="segment-remove">Rimuovi</button>
                </div>
            </div>

            <div class="segment-form-row">
                <div class="form-group duration-with-time">
                    <label>Durata (min) *</label>
                    <input type="number" name="duration_min" min="0" required value="${segmentData?.duration_min ? parseInt(segmentData.duration_min, 10) : ''}"
                           onchange="lessonPlanManager.updateSegmentTimes()">
                    <div class="time-display">
                        <span class="start-time" id="startTime_${this.segmentCounter}"></span>
                        <span class="time-separator">→</span>
                        <span class="end-time" id="endTime_${this.segmentCounter}"></span>
                    </div>
                </div>
                <div class="form-group">
                    <label>Argomento *</label>
                    <input type="text" name="topic" required value="${segmentData?.topic || ''}">
                </div>
                <div class="form-group">
                    <label>Metodo *</label>
                    <div class="method-pulldown-container"></div>
                </div>
            </div>

            <div class="segment-tools-row">
                <div class="form-group">
                    <label>Strumenti</label>
                    <div class="tools-pulldown-container"></div>
                </div>
            </div>
        `;

        container.appendChild(segmentDiv);
        this.renumberSegments();

        // Initialize pulldown components
        const methodContainer = segmentDiv.querySelector('.method-pulldown-container');
        const toolsContainer = segmentDiv.querySelector('.tools-pulldown-container');

        segmentDiv.methodPulldown = new PulldownComponent(methodContainer, this.methodOptions, false);
        segmentDiv.toolsPulldown = new PulldownComponent(toolsContainer, this.toolsOptions, true);

        // Set initial values if provided
        if (segmentData) {
            if (segmentData.method) {
                segmentDiv.methodPulldown.setValue(segmentData.method);
            }
            if (segmentData.tools) {
                segmentDiv.toolsPulldown.setValue(Array.isArray(segmentData.tools) ? segmentData.tools.join(', ') : segmentData.tools);
            }
        }

        // Update times after adding segment
        this.updateSegmentTimes();
    }

    parseToolsString(toolsString) {
        return toolsString
            .split(',')
            .map(tool => tool.trim())
            .filter(tool => tool.length > 0)
            .filter((tool, index, arr) => arr.indexOf(tool) === index); // Remove duplicates
    }

}
