// Lesson Plan Manager
class LessonPlanManager {
    // ============================================================================
    // CONSTRUCTOR & INITIALIZATION
    // ============================================================================

    constructor() {
        this.currentLessonPlan = null;
        this.currentCourse = null;
        this.lessonPlans = [];

        // Load configurable options (with defaults as fallback)
        this.methodOptions = this.loadMethodOptions();
        this.toolsOptions = this.loadToolsOptions();

        // Initialize persistence repository
        this.repository = PersistenceFactory.create();

        // Initialize SegmentManager with loaded options
        this.segmentManager = new SegmentManager(this.methodOptions, this.toolsOptions);

        this.initializeEventListeners();
        this.initializeObjectives();
        this.initializeNewCourse();
        this.updateUI();

        // Populate form with initial lesson plan data (including auto-generated ID)
        if (this.currentLessonPlan) {
            this.populateForm(this.currentLessonPlan);
        }

        this.segmentManager.addInitialSegment();
    }

    // ============================================================================
    // CONFIGURATION & OPTIONS MANAGEMENT
    // ============================================================================

    getDefaultMethodOptions() {
        return DEFAULT_METHOD_OPTIONS;
    }

    getDefaultToolsOptions() {
        return DEFAULT_TOOLS_OPTIONS;
    }

