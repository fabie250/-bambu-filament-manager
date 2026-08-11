import os
import datetime
import secrets
import logging
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from passlib.context import CryptContext
from jose import JWTError, jwt

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("filament_system")

# ----------------- 数据库与安全密钥配置 (脱敏占位符) -----------------
DB_USER = os.getenv("DB_USER", "你的数据库用户名")
DB_PASS = os.getenv("DB_PASS", "你的数据库密码")
DB_HOST = os.getenv("DB_HOST", "你的数据库服务器IP或网关")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "你的数据库名称")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

SECRET_KEY = os.getenv("JWT_SECRET", "你的自定义JWT随机加密密钥")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ----------------- ORM 模型 -----------------
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    api_keys = relationship("APIKey", back_populates="owner")
    filaments = relationship("Filament", back_populates="owner")
    records = relationship("UsageRecord", back_populates="owner")

class APIKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    key_name = Column(String(50), nullable=False)
    api_key = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="api_keys")

class Filament(Base):
    __tablename__ = "filaments"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(50), default="Bambu Lab")
    material = Column(String(50), nullable=False)
    color_name = Column(String(50), nullable=False)
    color_hex = Column(String(10), default="#000000")
    nfc_uid = Column(String(64), index=True, nullable=True)
    initial_weight_g = Column(Float, default=1000.0)
    current_weight_g = Column(Float, default=1000.0)
    spool_weight_g = Column(Float, default=250.0)
    price = Column(Float, default=0.0)
    remarks = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="filaments")

class UsageRecord(Base):
    __tablename__ = "usage_records"
    id = Column(Integer, primary_key=True, index=True)
    filament_id = Column(Integer, ForeignKey("filaments.id"), nullable=False)
    printer_id = Column(Integer, nullable=True)
    used_weight_g = Column(Float, nullable=False)
    remaining_weight_g = Column(Float, nullable=True)
    source = Column(String(50), default="script")
    task_name = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="records")

Base.metadata.create_all(bind=engine)
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE usage_records ADD COLUMN remaining_weight_g FLOAT DEFAULT NULL;"))
        conn.commit()
except Exception:
    pass

# ----------------- FastAPI 初始化 -----------------
app = FastAPI(title="拓竹耗材与打印机管理系统 API", version="1.8.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 多路径挂载前端，增强兼容性
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
possible_paths = [
    os.path.join(CURRENT_DIR, "frontend"),
    os.path.join(os.path.dirname(CURRENT_DIR), "frontend"),
    "../frontend",
    "./frontend",
    "/app/frontend"
]
for p in possible_paths:
    if os.path.exists(p) and os.path.isdir(p):
        app.mount("/static", StaticFiles(directory=p), name="static")
        break

@app.get("/", include_in_schema=False)
def read_index():
    for p in possible_paths:
        idx = os.path.join(p, "index.html")
        if os.path.exists(idx):
            return FileResponse(idx)
    return {"status": "success", "message": "API 服务运行正常"}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- Pydantic 结构体 -----------------
class UserCreate(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class APIKeyCreate(BaseModel):
    key_name: str

class APIKeyResponse(BaseModel):
    id: int
    key_name: str
    api_key: str
    created_at: datetime.datetime

class FilamentCreate(BaseModel):
    brand: str = "Bambu Lab"
    material: str
    color_name: str
    color_hex: str = "#000000"
    nfc_uid: Optional[str] = None
    initial_weight_g: float = 1000.0
    current_weight_g: float = 1000.0
    spool_weight_g: float = 250.0
    price: float = 0.0
    remarks: Optional[str] = None

class ManualAdjustWeightData(BaseModel):
    adjust_weight_g: float
    reason: Optional[str] = "手动调整"

class FilamentOut(BaseModel):
    id: int
    brand: str
    material: str
    color_name: str
    color_hex: str
    nfc_uid: Optional[str]
    initial_weight_g: float
    current_weight_g: float
    price: float
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class UsageRecordOut(BaseModel):
    id: int
    task_name: Optional[str]
    used_weight_g: float
    remaining_weight_g: Optional[float]
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class ScriptReportData(BaseModel):
    filament_id: int
    used_weight_g: float
    printer_id: Optional[int] = None
    task_name: Optional[str] = None

# ----------------- 安全鉴权逻辑 -----------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_token(data: dict, expires_delta: datetime.timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token 无效或已过期，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

def verify_script_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> User:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="缺少 API Key 鉴权标头")
    db_key = db.query(APIKey).filter(APIKey.api_key == x_api_key, APIKey.is_active == True).first()
    if not db_key:
        raise HTTPException(status_code=401, detail="API Key 无效或已禁用")
    return db_key.owner

# ----------------- API 接口 -----------------
@app.post("/api/auth/register", tags=["账号管理"])
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="用户名已被注册")
    new_user = User(username=user_data.username, hashed_password=get_password_hash(user_data.password))
    db.add(new_user)
    db.commit()
    return {"status": "success", "message": "注册成功"}

@app.post("/api/auth/login", response_model=TokenResponse, tags=["账号管理"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="账号或密码错误")
    return {
        "access_token": create_token({"sub": user.username}, datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)),
        "refresh_token": create_token({"sub": user.username}, datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)),
        "token_type": "bearer"
    }

