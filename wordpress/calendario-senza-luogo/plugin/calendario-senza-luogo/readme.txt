=== Calendario senza luogo ===
Contributors: pnlevolution
Requires at least: 5.8
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later

Mostra gli eventi di un calendario Google pubblico senza esporre il luogo.

== Uso ==

Inserire in un blocco Shortcode:

[calendario_senza_luogo id="c_classroom10484a8b@group.calendar.google.com"]

L'export CSV è attivo per impostazione predefinita. Per nasconderlo:

[calendario_senza_luogo id="c_classroom10484a8b@group.calendar.google.com" export="false"]

Il feed viene mantenuto in cache per 15 minuti. Se Google non risponde, il plugin usa l'ultima copia valida disponibile.

== Privacy ==

Il plugin non restituisce al browser il campo LOCATION, link all'evento Google o il feed iCalendar originale.
