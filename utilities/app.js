// ============================================================================
// Google Classroom Manager - App Logic
// Approccio Moderno: Google Identity Services + Fetch Dirette
// ============================================================================

// Configurazione
const CONFIG = {
    CLIENT_ID: '572268474022-54j1dba72gm26n00oi42ijrhv3ielep1.apps.googleusercontent.com',
    SCOPES: [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/classroom.courses.readonly',
        'https://www.googleapis.com/auth/classroom.coursework.me.readonly',
        'https://www.googleapis.com/auth/classroom.coursework.me',
        'https://www.googleapis.com/auth/classroom.coursework.students.readonly',
        'https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly',
        'https://www.googleapis.com/auth/classroom.topics.readonly',
        'openid',
        'email',
        'profile'
    ].join(' '),
    CALENDAR_API_BASE: 'https://www.googleapis.com/calendar/v3',
    CLASSROOM_API_BASE: 'https://classroom.googleapis.com/v1'
};

// Stato dell'applicazione
let state = {
    accessToken: null,
    tokenClient: null,
    user: null,
    calendars: [],
    selectedCalendars: new Set(),
    events: [],
    courses: [],
    currentCourse: null,
    topics: [],
    courseWork: [],
    pendingAction: null,
    tokenGranted: false,
    masterEvents: []  // Eventi master per sincronizzazione
};

/**
 * Inizializza il token client se non esiste
 */
function ensureTokenClient() {
    if (state.tokenClient) return true;
    if (!window.google || !google.accounts?.oauth2) {
        showError('Google Identity Services non disponibile. Ricarica la pagina.');
        return false;
    }

    state.tokenClient = google.accounts.oauth2.initTokenClient({
        client_id: CONFIG.CLIENT_ID,
        scope: CONFIG.SCOPES,
        callback: async (tokenResponse) => {
            if (tokenResponse.error) {
                console.error('Errore ottenimento token:', tokenResponse);
                showError('Errore durante l\'autorizzazione: ' + tokenResponse.error);
                return;
            }

            if (tokenResponse.access_token) {
                state.accessToken = tokenResponse.access_token;
                state.tokenGranted = true;

                if (!state.user) {
                    await fetchUserInfo();
                }
                if (state.user) {
                    updateUIAfterAuth();
                }

                // Esegui l'azione che ha richiesto il token
                const action = state.pendingAction;
                state.pendingAction = null;

                if (action === 'loadCalendars') {
                    await doLoadCalendars();
                } else if (action === 'loadCourses') {
                    await doLoadCourses();
                }
            }
        }
    });
    return true;
}

// ============================================================================
// Autenticazione Google Identity Services
// ============================================================================

/**
 * Callback chiamato dopo il login Google (dal bottone GSI)
 */
function handleCredentialResponse(response) {
    const credential = response.credential;

    // Decodifica il JWT per ottenere le info utente
    const userInfo = parseJwt(credential);

    state.user = {
        name: userInfo.name,
        email: userInfo.email,
        picture: userInfo.picture
    };

    console.log('✓ Utente autenticato:', state.user.email);

    // Aggiorna UI - mostra utente
    updateUIAfterAuth();

    // Inizializza il Token Client (ma NON richiedere token ancora)
    // Il token verrà richiesto quando l'utente clicca "Carica Calendari"
    state.tokenClient = google.accounts.oauth2.initTokenClient({
        client_id: CONFIG.CLIENT_ID,
        scope: CONFIG.SCOPES,
        callback: async (tokenResponse) => {
            if (tokenResponse.error) {
                console.error('Errore ottenimento token:', tokenResponse);
                showError('Errore durante l\'autorizzazione: ' + tokenResponse.error);
                return;
            }

            if (tokenResponse.access_token) {
                state.accessToken = tokenResponse.access_token;
                state.tokenGranted = true;

                // Esegui l'azione che ha richiesto il token
                const action = state.pendingAction;
                state.pendingAction = null;

                if (action === 'loadCalendars') {
                    await doLoadCalendars();
                } else if (action === 'loadCourses') {
                    await doLoadCourses();
                }
            }
        }
    });
}

/**
 * Richiede access token riusando l'account già selezionato
 */
function requestAccessTokenFor(action) {
    if (!ensureTokenClient()) return false;

    state.pendingAction = action;
    const hintEmail = state.user?.email;

    state.tokenClient.requestAccessToken({
        prompt: state.tokenGranted ? '' : 'consent',
        include_granted_scopes: true,
        ...(hintEmail ? { hint: hintEmail } : {})
    });
    return true;
}

/**
 * Recupera info utente (nome/email/foto) tramite userinfo endpoint
 */
async function fetchUserInfo() {
    try {
        const res = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
            headers: {
                'Authorization': `Bearer ${state.accessToken}`
            }
        });
        if (!res.ok) throw new Error('Impossibile recuperare il profilo utente');
        const info = await res.json();
        state.user = {
            name: info.name || info.email || '',
            email: info.email || '',
            picture: info.picture || ''
        };
    } catch (err) {
        console.error('Errore fetch userinfo:', err);
    }
}

/**
 * Parser JWT per estrarre info utente
 */
function parseJwt(token) {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
        atob(base64)
            .split('')
            .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
            .join('')
    );
    return JSON.parse(jsonPayload);
}

/**
 * Aggiorna l'interfaccia dopo autenticazione
 */
function updateUIAfterAuth() {
    // Nascondi vista non autenticata
    document.getElementById('notAuthenticatedView').classList.add('hidden');

    // Mostra vista autenticata
    const authView = document.getElementById('authenticatedView');
    authView.classList.remove('hidden');

    // Popola info utente
    document.getElementById('userName').textContent = state.user.name;
    document.getElementById('userEmail').textContent = state.user.email;

    // Imposta foto solo se esiste
    const photoElement = document.getElementById('userPhoto');
    const photoFallback = document.getElementById('userPhotoFallback');
    const initialsSpan = document.getElementById('userInitials');

    // Reset visibilità
    photoElement.style.display = 'none';
    photoFallback.classList.add('hidden');

    const initials = (state.user.name || state.user.email || 'U')
        .split(' ')
        .map(p => p[0])
        .join('')
        .slice(0, 2)
        .toUpperCase();
    if (initialsSpan) initialsSpan.textContent = initials;

    if (state.user.picture) {
        photoElement.onload = () => {
            photoElement.style.display = '';
            photoFallback.classList.add('hidden');
        };
        photoElement.onerror = () => {
            photoElement.style.display = 'none';
            photoFallback.classList.remove('hidden');
        };
        photoElement.src = state.user.picture;
    } else {
        photoElement.style.display = 'none';
        photoFallback.classList.remove('hidden');
    }

    // Mostra sezioni corsi e calendari
    document.getElementById('coursesSection').classList.remove('hidden');
    document.getElementById('calendarsSection').classList.remove('hidden');
}

