# Deploy Ubuntu Server

Runbook operativo del server Ubuntu su cui girano:

- `n8n` come servizio pubblico su dominio;
- `Rebekko Webapps` come servizio pubblico su dominio dedicato.

Scopo del file:

- sapere rapidamente cosa gira sul server;
- sapere su quali porte ascoltano i servizi;
- ricordare quali file di configurazione sono coinvolti;
- avere i comandi esatti di controllo e deploy.

## Stato attuale

### Stack in esecuzione

- OS: Ubuntu
- Reverse proxy pubblico: `Caddy`
- Application server Python: `uvicorn`
- App Python: `FastAPI`
- Service manager: `systemd`
- Deploy mode: senza Docker per `webapps`
- Docker: usato per `n8n`

### Host server

- provider: Infomaniak
- nome host: `automation-hub`
- utente SSH: `ubuntu`
- IP server: `83.228.222.114`

Accesso SSH:

```bash
ssh -i C:\Users\simone\.ssh\automation-hub-key.dropboxignore ubuntu@83.228.222.114
```

## Architettura attuale

### n8n

- container Docker osservato: `n8n-n8n-1`
- porta container pubblicata: `5678`
- restart policy verificata: `unless-stopped`
- dominio pubblico: `automation.pnlevolution.com`
- reverse proxy pubblico: `Caddy`

Routing pubblico attuale:

```text
automation.pnlevolution.com
  -> Caddy (:80/:443)
  -> reverse_proxy localhost:5678
  -> n8n
```

### Rebekko Webapps

- repository clonato in: `/opt/rebekko/webapps`
- virtualenv: `/opt/rebekko/webapps/.venv`
- backend entrypoint: `backend.main:app`
- modulo attivo oggi: `attendance`
- servizio `systemd`: `rebekko-webapps`
- ascolto interno: `127.0.0.1:8080`
- dominio pubblico: `rebekko.pnlevolution.com`
- reverse proxy pubblico: `Caddy`

Routing attuale:

```text
rebekko.pnlevolution.com
  -> Caddy (:80/:443)
  -> reverse_proxy 127.0.0.1:8080
  -> uvicorn
  -> FastAPI
```

Nota importante:

- `n8n` e `webapps` sono separati;
- il deploy di `webapps` non deve rompere `automation.pnlevolution.com`;
- il routing pubblico reale e' gestito da `Caddy`.

## File di configurazione coinvolti

### Webapps

- codice: `/opt/rebekko/webapps`
- virtualenv: `/opt/rebekko/webapps/.venv`
- unit file `systemd`: `/etc/systemd/system/rebekko-webapps.service`

### Caddy

- file principale: `/etc/caddy/Caddyfile`
- service name: `caddy`

Configurazione osservata:

```caddy
automation.pnlevolution.com {
    reverse_proxy localhost:5678
}

rebekko.pnlevolution.com {
    reverse_proxy 127.0.0.1:8080
}
```

### n8n

- gira in Docker
- verifica rapida:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## Installazione eseguita per Webapps

Pacchetti verificati sul server:

```bash
python3 --version
pip3 --version
git --version
caddy version
docker --version
```

Setup applicativo eseguito:

```bash
cd /opt/rebekko
git clone https://github.com/ai4444real/attendance.git webapps
cd /opt/rebekko/webapps
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Servizio systemd di Webapps

### Nome servizio

- `rebekko-webapps`

### File unit

Percorso:

```bash
/etc/systemd/system/rebekko-webapps.service
```

Contenuto attuale:

```ini
[Unit]
Description=Rebekko Webapps FastAPI
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/rebekko/webapps
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/rebekko/webapps/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Comandi utili systemd

Stato:

```bash
sudo systemctl status rebekko-webapps --no-pager
```

Avvio:

```bash
sudo systemctl start rebekko-webapps
```

Stop:

```bash
sudo systemctl stop rebekko-webapps
```

Restart:

```bash
sudo systemctl restart rebekko-webapps
```

Log recenti:

```bash
journalctl -u rebekko-webapps -n 100 --no-pager
```

Follow log:

```bash
journalctl -u rebekko-webapps -f
```

## Health e controlli runtime

### Health check applicazione

```bash
curl http://127.0.0.1:8080/health
```

Risposta attesa:

```json
{"status":"healthy","service":"rebekko-webapps"}
```

### Test rapido pagine principali

```bash
curl -s http://127.0.0.1:8080/ | head -c 120
echo
curl -s http://127.0.0.1:8080/attendance | head -c 120
echo
curl -s http://127.0.0.1:8080/attendance/view | head -c 120
echo
curl -s http://127.0.0.1:8080/attendance/manage/ | head -c 120
echo
```