@app.post("/api/auth/api-keys", response_model=APIKeyResponse, tags=["账号管理"])
def create_script_api_key(key_data: APIKeyCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    raw_key = f"sk_{secrets.token_hex(16)}"
    new_api_key = APIKey(key_name=key_data.key_name, api_key=raw_key, user_id=current_user.id)
    db.add(new_api_key)
    db.commit()
    db.refresh(new_api_key)
    return new_api_key

@app.post("/api/filaments", response_model=FilamentOut, tags=["耗材台账"])
def create_filament(f: FilamentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    filament = Filament(**f.dict(), user_id=user.id)
    db.add(filament)
    db.commit()
    db.refresh(filament)
    return filament

@app.get("/api/filaments", response_model=List[FilamentOut], tags=["耗材台账"])
def list_filaments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Filament).filter(Filament.user_id == user.id).all()

@app.get("/api/ingest/script-filaments", tags=["自动采集接入"])
def get_filaments_for_script(user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filaments = db.query(Filament).filter(Filament.user_id == user.id).all()
    return [
        {
            "id": f.id,
            "brand": f.brand,
            "material": f.material,
            "color_name": f.color_name,
            "current_weight_g": f.current_weight_g
        }
        for f in filaments
    ]

@app.post("/api/filaments/{filament_id}/adjust-weight", tags=["耗材台账"])
def adjust_filament_weight(
    filament_id: int, 
    data: ManualAdjustWeightData, 
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    filament = db.query(Filament).filter(Filament.id == filament_id, Filament.user_id == user.id).first()
    if not filament:
        raise HTTPException(status_code=404, detail="耗材不存在或无权访问")

    filament.current_weight_g = max(0.0, round(filament.current_weight_g - data.adjust_weight_g, 2))
    
    action_str = "手动增加" if data.adjust_weight_g < 0 else "手动减少"
    task_desc = f"{action_str} ({data.reason})" if data.reason else action_str

    record = UsageRecord(
        filament_id=filament_id,
        used_weight_g=data.adjust_weight_g,
        remaining_weight_g=filament.current_weight_g,
        source="manual",
        task_name=task_desc,
        user_id=user.id
    )
    db.add(record)
    db.commit()
    return {"status": "success", "message": "调整成功", "current_weight_g": filament.current_weight_g}

@app.get("/api/filaments/{filament_id}/logs", response_model=List[UsageRecordOut], tags=["耗材台账"])
def get_filament_usage_logs(filament_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = db.query(UsageRecord).filter(
        UsageRecord.filament_id == filament_id,
        UsageRecord.user_id == user.id
    ).order_by(UsageRecord.id.desc()).all()
    
    for r in records:
        if r.created_at:
            r.created_at = r.created_at + datetime.timedelta(hours=8)
    return records

# 支持正负对冲（允许撤销增加记录）
@app.delete("/api/usage-records/{record_id}", tags=["耗材台账"])
def delete_usage_record(
    record_id: int, 
    refund_weight_g: Optional[float] = None,
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    record = db.query(UsageRecord).filter(UsageRecord.id == record_id, UsageRecord.user_id == user.id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    filament = db.query(Filament).filter(Filament.id == record.filament_id, Filament.user_id == user.id).first()
    
    actual_refund = refund_weight_g if refund_weight_g is not None else record.used_weight_g
    
    if filament and actual_refund != 0:
        filament.current_weight_g = max(0.0, round(filament.current_weight_g + actual_refund, 2))

    db.delete(record)
    db.commit()
    return {"status": "success", "message": f"记录已删除，已成功处理 {actual_refund}g 耗材变更"}

@app.delete("/api/filaments/{filament_id}", tags=["耗材台账"])
def delete_filament(filament_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    filament = db.query(Filament).filter(Filament.id == filament_id, Filament.user_id == user.id).first()
    if not filament:
        raise HTTPException(status_code=404, detail="耗材不存在")
    db.query(UsageRecord).filter(UsageRecord.filament_id == filament_id).delete()
    db.delete(filament)
    db.commit()
    return {"status": "success", "message": "删除成功"}

@app.post("/api/ingest/script-report", tags=["自动采集接入"])
def report_usage_from_script(
    data: ScriptReportData,
    user: User = Depends(verify_script_api_key),
    db: Session = Depends(get_db)
):
    filament = db.query(Filament).filter(Filament.id == data.filament_id, Filament.user_id == user.id).first()
    if not filament:
        raise HTTPException(status_code=404, detail=f"找不到 ID={data.filament_id} 的耗材")

    filament.current_weight_g = max(0.0, round(filament.current_weight_g - data.used_weight_g, 2))
    
    record = UsageRecord(
        filament_id=data.filament_id,
        printer_id=data.printer_id,
        used_weight_g=data.used_weight_g,
        remaining_weight_g=filament.current_weight_g,
        source="script",
        task_name=data.task_name,
        user_id=user.id
    )
    db.add(record)
    db.commit()
    
    return {
        "status": "success",
        "message": "消耗上报成功",
        "filament_id": filament.id,
        "remaining_weight_g": filament.current_weight_g
    }
