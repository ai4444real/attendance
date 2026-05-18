# Deploy

Mini runbook operativo per ricordarsi come pubblicare `Rebekko Webapps` sul server.

Per il runbook completo vedi anche:
- [DEPLOY_UBUNTU_SERVER.md](DEPLOY_UBUNTU_SERVER.md)

## Host

- server IP: `83.228.222.114`
- utente SSH: `ubuntu`
- repo sul server: `/opt/rebekko/webapps`
- servizio app: `rebekko-webapps`
- dominio pubblico app: `https://rebekko.pnlevolution.com`

## Login SSH

Da Windows:

```powershell
ssh -i C:\Users\simone\.ssh\automation-hub-key.dropboxignore ubuntu@83.228.222.114
```

## Deploy rapido

Una volta loggato sul server:

```bash
cd /opt/rebekko/webapps
./deploy.sh
```

`deploy.sh` fa gia' tutto lui:

- `git pull --ff-only origin main`
- install/update dei requirement nel virtualenv
- restart del servizio `rebekko-webapps`
- health check locale con retry su `127.0.0.1:8080`
- health check pubblico finale su `https://rebekko.pnlevolution.com/health`

## Primo allineamento server

Se il server e' rimasto indietro e `git pull` si ferma per una modifica locale a
`deploy.sh`, fai una volta sola:

```bash
cd /opt/rebekko/webapps
git checkout -- deploy.sh
git pull --ff-only origin main
./deploy.sh
```

## Verifica

Sul server:

```bash
systemctl status rebekko-webapps --no-pager
curl https://rebekko.pnlevolution.com/health
```

Risposta attesa:

```json
{"status":"healthy","service":"rebekko-webapps"}
```

Poi da browser:

```text
https://rebekko.pnlevolution.com/
```

## Backup CSV Attendance

Export leggibile delle tabelle operative principali:

```bash
cd /opt/rebekko/webapps
./scripts/export_attendance_backup.sh
```

Output predefinito:

```text
/opt/rebekko/webapps/backups/attendance/YYYYMMDDTHHMMSSZ/
```

Dentro trovi un CSV per tabella, `manifest.txt` con conteggio righe e, se disponibile, `SHA256SUMS`.

## Se qualcosa va storto

Log servizio:

```bash
journalctl -u rebekko-webapps -n 100 --no-pager
```

Stato repo sul server:

```bash
cd /opt/rebekko/webapps
git log --oneline -1
git status --short --branch
```

## Nota importante

- `n8n` vive separato su `automation.pnlevolution.com`
- il deploy di `webapps` non dovrebbe toccarlo
- il reverse proxy pubblico e TLS sono gestiti da `Caddy`, non da `nginx`
