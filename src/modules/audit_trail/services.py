import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional
 
from src.modules.audit_trail.database import db
from src.modules.audit_trail.schemas import UserMeta, SuspiciousPattern, User, UserCreate, UserLogin
 
 
# ============= COLLECTIONS =============
audit_collection = db["audit_logs"]
pattern_collection = db["suspicious_patterns"]
patients_collection = db["patients"]
appointments_collection = db["appointments"]
 
 
# ============= USER AUTHENTICATION =============
def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()
 
 
def create_user(user_data: UserCreate) -> bool:
    """Create a new user account. Returns False if email already exists."""
    try:
        print(f"[DEBUG] Attempting to create user: {user_data.email}")
        
        # Check if user exists
        existing = db["users"].find_one({"email": user_data.email})
        print(f"[DEBUG] Existing user check: {existing}")
        
        if existing:
            print(f"[DEBUG] User already exists: {user_data.email}")
            return False
        
        # Create user object
        user = User(
            user_id=user_data.email,
            email=user_data.email,
            password=hash_password(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role
        )
        
        user_dict = user.dict()
        print(f"[DEBUG] User dict to insert: {user_dict}")
        
        # Insert into MongoDB
        result = db["users"].insert_one(user_dict)
        print(f"[DEBUG] Insert result - ID: {result.inserted_id}")
        
        # Verify insertion
        verify = db["users"].find_one({"_id": result.inserted_id})
        print(f"[DEBUG] Verification - user saved: {verify is not None}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to create user: {e}")
        import traceback
        traceback.print_exc()
        return False
 
 
def authenticate_user(login_data: UserLogin) -> Optional[User]:
    """Authenticate user credentials. Returns User on success, None on failure."""
    try:
        user_doc = db["users"].find_one({"email": login_data.email})
        if not user_doc:
            return None
 
        user = User(**user_doc)
        if user.password == hash_password(login_data.password) and user.is_active:
            return user
        return None
    except Exception as e:
        print(f"Error authenticating user: {e}")
        return None
 
 
def get_user_by_email(email: str) -> Optional[User]:
    """Get a user by email address."""
    try:
        user_doc = db["users"].find_one({"email": email})
        return User(**user_doc) if user_doc else None
    except Exception as e:
        print(f"Error getting user: {e}")
        return None
 
 
# ============= HASH GENERATION =============
def generate_hash(data: dict) -> str:
    """Generate a deterministic SHA256 hash of a dictionary."""
    # Exclude MongoDB _id and hash fields before hashing
    clean = {
        k: v for k, v in data.items()
        if k not in ("_id", "current_hash", "previous_hash")
    }
    encoded = json.dumps(clean, default=str, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
 
 
def get_last_hash() -> str:
    """Get the current_hash of the most recent audit log."""
    last_log = audit_collection.find_one(sort=[("_id", -1)])
    return last_log.get("current_hash", "0") if last_log else "0"
 
 
# ============= AUDIT LOG OPERATIONS =============
def create_audit_log(log) -> dict:
    """Create and store an audit log entry with a hash chain."""
    try:
        log_dict = log.dict()
 
        # Build hash chain
        log_dict["previous_hash"] = get_last_hash()
        log_dict["current_hash"] = generate_hash(log_dict)
 
        result = audit_collection.insert_one(log_dict)
 
        # Run pattern detection after every new log
        patterns = detect_all_patterns()
        save_patterns(patterns)
 
        return {"success": True, "log_id": str(result.inserted_id)}
    except Exception as e:
        print(f"Error creating audit log: {e}")
        return {"success": False, "error": str(e)}
 
 
def get_all_logs(limit: Optional[int] = None, skip: int = 0) -> list:
    """Get all audit logs with optional pagination."""
    query = audit_collection.find({}, {"_id": 0}).skip(skip)
    if limit:
        query = query.limit(limit)
    return list(query)
 
 
def get_logs_by_user(user_id: str, limit: int = 100) -> list:
    """Get audit logs for a specific user."""
    return list(
        audit_collection.find(
            {"user.user_id": user_id}, {"_id": 0}
        ).limit(limit)
    )
 
 
def get_logs_by_status(status: str, limit: int = 100) -> list:
    """Get logs filtered by status (SUCCESS / FAILURE)."""
    return list(
        audit_collection.find(
            {"status": status}, {"_id": 0}
        ).limit(limit)
    )
 
 
def get_logs_by_action(action_type: str) -> list:
    """Get logs filtered by action type."""
    return list(
        audit_collection.find(
            {"action.action_type": action_type}, {"_id": 0}
        )
    )
 
 
def get_logs_by_date_range(start_date: datetime, end_date: datetime) -> list:
    """Get logs within a date range."""
    return list(
        audit_collection.find({
            "timestamp": {"$gte": start_date, "$lte": end_date}
        }, {"_id": 0})
    )
 
 
def delete_logs_by_user(user_id: str) -> int:
    """Delete all audit logs for a specific user."""
    result = audit_collection.delete_many({"user.user_id": user_id})
    return result.deleted_count
 
 
def delete_old_logs(days: int = 90) -> int:
    """Delete audit logs older than the specified number of days."""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    result = audit_collection.delete_many({"timestamp": {"$lt": cutoff_date}})
    return result.deleted_count
 
 
# ============= DETECTION ENGINE =============
def _parse_timestamp(ts) -> Optional[datetime]:
    """Safely parse a timestamp that may be a string or datetime."""
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return None
    return None
 
 
def detect_all_patterns() -> List[SuspiciousPattern]:
    """
    Scan all audit logs and detect suspicious behaviour patterns.
    Returns a deduplicated list of SuspiciousPattern objects.
    """
    logs = get_all_logs()
    patterns: List[SuspiciousPattern] = []
 
    user_failures: Dict[str, int] = defaultdict(int)
    user_meta_map: Dict[str, UserMeta] = {}
    user_actions: Dict[str, int] = defaultdict(int)
    user_deletions: Dict[str, int] = defaultdict(int)
    user_creations: Dict[str, int] = defaultdict(int)
    user_rapid_actions: Dict[str, int] = defaultdict(int)
    user_access_denied: Dict[str, int] = defaultdict(int)
    user_sensitive_access: Dict[str, int] = defaultdict(int)
    user_last_action: Dict[str, Optional[datetime]] = defaultdict(lambda: None)
 
    # Track which pattern types have already been raised per user
    # to avoid duplicate alerts for the same issue
    raised: Dict[str, set] = defaultdict(set)
 
    for log in logs:
        uid = log["user"]["user_id"]
        user_meta = UserMeta(**log["user"])
        user_meta_map[uid] = user_meta
 
        # ---- FIX: read from "action", not "action_details" ----
        action = log.get("action", {})
        action_type = action.get("action_type", "").upper()
 
        user_actions[uid] += 1
 
        # MULTIPLE FAILURES
        if log.get("status") == "FAILURE":
            user_failures[uid] += 1
            if user_failures[uid] >= 3 and "MULTIPLE_FAILURES" not in raised[uid]:
                raised[uid].add("MULTIPLE_FAILURES")
                patterns.append(SuspiciousPattern(
                    user=user_meta,
                    pattern_type="MULTIPLE_FAILURES",
                    description=f"User has {user_failures[uid]} failed actions",
                    severity="HIGH",
                    risk_score=90
                ))
 
        # ACCESS DENIED
        if log.get("status") == "FAILURE" and any(
            kw in action_type for kw in ("ACCESS", "LOGIN")
        ):
            user_access_denied[uid] += 1
            if user_access_denied[uid] >= 3 and "ACCESS_DENIED_PATTERNS" not in raised[uid]:
                raised[uid].add("ACCESS_DENIED_PATTERNS")
                patterns.append(SuspiciousPattern(
                    user=user_meta,
                    pattern_type="ACCESS_DENIED_PATTERNS",
                    description=f"User has {user_access_denied[uid]} failed access/login attempts",
                    severity="HIGH",
                    risk_score=85
                ))
 
        # FREQUENT DELETIONS
        if "DELETE" in action_type:
            user_deletions[uid] += 1
            if user_deletions[uid] >= 10 and "FREQUENT_DELETIONS" not in raised[uid]:
                raised[uid].add("FREQUENT_DELETIONS")
                patterns.append(SuspiciousPattern(
                    user=user_meta,
                    pattern_type="FREQUENT_DELETIONS",
                    description=f"User performed {user_deletions[uid]} delete operations",
                    severity="HIGH",
                    risk_score=80
                ))
 
        # EXCESSIVE CREATIONS
        if "CREATE" in action_type:
            user_creations[uid] += 1
            if user_creations[uid] >= 20 and "EXCESSIVE_CREATIONS" not in raised[uid]:
                raised[uid].add("EXCESSIVE_CREATIONS")
                patterns.append(SuspiciousPattern(
                    user=user_meta,
                    pattern_type="EXCESSIVE_CREATIONS",
                    description=f"User created {user_creations[uid]} records",
                    severity="MEDIUM",
                    risk_score=55
                ))
 
        # SENSITIVE DATA ACCESS
        if any(kw in action_type for kw in ("PATIENT", "VIEW")):
            user_sensitive_access[uid] += 1
            if user_sensitive_access[uid] >= 50 and "SENSITIVE_DATA_ACCESS" not in raised[uid]:
                raised[uid].add("SENSITIVE_DATA_ACCESS")
                patterns.append(SuspiciousPattern(
                    user=user_meta,
                    pattern_type="SENSITIVE_DATA_ACCESS",
                    description=f"User accessed sensitive data {user_sensitive_access[uid]} times",
                    severity="MEDIUM",
                    risk_score=75
                ))
 
        # RAPID SUCCESSION ACTIONS
        timestamp = _parse_timestamp(log.get("timestamp"))
        if timestamp:
            last = user_last_action[uid]
            if last and (timestamp - last).total_seconds() < 10:
                user_rapid_actions[uid] += 1
                if user_rapid_actions[uid] >= 5 and "RAPID_SUCCESSION_ACTIONS" not in raised[uid]:
                    raised[uid].add("RAPID_SUCCESSION_ACTIONS")
                    patterns.append(SuspiciousPattern(
                        user=user_meta,
                        pattern_type="RAPID_SUCCESSION_ACTIONS",
                        description=f"User performed {user_rapid_actions[uid]} actions in rapid succession",
                        severity="MEDIUM",
                        risk_score=65
                    ))
 
            # UNUSUAL TIME ACCESS (only raise once per user)
            if (timestamp.hour < 6 or timestamp.hour > 22) and "UNUSUAL_TIME_ACCESS" not in raised[uid]:
                raised[uid].add("UNUSUAL_TIME_ACCESS")
                patterns.append(SuspiciousPattern(
                    user=user_meta,
                    pattern_type="UNUSUAL_TIME_ACCESS",
                    description=f"Access at unusual hour: {timestamp.hour:02d}:00",
                    severity="MEDIUM",
                    risk_score=60
                ))
 
            user_last_action[uid] = timestamp
 
    # HIGH ACTIVITY (evaluated after all logs)
    for uid, count in user_actions.items():
        if count >= 20 and "HIGH_ACTIVITY" not in raised[uid]:
            patterns.append(SuspiciousPattern(
                user=user_meta_map.get(uid, UserMeta(user_id=uid, username=uid, role="Unknown")),
                pattern_type="HIGH_ACTIVITY",
                description=f"User performed {count} actions",
                severity="MEDIUM",
                risk_score=70
            ))
 
    return patterns
 
 
def save_patterns(patterns: List[SuspiciousPattern]):
    """Replace all stored patterns with the latest detection results."""
    pattern_collection.delete_many({})
    if patterns:
        pattern_collection.insert_many([p.dict() for p in patterns])
 
 
def get_all_patterns() -> list:
    """Get all detected suspicious patterns."""
    return list(pattern_collection.find({}, {"_id": 0}))
 
 
# ============= ANALYTICS REPORT =============
def get_report() -> dict:
    """Generate a comprehensive analytics report from audit logs."""
    logs = get_all_logs()
 
    total = len(logs)
    success = sum(1 for log in logs if log.get("status") == "SUCCESS")
    failure = total - success
    success_rate = round((success / total * 100), 2) if total > 0 else 0.0
 
    user_activity: Dict[str, int] = defaultdict(int)
    action_type_count: Dict[str, int] = defaultdict(int)
    hourly_activity: Dict[int, int] = defaultdict(int)
 
    for log in logs:
        uid = log["user"]["user_id"]
        user_activity[uid] += 1
        action_type_count[log["action"]["action_type"]] += 1
 
        ts = _parse_timestamp(log.get("timestamp"))
        if ts:
            hourly_activity[ts.hour] += 1
 
    most_active_user = max(user_activity, key=user_activity.get) if user_activity else None
    most_active_users = dict(
        sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:5]
    )
    peak_hour = max(hourly_activity, key=hourly_activity.get) if hourly_activity else None
    anomaly_count = pattern_collection.count_documents({})
    integrity_valid = check_log_integrity()
 
    return {
        "total_logs": total,
        "success": success,
        "failure": failure,
        "success_rate": success_rate,
        "most_active_user": most_active_user,
        "most_active_users": most_active_users,
        "peak_activity_hour": peak_hour,
        "anomaly_count": anomaly_count,
        "user_activity": dict(user_activity),
        "actions_by_type": dict(action_type_count),
        "unique_users": len(user_activity),
        "integrity_status": "VALID" if integrity_valid else "COMPROMISED"
    }
 
 
# ============= INTEGRITY CHECK =============
def check_log_integrity() -> bool:
    """Verify the audit log hash chain has not been tampered with."""
    logs = list(audit_collection.find({}, {"_id": 0}).sort("_id", 1))
 
    if not logs:
        return True
 
    prev_hash = "0"
    for log in logs:
        if log.get("previous_hash") != prev_hash:
            return False
        prev_hash = log.get("current_hash", "")
 
    return True
 
 
def verify_log_chain(user_id: str) -> bool:
    """Verify the hash chain integrity for a specific user's logs."""
    logs = list(
        audit_collection.find(
            {"user.user_id": user_id}, {"_id": 0}
        ).sort("_id", 1)
    )
 
    prev_hash = "0"
    for log in logs:
        if log.get("previous_hash") != prev_hash:
            return False
        prev_hash = log.get("current_hash", "")
 
    return True
 
 
# ============= PATIENT OPERATIONS =============
def get_patient_stats() -> dict:
    """Get high-level patient and appointment statistics."""
    return {
        "total_patients": patients_collection.count_documents({}),
        "total_appointments": appointments_collection.count_documents({}),
        "active_appointments": appointments_collection.count_documents({"status": "Pending"}),
        "completed_appointments": appointments_collection.count_documents({"status": "Completed"})
    }
 
 
# ============= EXPORT =============
def export_audit_logs_csv() -> Optional[str]:
    """Export all audit logs as a CSV string."""
    logs = get_all_logs()
    if not logs:
        return None
 
    lines = ["user_id,username,action_type,status,timestamp,module"]
    for log in logs:
        lines.append(",".join([
            log["user"]["user_id"],
            log["user"]["username"],
            log["action"]["action_type"],
            log["status"],
            str(log.get("timestamp", "")),
            log["action"]["module"]
        ]))
 
    return "\n".join(lines)
 
 
def generate_compliance_report() -> dict:
    """Generate a full compliance report."""
    report_data = get_report()
    integrity_status = check_log_integrity()
    patterns = get_all_patterns()
 
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total_logs": report_data["total_logs"],
        "success_rate": report_data["success_rate"],
        "unique_users": report_data["unique_users"],
        "anomalies_detected": len(patterns),
        "integrity_status": "VALID" if integrity_status else "COMPROMISED",
        "critical_patterns": [p for p in patterns if p.get("severity") == "HIGH"],
        "most_active_users": report_data.get("most_active_users", {}),
        "timestamp": datetime.utcnow().isoformat()
    }