# Rebekko Codex Agent

Web app privata e autonoma per controllare Codex sul repository di sviluppo
Rebekko da telefono o browser.

L'agente non lavora direttamente sulla produzione. La directory di lavoro
predefinita di Codex e':

```text
/home/ubuntu/src/rebekko-webapps
```

La produzione (`/opt/rebekko/webapps`) viene toccata soltanto da
`/deploy confirm`, che esegue lo script di deploy configurato.

## Comandi chat

- testo normale: crea un job Codex;
- `/new`: dimentica la sessione corrente; il messaggio successivo ne crea una;
- `/status`: mostra branch, stato Git, job e sessione;
- `/stop`: interrompe il job attivo;
- `/deploy`: chiede conferma;
- `/deploy confirm`: entro 60 secondi esegue il deploy.

## Installazione sul VPS

La procedura dettagliata e' in [docs/INSTALL.md](docs/INSTALL.md). In breve:

```bash
sudo mkdir -p /opt/rebekko-agent
sudo cp -a agent/. /opt/rebekko-agent/
cd /opt/rebekko-agent
sudo ./scripts/install.sh
```

Per impostazione predefinita il servizio ascolta solo su `127.0.0.1:8090`.
Non esporre la porta tramite Caddy pubblico senza un livello di autenticazione
e controllo accessi dedicato.

## Sviluppo locale

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
REBEKKO_AGENT_REPO=/percorso/al/repo \
REBEKKO_AGENT_CODEX=/percorso/a/codex \
.venv/bin/uvicorn rebekko_agent.main:app --reload
```

Su PowerShell usare `$env:NOME_VARIABILE = "valore"`.
