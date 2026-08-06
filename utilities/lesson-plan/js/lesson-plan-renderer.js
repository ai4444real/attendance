// Unified Lesson Plan Renderer
class LessonPlanRenderer {
    // ============================================================================
    // INSTANCE METHODS - FORMATTING
    // ============================================================================

    formatDate(dateString) {
        // Delegate to shared TimeUtils
        return TimeUtils.formatDate(dateString);
    }

    formatObjectivesForDisplay(objectives) {
        // Convert learning objectives from list format (newline-separated) to comma-separated
        if (!objectives) return '';
        return objectives.includes('\n')
            ? objectives.split('\n').filter(obj => obj.trim()).join(', ')
            : objectives;
    }

    collectSegmentTools(plan) {
        if (!plan.segments) return [];

        const toolsSet = new Set();
        plan.segments.forEach(segment => {
            if (segment.tools && Array.isArray(segment.tools)) {
                segment.tools.forEach(tool => {
                    if (tool && tool.trim()) {
                        toolsSet.add(tool.trim());
                    }
                });
            }
        });

        return Array.from(toolsSet);
    }

    parseTime(timeString) {
        // Delegate to shared TimeUtils
        return TimeUtils.parseTime(timeString);
    }

    formatTime(totalMinutes) {
        // Delegate to shared TimeUtils
        return TimeUtils.formatTime(totalMinutes);
    }

    // ============================================================================
    // PRIVATE/UTILITY METHODS
    // ============================================================================

    _computeScheduleRows(plan) {
        // SINGLE SOURCE OF TRUTH for schedule table row logic
        // Computes schedule row data without rendering (used by both HTML string and DOM methods)

        if (!plan.segments || plan.segments.length === 0) {
            return []; // Empty array = no segments
        }

        const rows = [];
        let currentTime = null;

        // Check if we have a start time from simulation data
        if (plan.simulation && plan.simulation.start_time) {
            currentTime = this.parseTime(plan.simulation.start_time);
        }

        plan.segments.forEach((segment) => {
            // Time Range calculation
            let timeRange = '';
            if (currentTime !== null && segment.duration_min) {
                const startTimeStr = this.formatTime(currentTime);
                currentTime += parseInt(segment.duration_min, 10) || 0;
                const endTimeStr = this.formatTime(currentTime);
                timeRange = `${startTimeStr} – ${endTimeStr}`;
            } else if (segment.duration_min) {
                timeRange = `${segment.duration_min} min`;
            }

            // Extract data
            const topic = segment.topic || '';
            const method = segment.method || '';
            const tools = segment.tools && segment.tools.length > 0
                ? segment.tools.join(', ')
                : '—';

            // Detect pause
            const isPause = method.toLowerCase().includes('pausa')
                || method === '—'
                || topic.toLowerCase().includes('pausa');

            // Return row data object
            rows.push({
                timeRange,
                topic,
                method,
                tools,
                isPause
            });
        });

        return rows;
    }

    // ============================================================================
    // INSTANCE METHODS - RENDERING
    // ============================================================================

    createCourseDetails(plan, courseInfo) {
        // Learning objectives - convert from list format to comma-separated
        const objectivesText = this.formatObjectivesForDisplay(plan.learning_objectives);

        // Simulation info
        let deliveryDate = '';
        let teacherName = '';
        let roomName = '';
        let toolsInfo = '—';

        if (plan.simulation) {
            deliveryDate = plan.simulation.date ? this.formatDate(plan.simulation.date) : '';
            teacherName = plan.simulation.teacher || '';
            roomName = plan.simulation.room || '';
        }

        // Collect tools from segments
        const segmentTools = this.collectSegmentTools(plan);
        if (segmentTools.length > 0) {
            toolsInfo = segmentTools.join(', ');
        }

        return `
            <section class="course-details">
                <div class="detail-row">
                    <span class="label">Corso:</span>
                    <span class="value">${courseInfo}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Lezione:</span>
                    <span class="value">${plan.module ? `${plan.module} - ${plan.title || ''}` : (plan.title || '')}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Obiettivi didattici:</span>
                    <span class="value">${objectivesText}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Data:</span>
                    <span class="value">${deliveryDate}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Docente:</span>
                    <span class="value">${teacherName}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Aula:</span>
                    <span class="value">${roomName}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Strumenti:</span>
                    <span class="value">${toolsInfo}</span>
                </div>
            </section>
        `;
    }

