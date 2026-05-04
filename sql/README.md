# SQL Assets

Questa cartella contiene gli asset SQL versionati del progetto.

Uso previsto:
- `schema/`: DDL iniziale e successive revisioni dello schema
- `seed/`: eventuali dati iniziali o di supporto
- `queries/`: query utili per debug o operazioni manuali

Query utili gia' pronte:
- `queries/attendance_admin_queries.sql`: controlli rapidi su batch, lezioni,
  partecipanti e review actions del dominio attendance

Il database target è unico: `rebekko`.
I domini applicativi convivono nello stesso database con naming esplicito, ad
esempio:
- `attendance_*`
- `finance_*`
- `core_*`
