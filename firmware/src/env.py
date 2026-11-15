# Reads KEY=VALUE secrets from a .env file. Works on MicroPython and CPython
# (built-ins only). Never print or log the returned values.


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def load_env(path="/.env"):
    """Return a dict of the KEY=VALUE pairs in the file at `path`.

    Blank lines and lines starting with # are skipped. Keys and values are
    stripped of whitespace, and one pair of matching surrounding quotes is
    removed from values. Only the first "=" splits, so values may contain "=".
    """
    try:
        f = open(path, "r")
    except OSError:
        raise OSError(
            "No .env file at " + path + ": it wasn't deployed. Copy "
            "firmware/.env.example to firmware/.env, fill it in, and run the "
            "deploy script."
        )

    env = {}
    with f:
        line_no = 0
        for line in f:
            line_no += 1
            line = line.strip()
            if line_no == 1 and line.startswith("﻿"):
                line = line[1:].strip()  # UTF-8 BOM from some Windows editors
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                # Report the line number only, never the content.
                raise ValueError(".env line " + str(line_no) + " has no '='")
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                raise ValueError(".env line " + str(line_no) + " has no key")
            env[key] = _unquote(value.strip())
    return env
