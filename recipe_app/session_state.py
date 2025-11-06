"""Helpers for initializing Streamlit session state."""
from __future__ import annotations

import streamlit as st

SESSION_DEFAULTS = {
    "final_recipe": "",
    "compressed_image_bytes": None,
    "technical_title": "",
    "extracted_text": "",
}


def initialize_session_state() -> None:
    """Ensure Streamlit session state contains the expected keys."""
    for key, value in SESSION_DEFAULTS.items():
        st.session_state.setdefault(key, value)


__all__ = ["initialize_session_state", "SESSION_DEFAULTS"]
