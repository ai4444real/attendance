// Objectives Manager
class ObjectivesManager {
    constructor() {
        this.objectives = [];
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        const addBtn = document.getElementById('addObjectiveBtn');
        const input = document.getElementById('newObjective');

        addBtn.addEventListener('click', () => {
            this.addObjective();
        });

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.addObjective();
            }
        });
    }

    addObjective() {
        const input = document.getElementById('newObjective');
        const text = input.value.trim();

        if (text) {
            this.objectives.push(text);
            this.renderObjectives();
            input.value = '';
        }
    }

    removeObjective(index) {
        this.objectives.splice(index, 1);
        this.renderObjectives();
    }

    moveObjective(index, direction) {
        const targetIndex = index + direction;
        if (targetIndex < 0 || targetIndex >= this.objectives.length) return;

        [this.objectives[index], this.objectives[targetIndex]] =
            [this.objectives[targetIndex], this.objectives[index]];
        this.renderObjectives();
    }

    renderObjectives() {
        const list = document.getElementById('objectivesList');
        list.innerHTML = '';

        this.objectives.forEach((objective, index) => {
            const li = document.createElement('li');
            li.className = 'objective-item';
            li.dataset.index = index;

            li.innerHTML = `
                <span class="objective-text">${objective}</span>
                <span class="reorder-controls" aria-label="Riordina obiettivo">
                    <button type="button" class="reorder-btn" title="Sposta su" aria-label="Sposta obiettivo su"
                            onclick="objectivesManager.moveObjective(${index}, -1)" ${index === 0 ? 'disabled' : ''}>↑</button>
                    <button type="button" class="reorder-btn" title="Sposta giù" aria-label="Sposta obiettivo giù"
                            onclick="objectivesManager.moveObjective(${index}, 1)" ${index === this.objectives.length - 1 ? 'disabled' : ''}>↓</button>
                </span>
                <button type="button" class="objective-remove" title="Rimuovi obiettivo" aria-label="Rimuovi obiettivo"
                        onclick="objectivesManager.removeObjective(${index})">×</button>
            `;

            list.appendChild(li);
        });
    }

    getObjectives() {
        return this.objectives.join('\n');
    }

    setObjectives(objectivesText) {
        this.objectives = objectivesText ? objectivesText.split('\n').filter(obj => obj.trim()) : [];
        this.renderObjectives();
    }
}
