/**
 * Courses Configuration
 *
 * Questo file contiene la configurazione dei corsi per il sistema di gestione presenze.
 * Modificabile manualmente con qualsiasi editor di testo.
 *
 * Per ogni corso puoi specificare:
 * - totalLessons: Numero totale di lezioni del corso
 * - attendanceThreshold: Soglia minima presenza per accedere all'esame (0.8 = 80%)
 * - description: Descrizione opzionale del corso
 * - startDate: Data inizio corso (opzionale, formato YYYY-MM-DD)
 * - active: true se il corso è attivo, false se archiviato
 */

const COURSES_CONFIG = {
  "version": "1.0",
  "lastUpdated": "2024-12-02",
  "description": "Configurazione corsi con numero totale lezioni e soglia presenza minima",
  "courses": {
    "_Analisi Transazionale AT ATI 27.09.25": {
      "totalLessons": 20,
      "attendanceThreshold": 0.8,
      "description": "Corso di Analisi Transazionale AT ATI",
      "active": true
    },
    "_Assistenti Master 25": {
      "totalLessons": null,
      "attendanceThreshold": 0.8,
      "description": "Corso aperto per Assistenti Master 2025",
      "active": true
    },
    "_Assistenti Practitioner 2025": {
      "totalLessons": null,
      "attendanceThreshold": 0.8,
      "description": "Corso aperto per Assistenti Practitioner 2025",
      "active": true
    },
    "_Coaching 25": {
      "totalLessons": 40,
      "attendanceThreshold": 0.8,
      "description": "Corso di Coaching 2025",
      "active": true
    },
    "_Counseling 25": {
      "totalLessons": 40,
      "attendanceThreshold": 0.8,
      "description": "Corso di Counseling 2025",
      "active": true
    },
    "_Direttore Vendite 18.09.2025": {
      "totalLessons": 40,
      "attendanceThreshold": 0.8,
      "description": "Corso Direttore Vendite",
      "active": true
    },
    "_Formazione interna - piani di lezione": {
      "totalLessons": null,
      "attendanceThreshold": 0.8,
      "description": "Formazione interna - partecipazione libera",
      "active": true
    },
    "_FSEA 02.25": {
      "totalLessons": 40,
      "attendanceThreshold": 0.8,
      "description": "Corso FSEA Febbraio 2025",
      "active": true
    },
    "_FSEA 10.25": {
      "totalLessons": 40,
      "attendanceThreshold": 0.8,
      "description": "Corso FSEA Ottobre 2025",
      "active": true
    },
    "_Master 25": {
      "totalLessons": 32,
      "attendanceThreshold": 0.8,
      "description": "Master 2025",
      "active": true
    },
    "_Mentore Aziendale 01.2025": {
      "totalLessons": 40,
      "attendanceThreshold": 0.8,
      "description": "Corso Mentore Aziendale",
      "active": true
    },
    "_Practitioner 2025": {
      "totalLessons": 32,
      "attendanceThreshold": 0.8,
      "description": "Practitioner 2025",
      "active": true
    },
    "_Riunione Assistenti 24-25": {
      "totalLessons": null,
      "attendanceThreshold": 0.8,
      "description": "Riunioni aperte per Assistenti",
      "active": true
    },
    "_SABATO in PRATICA 24-25": {
      "totalLessons": null,
      "attendanceThreshold": 0.8,
      "description": "Sabati pratici - partecipazione libera",
      "active": true
    },
    "_Training Autogeno 10.2025": {
      "totalLessons": 10,
      "attendanceThreshold": 0.8,
      "description": "Corso Training Autogeno",
      "active": true
    },
    "Bias Cognitivi": {
      "totalLessons": 8,
      "attendanceThreshold": 0.8,
      "description": "Corso Bias Cognitivi",
      "active": true
    },
    "Direttore Vendite - Digital & ECommerce 19.06.2025": {
      "totalLessons": 10,
      "attendanceThreshold": 0.8,
      "description": "Corso Direttore Vendite - Digital & ECommerce",
      "active": true
    },
    "Direttore Vendite - Marketing 31.10.2024": {
      "totalLessons": 10,
      "attendanceThreshold": 0.8,
      "description": "Corso Direttore Vendite - Marketing",
      "active": true
    },
    "Direttore Vendite 24": {
      "totalLessons": 12,
      "attendanceThreshold": 0.8,
      "description": "Corso Direttore Vendite 2024",
      "active": true
    },
    "FSEA 09.24": {
      "totalLessons": 18,
      "attendanceThreshold": 0.8,
      "description": "Corso FSEA Settembre 2024",
      "active": false
    },
    "LIFE COACH 01.2025": {
      "totalLessons": 6,
      "attendanceThreshold": 0.8,
      "description": "Corso Life Coach",
      "active": true
    },
    "Master 24": {
      "totalLessons": 32,
      "attendanceThreshold": 0.8,
      "description": "Master 2024",
      "active": false
    },
    "TEST CLASSE": {
      "totalLessons": null,
      "attendanceThreshold": 0.8,
      "description": "Classe di test",
      "active": false
    },
    "TIROCINIO Counselor / Coach": {
      "totalLessons": null,
      "attendanceThreshold": 0.8,
      "description": "Tirocinio - partecipazione variabile",
      "active": true
    }
  },
  "defaults": {
    "totalLessons": null,
    "attendanceThreshold": 0.8,
    "description": "Corso generico",
    "active": true
  }
};
