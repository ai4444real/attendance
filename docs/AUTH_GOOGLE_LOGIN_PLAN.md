# Piano login Google

Obiettivo: proteggere Rebekko Webapps con login Google minimale, senza introdurre password locali e senza bloccare lo sviluppo se qualcosa non funziona.

## Principio guida

L'autenticazione deve essere reversibile in pochi secondi.

Kill switch nel `.env`:

```env
AUTH_ENABLED=false
```

Con `AUTH_ENABLED=false` l'app deve comportarsi esattamente come oggi.

Quando tutto e' pronto:

```env
AUTH_ENABLED=true
```

Rollback rapido sul server:

```bash
cd /opt/rebekko/webapps
sed -i 's/^AUTH_ENABLED=.*/AUTH_ENABLED=false/' .env
sudo systemctl restart rebekko-webapps
```

## Configurazione prevista

Variabili `.env`:

```env
AUTH_ENABLED=false
AUTH_GOOGLE_CLIENT_ID=163366057562-044umbigkalek9h110lb6ho5f8k5vnqe.apps.googleusercontent.com
AUTH_ALLOWED_EMAILS=nome@example.com,altro@example.com
AUTH_SESSION_SECRET=...
```

`AUTH_GOOGLE_CLIENT_ID` deve riferirsi a un OAuth client dedicato al login base, separato da eventuali client Google Classroom.

Scope previsti:

```text
openid email profile
```

## Routes pubbliche

Devono restare accessibili anche con auth attiva:

- `/login`
- `/logout`
- `/auth/google`
- `/health`
- asset statici: `/assets/*`, `/attendance/static/*`, eventuali statici utilities

## Routes protette

Quando `AUTH_ENABLED=true`, richiedono sessione valida:

- pagine Attendance
- API Attendance operative
- pagine Utilities
- API Utilities operative
- eventuali endpoint amministrativi futuri

## Rollout

1. Aggiungere codice auth spento di default.
2. Verificare deploy con `AUTH_ENABLED=false`: nessuna differenza funzionale.
3. Aggiungere pagina `/login` e verifica token Google lato backend.
4. Testare login e `/auth/whoami` senza proteggere tutta l'app.
5. Proteggere routes operative via middleware.
6. Accendere `AUTH_ENABLED=true` sul server.
7. Se qualcosa non va, usare il rollback rapido.

## Note operative

- Non fidarsi del solo frontend: il token Google va verificato lato backend.
- La allowlist nel `.env` e' il vero controllo applicativo.
- I test users in Google Cloud servono solo se l'app OAuth resta in modalita' Testing.
- Non usare gli scope Classroom/Calendar per questo login: complicano inutilmente la verifica OAuth.
