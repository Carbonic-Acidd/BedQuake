"""Wi-Fi + MQTT for the Pico. Knows nothing about the shaker.

Step 2 will: join Wi-Fi (env.WIFI_SSID / WIFI_PASSWORD), connect to HiveMQ Cloud
over TLS on env.MQTT_PORT with umqtt.simple, publish a retained bedquake/status
message with an {"online": false} last-will, and hand incoming commands to main.py.
Stub only in Step 1.
"""