/**
 * Logout
 */
function signOut() {
    // Revoca il token
    if (state.accessToken) {
        google.accounts.oauth2.revoke(state.accessToken, () => {
            console.log('✓ Token revocato');
        });
    }

    // Reset stato
    state = {
        accessToken: null,
        tokenClient: null,
        user: null,
        calendars: [],
        selectedCalendars: new Set(),
        events: [],
        courses: [],
        currentCourse: null,
        topics: [],
        courseWork: [],
        pendingAction: null,
        tokenGranted: false
    };

    // Reset UI
    document.getElementById('authenticatedView').classList.add('hidden');
    document.getElementById('notAuthenticatedView').classList.remove('hidden');
    document.getElementById('coursesSection').classList.add('hidden');
    document.getElementById('coursesListContainer').classList.add('hidden');
    document.getElementById('calendarsSection').classList.add('hidden');
    document.getElementById('calendarsListContainer').classList.add('hidden');

    // Ricarica pagina per reset completo
    window.location.reload();
}

// ============================================================================
// Google Calendar API - Fetch Dirette
// ============================================================================

/**
 * Effettua una chiamata GET alle API di Google Calendar
 */
async function calendarApiGet(endpoint, params = {}) {
    // Costruisci URL con parametri
    const url = new URL(`${CONFIG.CALENDAR_API_BASE}${endpoint}`);
    Object.keys(params).forEach(key => {
        const value = params[key];
        if (value === null || value === undefined) return;

        if (Array.isArray(value)) {
            value.forEach(v => url.searchParams.append(key, v));
        } else {
            url.searchParams.append(key, value);
        }
    });

    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${state.accessToken}`,
            'Accept': 'application/json'
        }
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: { message: response.statusText } }));
        throw new Error(error.error?.message || `HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
}

/**
 * Carica tutti i calendari con paginazione automatica
 */
async function fetchAllCalendars() {
    let allCalendars = [];
    let pageToken = null;

    do {
        const params = {
            maxResults: 250,
            showHidden: false,  // Mostra solo calendari non archiviati
            showDeleted: false
        };

        if (pageToken) {
            params.pageToken = pageToken;
        }

        const response = await calendarApiGet('/users/me/calendarList', params);

        if (response.items) {
            allCalendars = allCalendars.concat(response.items);
        }

        pageToken = response.nextPageToken;

    } while (pageToken);

    return allCalendars;
}

// ============================================================================
// Gestione Calendari
// ============================================================================

/**
 * Carica la lista dei calendari dell'utente (chiamata dal bottone)
 */
async function loadCalendars() {
    if (!ensureTokenClient()) return;

    if (state.accessToken) {
        await doLoadCalendars();
        return;
    }

    const btn = document.getElementById('loadCalendarsBtn');
    const loading = document.getElementById('loadingCalendars');
    btn.disabled = true;
    loading.classList.remove('hidden');

    requestAccessTokenFor('loadCalendars');
}

/**
 * Effettua il caricamento effettivo dei calendari
 */
async function doLoadCalendars() {
    const btn = document.getElementById('loadCalendarsBtn');
    const loading = document.getElementById('loadingCalendars');
    const listContainer = document.getElementById('calendarsListContainer');
    const errorDiv = document.getElementById('errorMessage');

    try {
        // Mostra loading
        btn.disabled = true;
        loading.classList.remove('hidden');
        listContainer.classList.add('hidden');
        errorDiv.classList.add('hidden');

        console.log('📅 Caricamento calendari in corso...');

        // Fetch calendari con paginazione automatica
        const calendars = await fetchAllCalendars();

        state.calendars = calendars;

        // Ordina per nome
        state.calendars.sort((a, b) => {
            const nameA = a.summary || a.id;
            const nameB = b.summary || b.id;
            return nameA.localeCompare(nameB);
        });

        console.log(`✓ Caricati ${state.calendars.length} calendari`);

        // Renderizza calendari
        renderCalendars();

        // Nascondi loading, mostra lista
        loading.classList.add('hidden');
        listContainer.classList.remove('hidden');

    } catch (error) {
        console.error('❌ Errore caricamento calendari:', error);
        loading.classList.add('hidden');

        let errorMessage = 'Errore durante il caricamento dei calendari.';
        if (error.message) {
            errorMessage += '\n' + error.message;
        }
        showError(errorMessage);
    } finally {
        btn.disabled = false;
    }
}

/**
 * Renderizza la lista dei calendari
 */
function renderCalendars() {
    const container = document.getElementById('calendarsList');
    const totalCount = document.getElementById('totalCount');

    container.innerHTML = '';
    totalCount.textContent = state.calendars.length;

    state.calendars.forEach(calendar => {
        const card = createCalendarCard(calendar);
        container.appendChild(card);
    });

    updateSelectedCount();
}

/**
 * Crea una card per un calendario
 */
function createCalendarCard(calendar) {
    const card = document.createElement('div');
    card.className = 'calendar-card';
    card.dataset.calendarId = calendar.id;

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = `cal-${calendar.id}`;
    checkbox.value = calendar.id;
    checkbox.onchange = () => toggleCalendarSelection(calendar.id);

    const label = document.createElement('label');
    label.className = 'calendar-checkbox';
    label.htmlFor = checkbox.id;

    const info = document.createElement('div');
    info.className = 'calendar-info';

    const name = document.createElement('div');
    name.className = 'calendar-name';
    name.textContent = calendar.summary || 'Senza nome';

    const id = document.createElement('div');
    id.className = 'calendar-id';
    id.textContent = calendar.id;

    info.appendChild(name);
    info.appendChild(id);

    label.appendChild(checkbox);
    label.appendChild(info);
    card.appendChild(label);

    return card;
}

/**
 * Toggle selezione calendario
 */
