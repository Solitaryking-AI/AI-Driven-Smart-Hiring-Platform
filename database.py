from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///smarthire.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
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

            # Check interview_sessions table columns
            res_i = conn.execute(text("PRAGMA table_info(interview_sessions)")).fetchall()
            int_cols = {row[1] for row in res_i}
            if "feedback" not in int_cols:
                conn.execute(text("ALTER TABLE interview_sessions ADD COLUMN feedback TEXT"))
            if "interview_type" not in int_cols:
                conn.execute(text("ALTER TABLE interview_sessions ADD COLUMN interview_type VARCHAR(50) DEFAULT 'mixed'"))
            if "difficulty" not in int_cols:
                conn.execute(text("ALTER TABLE interview_sessions ADD COLUMN difficulty VARCHAR(50) DEFAULT 'Medium'"))
            conn.commit()
    except Exception as e:
        # Avoid crashing if tables do not exist yet or are already migrated
        pass
