"""Wi-Fi + MQTT for the Pico. Knows nothing about the shaker.

connect(status) joins Wi-Fi, connects to the broker over TLS, and publishes status.
Then call check() often: it handles incoming messages and keeps the connection alive.
"""
import json
import machine
import network
import rp2
import ssl
import time
from binascii import hexlify

from umqtt.simple import MQTTClient

import env

STATUS_TOPIC = "bedquake/status"
KEEPALIVE_S = 60          # if we go silent this long (x1.5), the broker publishes the last-will
PING_MS = 30_000          # ping well inside the keepalive
WIFI_COUNTRY = "US"
WIFI_POWER_SAVE_OFF = 0xA11140   # Pico W value that turns Wi-Fi power saving off
WIFI_TIMEOUT_S = 20
CONNECT_TIMEOUT_S = 10

_client = None
_last_ping = 0


def connect(status):
    global _client, _last_ping
    rp2.country(WIFI_COUNTRY)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=WIFI_POWER_SAVE_OFF)   # with power saving on, joining the laptop hotspot failed
    if not wlan.isconnected():
        print("Wi-Fi: joining", env.WIFI_SSID)
        wlan.connect(env.WIFI_SSID, env.WIFI_PASSWORD)
        for _ in range(WIFI_TIMEOUT_S):
            if wlan.isconnected():
                break
            time.sleep(1)
        else:
            raise OSError("Wi-Fi: couldn't join %s (status %d)" % (env.WIFI_SSID, wlan.status()))
    print("Wi-Fi: connected,", wlan.ifconfig()[0])

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_NONE   # encrypted, but the broker's certificate isn't checked yet
    client_id = "bedquake-" + hexlify(machine.unique_id()).decode()
    # Passing an SSLContext makes umqtt send the host name (SNI), which EMQX Serverless requires.
    _client = MQTTClient(client_id, env.MQTT_HOST, port=env.MQTT_PORT, user=env.PICO_MQTT_USER,
                         password=env.PICO_MQTT_PASS, keepalive=KEEPALIVE_S, ssl=context)
    _client.set_last_will(STATUS_TOPIC, json.dumps({"online": False}), retain=True)
    print("MQTT: connecting to", env.MQTT_HOST)
    _client.connect(timeout=CONNECT_TIMEOUT_S)
    print("MQTT: connected")
    _last_ping = time.ticks_ms()
    publish_status(status)


def publish_status(status):
    _client.publish(STATUS_TOPIC, json.dumps(status), retain=True)
    print("MQTT: status", status)


def check():
    global _last_ping
    _client.check_msg()
    if time.ticks_diff(time.ticks_ms(), _last_ping) >= PING_MS:
        _client.ping()
        _last_ping = time.ticks_ms()