function toggleCalendarSelection(calendarId) {
    const card = document.querySelector(`[data-calendar-id="${calendarId}"]`);
    const checkbox = document.getElementById(`cal-${calendarId}`);

    if (checkbox.checked) {
        state.selectedCalendars.add(calendarId);
        card.classList.add('selected');
    } else {
        state.selectedCalendars.delete(calendarId);
        card.classList.remove('selected');
    }

    updateSelectedCount();
    updateSelectAllCheckbox();
}

/**
 * Toggle seleziona tutti
 */
function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('selectAllCalendars');
    const isChecked = selectAllCheckbox.checked;

    state.calendars.forEach(calendar => {
        const checkbox = document.getElementById(`cal-${calendar.id}`);
        if (checkbox && checkbox.checked !== isChecked) {
            checkbox.checked = isChecked;
            toggleCalendarSelection(calendar.id);
        }
    });
}

/**
 * Aggiorna il checkbox "Seleziona tutti"
 */
function updateSelectAllCheckbox() {
    const selectAllCheckbox = document.getElementById('selectAllCalendars');
    const visibleCalendars = document.querySelectorAll('.calendar-card:not([style*="display: none"])');
    const visibleSelected = Array.from(visibleCalendars).filter(card => {
        const checkbox = card.querySelector('input[type="checkbox"]');
        return checkbox && checkbox.checked;
    });

    selectAllCheckbox.checked = visibleCalendars.length > 0 &&
                                  visibleSelected.length === visibleCalendars.length;
}

/**
 * Aggiorna il contatore dei calendari selezionati
 */
function updateSelectedCount() {
    const selectedCount = document.getElementById('selectedCount');
    const loadEventsBtn = document.getElementById('loadEventsBtn');

    selectedCount.textContent = state.selectedCalendars.size;
    loadEventsBtn.disabled = state.selectedCalendars.size === 0;
}

/**
 * Filtra calendari per ricerca
 */
function filterCalendars() {
    const searchText = document.getElementById('calendarSearch').value.toLowerCase();
    const cards = document.querySelectorAll('.calendar-card');

    cards.forEach(card => {
        const name = card.querySelector('.calendar-name').textContent.toLowerCase();
        const id = card.querySelector('.calendar-id').textContent.toLowerCase();

        if (name.includes(searchText) || id.includes(searchText)) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });

    updateSelectAllCheckbox();
}

/**
 * Carica eventi da un singolo calendario con paginazione
 */
async function fetchEventsFromCalendar(calendarId, calendarName) {
    let allEvents = [];
    let pageToken = null;

    do {
        const params = {
            maxResults: 250,
            singleEvents: true,
            orderBy: 'startTime'
        };

        if (pageToken) {
            params.pageToken = pageToken;
        }

        const response = await calendarApiGet(`/calendars/${encodeURIComponent(calendarId)}/events`, params);

        if (response.items) {
            // Aggiungi il nome del calendario a ogni evento
            response.items.forEach(event => {
                event.calendarId = calendarId;
                event.calendarName = calendarName;
            });
            allEvents = allEvents.concat(response.items);
        }

        pageToken = response.nextPageToken;

    } while (pageToken);

    return allEvents;
}

/**
 * Carica eventi dai calendari selezionati
 */
async function loadSelectedEvents() {
    if (state.selectedCalendars.size === 0) {
        showError('Seleziona almeno un calendario.');
        return;
    }

    const loadingEl = document.getElementById('loadingEvents');
    const loadingText = document.getElementById('loadingEventsText');
    const tableContainer = document.getElementById('eventsTableContainer');
    const eventsSection = document.getElementById('eventsSection');
    const eventsError = document.getElementById('eventsError');

    try {
        // Mostra loading
        eventsSection.classList.remove('hidden');
        loadingEl.classList.remove('hidden');
        tableContainer.classList.add('hidden');
        eventsError.classList.add('hidden');

        state.events = [];

        console.log(`📅 Caricamento eventi da ${state.selectedCalendars.size} calendari...`);

        let completed = 0;
        const total = state.selectedCalendars.size;

        // Carica eventi da tutti i calendari selezionati
        for (const calendarId of state.selectedCalendars) {
            const calendar = state.calendars.find(cal => cal.id === calendarId);
            const calendarName = calendar ? calendar.summary || calendar.id : calendarId;

            loadingText.textContent = `Caricamento eventi (${completed + 1}/${total}): ${calendarName}`;

            const events = await fetchEventsFromCalendar(calendarId, calendarName);
            state.events = state.events.concat(events);

            completed++;
            console.log(`  ✓ ${calendarName}: ${events.length} eventi`);
        }

        // Ordina eventi per data di inizio
        state.events.sort((a, b) => {
            const dateA = a.start?.dateTime || a.start?.date || '';
            const dateB = b.start?.dateTime || b.start?.date || '';
            return dateA.localeCompare(dateB);
        });

        console.log(`✓ Totale eventi caricati: ${state.events.length}`);

        // Analizza eventi condivisi (stessa data/ora)
        analyzeSharedEvents();

        // Renderizza tabella
        renderEventsTable();

        // Nascondi loading, mostra tabella
        loadingEl.classList.add('hidden');
        tableContainer.classList.remove('hidden');

    } catch (error) {
        console.error('❌ Errore caricamento eventi:', error);
        loadingEl.classList.add('hidden');

        let errorMessage = 'Errore durante il caricamento degli eventi.';
        if (error.message) {
            errorMessage += '\n' + error.message;
        }

        eventsError.textContent = errorMessage;
        eventsError.classList.remove('hidden');
    }
}

/**
 * Analizza eventi condivisi (stessa data e ora di inizio)
 */
function analyzeSharedEvents() {
    // Raggruppa eventi per data/ora di inizio
    const groups = {};

    state.events.forEach(event => {
        // Usa data/ora inizio come chiave
        const key = event.start?.dateTime || event.start?.date || '';
        if (key) {
            if (!groups[key]) {
                groups[key] = [];
            }
            groups[key].push(event);
        }
    });

    // Assegna numero gruppo solo a gruppi con più di 1 evento
    let groupId = 1;
    const sharedGroups = [];

    Object.entries(groups).forEach(([key, events]) => {
        if (events.length > 1) {
            // Questo gruppo ha eventi condivisi!
            events.forEach(event => {
                event.sharedGroupId = groupId;
                event.sharedCount = events.length;
            });
            sharedGroups.push({
                id: groupId,
                dateTime: key,
                count: events.length,
                events: events
            });
            groupId++;
        }
    });

    console.log(`💰 Eventi condivisi trovati: ${sharedGroups.length} gruppi`);
    sharedGroups.forEach(group => {
        console.log(`  Gruppo #${group.id}: ${group.count} eventi alla stessa data/ora (${formatDateTime(group.dateTime, null)})`);
    });
}

