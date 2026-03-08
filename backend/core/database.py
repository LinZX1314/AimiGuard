from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Float,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone
import sqlite3
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aimiguard.db")


def _adapt_datetime(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat(sep=" ")


sqlite3.register_adapter(datetime, _adapt_datetime)


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

_RBAC_ROLE_DEFS = (
    ("admin", "System administrator with full access"),
    ("operator", "Security operator"),
    ("viewer", "Read-only viewer"),
)

_RBAC_PERMISSION_DEFS = (
    ("ai_chat", "ai", "chat", "Use AI chat"),
    ("view_ai_sessions", "ai", "view", "View AI sessions"),
    ("system:config", "system", "config", "Manage system configuration"),
    ("defense:manage", "defense", "manage", "Manage defense integrations"),
    ("view_events", "defense", "view", "View defense events"),
    ("approve_event", "defense", "approve", "Approve defense events"),
    ("reject_event", "defense", "reject", "Reject defense events"),
    ("firewall_sync", "firewall", "sync", "Execute firewall sync tasks"),
    ("view_firewall_tasks", "firewall", "view", "View firewall sync tasks"),
    ("scan:execute", "scan", "execute", "Execute scan tasks"),
    ("scan:view", "scan", "view", "View scan tasks"),
    ("view_push", "push", "view", "View push channels"),
    ("manage_push", "push", "manage", "Manage push channels"),
    ("manage_plugins", "plugin", "manage", "Manage plugins"),
    ("view_plugins", "plugin", "view", "View plugins"),
    ("create_tts_task", "tts", "create", "Create TTS tasks"),
    ("view_tts_tasks", "tts", "view", "View TTS tasks"),
    ("view_audit", "audit", "view", "View audit logs"),
    ("view_system_mode", "system", "view_mode", "View system mode"),
    ("set_system_mode", "system", "set_mode", "Set system mode"),
    ("workflow_view", "workflow", "view", "View workflow definitions"),
    ("workflow_edit", "workflow", "edit", "Edit workflow drafts"),
    ("workflow_publish", "workflow", "publish", "Publish workflow versions"),
    ("workflow_rollback", "workflow", "rollback", "Rollback workflow versions"),
    ("system_rollback", "system", "rollback", "Rollback system snapshot"),
    ("generate_report", "report", "generate", "Generate security reports"),
)

_RBAC_ROLE_PERMISSION_NAMES = {
    "viewer": (
        "view_events",
        "scan:view",
        "view_ai_sessions",
        "view_audit",
        "view_push",
        "view_plugins",
        "view_tts_tasks",
        "view_firewall_tasks",
        "view_system_mode",
    ),
    "operator": (
        "view_events",
        "approve_event",
        "reject_event",
        "scan:view",
        "scan:execute",
        "ai_chat",
        "view_ai_sessions",
        "firewall_sync",
        "view_firewall_tasks",
        "view_push",
        "manage_push",
        "view_plugins",
        "create_tts_task",
        "view_tts_tasks",
        "workflow_view",
        "view_audit",
        "view_system_mode",
        "system:config",
        "defense:manage",
        "generate_report",
    ),
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Core Business ──


class ThreatEvent(Base):
    __tablename__ = "threat_event"
    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False)
    source_vendor = Column(String)
    source_type = Column(String)
    source_event_id = Column(String)
    attack_count = Column(Integer, default=1)
    asset_ip = Column(String)
    service_name = Column(String)
    service_type = Column(String)
    service_port = Column(String)  # HFish: 服务端口
    threat_label = Column(String)
    is_white = Column(Integer, default=0)
    ip_location = Column(String)  # HFish: IP地理位置
    client_id = Column(String)  # HFish: 客户端ID
    client_name = Column(String)  # HFish: 客户端名称
    ai_score = Column(Integer)
    ai_reason = Column(Text)
    action_suggest = Column(String)
    status = Column(String, nullable=False, default="PENDING", index=True)
    trace_id = Column(String, nullable=False, index=True)
    raw_payload = Column(Text)
    extra_json = Column(Text)
    false_positive_by = Column(String)
    false_positive_reason = Column(Text)
    false_positive_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Asset(Base):
    __tablename__ = "asset"
    id = Column(Integer, primary_key=True, index=True)
    target = Column(String, unique=True, nullable=False)
    target_type = Column(String, nullable=False)
    tags = Column(Text)
    priority = Column(Integer, default=5)
    enabled = Column(Integer, default=1)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ExecutionTask(Base):
    __tablename__ = "execution_task"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("threat_event.id"), nullable=False)
    device_id = Column(Integer)
    action = Column(String, nullable=False)
    state = Column(String, nullable=False, default="QUEUED")
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    approved_by = Column(String)
    trace_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ScanTask(Base):
    __tablename__ = "scan_task"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("asset.id"), nullable=False)
    target = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    profile = Column(String)
    script_set = Column(String)
    state = Column(String, nullable=False, default="CREATED")
    priority = Column(Integer, default=5)
    timeout_seconds = Column(Integer, default=3600)
    retry_count = Column(Integer, default=0)
    raw_output_path = Column(String)
    error_message = Column(Text)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    trace_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ScanFinding(Base):
    __tablename__ = "scan_finding"
    id = Column(Integer, primary_key=True, index=True)
    scan_task_id = Column(Integer, ForeignKey("scan_task.id"), nullable=False)
    asset = Column(String, nullable=False)
    port = Column(Integer)
    service = Column(String)
    vuln_id = Column(String)
    cve = Column(String)
    severity = Column(String)
    evidence = Column(Text)
    # Nmap 扫描特有字段
    mac_address = Column(String)  # MAC地址
    vendor = Column(String)  # 厂商
    hostname = Column(String)  # 主机名
    state = Column(String)  # 主机状态 (up/down)
    os_type = Column(String)  # 操作系统类型
    os_accuracy = Column(String)  # OS识别精确度
    exploitability_json = Column(Text)
    cvss_score = Column(Float)
    cvss_vector = Column(String)
    epss_score = Column(Float)
    patch_url = Column(String)
    enriched_at = Column(DateTime)
    status = Column(String, nullable=False, default="NEW")
    trace_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Device(Base):
    __tablename__ = "device"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    ip = Column(String, nullable=False)
    port = Column(Integer, default=23)
    vendor = Column(String, nullable=False)
    device_type = Column(String)
    enabled = Column(Integer, default=1)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Credential(Base):
    __tablename__ = "credential"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("device.id"), nullable=False)
    username = Column(String, nullable=False)
    secret_ciphertext = Column(Text, nullable=False)
    key_version = Column(String, default="v1")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AIDecisionLog(Base):
    __tablename__ = "ai_decision_log"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("threat_event.id"))
    scan_task_id = Column(Integer, ForeignKey("scan_task.id"))
    context_type = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    decision = Column(String)
    confidence = Column(Float)
    reason = Column(Text)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    prompt_hash = Column(String)
    inference_ms = Column(Float)
    model_params = Column(Text)
    trace_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AIChatSession(Base):
    __tablename__ = "ai_chat_session"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    context_type = Column(String)
    context_id = Column(Integer)
    operator = Column(String, nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AIChatMessage(Base):
    __tablename__ = "ai_chat_message"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("ai_chat_session.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    evidence_refs = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AIReport(Base):
    __tablename__ = "ai_report"
    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String, nullable=False)
    scope = Column(String)
    summary = Column(Text, nullable=False)
    detail_path = Column(String)
    format = Column(String, default="markdown")
    trace_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AITTSTask(Base):
    __tablename__ = "ai_tts_task"
    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String, nullable=False)
    source_id = Column(Integer)
    text_content = Column(Text, nullable=False)
    voice_model = Column(String, default="local-tts-v1")
    audio_path = Column(String)
    state = Column(String, nullable=False, default="PENDING")
    error_message = Column(Text)
    trace_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class FixTicket(Base):
    __tablename__ = "fix_ticket"
    id = Column(Integer, primary_key=True, index=True)
    finding_id = Column(Integer, ForeignKey("scan_finding.id"))
    priority = Column(String, nullable=False, default="medium")
    assignee = Column(String)
    status = Column(String, nullable=False, default="OPEN")
    due_date = Column(String)
    resolution_note = Column(Text)
    closed_at = Column(DateTime)
    trace_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SecurityScanReport(Base):
    __tablename__ = "security_scan_report"
    id = Column(Integer, primary_key=True, index=True)
    scan_tool = Column(String, nullable=False)
    trigger_type = Column(String, nullable=False, default="manual")
    branch = Column(String)
    commit_sha = Column(String)
    total_findings = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    findings_json = Column(Text)
    passed = Column(Integer, default=1)
    trace_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Honeytoken(Base):
    __tablename__ = "honeytoken"
    id = Column(Integer, primary_key=True, index=True)
    token_type = Column(String, nullable=False)
    value_hash = Column(String, nullable=False)
    deployed_location = Column(String)
    status = Column(String, nullable=False, default="ACTIVE")
    triggered_at = Column(DateTime)
    attacker_ip = Column(String)
    trigger_count = Column(Integer, default=0)
    trace_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class HoneypotConfig(Base):
    __tablename__ = "honeypot_config"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    target_service = Column(String)
    bait_data = Column(Text)
    status = Column(String, nullable=False, default="INACTIVE")
    hfish_node_id = Column(String)
    trace_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PluginRegistry(Base):
    __tablename__ = "plugin_registry"
    id = Column(Integer, primary_key=True, index=True)
    plugin_name = Column(String, unique=True, nullable=False)
    plugin_type = Column(String, nullable=False)
    endpoint = Column(String)
    config_json = Column(Text)
    enabled = Column(Integer, default=1)
    declared_permissions = Column(Text)  # S2-02: JSON array e.g. ["read_only","network_access"]
    actual_calls_json = Column(Text)  # S2-02: 运行时调用记录
    risk_score = Column(Integer, default=0)  # S2-02: 风险评分
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PushChannel(Base):
    __tablename__ = "push_channel"
    id = Column(Integer, primary_key=True, index=True)
    channel_type = Column(String, nullable=False)
    channel_name = Column(String, unique=True, nullable=False)
    target = Column(String, nullable=False)
    config_json = Column(Text)
    enabled = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class FirewallSyncTask(Base):
    __tablename__ = "firewall_sync_task"
    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False)
    firewall_vendor = Column(String, nullable=False)
    policy_id = Column(String)
    action = Column(String, nullable=False)
    request_hash = Column(String, unique=True, nullable=False)
    state = Column(String, nullable=False, default="PENDING")
    retry_count = Column(Integer, default=0)
    response_digest = Column(String)
    error_message = Column(Text)
    trace_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ModelProfile(Base):
    __tablename__ = "model_profile"
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, unique=True, nullable=False)
    model_type = Column(String, nullable=False)
    is_local = Column(Integer, default=1)
    endpoint = Column(String)
    priority = Column(Integer, default=10)
    enabled = Column(Integer, default=1)
    config_json = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definition"
    id = Column(Integer, primary_key=True, index=True)
    workflow_key = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    definition_state = Column(String, nullable=False, default="DRAFT", index=True)
    latest_version = Column(Integer, nullable=False, default=1)
    published_version = Column(Integer)
    created_by = Column(String)
    updated_by = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class WorkflowVersion(Base):
    __tablename__ = "workflow_version"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_workflow_version_workflow_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflow_definition.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    definition_state = Column(String, nullable=False, default="DRAFT", index=True)
    dsl_json = Column(Text, nullable=False)
    change_note = Column(Text)
    created_by = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class WorkflowRun(Base):
    __tablename__ = "workflow_run"
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflow_definition.id"), nullable=False, index=True)
    workflow_version_id = Column(Integer, ForeignKey("workflow_version.id"), nullable=False, index=True)
    run_state = Column(String, nullable=False, default="QUEUED", index=True)
    trigger_source = Column(String)
    trigger_ref = Column(String)
    input_payload = Column(Text)
    output_payload = Column(Text)
    context_json = Column(Text)
    trace_id = Column(String, nullable=False, index=True)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class WorkflowStepRun(Base):
    __tablename__ = "workflow_step_run"
    __table_args__ = (
        UniqueConstraint("workflow_run_id", "node_id", "attempt", name="uq_workflow_step_run_node_attempt"),
    )

    id = Column(Integer, primary_key=True, index=True)
    workflow_run_id = Column(Integer, ForeignKey("workflow_run.id"), nullable=False, index=True)
    workflow_id = Column(Integer, ForeignKey("workflow_definition.id"), nullable=False, index=True)
    workflow_version_id = Column(Integer, ForeignKey("workflow_version.id"), nullable=False, index=True)
    node_id = Column(String, nullable=False)
    node_type = Column(String, nullable=False)
    step_state = Column(String, nullable=False, default="QUEUED", index=True)
    attempt = Column(Integer, nullable=False, default=1)
    input_payload = Column(Text)
    output_payload = Column(Text)
    error_message = Column(Text)
    trace_id = Column(String, nullable=False, index=True)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ── RBAC ──


