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
- `migrations/` o equivalente, se in futuro serviranno migrazioni automatiche

Implementazioni attuali:
- `attendance_draft_import_repository.py`: persistenza PostgreSQL del draft
  import (`import_batch`, `lessons`, `participants`)

Per ora lo schema SQL vive in `sql/schema/`.

Primo schema previsto:
- `attendance_import_batches`
- `attendance_lessons`
- `attendance_lesson_participants`
- `attendance_review_actions`
- `attendance_identity_aliases`

Regola architetturale:
- i contratti repository stanno fuori da `backend/db`
- `backend/db` contiene solo implementazioni concrete
- se domani cambia il database, deve cambiare qui e non nella logica applicativa