    createScheduleTable(plan) {
        // Use _computeScheduleRows for logic, generate HTML string output
        const rows = this._computeScheduleRows(plan);

        let scheduleRows = '';
        if (rows.length === 0) {
            scheduleRows = '<tr><td colspan="4" style="text-align: center; font-style: italic;">Nessun segmento definito</td></tr>';
        } else {
            rows.forEach(row => {
                scheduleRows += `
                    <tr>
                        <td class="${row.isPause ? 'pause' : 'time-range'}">${row.timeRange}</td>
                        <td>${row.topic}</td>
                        <td class="${row.isPause ? 'pause' : ''}">${row.method}</td>
                        <td class="${row.isPause ? 'pause' : ''}">${row.tools}</td>
                    </tr>
                `;
            });
        }

        return `
            <section class="schedule-table">
                <table>
                    <thead>
                        <tr>
                            <th>Orario</th>
                            <th>Tema</th>
                            <th>Modalità di svolgimento</th>
                            <th>Strumenti</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${scheduleRows}
                    </tbody>
                </table>
            </section>
        `;
    }

    populateScheduleTableInDOM(plan, tbody) {
        // Use _computeScheduleRows for logic, generate DOM elements output
        tbody.innerHTML = '';
        const rows = this._computeScheduleRows(plan);

        if (rows.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="4" style="text-align: center; font-style: italic;">Nessun segmento definito</td>';
            tbody.appendChild(row);
            return;
        }

        rows.forEach(rowData => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="${rowData.isPause ? 'pause' : 'time-range'}">${rowData.timeRange}</td>
                <td>${rowData.topic}</td>
                <td class="${rowData.isPause ? 'pause' : ''}">${rowData.method}</td>
                <td class="${rowData.isPause ? 'pause' : ''}">${rowData.tools}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    createLessonPlanPageHTML(plan, lessonNumber, courseName, totalPlans = 1) {
        // Generates complete HTML for a single lesson plan page
        // This is the SINGLE SOURCE OF TRUTH for lesson plan rendering

        const header = `
            <header class="page-header">
                <h1>Piano di lezione${lessonNumber ? ` ${lessonNumber}` : ''}</h1>
                <img src="/assets/brand/logo_pnl_evolution.png" alt="PNL Evolution" class="logo-img">
            </header>
        `;

        const generalGoal = `
            <section class="general-goal">
                <p>${plan.general_goal || ''}</p>
            </section>
        `;

        const details = this.createCourseDetails(plan, courseName);
        const scheduleTable = this.createScheduleTable(plan);

        const footer = `
            <footer class="page-footer">
                <div class="note">
                    <strong>Nota:</strong> il tempo riservato ai singoli temi può variare in corso di lezione
                </div>

                <div class="signatures-container">
                    <div class="signature-box">
                        <div class="signature-label">Firma del docente</div>
                        <div class="signature-line">____________________________________</div>
                    </div>
                    <div class="signature-box">
                        <div class="signature-label">Verificato dal Direttore didattico</div>
                        <div class="signature-line">____________________________________</div>
                    </div>
                </div>

                <div class="footer-info">
                    <div class="footer-left">
                        Modulo Piano di lezione_MQ Rev.2 del 08.02.2026
                    </div>
                </div>
            </footer>
        `;

        return header + generalGoal + details + scheduleTable + footer;
    }

    // ============================================================================
    // STATIC ENTRY POINTS (API pubblica - SINGLE SOURCE OF TRUTH)
    // ============================================================================

    static generateCoursePagesArray(courseData) {
        const renderer = new LessonPlanRenderer();
        const pages = [];

        // Page 1: Course summary
        let summaryPage = `
    <div class="lesson-plan-page">
        <div class="course-header">
            <h1 class="course-title">${courseData.course.name}</h1>
            <div class="course-summary">${courseData.lesson_plans.length} piani di lezione</div>
        </div>

        <section class="schedule-table">
            <h3>Sommario del Corso</h3>
            <table>
                <thead>
                    <tr>
                        <th style="width: 10%;">Piano</th>
                        <th style="width: 40%;">Titolo</th>
                        <th style="width: 50%;">Obiettivo Generale</th>
                    </tr>
                </thead>
                <tbody>`;

        courseData.lesson_plans.forEach((plan, index) => {
            summaryPage += `
                    <tr>
                        <td>${index + 1}</td>
                        <td>${plan.title || ''}</td>
                        <td>${plan.general_goal || ''}</td>
                    </tr>`;
        });

        summaryPage += `
                </tbody>
            </table>
        </section>
    </div>`;

        pages.push(summaryPage);

        // Pages 2+: Individual lesson plans
        courseData.lesson_plans.forEach((plan, index) => {
            const lessonPage = `
    <div class="lesson-plan-page">
        ${renderer.createLessonPlanPageHTML(plan, index + 1, courseData.course.name, courseData.lesson_plans.length)}
    </div>`;
            pages.push(lessonPage);
        });

        return pages;
    }

    // Generate full course preview HTML (for testing/export)
    static generateCoursePreviewHTML(courseData) {
        const pages = LessonPlanRenderer.generateCoursePagesArray(courseData);

        const html = `<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anteprima Corso - PNL Evolution</title>
    <link rel="stylesheet" href="/utilities/static/lesson-plan/css/print-styles.css">
</head>
<body>
${pages.join('\n')}
</body>
</html>`;

        return html;
    }
}
