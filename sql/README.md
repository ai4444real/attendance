# SQL Assets

Questa cartella contiene gli asset SQL versionati del progetto.

Uso previsto:
- `schema/`: DDL iniziale e successive revisioni dello schema
- `seed/`: eventuali dati iniziali o di supporto
- `queries/`: query utili per debug o operazioni manuali

Query utili gia' pronte:
- `queries/attendance_admin_queries.sql`: controlli rapidi su batch, lezioni,
  partecipanti e review actions del dominio attendance

Migrazioni schema attendance attuali:
- `schema/001_initial_schema.sql`
- `schema/002_attendance_identity_aliases.sql`
- `schema/003_attendance_identity_alias_types.sql`
- `schema/004_attendance_lesson_source_segments.sql`
- `schema/005_attendance_courses.sql`
- `schema/006_attendance_presence_source.sql`

Il database target è unico: `rebekko`.
I domini applicativi convivono nello stesso database con naming esplicito, ad
esempio:
- `attendance_*`
- `finance_*`
- `core_*`
