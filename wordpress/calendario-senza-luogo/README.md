# Calendario senza luogo

## Shortcode previsto

Il calendario richiede soltanto l'ID Google Calendar:

```text
[calendario_senza_luogo id="c_classroom10484a8b@group.calendar.google.com"]
```

L'esportazione CSV e' attiva per impostazione predefinita e puo' essere
controllata con il parametro opzionale `export`:

```text
[calendario_senza_luogo id="c_classroom10484a8b@group.calendar.google.com" export="true"]
[calendario_senza_luogo id="c_classroom10484a8b@group.calendar.google.com" export="false"]
```

Sono accettati come valori falsi `false`, `0` e `no`; ogni altro valore valido
mantiene l'esportazione visibile.

## Anteprima

Aprire `preview.html` normalmente per vedere il pulsante CSV. Per simulare
`export="false"`, aprire:

```text
preview.html?export=false
```

Il CSV contiene soltanto titolo, date, orari e descrizione degli eventi del
mese visualizzato. Non contiene il luogo o link all'evento Google.

## Colore del banner

Il parametro opzionale `colore` accetta un colore esadecimale. Se viene omesso,
resta il blu predefinito `#005090`:

```text
[calendario_senza_luogo id="c_classroom10484a8b@group.calendar.google.com" colore="#d98b19"]
```
