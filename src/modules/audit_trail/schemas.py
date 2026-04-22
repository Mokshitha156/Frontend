from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


# ============= ENUMS =============
class ActionTypeEnum(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    VIEW = "VIEW"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"


class SeverityEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class StatusEnum(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PENDING = "PENDING"


class RoleEnum(str, Enum):
    PATIENT = "Patient"
    DOCTOR = "Doctor"
    ADMIN = "Admin"
    STAFF = "Staff"


# ============= USER AUTHENTICATION =============
class User(BaseModel):
    user_id: str = Field(..., description="Unique user identifier")
    email: str
    password: str  # Should be hashed before storing
    full_name: str
    role: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str


class UserLogin(BaseModel):
    email: str
    password: str


# ============= PATIENT MODELS =============
class PatientCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    age: int = Field(..., ge=0, le=150)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not v or '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()


class PatientResponse(BaseModel):
    user_id: str
    name: str
    email: str
    age: int
    history: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None


# ============= APPOINTMENT MODELS =============
class AppointmentCreate(BaseModel):
    user_id: str
    patient: str
    doctor: str
    status: str = "Pending"
    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    user_id: str
    patient: str
    doctor: str
    status: str
    created_at: datetime
    notes: Optional[str] = None


# ============= USER INFO =============
class UserMeta(BaseModel):
    user_id: str
    username: str
    role: str
    email: Optional[str] = None
    ip_address: Optional[str] = None
    device_info: Optional[str] = None


# ============= SYSTEM ACTION =============
class ActionDetails(BaseModel):
    module: str
    action_type: str
    description: Optional[str] = None
    endpoint: Optional[str] = None
    table_affected: Optional[str] = None


# ============= LOG CONTEXT =============
class LogContext(BaseModel):
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    reason: Optional[str] = None
    metadata: Optional[Dict] = None
    duration_ms: Optional[int] = None


# ============= AUDIT LOG CREATE =============
class AuditLogCreate(BaseModel):
    user: UserMeta
    action: ActionDetails
    context: Optional[LogContext] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    status: str = Field(..., description="SUCCESS or FAILURE")
    previous_hash: Optional[str] = None
    current_hash: Optional[str] = None
    digital_signature: Optional[str] = None


# ============= AUDIT LOG RESPONSE =============
class AuditLogResponse(BaseModel):
    log_id: str
    user_id: str
    username: str
    role: str
    module: str
    action_type: str
    description: Optional[str]
    timestamp: datetime
    status: str
    previous_hash: Optional[str] = None
    current_hash: Optional[str] = None
    digital_signature: Optional[str] = None


# ============= AUDIT ANALYTICS =============
class AuditAnalyticsResponse(BaseModel):
    module: Optional[str] = None
    total_actions: int
    successful_actions: int
    failed_actions: int
    success_rate: float
    last_activity: Optional[datetime] = None
    most_active_user: Optional[str] = None
    anomaly_count: Optional[int] = 0
    peak_activity_hour: Optional[int] = None
    users_count: int
    actions_by_type: Dict[str, int] = {}


# ============= SUSPICIOUS PATTERN =============
class SuspiciousPattern(BaseModel):
    pattern_id: Optional[str] = None
    user: UserMeta
    pattern_type: str
    description: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    severity: str
    related_logs: Optional[List[str]] = None
    risk_score: Optional[int] = None


class SuspiciousPatternResponse(BaseModel):
    pattern_id: str
    user_id: str
    username: str
    pattern_type: str
    description: Optional[str]
    detected_at: datetime
    severity: str
    related_logs: Optional[List[str]] = None
    risk_score: Optional[int] = None


# ============= COMPLIANCE REPORT =============
class ComplianceReport(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_logs: int
    total_users: int
    success_rate: float
    failure_rate: float
    top_risky_users: Optional[List[str]] = None
    critical_alerts: Optional[int] = 0
    patterns_detected: int
    integrity_status: str


# ============= ERROR RESPONSE =============
class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict] = None