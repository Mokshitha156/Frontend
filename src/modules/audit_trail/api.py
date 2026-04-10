from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
 
from src.modules.audit_trail.services import (
    authenticate_user,
    create_user,
    get_user_by_email,
    create_audit_log,
    get_all_logs,
    detect_all_patterns,
    get_all_patterns,
    save_patterns,
    check_log_integrity,
    generate_compliance_report,
    export_audit_logs_csv,
    get_patient_stats
)
from src.modules.audit_trail.database import db, check_connection
from src.modules.audit_trail.schemas import (
    UserCreate,
    UserLogin,
    AuditLogCreate,
)
 
router = APIRouter(prefix="/api/v1", tags=["module39"])
 
 
# ============= HEALTH =============
@router.get("/health", tags=["system"])
def health_check():
    """Service health check including database connectivity."""
    db_alive = check_connection()
    return {
        "status": "healthy" if db_alive else "degraded",
        "database": "connected" if db_alive else "unreachable",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "MediCare API Module39"
    }
 
 
# ============= AUTHENTICATION =============
@router.post("/signup", tags=["auth"])
def signup(user_data: UserCreate):
    """Register a new user account."""
    try:
        if not create_user(user_data):
            raise HTTPException(status_code=400, detail="Email already registered")
        return {
            "status": "success",
            "message": "Account created successfully",
            "user_email": user_data.email
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.post("/login", tags=["auth"])
def login(login_data: UserLogin):
    """Authenticate a user and return their profile."""
    try:
        user = authenticate_user(login_data)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return {
            "status": "success",
            "message": "Login successful",
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.get("/user/{email}", tags=["auth"])
def get_user(email: str):
    """Look up a user by email address."""
    try:
        user = get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        # Never expose the password hash
        user_dict = user.dict()
        user_dict.pop("password", None)
        return user_dict
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
# ============= AUDIT LOGS =============
@router.get("/audit-logs", tags=["audit"])
def get_logs(
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    skip: int = Query(0, ge=0, description="Records to skip for pagination")
):
    """Get all audit logs with pagination support."""
    try:
        logs = list(db["audit_logs"].find({}, {"_id": 0}).skip(skip).limit(limit))
        total = db["audit_logs"].count_documents({})
        return {
            "status": "success",
            "total": total,
            "skip": skip,
            "limit": limit,
            "returned": len(logs),
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.get("/audit-logs/user/{user_id}", tags=["audit"])
def get_user_logs(
    user_id: str,
    limit: int = Query(50, ge=1, le=500)
):
    """Get audit logs for a specific user."""
    try:
        logs = list(
            db["audit_logs"].find(
                {"user.user_id": user_id}, {"_id": 0}
            ).limit(limit)
        )
        return {
            "status": "success",
            "user_id": user_id,
            "count": len(logs),
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.post("/audit-logs", tags=["audit"])
def create_log(log_data: AuditLogCreate):
    """Create a new audit log entry."""
    try:
        result = create_audit_log(log_data)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        return {
            "status": "success",
            "message": "Audit log created",
            "log_id": result.get("log_id")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.get("/audit-logs/integrity", tags=["audit"])
def verify_integrity():
    """Check the integrity of the audit log hash chain."""
    try:
        is_valid = check_log_integrity()
        return {
            "status": "success",
            "integrity": "VALID" if is_valid else "COMPROMISED",
            "checked_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.get("/audit-logs/export/csv", tags=["audit"])
def export_logs_csv():
    """Export all audit logs as a CSV string."""
    try:
        csv_data = export_audit_logs_csv()
        if not csv_data:
            raise HTTPException(status_code=404, detail="No audit logs found to export")
        return {"status": "success", "data": csv_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
# ============= SUSPICIOUS PATTERNS =============
@router.get("/suspicious-patterns", tags=["patterns"])
def get_patterns():
    """Get all currently stored suspicious patterns."""
    try:
        patterns = get_all_patterns()
        return {
            "status": "success",
            "count": len(patterns),
            "patterns": patterns
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.post("/suspicious-patterns/detect", tags=["patterns"])
def run_detection():
    """Trigger pattern detection and persist results."""
    try:
        patterns = detect_all_patterns()
        save_patterns(patterns)
        return {
            "status": "success",
            "message": f"Detected {len(patterns)} suspicious patterns",
            "patterns_count": len(patterns)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
# ============= COMPLIANCE =============
@router.get("/compliance/report", tags=["compliance"])
def compliance_report():
    """Generate a full compliance and analytics report."""
    try:
        report = generate_compliance_report()
        return {"status": "success", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
# ============= PATIENT STATS =============
@router.get("/patients/stats", tags=["patients"])
def patient_stats():
    """Get high-level patient and appointment statistics."""
    try:
        stats = get_patient_stats()
        return {"status": "success", "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
