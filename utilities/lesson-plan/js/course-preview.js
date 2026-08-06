// Course Preview Script
// Uses LessonPlanRenderer.generateCoursePagesArray() (SINGLE SOURCE OF TRUTH)

document.addEventListener('DOMContentLoaded', () => {
    // Load course data from localStorage
    const courseData = TimeUtils.loadFromLocalStorage(
        STORAGE_KEYS.COURSE,
        'Nessun corso disponibile per l\'anteprima'
    );

    if (!courseData) return; // loadFromLocalStorage already closed window

    // Generate all course pages using SINGLE SOURCE OF TRUTH
    const pages = LessonPlanRenderer.generateCoursePagesArray(courseData);
    document.getElementById('courseContent').innerHTML = pages.join('\n');

    // Set current date in all .current-date elements
    const formattedDate = TimeUtils.formatCurrentDate();
    document.querySelectorAll('.current-date').forEach(el => {
        el.textContent = formattedDate;
    });
});