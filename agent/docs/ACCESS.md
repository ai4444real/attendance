# Accesso a Rebekko Agent

## Indirizzo attuale

Rebekko Agent e' installato sul server `ov-0e356b` ed e' raggiungibile
esclusivamente dalla rete privata Tailscale.

Indirizzo verificato il 10 settembre 2026:

```text
http://100.96.47.111:8090
```

Link diretto: [Rebekko Agent](http://100.96.47.111:8090)

Usare esplicitamente **HTTP**, non HTTPS. Il servizio Uvicorn non gestisce TLS;
un tentativo HTTPS produce `Invalid HTTP request received` nei log.

Il nome breve seguente al momento non risolve e non deve essere usato come
indirizzo operativo:

```text
http://ov-0e356b:8090
```

Il dispositivo dal quale si apre la pagina deve essere collegato allo stesso
tailnet Tailscale del server.

## Configurazione effettiva

Il servizio systemd e' `rebekko-agent.service`. La configurazione installata
fa ascoltare Uvicorn direttamente sull'indirizzo Tailscale:

```text
REBEKKO_AGENT_BIND=100.96.47.111
REBEKKO_AGENT_PORT=8090
```

Per questo motivo `http://127.0.0.1:8090` sul server non funziona: il processo
non e' in ascolto sull'interfaccia loopback.

## Verifiche rapide

Sul server:

```bash
curl http://100.96.47.111:8090/health
sudo systemctl status rebekko-agent --no-pager -l
sudo journalctl -u rebekko-agent -n 80 --no-pager
grep -E '^REBEKKO_AGENT_(BIND|PORT)=' /etc/rebekko-agent.env
```

Per conoscere l'indirizzo Tailscale corrente del server:

```bash
tailscale ip -4
```

Se l'indirizzo cambia, aggiornare `REBEKKO_AGENT_BIND` in
`/etc/rebekko-agent.env` e riavviare il servizio:

```bash
sudo systemctl restart rebekko-agent
```

## Note

- Non e' configurato Tailscale Serve.
- Non e' necessario Visual Studio Code per accedere a questo agente.
- Non esporre direttamente la porta `8090` su Internet o tramite il Caddy
  pubblico: l'accesso previsto e' quello privato via Tailscale.