    loadMethodOptions() {
        try {
            const stored = localStorage.getItem(STORAGE_KEYS.METHOD_OPTIONS);
            if (stored) {
                const parsed = JSON.parse(stored);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    return parsed;
                }
            }
        } catch (e) {
            console.warn('Error loading methodOptions from localStorage:', e);
        }
        return this.getDefaultMethodOptions();
    }

    loadToolsOptions() {
        try {
            const stored = localStorage.getItem(STORAGE_KEYS.TOOLS_OPTIONS);
            if (stored) {
                const parsed = JSON.parse(stored);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    return parsed;
                }
            }
        } catch (e) {
            console.warn('Error loading toolsOptions from localStorage:', e);
        }
        return this.getDefaultToolsOptions();
    }

    saveMethodOptions(options) {
        try {
            localStorage.setItem(STORAGE_KEYS.METHOD_OPTIONS, JSON.stringify(options));
            this.methodOptions = options;
        } catch (e) {
            console.error('Error saving methodOptions to localStorage:', e);
        }
    }

    saveToolsOptions(options) {
        try {
            localStorage.setItem(STORAGE_KEYS.TOOLS_OPTIONS, JSON.stringify(options));
            this.toolsOptions = options;
        } catch (e) {
            console.error('Error saving toolsOptions to localStorage:', e);
        }
    }

    resetToDefaultOptions() {
        this.saveMethodOptions(this.getDefaultMethodOptions());
        this.saveToolsOptions(this.getDefaultToolsOptions());
        alert('Options ripristinate ai valori di default. Ricarica la pagina per applicare le modifiche.');
    }

    openConfigModal() {
        const modal = document.getElementById('configModal');
        modal.style.display = 'block';
    }

    closeConfigModal() {
        const modal = document.getElementById('configModal');
        modal.style.display = 'none';
    }

    exportConfiguration() {
        try {
            const config = {
                methodOptions: this.methodOptions,
                toolsOptions: this.toolsOptions
            };

            const dataStr = JSON.stringify(config, null, 2);
            const dataBlob = new Blob([dataStr], { type: 'application/json' });

            const link = document.createElement('a');
            link.href = URL.createObjectURL(dataBlob);
            link.download = 'lesson-plan-config.json';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            alert('✅ Configurazione esportata con successo!');
        } catch (error) {
            console.error('Errore durante l\'esportazione:', error);
            alert('❌ Errore durante l\'esportazione della configurazione');
        }
    }

    importConfiguration(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const config = JSON.parse(e.target.result);

                // Validate structure
                if (!config.methodOptions || !Array.isArray(config.methodOptions)) {
                    throw new Error('Campo methodOptions mancante o non valido');
                }
                if (!config.toolsOptions || !Array.isArray(config.toolsOptions)) {
                    throw new Error('Campo toolsOptions mancante o non valido');
                }

                // Validate methodOptions format
                config.methodOptions.forEach((opt, index) => {
                    if (!opt.value || !opt.label) {
                        throw new Error(`methodOptions[${index}] ha formato non valido (richiesti: value, label)`);
                    }
                });

                // Validate toolsOptions format
                config.toolsOptions.forEach((opt, index) => {
                    if (!opt.hasOwnProperty('value') || !opt.label) {
                        throw new Error(`toolsOptions[${index}] ha formato non valido (richiesti: value, label)`);
                    }
                });

                // Save to localStorage
                this.saveMethodOptions(config.methodOptions);
                this.saveToolsOptions(config.toolsOptions);

                alert('✅ Configurazione importata con successo! Ricarica la pagina per applicare le modifiche.');

                // Clear file input
                event.target.value = '';

            } catch (error) {
                console.error('Errore durante l\'importazione:', error);
                alert(`❌ Errore durante l\'importazione:\n\n${error.message}`);
            }
        };
        reader.readAsText(file);
    }

    // ============================================================================
    // EVENT LISTENERS & UI INITIALIZATION
    // ============================================================================

    initializeObjectives() {
        window.objectivesManager = new ObjectivesManager();
    }

    initializeEventListeners() {
        // Simulation checkbox toggle
        document.getElementById('hasSimulation').addEventListener('change', (e) => {
            const simulationSection = document.getElementById('simulationSection');
            simulationSection.style.display = e.target.checked ? 'block' : 'none';
        });

        // Start time change
        document.getElementById('startTime').addEventListener('change', () => {
            this.updateSegmentTimes();
        });

        // Add segment button
        document.getElementById('addSegmentBtn').addEventListener('click', () => {
            this.addSegment();
        });

        // Save button
        document.getElementById('saveBtn').addEventListener('click', () => {
            this.saveLessonPlan();
        });

        // Load button
        document.getElementById('loadBtn').addEventListener('click', () => {
            this.loadLessonPlan();
        });

        // Import only the lesson plans from another course file
        document.getElementById('importPlansBtn').addEventListener('click', () => {
            this.importLessonPlans();
        });

        // Preview course button
        document.getElementById('previewBtn').addEventListener('click', () => {
            this.openCoursePreview();
        });

        // Preview single plan button
        document.getElementById('previewPlanBtn').addEventListener('click', () => {
            this.openPlanPreview();
        });

        // Reset buttons
        document.getElementById('resetStartTime').addEventListener('click', () => {
            this.resetStartTime();
        });

        document.getElementById('resetSimulation').addEventListener('click', () => {
            this.resetSimulationData();
        });

        // File input change - now handled by repository
        // (removed event listener - repository manages file input directly)

        // Course management event listeners
        document.getElementById('editCourseBtn').addEventListener('click', () => {
            this.openCourseModal();
        });

        document.getElementById('saveCourseBtn').addEventListener('click', () => {
            this.saveCourseSettings();
        });

        document.getElementById('cancelCourseBtn').addEventListener('click', () => {
            this.closeCourseModal();
        });

        document.getElementById('addLessonPlanBtn').addEventListener('click', () => {
            this.addNewLessonPlan();
        });

        // Configuration modal
        document.getElementById('configBtn').addEventListener('click', () => {
            this.openConfigModal();
        });

        document.getElementById('closeConfigBtn').addEventListener('click', () => {
            this.closeConfigModal();
        });

        document.getElementById('exportConfigBtn').addEventListener('click', () => {
            this.exportConfiguration();
        });

        document.getElementById('importConfigBtn').addEventListener('click', () => {
            document.getElementById('configFileInput').click();
        });

        document.getElementById('configFileInput').addEventListener('change', (e) => {
            this.importConfiguration(e);
        });

        document.getElementById('resetConfigBtn').addEventListener('click', () => {
            this.resetToDefaultOptions();
        });

        // Lesson plans navigation event delegation
        document.getElementById('lessonPlansList').addEventListener('click', (e) => {
            if (e.target.classList.contains('lesson-plan-content') || e.target.classList.contains('lesson-plan-title')) {
                const planId = e.target.closest('.lesson-plan-content').dataset.planId;
                this.switchToLessonPlan(planId);
            } else if (e.target.classList.contains('btn-delete')) {
                const planId = e.target.dataset.planId;
                this.deleteLessonPlan(planId);
            }
        });
    }

    // ============================================================================
    // SEGMENT MANAGEMENT (delegated to SegmentManager)
    // ============================================================================

    addSegment(segmentData = null) {
        this.segmentManager.addSegment(segmentData);
    }

    addInitialSegment() {
        this.segmentManager.addInitialSegment();
    }

    removeSegment(segmentId) {
        this.segmentManager.removeSegment(segmentId);
    }

    moveSegment(segmentId, direction) {
        this.segmentManager.moveSegment(segmentId, direction);
    }

    updateSegmentTimes() {
        this.segmentManager.updateSegmentTimes();
    }

    // ============================================================================
    // FORM DATA MANAGEMENT
    // ============================================================================

    collectFormData() {
        const form = document.getElementById('lessonPlanForm');
        const formData = new FormData(form);

        // Basic fields
        const lessonPlan = {
            id: formData.get('id')?.trim(),
            title: formData.get('title')?.trim(),
            general_goal: formData.get('general_goal')?.trim(),
            learning_objectives: objectivesManager.getObjectives(),
            segments: []
        };

        // Optional course_id
        const courseId = formData.get('course_id')?.trim();
        if (courseId) {
            lessonPlan.course_id = courseId;
        }

        // Optional module
        const module = formData.get('module')?.trim();
        if (module) {
            lessonPlan.module = module;
        }

        // Simulation information
        if (document.getElementById('hasSimulation').checked) {
            const simulation = {};

            const startTime = document.getElementById('startTime').value;
            const simDate = formData.get('sim_date');
            const simTeacher = formData.get('sim_teacher')?.trim();
            const simRoom = formData.get('sim_room')?.trim();

            if (startTime) simulation.start_time = startTime;
            if (simDate) simulation.date = simDate;
            if (simTeacher) simulation.teacher = simTeacher;
            if (simRoom) simulation.room = simRoom;

            if (Object.keys(simulation).length > 0) {
                lessonPlan.simulation = simulation;
            }
        }

        // Collect segments
        const segments = document.querySelectorAll('.segment-item');
        segments.forEach(segmentDiv => {
            const segment = {};

            // Get duration from input
            const durationInput = segmentDiv.querySelector('input[name="duration_min"]');
            if (durationInput) {
                segment.duration_min = parseInt(durationInput.value, 10) || 0;
            }

            // Get topic from input
            const topicInput = segmentDiv.querySelector('input[name="topic"]');
            if (topicInput) {
                segment.topic = topicInput.value.trim();
            }

            // Get method from pulldown
            if (segmentDiv.methodPulldown) {
                segment.method = segmentDiv.methodPulldown.getValue().trim();
            }

            // Get tools from pulldown
            if (segmentDiv.toolsPulldown) {
                const toolsValue = segmentDiv.toolsPulldown.getValue().trim();
                segment.tools = toolsValue ? this.parseToolsString(toolsValue) : [];
            }

            // NOTE: start_time/end_time are NOT persisted in the data model
            // They are computed values only for rendering (see Data Model spec §6)

            if (segment.topic && segment.method) {
                lessonPlan.segments.push(segment);
            }
        });

        return lessonPlan;
    }

    parseToolsString(toolsString) {
        return this.segmentManager.parseToolsString(toolsString);
    }

    // ============================================================================
    // VALIDATION
    // ============================================================================

    validateLessonPlan(lessonPlan) {
        const errors = [];

        // Required fields validation
        if (!lessonPlan.id) errors.push('ID Piano è obbligatorio');
        if (!lessonPlan.title) errors.push('Titolo è obbligatorio');
        if (!lessonPlan.general_goal) errors.push('Obiettivo Generale è obbligatorio');
        if (!lessonPlan.learning_objectives) errors.push('Obiettivi Didattici sono obbligatori');
        if (!lessonPlan.segments || lessonPlan.segments.length === 0) {
            errors.push('Almeno un segmento è obbligatorio');
        }

        // Segments validation
        lessonPlan.segments.forEach((segment, index) => {
            if (!segment.topic) errors.push(`Segmento ${index + 1}: Argomento è obbligatorio`);
            if (!segment.method) errors.push(`Segmento ${index + 1}: Metodo è obbligatorio`);
            if (segment.duration_min < 0) errors.push(`Segmento ${index + 1}: Durata non può essere negativa`);
            if (segment.duration_min === 0) {
                console.warn(`Segmento ${index + 1}: Durata zero (W_DURATION_ZERO)`);
            }
        });

        // Date validation for delivery
        if (lessonPlan.delivery && lessonPlan.delivery.next) {
            const datePattern = /^\d{4}-\d{2}-\d{2}$/;
            if (!datePattern.test(lessonPlan.delivery.next.date)) {
                errors.push('Formato data non valido (richiesto YYYY-MM-DD)');
            }
        }

        return errors;
    }

    // ============================================================================
    // PERSISTENCE (SAVE/LOAD)
    // ============================================================================

    async saveLessonPlan() {
        try {
            // Auto-save current plan first
            if (this.currentLessonPlan) {
                this.autoSaveCurrentPlan();

                // Validate current plan
                const errors = this.validateLessonPlan(this.currentLessonPlan);
                if (errors.length > 0) {
                    alert('Errori di validazione nel piano corrente:\n' + errors.join('\n'));
                    return;
                }
            }

            // Save entire course using repository
            const courseData = this.createCourseStructure();
            await this.repository.save(courseData, 'course');

        } catch (error) {
            console.error('Errore durante il salvataggio:', error);
            alert('Errore durante il salvataggio del corso');
        }
    }

    async loadLessonPlan() {
        try {
            // Load course using repository
            const data = await this.repository.load(null, 'course');

            // Load course structure (handles both old and new formats)
            this.loadCourseStructure(data);

            // Update UI and populate form with current lesson plan
            this.updateUI();
            if (this.currentLessonPlan) {
                this.clearForm();
                this.populateForm(this.currentLessonPlan);
            }

        } catch (error) {
            // User cancelled or error occurred
            if (error.message !== 'Nessun file selezionato') {
                console.error('Errore durante il caricamento:', error);
                alert(error.message || 'Errore durante il caricamento del corso');
            }
        }
    }

    async importLessonPlans() {
        try {
            if (this.currentLessonPlan) {
                this.autoSaveCurrentPlan();
            }

            const data = await this.repository.load(null, 'course');
            if (!data || !data.course || !Array.isArray(data.lesson_plans)) {
                throw new Error('Il file deve contenere un corso con i relativi piani di lezione');
            }
            if (data.lesson_plans.length === 0) {
                throw new Error('Il corso selezionato non contiene piani di lezione');
            }

            const usedIds = new Set(this.lessonPlans.map(plan => plan.id));
            const importedPlans = data.lesson_plans.map(plan => {
                if (!plan || typeof plan !== 'object' || Array.isArray(plan)) {
                    throw new Error('Il file contiene un piano di lezione non valido');
                }

                const importedPlan = { ...plan, course_id: this.currentCourse.id };
                if (!importedPlan.id || usedIds.has(importedPlan.id)) {
                    importedPlan.id = this.generateUniquePlanId(usedIds);
                }
                usedIds.add(importedPlan.id);
                return importedPlan;
            });

            this.lessonPlans.push(...importedPlans);
            this.currentLessonPlan = importedPlans[0];
            this.clearForm();
            this.populateForm(this.currentLessonPlan);
            this.updateUI();

            const planLabel = importedPlans.length === 1 ? 'piano importato' : 'piani importati';
            alert(`✅ ${importedPlans.length} ${planLabel} nel corso "${this.currentCourse.name}"`);
        } catch (error) {
            if (error.message !== 'Nessun file selezionato') {
                console.error('Errore durante l\'importazione dei piani:', error);
                alert(error.message || 'Errore durante l\'importazione dei piani');
            }
        }
    }

    handleFileLoad(event) {
        // This method is no longer used - kept for backward compatibility
        // The repository now handles file loading directly
        console.warn('handleFileLoad is deprecated - repository handles file loading');
    }

    clearForm() {
        document.getElementById('lessonPlanForm').reset();
        document.getElementById('hasSimulation').checked = false;
        document.getElementById('simulationSection').style.display = 'none';

        // Clear segments
        const container = document.getElementById('segmentsContainer');
        container.innerHTML = '';
        this.segmentManager.segmentCounter = 0;

        // Reset objectives
        if (window.objectivesManager) {
            window.objectivesManager.objectives = [];
            window.objectivesManager.renderObjectives();
        }
    }

    populateForm(lessonPlan) {
        // Basic fields
        document.getElementById('planId').value = lessonPlan.id || '';
        document.getElementById('courseId').value = lessonPlan.course_id || '';
        document.getElementById('module').value = lessonPlan.module || '';
        document.getElementById('title').value = lessonPlan.title || '';
        document.getElementById('generalGoal').value = lessonPlan.general_goal || '';

        // Set objectives using the ObjectivesManager
        objectivesManager.setObjectives(lessonPlan.learning_objectives || '');

        // Simulation information
        const hasSimulation = lessonPlan.simulation && Object.keys(lessonPlan.simulation).length > 0;
        document.getElementById('hasSimulation').checked = hasSimulation;

        const simulationSection = document.getElementById('simulationSection');
        simulationSection.style.display = hasSimulation ? 'block' : 'none';

        if (hasSimulation) {
            const simulation = lessonPlan.simulation;
            document.getElementById('startTime').value = simulation.start_time || '';
            document.getElementById('simDate').value = simulation.date || '';
            document.getElementById('simTeacher').value = simulation.teacher || '';
            document.getElementById('simRoom').value = simulation.room || '';
        }

        // Clear existing segments
        const container = document.getElementById('segmentsContainer');
        container.innerHTML = '';
        this.segmentManager.segmentCounter = 0;

        // Add segments
        if (lessonPlan.segments && lessonPlan.segments.length > 0) {
            lessonPlan.segments.forEach(segment => {
                this.addSegment(segment);
            });
        } else {
            this.addInitialSegment();
        }
    }

    newLessonPlan() {
        if (confirm('Creare un nuovo piano lezione? I dati non salvati andranno persi.')) {
            document.getElementById('lessonPlanForm').reset();
            document.getElementById('hasSimulation').checked = false;
            document.getElementById('simulationSection').style.display = 'none';

            const container = document.getElementById('segmentsContainer');
            container.innerHTML = '';
            this.segmentManager.segmentCounter = 0;
            this.addInitialSegment();

            this.currentLessonPlan = null;
        }
    }

    // ============================================================================
    // PREVIEW OPERATIONS
    // ============================================================================

    openPlanPreview() {
        try {
            // Auto-save current plan first
            if (this.currentLessonPlan) {
                this.autoSaveCurrentPlan();
            }

            const errors = this.validateLessonPlan(this.currentLessonPlan);
            if (errors.length > 0) {
                alert('Correggi gli errori prima dell\'anteprima:\n' + errors.join('\n'));
                return;
            }

            // Store lesson plan data
            localStorage.setItem(STORAGE_KEYS.LESSON_PLAN, JSON.stringify(this.currentLessonPlan));

            // Store current course data for preview (same structure as course preview)
            if (this.currentCourse) {
                const courseData = this.createCourseStructure();
                localStorage.setItem(STORAGE_KEYS.COURSE, JSON.stringify(courseData));
            }

            // Open preview in new window
            const previewWindow = window.open('/utilities/static/lesson-plan/preview.html', 'lessonPlanPreview', 'width=800,height=1000,scrollbars=yes,resizable=yes');
            if (!previewWindow) {
                alert('Impossibile aprire la finestra di anteprima. Controlla se il blocco popup è attivo.');
            }

        } catch (error) {
            console.error('Errore durante l\'anteprima:', error);
            alert('Errore durante la creazione dell\'anteprima');
        }
    }

    openCoursePreview() {
        try {
            // Auto-save current plan first
            if (this.currentLessonPlan) {
                this.autoSaveCurrentPlan();
            }

            // Validate all lesson plans
            const invalidPlans = [];
            this.lessonPlans.forEach((plan, index) => {
                const errors = this.validateLessonPlan(plan);
                if (errors.length > 0) {
                    invalidPlans.push(`Piano ${index + 1} (${plan.title}): ${errors.join(', ')}`);
                }
            });

            if (invalidPlans.length > 0) {
                alert('Correggi gli errori nei seguenti piani prima dell\'anteprima:\n' + invalidPlans.join('\n\n'));
                return;
            }

            // Store course data for preview
            const courseData = this.createCourseStructure();
            localStorage.setItem(STORAGE_KEYS.COURSE, JSON.stringify(courseData));

            // Open course preview in new window
            const previewWindow = window.open('/utilities/static/lesson-plan/course-preview.html', 'coursePreview', 'width=800,height=1000,scrollbars=yes,resizable=yes');
            if (!previewWindow) {
                alert('Impossibile aprire la finestra di anteprima. Controlla se il blocco popup è attivo.');
            }

        } catch (error) {
            console.error('Errore durante l\'anteprima del corso:', error);
            alert('Errore durante la creazione dell\'anteprima del corso');
        }
    }

    resetStartTime() {
        document.getElementById('startTime').value = '';
        this.updateSegmentTimes();
    }

    resetSimulationData() {
        if (confirm('Cancellare tutti i dati per PDF? Questa azione non può essere annullata.')) {
            document.getElementById('hasSimulation').checked = false;
            document.getElementById('simulationSection').style.display = 'none';

            // Clear all simulation fields
            document.getElementById('startTime').value = '';
            document.getElementById('simDate').value = '';
            document.getElementById('simTeacher').value = '';
            document.getElementById('simRoom').value = '';

            // Update segment times
            this.updateSegmentTimes();
        }
    }

    // ============================================================================
    // COURSE MANAGEMENT
    // ============================================================================

    generateUUID() {
        return 'course_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    generateUniquePlanId(usedIds = new Set()) {
        let planId;
        do {
            planId = `plan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        } while (usedIds.has(planId));
        return planId;
    }

    initializeNewCourse() {
        this.currentCourse = {
            id: this.generateUUID(),
            name: 'Nuovo Corso'
        };

        // Create initial lesson plan
        const initialPlan = {
            id: `plan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            course_id: this.currentCourse.id,
            title: 'Piano Lezione 1',
            general_goal: '',
            learning_objectives: '',
            segments: []
        };

        this.lessonPlans = [initialPlan];
        this.currentLessonPlan = initialPlan;
    }

    createCourseStructure() {
        return {
            course: this.currentCourse,
            lesson_plans: this.lessonPlans
        };
    }

    loadCourseStructure(courseData) {
        // Handle both old format (single lesson plan) and new format (course with multiple plans)
        if (courseData.course && courseData.lesson_plans) {
            // New course format
            this.currentCourse = courseData.course;
            this.lessonPlans = courseData.lesson_plans;
            this.currentLessonPlan = this.lessonPlans.length > 0 ? this.lessonPlans[0] : null;
        } else {
            // Old single lesson plan format - migrate to course
            this.migrateSinglePlanToCourse(courseData);
        }
    }

    migrateSinglePlanToCourse(lessonPlan) {
        // Create course from single lesson plan
        this.currentCourse = {
            id: this.generateUUID(),
            name: lessonPlan.title || 'Corso Importato'
        };

        // Ensure lesson plan has course_id
        lessonPlan.course_id = this.currentCourse.id;

        this.lessonPlans = [lessonPlan];
        this.currentLessonPlan = lessonPlan;
    }

    // Course modal management
    openCourseModal() {
        const modal = document.getElementById('courseModal');
        const courseName = document.getElementById('courseName');
        courseName.value = this.currentCourse.name;
        modal.style.display = 'block';
        courseName.focus();
    }

    closeCourseModal() {
        const modal = document.getElementById('courseModal');
        modal.style.display = 'none';
    }

    saveCourseSettings() {
        const courseName = document.getElementById('courseName').value.trim();
        if (!courseName) {
            alert('Il nome del corso è obbligatorio');
            return;
        }

        this.currentCourse.name = courseName;
        this.updateUI();
        this.closeCourseModal();
    }

    // ============================================================================
    // LESSON PLAN NAVIGATION
    // ============================================================================

    addNewLessonPlan() {
        // Auto-save current lesson plan data before creating new one
        if (this.currentLessonPlan) {
            this.autoSaveCurrentPlan();
        }

        const newPlan = {
            id: `plan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            course_id: this.currentCourse.id,
            title: `Piano Lezione ${this.lessonPlans.length + 1}`,
            general_goal: '',
            learning_objectives: '',
            segments: []
        };

        this.lessonPlans.push(newPlan);
        this.currentLessonPlan = newPlan;
        this.updateUI();
        this.clearForm();
        this.populateForm(newPlan);
    }

    switchToLessonPlan(planId) {
        // Auto-save current lesson plan data before switching
        if (this.currentLessonPlan) {
            this.autoSaveCurrentPlan();
        }

        const plan = this.lessonPlans.find(p => p.id === planId);
        if (plan) {
            this.currentLessonPlan = plan;
            this.clearForm();
            this.populateForm(plan);
            this.updateUI();
        }
    }

    deleteLessonPlan(planId) {
        if (this.lessonPlans.length <= 1) {
            alert('Non puoi cancellare l\'ultimo piano di lezione');
            return;
        }

        if (confirm('Sei sicuro di voler cancellare questo piano di lezione?')) {
            const index = this.lessonPlans.findIndex(p => p.id === planId);
            if (index > -1) {
                this.lessonPlans.splice(index, 1);

                // Switch to first lesson plan if current was deleted
                if (this.currentLessonPlan && this.currentLessonPlan.id === planId) {
                    this.currentLessonPlan = this.lessonPlans[0];
                    this.clearForm();
                    this.populateForm(this.lessonPlans[0]);
                }

                this.updateUI();
            }
        }
    }

    // ============================================================================
    // UI UPDATES
    // ============================================================================

    updateUI() {
        // Update course title
        document.getElementById('courseTitle').textContent = this.currentCourse.name;

        // Update lesson plans navigation
        this.updateLessonPlansNavigation();

        // Update course_id field
        if (this.currentLessonPlan) {
            document.getElementById('courseId').value = this.currentCourse.id;
        }
    }

    autoSaveCurrentPlan() {
        try {
            const updatedPlan = this.collectFormData();
            const index = this.lessonPlans.findIndex(p => p.id === this.currentLessonPlan.id);
            if (index > -1) {
                this.lessonPlans[index] = updatedPlan;
                this.currentLessonPlan = updatedPlan;
            }
        } catch (error) {
            // Silently handle errors during auto-save to avoid disrupting user experience
            console.warn('Auto-save failed:', error);
        }
    }

    updateLessonPlansNavigation() {
        const list = document.getElementById('lessonPlansList');
        list.innerHTML = '';

        this.lessonPlans.forEach(plan => {
            const li = document.createElement('li');
            li.className = 'lesson-plan-item';
            if (this.currentLessonPlan && plan.id === this.currentLessonPlan.id) {
                li.classList.add('active');
            }

            li.innerHTML = `
                <div class="lesson-plan-content" data-plan-id="${plan.id}">
                    <span class="lesson-plan-title">${plan.title || 'Piano senza titolo'}</span>
                </div>
                <button class="btn-delete" data-plan-id="${plan.id}" title="Cancella piano">×</button>
            `;

            list.appendChild(li);
        });
    }
}

// Initialize the application
const lessonPlanManager = new LessonPlanManager();
