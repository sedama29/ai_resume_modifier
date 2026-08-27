"""Python side of the Firebase Google Sign-In widget. Static-folder component
(no npm/build step) -- see firebase_login/index.html for the JS half."""
from pathlib import Path

import streamlit.components.v1 as components

from config import FIREBASE_CONFIG

_component = components.declare_component(
    "firebase_login", path=str(Path(__file__).parent / "firebase_login")
)


def firebase_login_widget(command: str | None = None, key: str = "firebase_login") -> dict | None:
    """Returns None while the component is still checking the session, or a
    dict shaped {"status": "signed_in", "token": ...} | {"status": "signed_out"}
    | {"status": "error", "message": ...}."""
    return _component(firebaseConfig=FIREBASE_CONFIG, command=command, key=key, default=None)
