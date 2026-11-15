import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from env import load_env  # noqa: E402


def write_env(tmp_path, text):
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_reads_key_value_pairs(tmp_path):
    path = write_env(tmp_path, "WIFI_SSID=home\nDEVICE_ID=bed1\n")
    assert load_env(path) == {"WIFI_SSID": "home", "DEVICE_ID": "bed1"}


def test_skips_comments(tmp_path):
    path = write_env(tmp_path, "# a comment\nMQTT_USER=pico\n   # indented comment\n")
    assert load_env(path) == {"MQTT_USER": "pico"}


def test_skips_blank_lines(tmp_path):
    path = write_env(tmp_path, "\nA=1\n\n   \nB=2\n\n")
    assert load_env(path) == {"A": "1", "B": "2"}


def test_strips_whitespace(tmp_path):
    path = write_env(tmp_path, "  MQTT_HOST  =  broker.example.com  \r\n")
    assert load_env(path) == {"MQTT_HOST": "broker.example.com"}


def test_strips_surrounding_quotes(tmp_path):
    path = write_env(
        tmp_path,
        'DOUBLE="my network"\nSINGLE=\'pa ss\'\nMISMATCHED="abc\'\nEMPTY=""\n',
    )
    assert load_env(path) == {
        "DOUBLE": "my network",
        "SINGLE": "pa ss",
        "MISMATCHED": "\"abc'",
        "EMPTY": "",
    }


def test_value_containing_equals(tmp_path):
    path = write_env(tmp_path, 'WIFI_PASSWORD=a=b==c\nQUOTED="x=y"\n')
    assert load_env(path) == {"WIFI_PASSWORD": "a=b==c", "QUOTED": "x=y"}


def test_blank_value(tmp_path):
    path = write_env(tmp_path, "MQTT_PASSWORD=\n")
    assert load_env(path) == {"MQTT_PASSWORD": ""}


def test_missing_file_raises_clear_error(tmp_path):
    missing = str(tmp_path / "nope.env")
    with pytest.raises(OSError, match="wasn't deployed"):
        load_env(missing)


def test_malformed_line_error_hides_content(tmp_path):
    path = write_env(tmp_path, "A=1\nsupersecretvalue\n")
    with pytest.raises(ValueError) as excinfo:
        load_env(path)
    assert "line 2" in str(excinfo.value)
    assert "supersecretvalue" not in str(excinfo.value)
