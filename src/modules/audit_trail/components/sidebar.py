# components/sidebar.py
import streamlit as st
from streamlit_option_menu import option_menu

def sidebar(menu_items):
    with st.sidebar:
        st.markdown("## 🏥 MediCare")
        selected = option_menu(
            "",
            menu_items,
            icons=["activity", "flask", "capsule", "building", "credit-card", "people", "shield", "truck", "bar-chart"],
            default_index=0
        )

        st.divider()
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.page = "login"
            st.session_state.role = None
            st.session_state.view = "main"
            st.session_state.selected_category = None
            st.session_state.selected_module = None
            st.rerun()

    return selected