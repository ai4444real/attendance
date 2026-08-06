// Preview Script for Lesson Plan
// Uses LessonPlanRenderer.createLessonPlanPageHTML() (SINGLE SOURCE OF TRUTH)

document.addEventListener('DOMContentLoaded', () => {
    // Load lesson plan from localStorage
    const lessonPlan = TimeUtils.loadFromLocalStorage(
        STORAGE_KEYS.LESSON_PLAN,
        'Nessun piano lezione disponibile per l\'anteprima'
    );

    if (!lessonPlan) return; // loadFromLocalStorage already closed window

    // Load current course data (optional - used for course name)
    let courseName = 'Non specificato';
    const courseStored = localStorage.getItem(STORAGE_KEYS.COURSE);
    if (courseStored) {
        try {
            const courseData = JSON.parse(courseStored);
            if (courseData && courseData.course && courseData.course.name) {
                courseName = courseData.course.name;
            }
        } catch (e) {
            console.error('Error parsing stored course:', e);
        }
    }

    // Generate lesson plan page using SINGLE SOURCE OF TRUTH
    const renderer = new LessonPlanRenderer();
    const pageHTML = renderer.createLessonPlanPageHTML(lessonPlan, null, courseName, 1);

    // Wrap in lesson-plan-page div (same as course preview does)
    const wrappedHTML = `<div class="lesson-plan-page">${pageHTML}</div>`;
    document.getElementById('previewContent').innerHTML = wrappedHTML;

    // Set current date in all .current-date elements
    const formattedDate = TimeUtils.formatCurrentDate();
    document.querySelectorAll('.current-date').forEach(el => {
        el.textContent = formattedDate;
    });
});