class Role(Base):
    __tablename__ = "role"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Permission(Base):
    __tablename__ = "permission"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    resource = Column(String)
    action = Column(String)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserRole(Base):
    __tablename__ = "user_role"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("role.id"), nullable=False)
    granted_by = Column(String)
    reason = Column(Text)
    trace_id = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class RolePermission(Base):
    __tablename__ = "role_permission"
    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("role.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permission.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    email = Column(String)
    full_name = Column(String)
    enabled = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    user_roles = relationship("UserRole", backref="user", lazy="joined")


# ── System Management ──


class ReleaseHistory(Base):
    __tablename__ = "release_history"
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, nullable=False)
    git_commit = Column(String, nullable=False)
    schema_version = Column(String, nullable=False)
    deploy_env = Column(String, nullable=False)
    status = Column(String, nullable=False)
    deployed_by = Column(String)
    rollback_reason = Column(Text)
    trace_id = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SystemConfigSnapshot(Base):
    __tablename__ = "system_config_snapshot"
    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String, nullable=False, index=True)
    config_value = Column(Text)
    source = Column(String, nullable=False)
    is_sensitive = Column(Integer, nullable=False, default=0)
    env = Column(String, nullable=False, index=True)
    loaded_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CollectorConfig(Base):
    """数据采集器配置表（HFish、Nmap等）"""
    __tablename__ = "collector_config"
    id = Column(Integer, primary_key=True, index=True)
    collector_type = Column(String, nullable=False, index=True)  # hfish, nmap
    config_key = Column(String, nullable=False)
    config_value = Column(Text)
    is_sensitive = Column(Integer, default=0)  # 是否敏感信息（如API密钥）
    enabled = Column(Integer, default=1)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ── Audit ──


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    target = Column(String, nullable=False)
    target_type = Column(String)
    target_ip = Column(String)
    reason = Column(Text)
    result = Column(String, nullable=False)
    error_message = Column(Text)
    trace_id = Column(String, nullable=False, index=True)
    integrity_hash = Column(String)  # SHA-256 哈希链，用于不可篡改校验
    prev_hash = Column(String)  # 前一条日志的 integrity_hash
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def _ensure_default_rbac_data() -> None:
    """Backfill missing RBAC roles/permissions for existing databases."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        roles_by_name: dict[str, Role] = {}
        for role_name, role_desc in _RBAC_ROLE_DEFS:
            role = db.query(Role).filter(Role.name == role_name).first()
            if role is None:
                role = Role(name=role_name, description=role_desc, created_at=now, updated_at=now)
                db.add(role)
                db.flush()
            elif not role.description:
                role.description = role_desc
            roles_by_name[role_name] = role

        perms_by_name: dict[str, Permission] = {}
        for name, resource, action, desc in _RBAC_PERMISSION_DEFS:
            permission = db.query(Permission).filter(Permission.name == name).first()
            if permission is None:
                # Backward compatibility: old DBs may have legacy permission names
                # with the same resource/action pair.
                permission = (
                    db.query(Permission)
                    .filter(Permission.resource == resource, Permission.action == action)
                    .first()
                )
                if permission is not None and permission.name != name:
                    name_conflict = db.query(Permission).filter(Permission.name == name).first()
                    if name_conflict is None:
                        permission.name = name
            if permission is None:
                permission = Permission(
                    name=name,
                    resource=resource,
                    action=action,
                    description=desc,
                    created_at=now,
                )
                db.add(permission)
                db.flush()
            else:
                if not permission.resource:
                    permission.resource = resource
                if not permission.action:
                    permission.action = action
                if not permission.description:
                    permission.description = desc
            perms_by_name[name] = permission

        all_permission_ids = {perm.id for perm in db.query(Permission).all() if perm.id is not None}
        for role_name, role in roles_by_name.items():
            existing_permission_ids = {
                rp.permission_id
                for rp in db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
            }
            if role_name == "admin":
                target_permission_ids = all_permission_ids
            else:
                target_permission_ids = {
                    perms_by_name[name].id
                    for name in _RBAC_ROLE_PERMISSION_NAMES.get(role_name, ())
                    if name in perms_by_name and perms_by_name[name].id is not None
                }

            for permission_id in target_permission_ids:
                if permission_id in existing_permission_ids:
                    continue
                db.add(RolePermission(role_id=role.id, permission_id=permission_id, created_at=now))

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)

    # 轻量迁移：SQLite 上为既有表补齐新增列（兼容历史数据库）
    # 说明：SQLAlchemy create_all 不会对已存在表执行 ALTER TABLE。
    with engine.begin() as conn:
        def _sqlite_columns(table_name: str) -> set[str]:
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
            return {str(r[1]) for r in rows}

        def _ensure_sqlite_column(table_name: str, column_name: str, column_type_sql: str) -> None:
            cols = _sqlite_columns(table_name)
            if column_name in cols:
                return
            conn.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type_sql}"
            )

        # scan_finding: 新增 Nmap 主机发现字段，兼容旧库
        _ensure_sqlite_column("scan_finding", "mac_address", "VARCHAR")
        _ensure_sqlite_column("scan_finding", "vendor", "VARCHAR")
        _ensure_sqlite_column("scan_finding", "hostname", "VARCHAR")
        _ensure_sqlite_column("scan_finding", "state", "VARCHAR")
        _ensure_sqlite_column("scan_finding", "os_type", "VARCHAR")
        _ensure_sqlite_column("scan_finding", "os_accuracy", "VARCHAR")

        # threat_event: 历史库可能缺少以下字段，查询 ORM 全字段时会触发 no such column。
        _ensure_sqlite_column("threat_event", "service_port", "VARCHAR")
        _ensure_sqlite_column("threat_event", "ip_location", "VARCHAR")
        _ensure_sqlite_column("threat_event", "client_id", "VARCHAR")
        _ensure_sqlite_column("threat_event", "client_name", "VARCHAR")

        # audit_log: 审计哈希链字段（日报/周报等写审计时依赖）
        _ensure_sqlite_column("audit_log", "integrity_hash", "VARCHAR")
        _ensure_sqlite_column("audit_log", "prev_hash", "VARCHAR")

        # scan_finding: A1-01 可利用性评估 + D1-01 CVE enrichment
        _ensure_sqlite_column("scan_finding", "exploitability_json", "TEXT")
        _ensure_sqlite_column("scan_finding", "cvss_score", "REAL")
        _ensure_sqlite_column("scan_finding", "cvss_vector", "TEXT")
        _ensure_sqlite_column("scan_finding", "epss_score", "REAL")
        _ensure_sqlite_column("scan_finding", "patch_url", "TEXT")
        _ensure_sqlite_column("scan_finding", "enriched_at", "TEXT")

        # plugin_registry: S2-02 权限声明
        _ensure_sqlite_column("plugin_registry", "declared_permissions", "TEXT")
        _ensure_sqlite_column("plugin_registry", "actual_calls_json", "TEXT")
        _ensure_sqlite_column("plugin_registry", "risk_score", "INTEGER")

        # fix_ticket: A2-01 修复工单
        _ensure_sqlite_column("fix_ticket", "finding_id", "INTEGER")
        _ensure_sqlite_column("fix_ticket", "priority", "VARCHAR")
        _ensure_sqlite_column("fix_ticket", "assignee", "VARCHAR")
        _ensure_sqlite_column("fix_ticket", "status", "VARCHAR")
        _ensure_sqlite_column("fix_ticket", "due_date", "VARCHAR")
        _ensure_sqlite_column("fix_ticket", "resolution_note", "TEXT")
        _ensure_sqlite_column("fix_ticket", "closed_at", "VARCHAR")

    _ensure_default_rbac_data()
