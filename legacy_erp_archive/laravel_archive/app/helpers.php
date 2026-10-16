<?php

/**
 * Legacy ERP amounts are stored in SQLite as text with thousands separators
 * (e.g. "5,000,000.00"). PHP's (float) cast stops at the first comma → 5.0.
 */

if (! function_exists('legacy_amount')) {
    function legacy_amount(mixed $value): float
    {
        if ($value === null || $value === '') {
            return 0.0;
        }
        if (is_int($value) || is_float($value)) {
            return (float) $value;
        }

        $s = trim((string) $value);
        $s = str_replace([',', ' '], '', $s);
        if ($s === '' || $s === '-') {
            return 0.0;
        }

        return (float) $s;
    }
}

if (! function_exists('format_legacy_amount')) {
    function format_legacy_amount(mixed $value, int $decimals = 2): string
    {
        return number_format(legacy_amount($value), $decimals);
    }
}
