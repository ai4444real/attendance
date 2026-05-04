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
chmod +x deploy.sh
./deploy.sh
```

`deploy.sh` fa gia' tutto lui:

- `git pull --ff-only origin main`
- install/update dei requirement nel virtualenv
- restart del servizio `rebekko-webapps`
- health check finale

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