/**
 * Normalizza data in formato leggibile (timezone Europe/Zurich)
 */
function formatDateTime(dateTimeStr, dateStr) {
    if (!dateTimeStr && !dateStr) return '';

    try {
        const dateInput = dateTimeStr || dateStr;
        const date = new Date(dateInput);

        // Se è solo una data (senza orario), mostra solo la data
        if (dateStr && !dateTimeStr) {
            return date.toLocaleDateString('it-CH', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                timeZone: 'Europe/Zurich'
            });
        }

        // Altrimenti mostra data e ora
        return date.toLocaleString('it-CH', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            timeZone: 'Europe/Zurich'
        });
    } catch (error) {
        return dateTimeStr || dateStr || '';
    }
}

/**
 * Renderizza la tabella degli eventi
 */
function renderEventsTable() {
    const tbody = document.getElementById('eventsTableBody');
    const eventsCount = document.getElementById('eventsCount');
    const calendarsCount = document.getElementById('calendarsCount');

    tbody.innerHTML = '';
    eventsCount.textContent = state.events.length;
    calendarsCount.textContent = state.selectedCalendars.size;

    state.events.forEach(event => {
        const row = createEventRow(event);
        tbody.appendChild(row);
    });
}

/**
 * Crea una riga per un evento
 */
function createEventRow(event) {
    const tr = document.createElement('tr');
    tr.dataset.eventId = event.id;

    // Data/Ora Inizio
    const tdStart = document.createElement('td');
    tdStart.textContent = formatDateTime(event.start?.dateTime, event.start?.date);
    tr.appendChild(tdStart);

    // Data/Ora Fine
    const tdEnd = document.createElement('td');
    tdEnd.textContent = formatDateTime(event.end?.dateTime, event.end?.date);
    tr.appendChild(tdEnd);

    // Calendario
    const tdCalendar = document.createElement('td');
    tdCalendar.textContent = event.calendarName || event.calendarId;
    tdCalendar.style.fontSize = '0.9em';
    tdCalendar.style.color = '#666';
    tr.appendChild(tdCalendar);

    // Titolo + Descrizione
    const tdTitle = document.createElement('td');

    const titleContainer = document.createElement('div');
    titleContainer.className = 'event-title-container';

    // Titolo
    const titleDiv = document.createElement('div');
    titleDiv.className = 'event-title';
    titleDiv.textContent = event.summary || '(Nessun titolo)';
    titleContainer.appendChild(titleDiv);

    // Descrizione (se esiste)
    if (event.description) {
        const descDiv = document.createElement('div');
        descDiv.className = 'event-description';
        // Rimuovi HTML tags e tronca se troppo lungo
        const cleanDesc = event.description.replace(/<[^>]*>/g, '').trim();
        descDiv.textContent = cleanDesc.length > 200
            ? cleanDesc.substring(0, 200) + '...'
            : cleanDesc;
        titleContainer.appendChild(descDiv);
    }

    tdTitle.appendChild(titleContainer);
    tr.appendChild(tdTitle);

    // Colonna Condiviso (badge)
    const tdShared = document.createElement('td');
    if (event.sharedGroupId) {
        const badge = document.createElement('span');
        badge.className = 'shared-badge';
        badge.textContent = `#${event.sharedGroupId} (${event.sharedCount}x)`;
        badge.title = `Questo evento è condiviso in ${event.sharedCount} calendari - Gruppo #${event.sharedGroupId}`;
        tdShared.appendChild(badge);
    }
    tr.appendChild(tdShared);

    // Stato
    const tdStatus = document.createElement('td');
    const statusSpan = document.createElement('span');
    statusSpan.className = `event-status ${event.status || 'confirmed'}`;
    statusSpan.textContent = event.status || 'confirmed';
    tdStatus.appendChild(statusSpan);
    tr.appendChild(tdStatus);

    // Azioni
    const tdActions = document.createElement('td');
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'event-actions';

    if (event.htmlLink) {
        const linkA = document.createElement('a');
        linkA.href = event.htmlLink;
        linkA.target = '_blank';
        linkA.textContent = 'Apri';
        actionsDiv.appendChild(linkA);
    }

    const detailsA = document.createElement('a');
    detailsA.href = '#';
    detailsA.textContent = 'Dettagli';
    detailsA.onclick = (e) => {
        e.preventDefault();
        showEventDetails(event);
    };
    actionsDiv.appendChild(detailsA);

    tdActions.appendChild(actionsDiv);
    tr.appendChild(tdActions);

    return tr;
}

/**
 * Mostra dettagli evento (placeholder)
 */
function showEventDetails(event) {
    const details = `
Titolo: ${event.summary || '(Nessun titolo)'}
Calendario: ${event.calendarName}
Inizio: ${formatDateTime(event.start?.dateTime, event.start?.date)}
Fine: ${formatDateTime(event.end?.dateTime, event.end?.date)}
Stato: ${event.status || 'confirmed'}
Descrizione: ${event.description || '(Nessuna descrizione)'}
    `.trim();

    alert(details);
}

/**
 * Filtra eventi per ricerca
 */
