import streamlit as st
from src.modules.audit_trail.services import authenticate_user, create_user, create_audit_log, get_user_by_email
from src.modules.audit_trail.schemas import UserLogin, UserCreate, AuditLogCreate, UserMeta, ActionDetails, LogContext
from src.modules.audit_trail.database import db

def login_page():
    st.title("🏥 MediCare Login")
    
    # Debug: Show MongoDB Atlas connection status
    try:
        users_count = db["users"].count_documents({})
        st.caption(f"🟢 Connected to MongoDB Atlas | Users in database: {users_count}")
    except Exception as e:
        st.error(f"🔴 MongoDB Connection Error: {e}")

    role = st.selectbox("Login as", ["Patient", "Doctor", "Admin"])
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    # Optional: Full name for new user registration
    st.markdown("---")
    st.caption("If you're a new user, please also enter your full name below:")
    full_name = st.text_input("Full Name (required for new users)", placeholder="Enter your full name if creating new account")

    if st.button("Login"):
        if not email or not password:
            st.error("Please enter email and password")
        else:
            login_data = UserLogin(email=email, password=password)
            user = authenticate_user(login_data)
            
            # If user doesn't exist, try to create them (auto-registration)
            if not user:
                existing_user = get_user_by_email(email)
                if not existing_user:
                    if not full_name:
                        st.error("❌ Account not found. Please enter your Full Name above to create a new account.")
                        return
                    # Create new user
                    user_data = UserCreate(
                        email=email,
                        password=password,
                        full_name=full_name,
                        role=role
                    )
                    if create_user(user_data):
                        st.success("✅ New account created successfully!")
                        # Now authenticate the newly created user
                        user = authenticate_user(login_data)
                    else:
                        st.error("❌ Failed to create account. Please try again.")
                        return
                else:
                    st.error("❌ Invalid email or password")

            if user:
                # Check if selected role matches the account's role
                if user.role != role:
                    st.error(f"❌ This account is not registered as a {role}")
                    return

                # Set session state
                st.session_state.logged_in = True
                st.session_state.role = user.role
                st.session_state.user_id = user.user_id
                st.session_state.user_email = user.email
                st.session_state.user_name = user.full_name
                st.session_state.page = "dashboard"

                create_audit_log(AuditLogCreate(
                    user=UserMeta(
                        user_id=user.user_id,
                        username=user.full_name,
                        role=user.role,
                        email=user.email
                    ),
                    action=ActionDetails(
                        module="auth",
                        action_type="LOGIN",
                        description=f"{user.full_name} logged in as {user.role}"
                    ),
                    status="SUCCESS",
                    context=LogContext(ip_address="127.0.0.1", user_agent="Streamlit App")
                ))

                st.rerun()
            else:
                st.error("❌ Invalid email or password")
                create_audit_log(AuditLogCreate(
                    user=UserMeta(user_id=email, username=email, role="Unknown"),
                    action=ActionDetails(
                        module="auth",
                        action_type="LOGIN",
                        description=f"Failed login attempt for {email}"
                    ),
                    status="FAILURE",
                    context=LogContext(ip_address="127.0.0.1", user_agent="Streamlit App")
                ))

    st.markdown("Don't have an account?")
    if st.button("Signup"):
        st.session_state.page = "signup"
        st.rerun()
    
    # Debug: Show existing users in MongoDB
    with st.expander("🔍 Debug: View Users in MongoDB Atlas"):
        try:
            users = list(db["users"].find({}, {"_id": 0, "password": 0}))
            if users:
                st.write(f"**Total Users: {len(users)}**")
                for user in users:
                    st.json(user)
            else:
                st.info("No users found in database. Signup to create one!")
        except Exception as e:
            st.error(f"Error fetching users: {e}")
