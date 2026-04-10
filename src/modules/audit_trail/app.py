import sys
import os

# Fix import path so 'src' is recognized as a package root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

import streamlit as st
from src.modules.audit_trail.auth.login import login_page
from src.modules.audit_trail.auth.signup import signup_page
from src.modules.audit_trail.dashboards.patient_dashboard import patient_dashboard
from src.modules.audit_trail.dashboards.doctor_dashboard import doctor_dashboard
from src.modules.audit_trail.dashboards.admin_dashboard import admin_dashboard

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="MediCare", layout="wide")

# ---------------- SESSION STATE INIT ----------------
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("page", "login")
st.session_state.setdefault("role", None)

# ---------------- HARD REDIRECT AFTER LOGIN ----------------
if st.session_state.logged_in:
    if st.session_state.role == "Patient":
        patient_dashboard()
        st.stop()
    elif st.session_state.role == "Doctor":
        doctor_dashboard()
        st.stop()
    elif st.session_state.role == "Admin":
        admin_dashboard()
        st.stop()

# ---------------- AUTH ROUTING ----------------
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "signup":
    signup_page()

