import re
import streamlit as st
from datetime import datetime
from src.modules.audit_trail.database import db
from src.modules.audit_trail.services import create_audit_log
from src.modules.audit_trail.schemas import UserMeta, ActionDetails, AuditLogCreate, LogContext
 
 
# ============= HELPERS =============
def validate_email(email: str) -> bool:
    """Validate email format using regex."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
 
 
def get_client_ip() -> str:
    """Get client IP from session state or return default."""
    return st.session_state.get('client_ip', '127.0.0.1')
 
 
def create_user_meta(user_id: str, username: str, email: str) -> UserMeta:
    """Build a UserMeta object from current form inputs."""
    return UserMeta(
        user_id=user_id or "unknown",
        username=username or "unknown",
        role="Patient",
        email=email if email and validate_email(email) else None,
        ip_address=get_client_ip(),
        device_info=st.session_state.get('device_info', 'Web')
    )
 
 
def log_action(user: UserMeta, action_type: str, description: str,
               reason: str, status: str):
    """Create an audit log entry."""
    create_audit_log(AuditLogCreate(
        user=user,
        action=ActionDetails(
            module="Patient Dashboard",
            action_type=action_type,
            description=description
        ),
        context=LogContext(reason=reason),
        status=status
    ))
 
 
# ============= CACHED QUERIES =============
@st.cache_data(ttl=60)
def get_patient_profile(patient_name: str):
    """Cached lookup for a patient profile by name."""
    if not patient_name:
        return None
    return db["patients"].find_one({"name": patient_name}, {"_id": 0})
 
 
@st.cache_data(ttl=30)
def get_summary_stats() -> dict:
    """Cached summary statistics for the dashboard."""
    return {
        "total_patients": db["patients"].count_documents({}),
        "total_appointments": db["appointments"].count_documents({})
    }
 
 
# ============= MAIN VIEW =============
def patient_view():
    st.title("🏥 Patient Dashboard")
 
    # Session state initialisation
    st.session_state.setdefault('last_action', None)
    st.session_state.setdefault('patient_data', {})
 
    # ---- PATIENT INFORMATION ----
    with st.expander("👤 Patient Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            user_id = st.text_input("Patient ID", placeholder="e.g., PAT001", key="patient_id")
            patient_name = st.text_input("Full Name", placeholder="John Doe", key="patient_name")
        with col2:
            email = st.text_input("Email Address", placeholder="john@example.com", key="email")
            doctor = st.text_input("Doctor Name", placeholder="Dr. Smith", key="doctor")
 
        if email and not validate_email(email):
            st.error("⚠️ Please enter a valid email address")
 
    user = create_user_meta(user_id, patient_name, email)
 
    # ---- VIEW PROFILE ----
    st.divider()
    with st.container():
        st.subheader("📄 View Profile")
 
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            load_clicked = st.button("🔍 Load Profile", use_container_width=True, type="primary")
 
        if load_clicked:
            if not patient_name.strip():
                st.warning("⚠️ Please enter a patient name to load profile")
                log_action(user, "VIEW", "Attempted profile view without name",
                           "Missing patient name input", "FAILURE")
            else:
                with st.spinner("Loading profile..."):
                    profile = get_patient_profile(patient_name.strip())
 
                if profile:
                    st.session_state.patient_data = profile
                    st.success(f"✅ Profile loaded for **{patient_name}**")
 
                    with st.expander("View Profile Details", expanded=True):
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Name", profile.get('name', 'N/A'))
                        c2.metric("Age", profile.get('age', 'N/A'))
                        c3.metric("Email", profile.get('email', 'N/A'))
 
                        if profile.get('history'):
                            st.write("**Medical History:**")
                            for item in profile['history']:
                                st.write(f"- {item}")
 
                    log_action(user, "VIEW", f"Viewed profile of {patient_name}",
                               "User requested profile", "SUCCESS")
                else:
                    st.error(f"❌ No profile found for **{patient_name}**")
                    st.info("💡 You can create a new profile using the form below")
                    log_action(user, "VIEW", f"Profile not found for {patient_name}",
                               "Patient name not in database", "FAILURE")
 
    # ---- CREATE PROFILE ----
    st.divider()
    with st.container():
        st.subheader("➕ Create New Profile")
 
        with st.form("create_profile_form", clear_on_submit=False):
            form_col1, form_col2 = st.columns(2)
            with form_col1:
                new_name = st.text_input("Patient Name", value=patient_name,
                                         placeholder="Enter full name")
                new_email = st.text_input("Email", value=email,
                                          placeholder="patient@example.com")
            with form_col2:
                new_user_id = st.text_input("Patient ID", value=user_id,
                                            placeholder="Auto-generated if empty")
                new_age = st.number_input("Age", min_value=0, max_value=150, step=1, value=0)
 
            medical_history = st.text_area(
                "Medical History (Optional)",
                placeholder="Enter any known medical conditions, one per line..."
            )
            submitted = st.form_submit_button("✨ Create Profile", use_container_width=True)
 
            if submitted:
                if not new_name.strip():
                    st.error("❌ Patient name is required")
                    log_action(user, "CREATE", "Attempted profile creation without name",
                               "Missing required patient name", "FAILURE")
                elif new_email and not validate_email(new_email):
                    st.error("❌ Please enter a valid email address")
                    log_action(user, "CREATE", "Attempted profile creation with invalid email",
                               "Invalid email format", "FAILURE")
                else:
                    existing = db["patients"].find_one({"name": new_name.strip()})
                    if existing:
                        st.warning("⚠️ A profile with this name already exists")
                        st.info("Use the 'View Profile' section above to see existing records")
                        log_action(user, "CREATE", f"Duplicate profile attempt for {new_name}",
                                   "Patient name already exists", "FAILURE")
                    else:
                        generated_id = (
                            new_user_id.strip()
                            or f"PAT_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        )
                        new_profile = {
                            "user_id": generated_id,
                            "name": new_name.strip(),
                            "email": new_email.strip() if validate_email(new_email) else None,
                            "age": new_age,
                            "history": [
                                line.strip()
                                for line in medical_history.split('\n')
                                if line.strip()
                            ],
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat()
                        }
                        try:
                            db["patients"].insert_one(new_profile)
                            st.success(f"✅ Profile created successfully for **{new_name}**")
                            st.balloons()
                            with st.expander("View Created Profile"):
                                st.json({k: v for k, v in new_profile.items() if k != "_id"})
                            log_action(user, "CREATE", f"Created profile for {new_name}",
                                       "New patient registration", "SUCCESS")
                            get_summary_stats.clear()
                        except Exception as e:
                            st.error(f"❌ Error creating profile: {e}")
                            log_action(user, "CREATE", f"Error creating profile: {e}",
                                       "Database error", "FAILURE")
 
    # ---- BOOK APPOINTMENT ----
    st.divider()
    with st.container():
        st.subheader("📅 Book Appointment")
 
        available_doctors = (
            list(db["doctors"].distinct("name"))
            if "doctors" in db.list_collection_names()
            else []
        )
 
        with st.form("appointment_form"):
            appt_col1, appt_col2 = st.columns(2)
            with appt_col1:
                appt_patient = st.text_input("Patient Name", value=patient_name,
                                             placeholder="Your name")
                appointment_date = st.date_input(
                    "Preferred Date", min_value=datetime.now().date()
                )
            with appt_col2:
                if available_doctors:
                    appt_doctor = st.selectbox("Select Doctor", available_doctors)
                else:
                    appt_doctor = st.text_input("Doctor Name", value=doctor,
                                                placeholder="Dr. Smith")
                appointment_type = st.selectbox(
                    "Appointment Type",
                    ["General Consultation", "Follow-up", "Emergency", "Specialist Referral"]
                )
 
            notes = st.text_area(
                "Additional Notes (Optional)",
                placeholder="Describe symptoms or reason for visit..."
            )
            book_submitted = st.form_submit_button("📆 Book Appointment", use_container_width=True)
 
            if book_submitted:
                if not appt_patient.strip() or not appt_doctor:
                    st.error("❌ Please provide both patient name and doctor")
                    log_action(user, "CREATE", "Failed appointment booking - missing fields",
                               "Missing patient or doctor information", "FAILURE")
                else:
                    patient_exists = db["patients"].find_one({"name": appt_patient.strip()})
                    if not patient_exists:
                        st.warning("⚠️ Patient profile not found. Please create a profile first.")
                        log_action(user, "CREATE",
                                   f"Appointment failed - patient {appt_patient} not found",
                                   "Patient profile does not exist", "FAILURE")
                    else:
                        appointment = {
                            "patient": appt_patient.strip(),
                            "doctor": appt_doctor,
                            "user_id": user_id or patient_exists.get("user_id"),
                            "appointment_date": appointment_date.isoformat(),
                            "type": appointment_type,
                            "notes": notes.strip() if notes else None,
                            "status": "Pending",
                            "created_at": datetime.now().isoformat()
                        }
                        try:
                            db["appointments"].insert_one(appointment)
                            st.success(
                                f"✅ Appointment booked with **{appt_doctor}** on **{appointment_date}**"
                            )
                            with st.expander("Appointment Details"):
                                st.json({k: v for k, v in appointment.items() if k != "_id"})
                            log_action(
                                user, "CREATE",
                                f"Booked {appointment_type} with Dr. {appt_doctor}",
                                f"User requested {appointment_type.lower()}", "SUCCESS"
                            )
                            get_summary_stats.clear()
                        except Exception as e:
                            st.error(f"❌ Error booking appointment: {e}")
                            log_action(user, "CREATE", f"Error booking appointment: {e}",
                                       "Database error", "FAILURE")
 
    # ---- DASHBOARD SUMMARY ----
    st.divider()
    st.subheader("📊 Dashboard Summary")
 
    stats = get_summary_stats()
    pending_appointments = db["appointments"].count_documents({"status": "Pending"})
    today = datetime.now().date().isoformat()
    today_appointments = db["appointments"].count_documents({
        "appointment_date": {"$gte": today},
        "status": {"$ne": "Cancelled"}
    })
 
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👥 Total Patients", stats["total_patients"])
    m2.metric("📋 Total Appointments", stats["total_appointments"])
    m3.metric("⏳ Pending", pending_appointments,
              delta=pending_appointments if pending_appointments > 0 else None)
    m4.metric("📅 Upcoming", today_appointments)
 
    if st.button("🔄 Refresh Statistics"):
        get_summary_stats.clear()
        st.rerun()