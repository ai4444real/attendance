# Database Backend

Questa cartella ospita il codice Python di accesso al database condiviso
`rebekko`.

Obiettivo:
- tenere separata la persistenza dal dominio `attendance_normalization`
- preparare il terreno per moduli futuri come `finance`
- evitare di mischiare SQL, connessioni e logica di business

Struttura prevista:
- `config.py`: lettura configurazione DB (`DATABASE_URL`)
- `connection.py`: connessione e helper di basso livello
- `repositories/`: accesso ai dati per dominio
- `migrations/` o equivalente, se in futuro serviranno migrazioni automatiche

Per ora lo schema SQL vive in `sql/schema/`.

Primo schema previsto:
- `attendance_import_batches`
- `attendance_lessons`
- `attendance_lesson_participants`
- `attendance_review_actions`
