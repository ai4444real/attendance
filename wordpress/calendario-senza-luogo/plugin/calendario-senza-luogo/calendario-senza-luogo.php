<?php
/**
 * Plugin Name: Calendario senza luogo
 * Description: Mostra un calendario Google pubblico senza trasmettere il luogo al browser.
 * Version: 1.0.1
 * Author: PNL Evolution
 * License: GPL-2.0-or-later
 * Text Domain: calendario-senza-luogo
 */

if (!defined('ABSPATH')) {
    exit;
}

define('CSL_VERSION', '1.0.1');
define('CSL_DIR', plugin_dir_path(__FILE__));
define('CSL_URL', plugin_dir_url(__FILE__));

require_once CSL_DIR . 'vendor/autoload.php';
require_once CSL_DIR . 'includes/class-csl-calendar-service.php';

final class CSL_Plugin
{
    public static function init()
    {
        add_action('rest_api_init', array(__CLASS__, 'register_rest_routes'));
        add_shortcode('calendario_senza_luogo', array(__CLASS__, 'render_shortcode'));
    }

    public static function register_rest_routes()
    {
        register_rest_route('calendario-senza-luogo/v1', '/events', array(
            'methods' => WP_REST_Server::READABLE,
            'callback' => array(__CLASS__, 'get_events'),
            'permission_callback' => '__return_true',
            'args' => array(
                'id' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                'from' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                'to' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
            ),
        ));
    }

    public static function get_events(WP_REST_Request $request)
    {
        $service = new CSL_Calendar_Service();
        $result = $service->events($request['id'], $request['from'], $request['to']);
        if (is_wp_error($result)) {
            return $result;
        }
        return rest_ensure_response($result);
    }

    public static function render_shortcode($attributes)
    {
        $attributes = shortcode_atts(array(
            'id' => '',
            'export' => 'true',
            'colore' => '',
            'color' => '',
        ), $attributes, 'calendario_senza_luogo');
        $calendar_id = trim((string) $attributes['id']);
        if (!CSL_Calendar_Service::valid_calendar_id($calendar_id)) {
            return '<p class="csl-message csl-error">ID del calendario mancante o non valido.</p>';
        }

        $export = !in_array(strtolower(trim((string) $attributes['export'])), array('false', '0', 'no'), true);
        $banner_color = sanitize_hex_color($attributes['colore'] ?: $attributes['color']);
        if (!$banner_color) {
            $banner_color = '#005090';
        }
        wp_enqueue_style('csl-calendar', CSL_URL . 'assets/calendar.css', array(), CSL_VERSION);
        wp_enqueue_script('csl-calendar', CSL_URL . 'assets/calendar.js', array(), CSL_VERSION, true);

        $instance = wp_unique_id('csl-calendar-');
        ob_start();
        ?>
        <section id="<?php echo esc_attr($instance); ?>" class="csl-calendar" style="--csl-banner:<?php echo esc_attr($banner_color); ?>"
            data-calendar-id="<?php echo esc_attr($calendar_id); ?>"
            data-endpoint="<?php echo esc_url(rest_url('calendario-senza-luogo/v1/events')); ?>"
            data-export="<?php echo $export ? 'true' : 'false'; ?>">
            <header class="csl-hero">
                <div class="csl-brand">
                    <div><p class="csl-eyebrow">Calendario della scuola</p><h2>Prossimi appuntamenti</h2></div>
                </div>
            </header>
            <div class="csl-toolbar">
                <button type="button" class="csl-nav csl-prev" aria-label="Mese precedente">&#8249;</button>
                <h3 class="csl-month" aria-live="polite"></h3>
                <button type="button" class="csl-nav csl-next" aria-label="Mese successivo">&#8250;</button>
                <?php if ($export) : ?><button type="button" class="csl-export">Esporta CSV</button><?php endif; ?>
            </div>
            <div class="csl-status" aria-live="polite">Caricamento eventi…</div>
            <div class="csl-grid" hidden></div>
            <div class="csl-agenda" hidden></div>
            <dialog class="csl-dialog"><button type="button" class="csl-close" aria-label="Chiudi">×</button><div class="csl-detail"></div></dialog>
        </section>
        <?php
        return ob_get_clean();
    }
}

CSL_Plugin::init();
