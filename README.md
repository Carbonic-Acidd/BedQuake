# BedQuake

A silent bed-shaker alarm. A Raspberry Pi Pico WH drives a bass shaker through an
amp. A web page toggles it on and off through a public MQTT broker.

## Pico

One-time setup: `python -m pip install mpremote`, then copy
`pico/secrets.example.py` to `pico/secrets.py` and fill it in.

- Try code without saving it: `mpremote run --no-follow pico/main.py + repl`
  (Ctrl-C stops it on the Pico, Ctrl-] exits). Plain `mpremote run` doesn't pass
  Ctrl-C to the Pico, so the shaker would keep going.
- Save to the Pico so it runs on power-up: `mpremote cp pico/main.py pico/secrets.py : + reset`

`pico/shaker_test.py` is a standalone bench test (smooth rumble): `mpremote run pico/shaker_test.py`
