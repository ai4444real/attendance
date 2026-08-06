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

    renderObjectives() {
        const list = document.getElementById('objectivesList');
        list.innerHTML = '';

        this.objectives.forEach((objective, index) => {
            const li = document.createElement('li');
            li.className = 'objective-item';
            li.dataset.index = index;

            li.innerHTML = `
                <span class="objective-text">${objective}</span>
                <button type="button" class="objective-remove" onclick="objectivesManager.removeObjective(${index})">×</button>
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
