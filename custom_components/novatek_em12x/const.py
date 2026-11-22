"""Constants for the Novatek Electro EM integration."""

DOMAIN = "novatek_em12x"
MANUFACTURER = "Novatek Electro"

CONF_PASSWORD = "password"
CONF_SYNC_TIME = "sync_time"

DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 300
DEFAULT_SETTINGS_EVERY = 5
TIME_SYNC_INTERVAL = 3600

MODEL_NAMES = {
    243: "EM-125",
    271: "EM-129",
    273: "EM-129",
    293: "EM-126T",
}

LOGIN_PREFIX = "EM-129"

MEASUREMENT_PARAMS = (
    "volt_msr",
    "cur_msr",
    "powa_msr",
    "pows_msr",
    "freq_msr",
    "tempr_msr",
    "enrga_msr",
    "enrgs_msr",
    "enrga_d_msr",
    "enrga_w_msr",
    "enrga_m_msr",
    "sys_flag",
    "faul_flag",
    "ar_time",
    "time",
)

SETTING_PARAMS = (
    "volt_leveloff_hi",
    "volt_leveloff_lo",
    "volt_level_hys",
    "volt_timeoff_hi",
    "volt_timeoff_lo",
    "volt_timeon_apv",
    "volt_count_apv",
    "cur_leveloff",
    "cur_timeoff",
    "cur_timeon_apv",
    "cur_count_apv",
    "pow_enable",
    "pow_leveloff",
    "pow_timeoff",
    "pow_timeon_apv",
    "pow_count_apv",
    "freq_enable",
    "freq_leveloff_hi",
    "freq_leveloff_lo",
    "freq_timeoff",
    "freq_timeon_apv",
    "freq_count_apv",
    "hctrl_enable",
    "hctrl_from",
    "hctrl_to",
    "time_gmt",
    "time_corr",
    "dst_enable",
    "lock_panel_time",
    "on_time_limit",
    "apv_reset_time",
    "sync_sntp_enable",
    "sync_sntp_address",
    "sync_sntp_port",
    "sync_sntp_time",
    "led_intens",
    "cost_energy",
    "cost_unit",
    "wifi_wdt_enable",
)

COST_UNITS = (
    "BYR",
    "BGN",
    "CZK",
    "CHF",
    "EUR",
    "GBP",
    "INR",
    "KZT",
    "LVL",
    "LTL",
    "MDL",
    "PLN",
    "PRB",
    "RUB",
    "RON",
    "SEK",
    "UAH",
    "USD",
)

COUNT_APV_FOREVER = 65535
COUNT_APV_OPTIONS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, COUNT_APV_FOREVER)

FAULT_BITS = {
    0: "overvoltage",
    1: "undervoltage",
    2: "voltage_over_290v",
    3: "voltage_apv_limit",
    4: "overcurrent",
    5: "current_over_17a",
    6: "current_apv_limit",
    7: "overpower",
    8: "power_apv_limit",
    9: "temperature_sensor_fault",
    10: "temperature_sensor_open",
    11: "temperature_sensor_short",
    12: "rtc_fault",
    13: "relay_fault",
    14: "on_time_limit_blocked",
    15: "overfrequency",
    16: "underfrequency",
    17: "frequency_apv_limit",
    30: "not_calibrated",
    31: "settings_damaged",
}

STATUS_NTP_SYNCED_BIT = 9
STATUS_CLOUD_SYNCED_BIT = 10
STATUS_PANEL_LOCKED_BIT = 11
STATUS_RELAY_BIT = 4
