<?php

/* Runtime autoloader for the Sabre libraries bundled with this plugin. */
spl_autoload_register(function ($class) {
    $prefixes = array(
        'Sabre\\VObject\\' => __DIR__ . '/sabre/vobject/lib/',
        'Sabre\\Xml\\' => __DIR__ . '/sabre/xml/lib/',
        'Sabre\\Uri\\' => __DIR__ . '/sabre/uri/lib/',
    );
    foreach ($prefixes as $prefix => $base) {
        if (strncmp($class, $prefix, strlen($prefix)) === 0) {
            $file = $base . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';
            if (is_file($file)) {
                require $file;
            }
            return;
        }
    }
});

require_once __DIR__ . '/sabre/xml/lib/Deserializer/functions.php';
require_once __DIR__ . '/sabre/xml/lib/Serializer/functions.php';
require_once __DIR__ . '/sabre/uri/lib/functions.php';
