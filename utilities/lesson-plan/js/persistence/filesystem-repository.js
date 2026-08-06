/**
 * FileSystem Repository Implementation
 * Handles persistence via browser file download/upload (current implementation)
 */
class FileSystemRepository extends Repository {
    constructor() {
        super();
        this.fileInputElement = null;
    }

    get type() {
        return 'filesystem';
    }

    get capabilities() {
        return {
            browse: false,  // Cannot browse files on user's filesystem
            search: false   // Cannot search across user's files
        };
    }

    /**
     * Save entity to filesystem (native save dialog or download as JSON file)
     * @param {Object} entity - Course structure with lesson_plans array
     * @param {string} type - Always 'course' for filesystem (we save entire course)
     * @returns {Promise<void>}
     */
    async save(entity, type) {
        try {
            // Determine default filename
            let suggestedName;
            if (type === 'course') {
                // Use course name (sanitized) for better readability
                const courseName = entity.course.name || 'Nuovo Corso';
                const sanitizedName = courseName.replace(/[/\\:*?"<>|]/g, '_');
                suggestedName = `${sanitizedName}.json`;
            } else {
                suggestedName = `${type}_${entity.id}.json`;
            }

            // Convert to JSON
            const dataStr = JSON.stringify(entity, null, 2);

            // Check if File System Access API is supported (Chrome, Edge, Opera)
            if ('showSaveFilePicker' in window) {
                // Modern API - show native save dialog
                const options = {
                    suggestedName: suggestedName,
                    types: [{
                        description: 'File JSON',
                        accept: {
                            'application/json': ['.json']
                        }
                    }]
                };

                const handle = await window.showSaveFilePicker(options);
                const writable = await handle.createWritable();
                await writable.write(dataStr);
                await writable.close();

            } else {
                // Fallback for browsers that don't support File System Access API (Firefox, Safari)
                const dataBlob = new Blob([dataStr], { type: 'application/json' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(dataBlob);
                link.download = suggestedName;

                // Trigger download
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                // Cleanup
                URL.revokeObjectURL(link.href);
            }

        } catch (error) {
            // User cancelled or error occurred
            if (error.name === 'AbortError') {
                throw new Error('Salvataggio annullato dall\'utente');
            }
            throw new Error(`Errore durante il salvataggio: ${error.message}`);
        }
    }

    /**
     * Load entity from filesystem (open file picker)
     * @param {string} id - Not used for filesystem (user selects file)
     * @param {string} type - Entity type ('course' or 'lesson_plan')
     * @returns {Promise<Object>} Loaded entity
     */
    async load(id, type) {
        return new Promise((resolve, reject) => {
            // Create file input if doesn't exist
            if (!this.fileInputElement) {
                this.fileInputElement = document.getElementById('fileInput');
                if (!this.fileInputElement) {
                    // Create hidden file input
                    this.fileInputElement = document.createElement('input');
                    this.fileInputElement.type = 'file';
                    this.fileInputElement.accept = '.json';
                    this.fileInputElement.style.display = 'none';
                    this.fileInputElement.id = 'fileInput';
                    document.body.appendChild(this.fileInputElement);
                }
            }

            // Setup one-time event listener
            const handleFileSelect = (event) => {
                const file = event.target.files[0];
                if (!file) {
                    reject(new Error('Nessun file selezionato'));
                    return;
                }

                const reader = new FileReader();

                reader.onload = (e) => {
                    try {
                        const data = JSON.parse(e.target.result);
                        // Clear file input for next use
                        this.fileInputElement.value = '';
                        resolve(data);
                    } catch (error) {
                        reject(new Error('Errore: file JSON non valido'));
                    }
                };

                reader.onerror = () => {
                    reject(new Error('Errore durante la lettura del file'));
                };

                reader.readAsText(file);

                // Remove event listener after use
                this.fileInputElement.removeEventListener('change', handleFileSelect);
            };

            // Attach event listener
            this.fileInputElement.addEventListener('change', handleFileSelect);

            // Open file picker
            this.fileInputElement.click();
        });
    }

    /**
     * Delete operation not supported for filesystem
     * @throws {Error} Always throws - operation not supported
     */
    async delete(id, type) {
        throw new Error('Delete operation not supported for filesystem repository');
    }

    /**
     * LoadAll operation not supported for filesystem
     * @throws {Error} Always throws - operation not supported
     */
    async loadAll(type) {
        throw new Error('Browse operation not supported for filesystem repository. User must select files manually.');
    }

    /**
     * Search operation not supported for filesystem
     * @throws {Error} Always throws - operation not supported
     */
    async search(query, type) {
        throw new Error('Search operation not supported for filesystem repository');
    }
}
