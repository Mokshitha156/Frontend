import streamlit as st

def module_tabs():
    return st.radio(
        "",
        ["Home", "ER Diagram", "Tables", "SQL Query", "Triggers", "Output"],
        horizontal=True
    )
