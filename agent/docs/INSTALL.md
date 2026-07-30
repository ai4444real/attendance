# Installazione privata sul VPS

## Prerequisiti

- Codex autenticato per l'utente `ubuntu`;
- clone non-prod del repository Rebekko in `/home/ubuntu/src/rebekko-webapps`;
- produzione attuale in `/opt/rebekko/webapps`;
- Python 3 con il pacchetto `venv`;
- accesso privato al servizio, per esempio via tunnel SSH o rete privata.

Sul VPS il path standard atteso per Codex e':

```text
/home/ubuntu/.npm-global/bin/codex
```

## Copia e installazione

Copiare soltanto questa directory autonoma in `/opt/rebekko-agent`, quindi:

```bash
cd /opt/rebekko-agent
sudo ./scripts/install.sh
```

Il database locale dell'agente viene creato in:

```text
/var/lib/rebekko-agent/agent.sqlite3
```

Il file di configurazione privato e':

```text
/etc/rebekko-agent.env
```

Il servizio usa due livelli di protezione:

- Codex viene avviato con sandbox `workspace-write` sul clone di sviluppo.
- systemd limita comunque le directory scrivibili a clone, `~/.codex` e database
  interno dell'agente.

La produzione viene toccata solo dal deploy confermato.

Il deploy confermato viene eseguito in una unita' systemd transitoria e
separata tramite `sudo systemd-run`. L'utente `ubuntu` deve avere il permesso
sudo non interattivo necessario.

## Configurazione

Valori iniziali:

```text
REBEKKO_AGENT_BIND=127.0.0.1
REBEKKO_AGENT_PORT=8090
REBEKKO_AGENT_REPO=/home/ubuntu/src/rebekko-webapps
REBEKKO_AGENT_CODEX=/home/ubuntu/.npm-global/bin/codex
REBEKKO_AGENT_DB=/var/lib/rebekko-agent/agent.sqlite3
REBEKKO_AGENT_DEPLOY_SCRIPT=/opt/rebekko/webapps/deploy.sh
REBEKKO_AGENT_DEPLOY_CONFIRM_SECONDS=60
```

## Accesso

La configurazione iniziale ascolta su localhost:

```text
http://127.0.0.1:8090
```

Per un primo collaudo usare un tunnel SSH:

```bash
ssh -L 8090:127.0.0.1:8090 ubuntu@VPS
```

Se si usa una rete privata tipo Tailscale, impostare il bind in
`/etc/rebekko-agent.env`, poi:

```bash
sudo systemctl restart rebekko-agent
```

La porta 8090 non deve essere aperta nel firewall pubblico.

## Verifiche

```bash
curl http://127.0.0.1:8090/health
sudo systemctl status rebekko-agent --no-pager
journalctl -u rebekko-agent -n 100 --no-pager
```

Controllare dalla chat:

```text
/status
```

Poi inviare una richiesta innocua, per esempio chiedere di leggere lo stato
del progetto senza modificare file. Verificare che sessione e storico
sopravvivano a:

```bash
sudo systemctl restart rebekko-agent
```

Un job in esecuzione durante il riavvio viene terminato dal gruppo systemd e
marcato `failed` al successivo avvio.
