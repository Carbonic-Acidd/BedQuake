"""Wi-Fi + MQTT for the Pico. Knows nothing about the shaker.

connect(status, on_message) joins Wi-Fi, sets the clock from the internet (NTP),
connects to the broker over TLS, publishes status, and subscribes to the command topics.
It raises if it can't: without the internet clock, alarms can't work.

After that, network errors never raise. They just take the Pico offline (online() is
False) and the clock keeps running, so alarms still fire. While online, call check()
often: it passes each incoming message to on_message(topic, payload) and keeps the
connection alive. While offline, call reconnect(status) often: every RECONNECT_MS it
tries to get back online.
"""
import gc
import json
import machine
import network
import ntptime
import rp2
import ssl
import time
from binascii import hexlify

from umqtt.simple import MQTTClient, MQTTException

import env

STATUS_TOPIC = "shakeawake/status"
TEST_TOPIC = "shakeawake/alarm/test"
STOP_TOPIC = "shakeawake/alarm/stop"
SET_TOPIC = "shakeawake/alarm/set"
KEEPALIVE_S = 60          # if we go silent this long (x1.5), the broker publishes the last-will
PING_MS = 30_000          # ping well inside the keepalive
RECONNECT_MS = 30_000     # while offline, how often to try to get back online
RADIO_OFF_S = 2           # how long the Wi-Fi radio stays off when rejoining
WIFI_COUNTRY = "US"
WIFI_POWER_SAVE_OFF = 0xA11140   # Pico W value that turns Wi-Fi power saving off
WIFI_TIMEOUT_S = 20
CONNECT_TIMEOUT_S = 10
NETWORK_ERRORS = (OSError, MQTTException)

# The web app sends UTC Unix seconds. Older MicroPython counts time from 2000, not 1970.
UNIX_OFFSET = 946684800 if time.gmtime(0)[0] == 2000 else 0

_wlan = None
_client = None            # None while offline
_on_message = None
_last_ping = 0
_last_try = 0
_offline_since = 0


def connect(status, on_message):
    global _wlan, _on_message
    _on_message = on_message
    rp2.country(WIFI_COUNTRY)
    _wlan = network.WLAN(network.STA_IF)
    _wlan.active(True)
    _wlan.config(pm=WIFI_POWER_SAVE_OFF)   # with power saving on, joining the laptop hotspot failed
    if not _wlan.isconnected():
        print("Wi-Fi: joining", env.WIFI_SSID)
        _wlan.connect(env.WIFI_SSID, env.WIFI_PASSWORD)
        for _ in range(WIFI_TIMEOUT_S):
            if _wlan.isconnected():
                break
            time.sleep(1)
        else:
            raise OSError("Wi-Fi: couldn't join %s (status %d)" % (env.WIFI_SSID, _wlan.status()))
    print("Wi-Fi: connected,", _wlan.ifconfig()[0])
    ntptime.settime()   # sets the clock to UTC; it keeps running while offline
    print("Time: set,", unix_time(), "UTC")
    _connect_broker(status)


def _connect_broker(status):
    global _client, _last_ping
    gc.collect()   # TLS needs a big block of memory, and reconnecting can leave it fragmented
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_NONE   # encrypted, but the broker's certificate isn't checked yet
    client_id = "shakeawake-" + hexlify(machine.unique_id()).decode()
    # Passing an SSLContext makes umqtt send the host name (SNI), which EMQX Serverless requires.
    client = MQTTClient(client_id, env.MQTT_HOST, port=env.MQTT_PORT, user=env.PICO_MQTT_USER,
                        password=env.PICO_MQTT_PASS, keepalive=KEEPALIVE_S, ssl=context)
    client.set_last_will(STATUS_TOPIC, json.dumps({"online": False}), retain=True)
    client.set_callback(lambda topic, msg: _on_message(topic.decode(), msg.decode()))
    print("MQTT: connecting to", env.MQTT_HOST)
    try:
        client.connect(timeout=CONNECT_TIMEOUT_S)
        client.subscribe(TEST_TOPIC)
        client.subscribe(STOP_TOPIC)
        client.subscribe(SET_TOPIC)   # retained, so a set alarm arrives right after connecting
    except NETWORK_ERRORS:
        _close(client)
        raise
    print("MQTT: connected, listening on shakeawake/alarm/test, stop and set")
    _client = client
    _last_ping = time.ticks_ms()
    publish_status(status)


def online():
    return _client is not None


def offline_s():
    return time.ticks_diff(time.ticks_ms(), _offline_since) // 1000


def publish_status(status):
    if _client is None:
        return   # offline: reconnecting publishes the latest status
    try:
        _client.publish(STATUS_TOPIC, json.dumps(status), retain=True)
        print("MQTT: status", status)
    except NETWORK_ERRORS as e:
        _go_offline(e)


def unix_time():
    return time.time() + UNIX_OFFSET


def check():
    global _last_ping
    try:
        if not _wlan.isconnected():
            raise OSError("Wi-Fi lost")
        _client.check_msg()   # may call on_message, which may go offline
        if _client and time.ticks_diff(time.ticks_ms(), _last_ping) >= PING_MS:
            _client.ping()
            _last_ping = time.ticks_ms()
    except NETWORK_ERRORS as e:
        _go_offline(e)


def reconnect(status):
    global _last_try
    if time.ticks_diff(time.ticks_ms(), _last_try) < RECONNECT_MS:
        return
    _last_try = time.ticks_ms()
    if not _wlan.isconnected():
        # After the network vanishes, a plain connect() can stay stuck "joining" forever.
        # Switching the radio off and on first unsticks it.
        print("Wi-Fi: rejoining", env.WIFI_SSID)
        _wlan.active(False)
        time.sleep(RADIO_OFF_S)
        _wlan.active(True)
        _wlan.config(pm=WIFI_POWER_SAVE_OFF)
        _wlan.connect(env.WIFI_SSID, env.WIFI_PASSWORD)   # doesn't wait; the next try checks it
        return
    try:
        ntptime.settime()   # the clock drifts a little while offline
        print("Time: resynced,", unix_time(), "UTC")
        _connect_broker(status)
    except NETWORK_ERRORS as e:
        print("MQTT: still offline,", repr(e))


def _go_offline(error):
    global _client, _last_try, _offline_since
    print("Offline:", repr(error), "- alarms still work; retrying every", RECONNECT_MS // 1000, "s")
    _close(_client)
    _client = None
    _last_try = _offline_since = time.ticks_ms()


def _close(client):
    try:
        client.sock.close()
    except Exception:
        pass   # already closed or never opened
