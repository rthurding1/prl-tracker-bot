"""Tiny JSON-file persistence for subscribers and alert state."""
from __future__ import annotations

import json
import os
import threading

import config

_lock = threading.Lock()

_DEFAULT = {
    "subscribers": [],     # list[int] chat ids
    "last_bucket": None,   # int | None
    "last_alert_ts": 0,    # float epoch seconds
}


def load() -> dict:
    with _lock:
        if not os.path.exists(config.STATE_FILE):
            return dict(_DEFAULT)
        try:
            with open(config.STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return dict(_DEFAULT)
        merged = dict(_DEFAULT)
        merged.update(data)
        return merged


def save(state: dict) -> None:
    with _lock:
        tmp = config.STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, config.STATE_FILE)


def add_subscriber(chat_id: int) -> bool:
    state = load()
    subs = state.get("subscribers", [])
    if chat_id in subs:
        return False
    subs.append(chat_id)
    state["subscribers"] = subs
    save(state)
    return True


def remove_subscriber(chat_id: int) -> bool:
    state = load()
    subs = state.get("subscribers", [])
    if chat_id not in subs:
        return False
    subs.remove(chat_id)
    state["subscribers"] = subs
    save(state)
    return True
