// Pulldown Component for Method Field
class PulldownComponent {
    constructor(container, options, isMultiSelect = false) {
        this.container = container;
        this.options = options;
        this.isMultiSelect = isMultiSelect;
        this.selectedValues = [];

        // Bind handleDocumentClick to this instance for proper cleanup
        this.handleDocumentClick = this.handleDocumentClick.bind(this);

        this.create();
    }

    create() {
        this.container.innerHTML = `
            <div class="pulldown-container">
                <input type="text" class="pulldown-input" placeholder="${this.isMultiSelect ? 'Digita o seleziona strumenti...' : 'Digita o seleziona metodo...'}">
                <div class="pulldown-options">
                    ${this.options.map(option => `
                        <div class="pulldown-option ${option.empty ? 'empty' : ''}" data-value="${option.value}">
                            ${option.label}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        this.input = this.container.querySelector('.pulldown-input');
        this.optionsContainer = this.container.querySelector('.pulldown-options');
        this.setupEventListeners();
    }

    handleDocumentClick(e) {
        if (!this.container.contains(e.target)) {
            this.optionsContainer.classList.remove('show');
        }
    }

    setupEventListeners() {
        // Show/hide options on focus/blur
        this.input.addEventListener('focus', () => {
            this.optionsContainer.classList.add('show');
        });

        // Hide options when clicking outside (using bound method for cleanup)
        document.addEventListener('click', this.handleDocumentClick);

        // Handle option clicks
        this.optionsContainer.addEventListener('click', (e) => {
            const option = e.target.closest('.pulldown-option');
            if (option) {
                const value = option.dataset.value;
                this.selectOption(value);
            }
        });

        // Filter options as user types
        this.input.addEventListener('input', () => {
            this.filterOptions();

            // For multi-select, update selections based on current input
            if (this.isMultiSelect) {
                this.updateSelectionsFromInput();
            }
        });
    }

    selectOption(value) {
        if (this.isMultiSelect) {
            if (value === '') {
                // Empty option clears all selections
                this.selectedValues = [];
                this.input.value = '';
            } else {
                // Toggle behavior: if already selected, remove it
                const index = this.selectedValues.indexOf(value);
                if (index > -1) {
                    this.selectedValues.splice(index, 1);
                } else {
                    this.selectedValues.push(value);
                }

                // Smart merge: preserve user typed text + selections
                this.updateInputValue();
            }
            this.updateMultiSelectDisplay();
        } else {
            // For single select, check if it's the same value to toggle off
            if (this.input.value === value) {
                this.input.value = '';
            } else {
                this.input.value = value;
            }
            this.optionsContainer.classList.remove('show');
        }
    }

    updateSelectionsFromInput() {
        // Update selectedValues based on what's currently in the input
        const currentValue = this.input.value;
        const parts = currentValue.split(',').map(p => p.trim());
        const predefinedValues = this.options.map(opt => opt.value).filter(v => v !== '');

        // Update selectedValues to match predefined options that are in the input
        this.selectedValues = parts.filter(part => predefinedValues.includes(part));
        this.updateMultiSelectDisplay();
    }

    updateInputValue() {
        if (this.isMultiSelect) {
            // Extract user-typed text that's not in predefined options
            const currentValue = this.input.value;
            const userTypedParts = [];

            if (currentValue) {
                const parts = currentValue.split(',').map(p => p.trim());
                const predefinedValues = this.options.map(opt => opt.value).filter(v => v !== '');

                parts.forEach(part => {
                    if (part && !predefinedValues.includes(part) && !this.selectedValues.includes(part)) {
                        userTypedParts.push(part);
                    }
                });
            }

            // Combine user typed + selected values
            const allValues = [...userTypedParts, ...this.selectedValues].filter(v => v);
            this.input.value = allValues.join(', ');
        }
    }

    updateMultiSelectDisplay() {
        const options = this.optionsContainer.querySelectorAll('.pulldown-option');
        options.forEach(option => {
            const value = option.dataset.value;
            if (this.selectedValues.includes(value)) {
                option.classList.add('selected');
            } else {
                option.classList.remove('selected');
            }
        });
    }

    filterOptions() {
        const searchTerm = this.input.value.toLowerCase();
        const options = this.optionsContainer.querySelectorAll('.pulldown-option');

        options.forEach(option => {
            const text = option.textContent.toLowerCase();
            if (text.includes(searchTerm) || searchTerm === '') {
                option.style.display = 'block';
            } else {
                option.style.display = 'none';
            }
        });
    }

    getValue() {
        return this.input.value;
    }

    setValue(value) {
        this.input.value = value;
        if (this.isMultiSelect) {
            // Parse the incoming value and separate predefined vs user-typed
            const parts = value ? value.split(',').map(v => v.trim()) : [];
            const predefinedValues = this.options.map(opt => opt.value).filter(v => v !== '');

            this.selectedValues = parts.filter(part => predefinedValues.includes(part));
            this.updateMultiSelectDisplay();
        }
    }

    destroy() {
        // Cleanup: remove document event listener to prevent memory leak
        document.removeEventListener('click', this.handleDocumentClick);
    }
}
