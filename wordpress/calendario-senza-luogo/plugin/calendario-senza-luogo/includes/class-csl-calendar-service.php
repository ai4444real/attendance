<?php

use Sabre\VObject\Reader;

final class CSL_Calendar_Service
{
    const CACHE_SECONDS = 900;
    const MAX_RANGE_DAYS = 93;

    public static function valid_calendar_id($id)
    {
        return is_string($id) && strlen($id) <= 254 && (bool) preg_match('/^[A-Za-z0-9._%+@-]+$/', $id);
    }

    public function events($calendar_id, $from, $to)
    {
        if (!self::valid_calendar_id($calendar_id)) {
            return new WP_Error('csl_bad_id', 'ID del calendario non valido.', array('status' => 400));
        }
        try {
            $start = new DateTimeImmutable($from, new DateTimeZone('UTC'));
            $end = new DateTimeImmutable($to, new DateTimeZone('UTC'));
        } catch (Exception $exception) {
            return new WP_Error('csl_bad_range', 'Intervallo di date non valido.', array('status' => 400));
        }
        if ($end <= $start || ($end->getTimestamp() - $start->getTimestamp()) > self::MAX_RANGE_DAYS * DAY_IN_SECONDS) {
            return new WP_Error('csl_bad_range', 'Intervallo di date non valido.', array('status' => 400));
        }

        $feed = $this->feed($calendar_id);
        if (is_wp_error($feed)) {
            return $feed;
        }

        try {
            $calendar = Reader::read($feed['body'], Reader::OPTION_FORGIVING);
            $expanded = $calendar->expand(DateTime::createFromImmutable($start), DateTime::createFromImmutable($end));
            $events = array();
            foreach ($expanded->VEVENT as $event) {
                if (isset($event->STATUS) && strtoupper((string) $event->STATUS) === 'CANCELLED') {
                    continue;
                }
                $starts_at = $event->DTSTART->getDateTime();
                $all_day = strtoupper((string) $event->DTSTART['VALUE']) === 'DATE';
                $ends_at = isset($event->DTEND) ? $event->DTEND->getDateTime() : clone $starts_at;
                if (!isset($event->DTEND)) {
                    $ends_at->modify($all_day ? '+1 day' : '+1 hour');
                }
                $title = isset($event->SUMMARY) ? sanitize_text_field(html_entity_decode((string) $event->SUMMARY, ENT_QUOTES | ENT_HTML5, 'UTF-8')) : 'Evento';
                $description = isset($event->DESCRIPTION) ? sanitize_textarea_field(wp_strip_all_tags(html_entity_decode((string) $event->DESCRIPTION, ENT_QUOTES | ENT_HTML5, 'UTF-8'))) : '';
                $events[] = array(
                    'id' => hash('sha256', (isset($event->UID) ? (string) $event->UID : $title) . '|' . $starts_at->format(DateTimeInterface::ATOM)),
                    'title' => $title,
                    'description' => $description,
                    'start' => $starts_at->format(DateTimeInterface::ATOM),
                    'end' => $ends_at->format(DateTimeInterface::ATOM),
                    'allDay' => $all_day,
                );
            }
            usort($events, function ($a, $b) { return strcmp($a['start'], $b['start']); });
            return array('events' => $events, 'stale' => (bool) $feed['stale']);
        } catch (Throwable $exception) {
            return new WP_Error('csl_parse_error', 'Il calendario non è temporaneamente disponibile.', array('status' => 502));
        }
    }

    private function feed($calendar_id)
    {
        $key = 'csl_feed_' . md5($calendar_id);
        $cached = get_transient($key);
        if (is_string($cached) && $cached !== '') {
            return array('body' => $cached, 'stale' => false);
        }

        $url = 'https://calendar.google.com/calendar/ical/' . rawurlencode($calendar_id) . '/public/basic.ics';
        $response = wp_remote_get($url, array('timeout' => 12, 'redirection' => 2, 'user-agent' => 'Calendario-senza-luogo/' . CSL_VERSION));
        if (!is_wp_error($response) && wp_remote_retrieve_response_code($response) === 200) {
            $body = wp_remote_retrieve_body($response);
            if (is_string($body) && strlen($body) > 20 && strpos($body, 'BEGIN:VCALENDAR') !== false) {
                set_transient($key, $body, self::CACHE_SECONDS);
                update_option($key . '_last_good', $body, false);
                return array('body' => $body, 'stale' => false);
            }
        }

        $stale = get_option($key . '_last_good');
        if (is_string($stale) && $stale !== '') {
            return array('body' => $stale, 'stale' => true);
        }
        return new WP_Error('csl_feed_unavailable', 'Il calendario non è temporaneamente disponibile.', array('status' => 502));
    }
}
