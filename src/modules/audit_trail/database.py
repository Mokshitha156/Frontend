from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional
 
 
# ============= CACHE MANAGEMENT =============
def clear_cache():
    """Clear Streamlit cache for data queries"""
    try:
        st.cache_data.clear()
    except Exception:
        pass
 
    try:
        st.session_state.pop("last_query", None)
    except Exception:
        pass
 
 
# ============= CONNECTION =============
@st.cache_resource
def init_connection():
    try:
        client = MongoClient(
            st.secrets["MONGO_URI"],
            serverSelectionTimeoutMS=5000
        )
        client.server_info()  # Validate connection on startup
        return client
    except Exception as e:
        st.error(f"❌ Failed to connect to MongoDB: {e}")
        st.stop()
 
 
# Initialize client and database
client = init_connection()
db = client["mydatabase"]
 
# ============= COLLECTIONS =============
collection = db["users"]
patients_collection = db["patients"]
appointments_collection = db["appointments"]
audit_collection = db["audit_logs"]
pattern_collection = db["suspicious_patterns"]
 
 
# ============= HELPERS =============
def get_collection(name: str):
    """Generic collection getter"""
    return db[name]
 
 
def check_connection() -> bool:
    """Ping the database to verify it's alive"""
    try:
        client.admin.command("ping")
        return True
    except PyMongoError:
        return False
 
 
# ============= STATISTICS =============
def get_database_stats() -> dict:
    """Get comprehensive database statistics"""
    return {
        "patients": patients_collection.count_documents({}),
        "appointments": appointments_collection.count_documents({}),
        "audit_logs": audit_collection.count_documents({}),
        "suspicious_patterns": pattern_collection.count_documents({}),
        "collections": db.list_collection_names(),
        "is_connected": check_connection()
    }
 
 
def get_collection_names() -> list:
    """Get all collection names in the database"""
    return db.list_collection_names()
 
 
def get_collection_size(collection_name: str) -> int:
    """Get the number of documents in a collection"""
    try:
        return db[collection_name].count_documents({})
    except PyMongoError:
        return 0
 
 
# ============= DATA CLEANUP =============
def delete_expired_appointments(days: int = 30) -> int:
    """Delete appointments older than specified days"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    try:
        result = appointments_collection.delete_many({
            "created_at": {"$lt": cutoff_date.isoformat()}
        })
        return result.deleted_count
    except PyMongoError as e:
        st.error(f"Error deleting expired appointments: {e}")
        return 0
 
 
def delete_old_audit_logs(days: int = 90) -> int:
    """Delete audit logs older than specified days"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    try:
        result = audit_collection.delete_many({
            "timestamp": {"$lt": cutoff_date}
        })
        return result.deleted_count
    except PyMongoError as e:
        st.error(f"Error deleting old audit logs: {e}")
        return 0
 
 
def archive_completed_appointments() -> int:
    """Soft-delete completed appointments by flagging them as archived"""
    try:
        result = appointments_collection.update_many(
            {"status": "Completed", "archived": {"$ne": True}},
            {"$set": {
                "archived": True,
                "archived_at": datetime.utcnow().isoformat()
            }}
        )
        return result.modified_count
    except PyMongoError as e:
        st.error(f"Error archiving appointments: {e}")
        return 0
 
 
# ============= BULK OPERATIONS =============
def bulk_delete_patients(patient_ids: list) -> int:
    """Delete multiple patients by user_id"""
    if not patient_ids:
        return 0
    try:
        result = patients_collection.delete_many({"user_id": {"$in": patient_ids}})
        return result.deleted_count
    except PyMongoError as e:
        st.error(f"Error bulk deleting patients: {e}")
        return 0
 
 
def bulk_delete_appointments(patient_ids: list) -> int:
    """Delete all appointments for a list of patients"""
    if not patient_ids:
        return 0
    try:
        result = appointments_collection.delete_many({"user_id": {"$in": patient_ids}})
        return result.deleted_count
    except PyMongoError as e:
        st.error(f"Error bulk deleting appointments: {e}")
        return 0
 
 
def bulk_delete_audit_logs(user_ids: list) -> int:
    """Delete audit logs for multiple users"""
    if not user_ids:
        return 0
    try:
        result = audit_collection.delete_many({"user.user_id": {"$in": user_ids}})
        return result.deleted_count
    except PyMongoError as e:
        st.error(f"Error bulk deleting audit logs: {e}")
        return 0
 
 
# ============= INDEX MANAGEMENT =============
def create_indexes():
    """Create indexes for optimal query performance"""
    try:
        patients_collection.create_index("user_id", unique=True)
        patients_collection.create_index("email")
        patients_collection.create_index("created_at")
 
        appointments_collection.create_index("user_id")
        appointments_collection.create_index("status")
        appointments_collection.create_index("created_at")
 
        audit_collection.create_index("user.user_id")
        audit_collection.create_index("status")
        audit_collection.create_index("timestamp")
        audit_collection.create_index("action.action_type")
 
        pattern_collection.create_index("user.user_id")
        pattern_collection.create_index("severity")
        pattern_collection.create_index("detected_at")
    except PyMongoError as e:
        st.warning(f"Index creation warning: {e}")
 
 
# ============= BACKUP & EXPORT =============
def export_collection_to_dict(collection_name: str) -> list:
    """Export entire collection as a list of dicts (excluding _id)"""
    try:
        return list(db[collection_name].find({}, {"_id": 0}))
    except PyMongoError as e:
        return [{"error": str(e)}]
 
 
def get_collection_stats_by_date(collection_name: str, date_field: str = "created_at") -> list:
    """
    Get document counts per day for a collection.
    Handles both string ISO dates and native BSON dates.
    """
    col = db[collection_name]
    pipeline = [
        {
            "$addFields": {
                "_parsed_date": {
                    "$cond": {
                        "if": {"$eq": [{"$type": f"${date_field}"}, "string"]},
                        "then": {"$dateFromString": {"dateString": f"${date_field}"}},
                        "else": f"${date_field}"
                    }
                }
            }
        },
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$_parsed_date"
                    }
                },
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"_id": ASCENDING}}
    ]
    try:
        return list(col.aggregate(pipeline))
    except PyMongoError as e:
        return [{"error": str(e)}]
 
 
# ============= DATA VALIDATION =============
def validate_patient_exists(user_id: str) -> bool:
    """Check if a patient exists by user_id"""
    return patients_collection.find_one({"user_id": user_id}) is not None
 
 
def validate_appointment_exists(user_id: str, patient: str) -> bool:
    """Check if an appointment exists for a given user and patient"""
    return appointments_collection.find_one({
        "user_id": user_id,
        "patient": patient
    }) is not None
 
 
# ============= SEARCH OPERATIONS =============
def search_patients(query: str) -> list:
    """Search patients by user_id, name, or email (case-insensitive)"""
    if not query:
        return []
    regex = {"$regex": query, "$options": "i"}
    return list(patients_collection.find({
        "$or": [
            {"user_id": regex},
            {"name": regex},
            {"email": regex}
        ]
    }, {"_id": 0}))
 
 
def search_audit_logs(query: str) -> list:
    """Search audit logs by description or username (case-insensitive)"""
    if not query:
        return []
    regex = {"$regex": query, "$options": "i"}
    return list(audit_collection.find({
        "$or": [
            {"action.description": regex},
            {"user.username": regex}
        ]
    }, {"_id": 0}))