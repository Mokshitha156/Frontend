import streamlit as st
from src.modules.audit_trail.services import create_user
from src.modules.audit_trail.schemas import UserCreate
from src.modules.audit_trail.database import db, check_connection

def signup_page():
    st.title("Create Account")
    
    # Debug: Check MongoDB connection
    try:
        is_connected = check_connection()
        users_count = db["users"].count_documents({})
        if is_connected:
            st.caption(f"🟢 Connected to MongoDB Atlas | Current users: {users_count}")
        else:
            st.error("🔴 Not connected to MongoDB Atlas")
    except Exception as e:
        st.error(f"🔴 MongoDB Error: {e}")

    role = st.selectbox("Signup as", ["Patient", "Doctor"])
    full_name = st.text_input("Full Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")

    if st.button("Create Account"):
        if not all([full_name, email, password, confirm_password]):
            st.error("Please fill all fields")
        elif password != confirm_password:
            st.error("Passwords do not match")
        elif len(password) < 6:
            st.error("Password must be at least 6 characters")
        else:
            user_data = UserCreate(
                email=email,
                password=password,
                full_name=full_name,
                role=role
            )
            
            result = create_user(user_data)
            if result:
                st.success("✅ Account created successfully! Please login.")
                # Verify it was saved
                saved_user = db["users"].find_one({"email": email})
                if saved_user:
                    st.info(f"✅ Verified in MongoDB Atlas! User ID: {saved_user.get('user_id')}")
                st.session_state.page = "login"
                st.rerun()
            else:
                # Check if email exists
                existing = db["users"].find_one({"email": email})
                if existing:
                    st.error("❌ Email already exists in database")
                else:
                    st.error("❌ Failed to create account. Check console for error details.")

    st.markdown("Already have an account?")
    if st.button("Login"):
        st.session_state.page = "login"
        st.rerun()
    
    # Debug: Show all users in database
    with st.expander("🔍 Debug: View Users in MongoDB"):
        try:
            all_users = list(db["users"].find({}, {"_id": 0, "password": 0}))
            st.write(f"Total users in database: {len(all_users)}")
            if all_users:
                for u in all_users:
                    st.json(u)
            else:
                st.info("No users found in the database")
        except Exception as e:
            st.error(f"Error: {e}")