function filterEvents() {
    const searchText = document.getElementById('eventSearch').value.toLowerCase();
    const rows = document.querySelectorAll('#eventsTableBody tr');

    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        if (text.includes(searchText)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

/**
 * Esporta eventi in CSV
 */
function exportEventsCSV() {
    if (state.events.length === 0) {
        alert('Nessun evento da esportare.');
        return;
    }

    // Intestazioni CSV
    const headers = ['calendarId', 'calendarName', 'eventId', 'summary', 'start', 'end', 'status', 'description', 'htmlLink'];

    // Converti eventi in righe CSV
    const rows = state.events.map(event => {
        return [
            event.calendarId || '',
            event.calendarName || '',
            event.id || '',
            event.summary || '',
            formatDateTime(event.start?.dateTime, event.start?.date),
            formatDateTime(event.end?.dateTime, event.end?.date),
            event.status || '',
            (event.description || '').replace(/\n/g, ' '),
            event.htmlLink || ''
        ].map(field => {
            // Escape virgole e virgolette
            const str = String(field);
            if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                return '"' + str.replace(/"/g, '""') + '"';
            }
            return str;
        }).join(',');
    });

    // Combina intestazioni e righe
    const csv = [headers.join(','), ...rows].join('\n');

    // Download file
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', `events_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.display = 'none';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    console.log(`✓ CSV esportato: ${state.events.length} eventi`);
}

// ============================================================================
// Google Classroom API
// ============================================================================

/**
 * Wrapper per chiamate API Classroom
 */
async function classroomApiGet(endpoint, params = {}) {
    const url = new URL(`${CONFIG.CLASSROOM_API_BASE}${endpoint}`);
    Object.keys(params).forEach(key => {
        const value = params[key];
        if (value === null || value === undefined) return;

        if (Array.isArray(value)) {
            value.forEach(v => url.searchParams.append(key, v));
        } else {
            url.searchParams.append(key, value);
        }
    });

    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${state.accessToken}`,
            'Accept': 'application/json'
        }
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: { message: response.statusText } }));
        throw new Error(error.error?.message || `HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
}

/**
 * Carica tutti i corsi con paginazione automatica
 */
async function fetchAllCourses() {
    let allCourses = [];
    let pageToken = null;

    do {
        const params = {
            pageSize: 100,
            courseStates: 'ACTIVE' // Solo corsi attivi
        };

        if (pageToken) {
            params.pageToken = pageToken;
        }

        const response = await classroomApiGet('/courses', params);

        if (response.courses) {
            allCourses = allCourses.concat(response.courses);
        }

        pageToken = response.nextPageToken;

    } while (pageToken);

    return allCourses;
}

/**
 * Carica la lista dei corsi (chiamata dal bottone)
 */
async function loadCourses() {
    if (!ensureTokenClient()) return;

    // Se abbiamo già il token, carica direttamente
    if (state.accessToken) {
        await doLoadCourses();
        return;
    }

    // Mostra loading UI e richiedi token (consent solo al primo giro)
    const btn = document.getElementById('loadCoursesBtn');
    const loading = document.getElementById('loadingCourses');
    btn.disabled = true;
    loading.classList.remove('hidden');

    requestAccessTokenFor('loadCourses');
}

/**
 * Esegue il caricamento effettivo dei corsi
 */
async function doLoadCourses() {
    const btn = document.getElementById('loadCoursesBtn');
    const loading = document.getElementById('loadingCourses');
    const listContainer = document.getElementById('coursesListContainer');
    const errorDiv = document.getElementById('coursesErrorMessage');

    try {
        btn.disabled = true;
        loading.classList.remove('hidden');
        errorDiv.classList.add('hidden');
        listContainer.classList.add('hidden');

        console.log('📚 Caricamento corsi Google Classroom...');

        const courses = await fetchAllCourses();
        state.courses = courses;

        console.log(`✓ Caricati ${courses.length} corsi`);

        // Renderizza lista corsi
        renderCoursesList(courses);

        // Mostra lista
        listContainer.classList.remove('hidden');

    } catch (error) {
        console.error('❌ Errore caricamento corsi:', error);
        showCoursesError(`Errore nel caricamento dei corsi: ${error.message}`);
    } finally {
        loading.classList.add('hidden');
        btn.disabled = false;
    }
}

/**
 * Renderizza la lista dei corsi
 */
function renderCoursesList(courses) {
    const container = document.getElementById('coursesList');
    container.innerHTML = '';

    document.getElementById('totalCoursesCount').textContent = courses.length;

    if (courses.length === 0) {
        container.innerHTML = '<p style="text-align:center; color:#666; padding:40px;">Nessun corso trovato</p>';
        return;
    }

    courses.forEach(course => {
        const card = createCourseCard(course);
        container.appendChild(card);
    });
}

/**
 * Crea card per un corso (cliccabile)
 */
function createCourseCard(course) {
    const card = document.createElement('div');
    card.className = 'course-card clickable';
    card.onclick = () => loadCourseClasswork(course);

    const info = document.createElement('div');
    info.className = 'course-info';

    const name = document.createElement('div');
    name.className = 'course-name';
    name.textContent = course.name;

    const details = document.createElement('div');
    details.className = 'course-details';

    const section = course.section ? `${course.section}` : '';
    const room = course.room ? ` · ${course.room}` : '';
    const state_text = course.courseState ? ` · ${course.courseState}` : '';

    details.textContent = `${section}${room}${state_text}`.trim() || 'Nessun dettaglio';

    const id = document.createElement('div');
    id.className = 'course-id';
    id.textContent = `ID: ${course.id}`;

    info.appendChild(name);
    info.appendChild(details);
    info.appendChild(id);

    card.appendChild(info);

    return card;
}async function loadCourseClasswork(course) {
    state.currentCourse = course;

    const loadingDiv = document.getElementById('loadingClasswork');
    const contentDiv = document.getElementById('classworkContainer');
    const errorDiv = document.getElementById('classworkErrorMessage');

    try {
        // Nascondi sezione corsi e mostra sezione classwork
        document.getElementById('coursesSection').classList.add('hidden');
        document.getElementById('classworkSection').classList.remove('hidden');
        document.getElementById('currentCourseName').textContent = course.name;

        loadingDiv.classList.remove('hidden');
        contentDiv.classList.add('hidden');
        errorDiv.classList.add('hidden');

        console.log(`📚 Caricamento classwork per: ${course.name}`);

        // Carica topics, courseWork e materiali in parallelo
        const [topics, courseWork, courseMaterials] = await Promise.all([
            fetchCourseTopics(course.id),
            fetchCourseWork(course.id),
            fetchCourseWorkMaterials(course.id)
        ]);

        state.topics = topics;
        state.courseWork = courseWork.concat(courseMaterials);

        updateClassworkSummary(course);

        console.log(`V Caricati ${topics.length} argomenti e ${state.courseWork.length} materiali/compiti`);
        // Renderizza contenuto organizzato
        renderClasswork();

        contentDiv.classList.remove('hidden');

    } catch (error) {
        console.error('❌ Errore caricamento classwork:', error);
        showClassworkError(`Errore: ${error.message}`);
    } finally {
        loadingDiv.classList.add('hidden');
    }
}

/**
 * Carica topics di un corso
 */
async function fetchCourseTopics(courseId) {
    let allTopics = [];
    let pageToken = null;

    do {
        const params = { pageSize: 100 };
        if (pageToken) params.pageToken = pageToken;

        const response = await classroomApiGet(`/courses/${courseId}/topics`, params);

        if (response.topic) {
            allTopics = allTopics.concat(response.topic);
        } else if (response.topics) {
            allTopics = allTopics.concat(response.topics);
        }

        pageToken = response.nextPageToken;

    } while (pageToken);

    return allTopics;
}

/**
 * Carica courseWork di un corso
 */
async function fetchCourseWork(courseId) {
    let allCourseWork = [];
    let pageToken = null;

    do {
        const params = {
            pageSize: 100,
            orderBy: 'updateTime desc',
            courseWorkStates: ['PUBLISHED', 'DRAFT'] // 'SCHEDULED' non supportato dall'API
        };
        if (pageToken) params.pageToken = pageToken;

        const response = await classroomApiGet(`/courses/${courseId}/courseWork`, params);

        if (response.courseWork) {
            allCourseWork = allCourseWork.concat(response.courseWork);
        }

        pageToken = response.nextPageToken;

    } while (pageToken);

    return allCourseWork;
}

/**
 * Carica courseWorkMaterials di un corso
 */
async function fetchCourseWorkMaterials(courseId) {
    let allMaterials = [];
    let pageToken = null;

    do {
        const params = {
            pageSize: 100,
            orderBy: 'updateTime desc',
            courseWorkMaterialStates: ['PUBLISHED', 'DRAFT'] // 'SCHEDULED' non supportato
        };
        if (pageToken) params.pageToken = pageToken;

        const response = await classroomApiGet(`/courses/${courseId}/courseWorkMaterials`, params);

        if (response.courseWorkMaterial) {
            allMaterials = allMaterials.concat(response.courseWorkMaterial);
        }

        pageToken = response.nextPageToken;

    } while (pageToken);

    return allMaterials;
}

/**
 * Aggiorna riepilogo del corso selezionato (info + conteggi)
 */
function updateClassworkSummary(course) {
    const summaryEl = document.getElementById('classworkSummary');
    if (!summaryEl) return;

    const metaParts = [];
    if (course.section) metaParts.push(course.section);
    if (course.room) metaParts.push(course.room);
    if (course.courseState) metaParts.push(course.courseState);

    summaryEl.innerHTML = `
        <div class="classwork-course-name">${course.name} (ID: ${course.id})</div>
        <div class="classwork-meta">${metaParts.join(' · ') || 'Nessun dettaglio'}</div>
        <div class="classwork-counts">${state.topics.length} argomenti, ${state.courseWork.length} materiali/compiti</div>
    `;
}

/**
 * Renderizza classwork organizzato per argomento
 */
function renderClasswork() {
    const container = document.getElementById('classworkContent');
    container.innerHTML = '';

    // Organizza courseWork per topicId
    const workByTopic = {};
    const orphanedWork = [];

    // Mappa topicId -> topic per riferimento rapido
    const topicMap = {};
    state.topics.forEach(topic => { topicMap[topic.topicId] = topic; });

    state.courseWork.forEach(work => {
        if (work.topicId && topicMap[work.topicId]) {
            if (!workByTopic[work.topicId]) {
                workByTopic[work.topicId] = [];
            }
            workByTopic[work.topicId].push(work);
        } else {
            // Nessun topic o topic non presente: considera orfano
            orphanedWork.push(work);
        }
    });

    // Renderizza topics con i loro materiali
    state.topics.forEach(topic => {
        const topicSection = createTopicSection(topic, workByTopic[topic.topicId] || []);
        container.appendChild(topicSection);
    });

    // Renderizza materiali orfani
    if (orphanedWork.length > 0) {
        const orphanSection = createTopicSection(
            { topicId: null, name: 'Senza argomento' },
            orphanedWork
        );
        orphanSection.classList.add('orphan-topic');
        container.appendChild(orphanSection);
    }

    if (state.topics.length === 0 && orphanedWork.length === 0) {
        container.innerHTML = '<p style="text-align:center; color:#666; padding:40px;">Nessun materiale trovato</p>';
    }
}

/**
 * Raggruppa classwork per topic, includendo orfani
 */
function getClassworkByTopic() {
    const topicMap = {};
    state.topics.forEach(t => { topicMap[t.topicId] = t.name; });

    const grouped = state.topics.map(t => ({
        id: t.topicId,
        name: t.name,
        items: []
    }));

    const orphanItems = [];

    state.courseWork.forEach(item => {
        if (item.topicId && topicMap[item.topicId]) {
            const target = grouped.find(g => g.id === item.topicId);
            if (target) {
                target.items.push(item);
            }
        } else {
            orphanItems.push(item);
        }
    });

    return { grouped, orphanItems };
}

/**
 * Export classwork in JSON (course -> topics -> items, più orfani)
 */
function exportClassworkJSON() {
    if (!state.currentCourse) {
        alert('Seleziona un corso prima di esportare.');
        return;
    }

    const { grouped, orphanItems } = getClassworkByTopic();

    const data = {
        course: {
            id: state.currentCourse.id,
            name: state.currentCourse.name,
            section: state.currentCourse.section || '',
            room: state.currentCourse.room || '',
            state: state.currentCourse.courseState || ''
        },
        topics: grouped.map(t => ({
            id: t.id,
            name: t.name,
            items: t.items.map(item => ({
                id: item.id || '',
                title: item.title || '',
                description: item.description || '',
                workType: item.workType || '',
                state: item.state || '',
                alternateLink: item.alternateLink || ''
            }))
        })),
        noTopic: orphanItems.map(item => ({
            id: item.id || '',
            title: item.title || '',
            description: item.description || '',
            workType: item.workType || '',
            state: item.state || '',
            alternateLink: item.alternateLink || ''
        }))
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const safeCourse = (state.currentCourse.name || 'classwork').replace(/[^a-z0-9_-]+/gi, '_');
    link.download = `${safeCourse}_classwork.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

/**
 * Export classwork in CSV: Argomento, Titolo, Descrizione
 */
function exportClassworkCSV() {
    if (!state.currentCourse) {
        alert('Seleziona un corso prima di esportare.');
        return;
    }

    const { grouped, orphanItems } = getClassworkByTopic();
    const rows = [];

    const escapeCSV = (val) => {
        const str = (val ?? '').toString().replace(/\r?\n/g, ' ').replace(/\s+/g, ' ').trim();
        if (str.includes(',') || str.includes('"')) {
            return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
    };

    grouped.forEach(topic => {
        const topicName = topic.name || '';
        topic.items.forEach(item => {
            rows.push([
                escapeCSV(topicName),
                escapeCSV(item.title || ''),
                escapeCSV(item.description || '')
            ].join(','));
        });
    });

    if (orphanItems.length) {
        const orphanLabel = 'Senza argomento';
        orphanItems.forEach(item => {
            rows.push([
                escapeCSV(orphanLabel),
                escapeCSV(item.title || ''),
                escapeCSV(item.description || '')
            ].join(','));
        });
    }

    const header = ['Argomento', 'Titolo materiale', 'Descrizione'].join(',');
    const csv = [header, ...rows].join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const safeCourse = (state.currentCourse.name || 'classwork').replace(/[^a-z0-9_-]+/gi, '_');
    link.download = `${safeCourse}_classwork.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

/**
 * Crea sezione per un topic con i suoi courseWork
 */
function createTopicSection(topic, workItems) {
    const section = document.createElement('div');
    section.className = 'topic-section';

    const header = document.createElement('div');
    header.className = 'topic-header';
    header.textContent = topic.name;
    section.appendChild(header);

    if (workItems.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'topic-empty';
        empty.textContent = 'Nessun materiale in questo argomento';
        section.appendChild(empty);
    } else {
        const workList = document.createElement('div');
        workList.className = 'work-list';

        workItems.forEach(work => {
            const workItem = createWorkItem(work);
            workList.appendChild(workItem);
        });

        section.appendChild(workList);
    }

    return section;
}

/**
 * Crea elemento per un courseWork
 */
function createWorkItem(work) {
    const item = document.createElement('div');
    item.className = 'work-item';

    const title = document.createElement('div');
    title.className = 'work-title';
    title.textContent = work.title || '(Senza titolo)';

    const meta = document.createElement('div');
    meta.className = 'work-meta';

    const type = work.workType || 'ASSIGNMENT';
    const state = work.state || 'PUBLISHED';
    meta.textContent = `${type}  ·  ${state}`;

    if (work.description) {
        const desc = document.createElement('div');
        desc.className = 'work-description';
        desc.textContent = work.description.replace(/<[^>]*>/g, '').substring(0, 150);
        item.appendChild(title);
        item.appendChild(desc);
        item.appendChild(meta);
    } else {
        item.appendChild(title);
        item.appendChild(meta);
    }

    if (work.alternateLink) {
        item.style.cursor = 'pointer';
        item.onclick = () => window.open(work.alternateLink, '_blank');
    }

    return item;
}

/**
 * Torna alla lista corsi
 */
function backToCourses() {
    document.getElementById('classworkSection').classList.add('hidden');
    document.getElementById('coursesSection').classList.remove('hidden');
    state.currentCourse = null;
    state.topics = [];
    state.courseWork = [];
    const summaryEl = document.getElementById('classworkSummary');
    if (summaryEl) summaryEl.innerHTML = '';
}

/**
 * Filtra corsi in base alla ricerca
 */
function filterCourses() {
    const searchText = document.getElementById('courseSearch').value.toLowerCase();
    const cards = document.querySelectorAll('.course-card');

    cards.forEach(card => {
        const name = card.querySelector('.course-name').textContent.toLowerCase();
        const details = card.querySelector('.course-details').textContent.toLowerCase();
        const id = card.querySelector('.course-id').textContent.toLowerCase();

        if (name.includes(searchText) || details.includes(searchText) || id.includes(searchText)) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
}

/**
 * Mostra errore nella sezione corsi
 */
function showCoursesError(message) {
    const errorDiv = document.getElementById('coursesErrorMessage');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
}

/**
 * Mostra errore nella sezione classwork
 */
function showClassworkError(message) {
    const errorDiv = document.getElementById('classworkErrorMessage');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
}

// ============================================================================
// Utility
// ============================================================================

/**
 * Mostra messaggio di errore
 */
function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
}

// ============================================================================
// Sincronizzazione Eventi Condivisi
// ============================================================================

/**
 * Parse tag [>calId1,calId2,...] da description
 * @param {string} description - Description dell'evento
 * @returns {Array<string>} Array di calendar IDs
 */
function parseReplicaTag(description) {
    if (!description) return [];

    const match = description.match(/\[>([^\]]+)\]/);
    if (!match) return [];

    return match[1].split(',').map(id => id.trim()).filter(id => id.length > 0);
}

/**
 * Parse tag [<masterCalId:masterEventId] da description
 * @param {string} description - Description dell'evento
 * @returns {Object|null} {calendarId, eventId} or null
 */
function parseMasterTag(description) {
    if (!description) return null;

    const match = description.match(/\[<([^:]+):([^\]]+)\]/);
    if (!match) return null;

    return {
        calendarId: match[1].trim(),
        eventId: match[2].trim()
    };
}

/**
 * Carica eventi master (con tag [>...]) da tutti i calendari
 */
async function loadMasterEvents() {
    const btn = document.getElementById('loadMasterBtn');
    const loading = document.getElementById('loadingMasterEvents');
    const container = document.getElementById('masterEventsContainer');
    const errorDiv = document.getElementById('syncErrorMessage');

    // Verifica autenticazione
    if (!state.accessToken) {
        showSyncError('Devi prima autenticarti. Clicca su "Carica Calendari" o "Carica Corsi".');
        return;
    }

    try {
        btn.disabled = true;
        loading.classList.remove('hidden');
        container.classList.add('hidden');
        errorDiv.classList.add('hidden');

        console.log('🔍 Ricerca eventi master...');

        // Carica tutti i calendari se non già caricati
        if (state.calendars.length === 0) {
            await doLoadCalendars();
        }

        // Cerca eventi master in tutti i calendari
        const masterEvents = [];

        for (const calendar of state.calendars) {
            const events = await fetchEventsFromCalendar(calendar.id, calendar.summary || calendar.id);

            // Filtra eventi con tag [>...]
            for (const event of events) {
                const description = event.description || '';
                const targetIds = parseReplicaTag(description);

                if (targetIds.length > 0) {
                    masterEvents.push({
                        calendar: calendar,
                        event: event,
                        targetCalendarIds: targetIds
                    });
                }
            }
        }

        console.log(`✓ Trovati ${masterEvents.length} eventi master`);

        // Salva in state
        state.masterEvents = masterEvents;

        // Renderizza
        renderMasterEvents(masterEvents);

        // Carica stato ultima sync
        loadSyncState();

        // Mostra container
        loading.classList.add('hidden');
        container.classList.remove('hidden');

    } catch (error) {
        console.error('❌ Errore caricamento eventi master:', error);
        loading.classList.add('hidden');
        showSyncError(`Errore: ${error.message}`);
    } finally {
        btn.disabled = false;
    }
}

/**
 * Renderizza lista eventi master
 * @param {Array} masterEvents - Array di eventi master
 */
function renderMasterEvents(masterEvents) {
    const listEl = document.getElementById('masterEventsList');
    const countEl = document.getElementById('masterEventsCount');

    listEl.innerHTML = '';
    countEl.textContent = masterEvents.length;

    if (masterEvents.length === 0) {
        listEl.innerHTML = `
            <div class="no-master-events">
                <p>Nessun evento master trovato.</p>
                <p>Per creare eventi master, aggiungi nella description dell'evento:</p>
                <code>[>calendarId1,calendarId2,calendarId3]</code>
            </div>
        `;
        return;
    }

    masterEvents.forEach(masterInfo => {
        const card = createMasterEventCard(masterInfo);
        listEl.appendChild(card);
    });
}

/**
 * Crea card per evento master
 * @param {Object} masterInfo - Info evento master
 * @returns {HTMLElement}
 */
function createMasterEventCard(masterInfo) {
    const { calendar, event, targetCalendarIds } = masterInfo;

    const card = document.createElement('div');
    card.className = 'master-event-card';

    // Header con titolo e calendario
    const header = document.createElement('div');
    header.className = 'master-event-header';

    const title = document.createElement('div');
    title.className = 'master-event-title';
    title.textContent = event.summary || '(Nessun titolo)';

    const calendarInfo = document.createElement('div');
    calendarInfo.className = 'master-event-calendar';
    calendarInfo.textContent = `📅 ${calendar.summary || calendar.id}`;

    header.appendChild(title);
    header.appendChild(calendarInfo);

    // Dettagli evento
    const details = document.createElement('div');
    details.className = 'master-event-details';

    const dateTime = formatDateTime(event.start?.dateTime, event.start?.date);
    const dateInfo = document.createElement('div');
    dateInfo.className = 'master-event-date';
    dateInfo.textContent = `📆 ${dateTime}`;
    details.appendChild(dateInfo);

    // Location se presente
    if (event.location) {
        const locationInfo = document.createElement('div');
        locationInfo.className = 'master-event-location';
        locationInfo.textContent = `📍 ${event.location}`;
        details.appendChild(locationInfo);
    }

    // Meet link se presente
    if (event.hangoutLink) {
        const meetInfo = document.createElement('div');
        meetInfo.className = 'master-event-meet';
        const meetLink = document.createElement('a');
        meetLink.href = event.hangoutLink;
        meetLink.target = '_blank';
        meetLink.textContent = '🎥 Link Google Meet';
        meetInfo.appendChild(meetLink);
        details.appendChild(meetInfo);
    }

    // Target calendari
    const targetsInfo = document.createElement('div');
    targetsInfo.className = 'master-event-targets';
    targetsInfo.innerHTML = `<strong>Replica verso ${targetCalendarIds.length} calendari:</strong>`;

    const targetsList = document.createElement('ul');
    targetsList.className = 'target-calendars-list';

    targetCalendarIds.forEach(targetId => {
        const li = document.createElement('li');

        // Cerca nome calendario se disponibile
        const targetCal = state.calendars.find(c => c.id === targetId);
        const targetName = targetCal ? targetCal.summary : targetId;

        li.textContent = targetName;
        li.title = targetId;
        targetsList.appendChild(li);
    });

    targetsInfo.appendChild(targetsList);

    // Actions
    const actions = document.createElement('div');
    actions.className = 'master-event-actions';

    if (event.htmlLink) {
        const viewLink = document.createElement('a');
        viewLink.href = event.htmlLink;
        viewLink.target = '_blank';
        viewLink.className = 'btn-link';
        viewLink.textContent = 'Apri in Google Calendar';
        actions.appendChild(viewLink);
    }

    // Assemble card
    card.appendChild(header);
    card.appendChild(details);
    card.appendChild(targetsInfo);
    card.appendChild(actions);

    return card;
}

/**
 * Carica stato ultima sincronizzazione da sync_state.json
 */
async function loadSyncState() {
    try {
        const response = await fetch('sync_state.json');
        if (!response.ok) {
            // File non esiste ancora
            return;
        }

        const syncState = await response.json();

        if (syncState.last_sync) {
            const lastSync = new Date(syncState.last_sync);
            const timeAgo = getTimeAgo(lastSync);

            const infoEl = document.getElementById('lastSyncInfo');
            infoEl.textContent = `Ultima sincronizzazione: ${timeAgo}`;
            infoEl.title = lastSync.toLocaleString('it-IT');
        }

    } catch (error) {
        // Ignora errori (file potrebbe non esistere)
        console.log('Nessuno stato di sincronizzazione trovato');
    }
}

/**
 * Calcola tempo trascorso in formato leggibile
 * @param {Date} date - Data da confrontare
 * @returns {string}
 */
function getTimeAgo(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'meno di 1 minuto fa';
    if (diffMins < 60) return `${diffMins} minuti fa`;
    if (diffHours < 24) return `${diffHours} ore fa`;
    if (diffDays === 1) return 'ieri';
    if (diffDays < 7) return `${diffDays} giorni fa`;

    return date.toLocaleDateString('it-IT');
}

/**
 * Mostra errore nella sezione sync
 * @param {string} message - Messaggio di errore
 */
function showSyncError(message) {
    const errorDiv = document.getElementById('syncErrorMessage');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
}