### Verifica porte in ascolto

```bash
ss -ltnp | grep -E ':80|:443|:5678|:8080'
```

Stato atteso:

- `Caddy` su `:80` e `:443`
- `n8n` su `:5678`
- `uvicorn` su `127.0.0.1:8080`

## Caddy

### Comandi utili

Status:

```bash
sudo systemctl status caddy --no-pager
```

Restart:

```bash
sudo systemctl restart caddy
```

Log:

```bash
journalctl -u caddy -n 100 --no-pager
```

### Test pubblico n8n

HTTP:

```bash
curl -I http://automation.pnlevolution.com
```

Risposta attesa:

- `308 Permanent Redirect` verso HTTPS

HTTPS:

```bash
curl -I https://automation.pnlevolution.com
```

Risposta attesa:

- `200`

Nota:

- `n8n` richiede HTTPS per i secure cookie;
- se `automation.pnlevolution.com` viene servito solo in HTTP, la UI segnala errore e non e' usabile.

### Test pubblico Rebekko Webapps

HTTP:

```bash
curl -I http://rebekko.pnlevolution.com
```

Risposta attesa:

- `308 Permanent Redirect` verso HTTPS

HTTPS:

```bash
curl https://rebekko.pnlevolution.com/health
```

Risposta attesa:

```json
{"status":"healthy","service":"rebekko-webapps"}
```

## Nginx

Stato desiderato attuale:

- `nginx` non deve stare davanti al traffico pubblico;
- il reverse proxy pubblico corretto e' `Caddy`;
- `nginx` puo' restare installato, ma non deve occupare `:80` o `:443`.

Controlli rapidi:

```bash
sudo systemctl status nginx --no-pager
sudo systemctl is-enabled nginx
```

Stato atteso:

- fermo o comunque non in ascolto sulle porte pubbliche

## Deploy

Questa e' la procedura corretta per aggiornare `Rebekko Webapps` senza toccare `n8n`.

### Deploy rapido

```bash
cd /opt/rebekko/webapps
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart rebekko-webapps
sudo systemctl status rebekko-webapps --no-pager
```

### Verifica post-deploy

```bash
curl http://127.0.0.1:8080/health
curl https://rebekko.pnlevolution.com/health
curl -s http://127.0.0.1:8080/ | head -c 120
echo
curl -s http://127.0.0.1:8080/attendance | head -c 120
echo
curl -s http://127.0.0.1:8080/attendance/view | head -c 120
echo
curl -s http://127.0.0.1:8080/attendance/manage/ | head -c 120
echo
```

### Deploy one-command consigliato

Nel repository esiste gia' una base versionata:

```bash
deploy.sh
```

Puoi usarla cosi':

```bash
cd /opt/rebekko/webapps
chmod +x deploy.sh
./deploy.sh
```

Se vuoi ricrearla a mano sul server, il contenuto di riferimento e':

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/rebekko/webapps"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="rebekko-webapps"

cd "$APP_DIR"
git pull origin main
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl --no-pager --full status "$SERVICE_NAME"
```

## Controlli rapidi

### Quale versione di codice c'e' sul server?

```bash
cd /opt/rebekko/webapps
git log --oneline -1
git status --short --branch
```

### L'app Python gira davvero?

```bash
sudo systemctl status rebekko-webapps --no-pager
curl http://127.0.0.1:8080/health
```

### Caddy sta davvero servendo n8n?

```bash
curl -I http://automation.pnlevolution.com
curl -I https://automation.pnlevolution.com
```

### Caddy sta davvero servendo Rebekko Webapps?

```bash
curl -I http://rebekko.pnlevolution.com
curl https://rebekko.pnlevolution.com/health
```

### Docker ha ancora n8n in piedi?

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker inspect -f '{{ .HostConfig.RestartPolicy.Name }}' n8n-n8n-1
```

## Prossimi passi probabili

- mantenere `n8n` separato su `automation.pnlevolution.com`;
- mantenere `webapps` separata su `rebekko.pnlevolution.com`;
- introdurre `.env` reale quando entreranno database e integrazioni;
- tenere sincronizzato il `Caddyfile` reale del server con `infra/caddy/Caddyfile.example`;
- eventualmente dockerizzare `webapps` in futuro, se servirà davvero.

La scelta corrente resta intenzionalmente semplice:

- `Caddy` per esposizione pubblica e TLS;
- `systemd` + `uvicorn` per la webapp Python;
- niente Docker per `webapps`, per ora;
- Docker solo dove serve gia', cioe' su `n8n`.
