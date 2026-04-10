import streamlit as st
from src.modules.audit_trail.components.tabs import module_tabs

def module_detail():
    code, name = st.session_state.selected_module

    st.markdown(f"### Category A > {name}")
    st.markdown(f"## {name}")

    tab = module_tabs()
    st.divider()

    if tab == "Home":
        st.info(f"{name} overview and purpose")
        st.write("Input Entities")
        st.success("Patient Form")
        st.success("Insurance Details")
        st.success("Emergency Contact")

        st.write("Output Entities")
        st.success("Patient Record")
        st.success("Admission Summary")
        st.success("Patient ID")

    elif tab == "ER Diagram":
        st.image("https://via.placeholder.com/800x400?text=ER+Diagram")

    elif tab == "Tables":
        st.table({
            "Table Name": ["patients", "insurance", "contacts"],
            "Records": [12500, 8900, 6400]
        })

    elif tab == "SQL Query":
        st.code("""
SELECT * FROM patients
JOIN insurance ON patients.id = insurance.patient_id;
""", language="sql")

    elif tab == "Triggers":
        st.code("""
CREATE TRIGGER after_insert_patient
AFTER INSERT ON patients
FOR EACH ROW
BEGIN
  INSERT INTO logs VALUES (NEW.id, NOW());
END;
""", language="sql")

    elif tab == "Output":
        st.success("Patient Registered Successfully")

    if st.button("⬅ Back to Modules"):
        st.session_state.view = "modules"
        st.experimental_rerun()
