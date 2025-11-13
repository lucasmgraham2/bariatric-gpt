from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, Date, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date
import hashlib
import secrets
import os
import time

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://bariatric_user:bariatric_password@localhost:5432/bariatric_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# User table
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    # JSON string storing user's profile/preferences (kept simple for portability)
    profile_json = Column(String, nullable=True, default='{}')
    # Concise conversation memory / summary for this user (grows over time)
    conversation_memory = Column(String, nullable=True, default='')
    # Optional conversation log stored as JSON array string (recent exchanges)
    conversation_log = Column(String, nullable=True, default='[]')

# Patient table (for demo purposes)
class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    surgery_type = Column(String)
    surgery_date = Column(Date)
    current_weight = Column(Float)
    starting_weight = Column(Float)
    bmi = Column(Float)
    status = Column(String)

# Request/Response models
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    profile: Optional[dict] = None
    memory: Optional[str] = None
    
    class Config:
        from_attributes = True

class PatientResponse(BaseModel):
    id: int
    name: str
    age: Optional[int]
    surgery_type: Optional[str]
    surgery_date: Optional[date]
    current_weight: Optional[float]
    starting_weight: Optional[float]
    bmi: Optional[float]
    status: Optional[str]
    
    class Config:
        from_attributes = True

app = FastAPI()

# Optional service API key to protect memory writes. If set, PUT /me/{user_id}/memory
# requires the header 'X-SERVICE-KEY' to match this value. If not set, behavior is
# backwards compatible (no header required).
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY")


def ensure_profile_json_column():
    """Ensure the users table has a profile_json column; if not, add it.

    This helps when the database was created before the code added the column.
    """
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if 'users' in tables:
            cols = [c['name'] for c in inspector.get_columns('users')]
            if 'profile_json' not in cols:
                print("'profile_json' column missing on users table; adding it now...")
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN profile_json TEXT DEFAULT '{}'"))
                    print("Added 'profile_json' column to users table")
                except Exception as e:
                    print(f"Failed to add profile_json column: {e}")
            else:
                print("'profile_json' column already exists on users table")

            if 'conversation_memory' not in cols:
                print("'conversation_memory' column missing on users table; adding it now...")
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN conversation_memory TEXT DEFAULT ''"))
                    print("Added 'conversation_memory' column to users table")
                except Exception as e:
                    print(f"Failed to add conversation_memory column: {e}")
            else:
                print("'conversation_memory' column already exists on users table")

            if 'conversation_log' not in cols:
                print("'conversation_log' column missing on users table; adding it now...")
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN conversation_log TEXT DEFAULT '[]'"))
                    print("Added 'conversation_log' column to users table")
                except Exception as e:
                    print(f"Failed to add conversation_log column: {e}")
            else:
                print("'conversation_log' column already exists on users table")
        else:
            print("Users table does not exist yet; create_all will create it with the profile_json column if present in the model")
    except Exception as e:
        print(f"Could not inspect database schema to ensure profile_json column: {e}")

@app.on_event("startup")
async def startup_event():
    # Try to create tables with retry logic
    print(f"Using database URL: {DATABASE_URL}")
    max_retries = 5
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database tables created successfully")
            # Ensure profile_json column exists for compatibility with older databases
            ensure_profile_json_column()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Database connection attempt {attempt + 1} failed, retrying in 2 seconds...")
                time.sleep(2)
            else:
                print(f"Failed to connect to database after {max_retries} attempts: {e}")
                raise

def get_db():
    max_retries = 3
    for attempt in range(max_retries):
        db = None
        try:
            db = SessionLocal()
            # Test the connection
            db.execute(text("SELECT 1"))
            break
        except Exception as e:
            if db:
                db.close()
                db = None
            if attempt < max_retries - 1:
                print(f"Database connection attempt {attempt + 1} failed, retrying in 1 second...")
                time.sleep(1)
            else:
                print(f"Database connection failed after {max_retries} attempts: {e}")
                raise HTTPException(status_code=503, detail="Database service temporarily unavailable")
    
    if db is None:
        raise HTTPException(status_code=503, detail="Database service temporarily unavailable")
    
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    """Simple password hashing with SHA-256 and salt"""
    # Generate a random salt
    salt = secrets.token_hex(16)
    # Hash password with salt
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    # Return salt + hash combined
    return f"{salt}${password_hash}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    try:
        # Split salt and hash
        salt, stored_hash = hashed_password.split('$')
        # Hash the plain password with the same salt
        password_hash = hashlib.sha256((plain_password + salt).encode()).hexdigest()
        # Compare hashes
        return password_hash == stored_hash
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

