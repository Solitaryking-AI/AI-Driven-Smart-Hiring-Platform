import os
import logging
import env_loader  # Ensures .env is loaded before environment variable access
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = "sqlite:///smarthire.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    import models
    Base.metadata.create_all(bind=engine)
    # Perform non-destructive migrations for existing SQLite tables
    try:
        with engine.connect() as conn:
            # Check candidates table columns
            res = conn.execute(text("PRAGMA table_info(candidates)")).fetchall()
            cand_cols = {row[1] for row in res}
            if "user_id" not in cand_cols:
                conn.execute(text("ALTER TABLE candidates ADD COLUMN user_id INTEGER REFERENCES users(user_id)"))
            if "stage" not in cand_cols:
                conn.execute(text("ALTER TABLE candidates ADD COLUMN stage VARCHAR(50)"))
            if "deleted_at" not in cand_cols:
                conn.execute(text("ALTER TABLE candidates ADD COLUMN deleted_at DATETIME"))

            # Check users table columns
            res_u = conn.execute(text("PRAGMA table_info(users)")).fetchall()
            user_cols = {row[1] for row in res_u}
            if "last_login_at" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at DATETIME"))

            # Check interview_sessions table columns
            res_i = conn.execute(text("PRAGMA table_info(interview_sessions)")).fetchall()
            int_cols = {row[1] for row in res_i}
            if "feedback" not in int_cols:
                conn.execute(text("ALTER TABLE interview_sessions ADD COLUMN feedback TEXT"))
            if "interview_type" not in int_cols:
                conn.execute(text("ALTER TABLE interview_sessions ADD COLUMN interview_type VARCHAR(50) DEFAULT 'mixed'"))
            # Check applications table columns
            res_a = conn.execute(text("PRAGMA table_info(applications)")).fetchall()
            app_cols = {row[1] for row in res_a}
            if app_cols:
                if "notes" not in app_cols:
                    conn.execute(text("ALTER TABLE applications ADD COLUMN notes TEXT"))
                if "stage_history" not in app_cols:
                    conn.execute(text("ALTER TABLE applications ADD COLUMN stage_history TEXT"))
            conn.commit()

            # Ensure existing candidates have at least one pipeline application record (single-query backfill)
            conn.execute(text("""
                INSERT INTO applications (candidate_id, stage, stage_history, created_at, updated_at)
                SELECT
                    c.candidate_id,
                    CASE
                        WHEN LOWER(TRIM(COALESCE(c.stage, 'new'))) IN ('new', 'shortlisted', 'interview', 'offered', 'hired', 'rejected')
                        THEN LOWER(TRIM(c.stage))
                        ELSE 'new'
                    END,
                    '[{"from_stage": null, "to_stage": "' ||
                    CASE
                        WHEN LOWER(TRIM(COALESCE(c.stage, 'new'))) IN ('new', 'shortlisted', 'interview', 'offered', 'hired', 'rejected')
                        THEN LOWER(TRIM(c.stage))
                        ELSE 'new'
                    END || '", "timestamp": "' || COALESCE(c.created_at, '2026-01-01 00:00:00') || '", "updated_by": "system", "notes": "Initial pipeline record"}]',
                    COALESCE(c.created_at, CURRENT_TIMESTAMP),
                    COALESCE(c.created_at, CURRENT_TIMESTAMP)
                FROM candidates c
                WHERE NOT EXISTS (
                    SELECT 1 FROM applications a WHERE a.candidate_id = c.candidate_id
                )
            """))
            conn.commit()

            # Bootstrap initial admin if no admin exists and env vars are set
            admin_row = conn.execute(
                text("SELECT user_id FROM users WHERE LOWER(job_title) = 'admin' LIMIT 1")
            ).fetchone()
            if not admin_row:
                boot_email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip()
                boot_pass = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
                if boot_email and boot_pass:
                    import auth
                    hashed_pwd = auth.hash_password(boot_pass)
                    conn.execute(
                        text(
                            "INSERT INTO users (full_name, email, password_hash, company_name, job_title, is_active, created_at) "
                            "VALUES (:name, :email, :pwd, :company, 'Admin', 1, CURRENT_TIMESTAMP)"
                        ),
                        {
                            "name": "System Administrator",
                            "email": boot_email.lower(),
                            "pwd": hashed_pwd,
                            "company": "SmartHire AI",
                        }
                    )
                    conn.commit()
                    logger.info("Bootstrap admin created successfully for %s", boot_email.lower())
                else:
                    logger.warning(
                        "No admin user exists in the database, and BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD are not set. "
                        "Admin-level access and provisioning will be unavailable until an admin is created."
                    )
    except Exception as e:
        logger.warning("Non-critical migration/bootstrap issue during init_db: %s", e)