@app.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    print(f"Register attempt for user: {user.username}, email: {user.email}")
    if db.query(User).filter((User.email == user.email) | (User.username == user.username)).first():
        raise HTTPException(status_code=400, detail="User already exists")
    
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hash_password(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    print(f"User {user.username} registered successfully with ID: {db_user.id}")
    return db_user

@app.post("/login")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    print(f"Login attempt for user: {login_data.username}")
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user:
        print(f"User {login_data.username} not found in database")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        print(f"User {login_data.username} is not active")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(login_data.password, user.hashed_password):
        print(f"Password verification failed for user {login_data.username}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    print(f"Login successful for user: {login_data.username}")
    return {"user_id": user.id}

@app.get("/me/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Parse profile JSON into dict for response
    try:
        profile = {}
        if user.profile_json:
            import json as _json
            profile = _json.loads(user.profile_json)
    except Exception:
        profile = {}

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "is_active": user.is_active,
        "profile": profile,
        "memory": user.conversation_memory or "",
    }


class ProfileUpdate(BaseModel):
    profile: dict


@app.put("/me/{user_id}/profile")
def update_profile(user_id: int, update: ProfileUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    import json as _json
    user.profile_json = _json.dumps(update.profile)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"profile": update.profile}


class MemoryUpdate(BaseModel):
    memory: str


@app.get("/me/{user_id}/memory")
def get_memory(user_id: int, x_service_key: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """Return the conversation memory for a user.

    If SERVICE_API_KEY is configured, require the matching X-SERVICE-KEY header.
    """
    # If a service key is configured, require the caller to present it.
    if SERVICE_API_KEY:
        if not x_service_key or x_service_key != SERVICE_API_KEY:
            raise HTTPException(status_code=403, detail="Forbidden: invalid service key")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"memory": user.conversation_memory or ""}


@app.put("/me/{user_id}/memory")
def update_memory(user_id: int, update: MemoryUpdate, x_service_key: Optional[str] = Header(None), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # If a SERVICE_API_KEY is configured, require the matching header for writes.
    if SERVICE_API_KEY:
        if not x_service_key or x_service_key != SERVICE_API_KEY:
            raise HTTPException(status_code=403, detail="Forbidden: invalid service key")

    # Update the stored concise conversation memory. This endpoint is intended to
    # be used only by trusted backend services (API Gateway / LLM orchestrator).
    user.conversation_memory = update.memory
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"memory": update.memory}


class ConversationLogUpdate(BaseModel):
    log: str  # JSON array string (list of exchanges)


@app.get("/me/{user_id}/conversation_log")
def get_conversation_log(user_id: int, x_service_key: Optional[str] = Header(None), db: Session = Depends(get_db)):
    # Require service key if configured
    if SERVICE_API_KEY:
        if not x_service_key or x_service_key != SERVICE_API_KEY:
            raise HTTPException(status_code=403, detail="Forbidden: invalid service key")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"log": user.conversation_log or "[]"}


@app.put("/me/{user_id}/conversation_log")
def update_conversation_log(user_id: int, update: ConversationLogUpdate, x_service_key: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if SERVICE_API_KEY:
        if not x_service_key or x_service_key != SERVICE_API_KEY:
            raise HTTPException(status_code=403, detail="Forbidden: invalid service key")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.conversation_log = update.log
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"log": update.log}

@app.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    """
    Retrieve patient data by patient ID.
    Used by the AI agents to fetch patient information.
    """
    print(f"Fetching patient data for ID: {patient_id}")
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)