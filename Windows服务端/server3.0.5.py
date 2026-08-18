import os
import sys
import datetime
import secrets
import logging
import hashlib
import socket
import urllib.request
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status, Header, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from jose import JWTError, jwt
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("filament_server")

# ----------------- 0. 路径定位与运行时环境 -----------------
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
DB_FILE_PATH = os.path.join(BASE_DIR, "filament_db.db")

# ----------------- 1. 数据库配置 (本地 SQLite) -----------------
DB_SECRET_KEY = os.getenv("DB_SECRET_KEY", "") 
DATABASE_URL = f"sqlite:///{DB_FILE_PATH}"

# SQLite 引擎配置（支持多线程并发）
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)

if DB_SECRET_KEY:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA key = '{DB_SECRET_KEY}'")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

SECRET_KEY = os.getenv("JWT_SECRET", "bambu-filament-local-jwt-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ----------------- 2. ORM 模型定义 -----------------
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

# 自动创建本地数据库表结构
Base.metadata.create_all(bind=engine)

# ----------------- 3. FastAPI 初始化与静态资源托管 -----------------
app = FastAPI(
    title="拓竹耗材与打印机管理系统 - Windows 服务端", 
    version="2.1.0",
    docs_url="/api/docs",
    redoc_url=None
)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_frontend_dir():
    if hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, "frontend")
        if os.path.exists(p): return p
    possible_paths = [
        os.path.join(BASE_DIR, "frontend"),
        os.path.join(os.path.dirname(BASE_DIR), "frontend"),
        "./frontend"
    ]
    for p in possible_paths:
        if os.path.exists(p) and os.path.isdir(p):
            return p
    return None

FRONTEND_DIR = get_frontend_dir()
if FRONTEND_DIR:
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", include_in_schema=False)
def read_index():
    if FRONTEND_DIR:
        idx_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(idx_path):
            return FileResponse(idx_path)
    return {"status": "success", "message": "拓竹耗材管理服务端 (Windows SQLite) 服务运行正常"}

# 公网机器人探测过滤
@app.get("/robots.txt", include_in_schema=False)
def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- 4. Pydantic 数据结构 -----------------
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

# ----------------- 5. 原生安全加盐哈希鉴权逻辑 -----------------
def get_password_hash(password: str) -> str:
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return f"{salt}${pwd_hash}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, pwd_hash = hashed_password.split('$')
        check_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
        return check_hash == pwd_hash
    except Exception:
        return False

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

# ----------------- 6. API 业务接口 -----------------
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

# 【新增】客户端输入账号密码一键获取/生成长效 API Key
@app.post("/api/auth/quick-api-key", tags=["账号管理"])
def quick_get_api_key(user_data: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="账号或密码错误")
    
    # 优先返回已有且启用的 API Key
    existing_key = db.query(APIKey).filter(APIKey.user_id == user.id, APIKey.is_active == True).first()
    if existing_key:
        return {"status": "success", "username": user.username, "api_key": existing_key.api_key}
    
    # 无则自动生成一个客户端专属 Key
    raw_key = f"sk_{secrets.token_hex(16)}"
    new_key = APIKey(key_name="ClientAutoGenerated", api_key=raw_key, user_id=user.id)
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    return {"status": "success", "username": user.username, "api_key": new_key.api_key}

# 【新增】API Key 验证与当前用户信息读取
@app.get("/api/ingest/script-user-info", tags=["自动采集接入"])
def get_script_user_info(user: User = Depends(verify_script_api_key)):
    return {
        "status": "success",
        "username": user.username,
        "user_id": user.id
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
            "color_hex": f.color_hex,
            "initial_weight_g": f.initial_weight_g,
            "current_weight_g": f.current_weight_g,
            "price": f.price
        }
        for f in filaments
    ]

@app.post("/api/ingest/script-report-create", response_model=FilamentOut, tags=["自动采集接入"])
def create_filament_for_script(f: FilamentCreate, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filament = Filament(**f.dict(), user_id=user.id)
    db.add(filament)
    db.commit()
    db.refresh(filament)
    return filament

@app.delete("/api/ingest/script-report-delete/{filament_id}", tags=["自动采集接入"])
def delete_filament_for_script(filament_id: int, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filament = db.query(Filament).filter(Filament.id == filament_id, Filament.user_id == user.id).first()
    if not filament:
        raise HTTPException(status_code=404, detail="耗材不存在")
    db.query(UsageRecord).filter(UsageRecord.filament_id == filament_id).delete()
    db.delete(filament)
    db.commit()
    return {"status": "success", "message": "删除成功"}

@app.get("/api/ingest/script-filament-logs/{filament_id}", tags=["自动采集接入"])
def get_filament_logs_for_script(filament_id: int, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filament = db.query(Filament).filter(Filament.id == filament_id, Filament.user_id == user.id).first()
    if not filament:
        raise HTTPException(status_code=404, detail="耗材不存在或无权访问")

    records = db.query(UsageRecord).filter(
        UsageRecord.filament_id == filament_id,
        UsageRecord.user_id == user.id
    ).order_by(UsageRecord.id.desc()).all()
    
    res = []
    for r in records:
        created_time = r.created_at + datetime.timedelta(hours=8) if r.created_at else None
        res.append({
            "id": r.id,
            "task_name": r.task_name,
            "used_weight_g": r.used_weight_g,
            "remaining_weight_g": r.remaining_weight_g,
            "created_at": created_time.strftime("%Y-%m-%d %H:%M:%S") if created_time else ""
        })
    return res

@app.delete("/api/ingest/script-undo-record/{record_id}", tags=["自动采集接入"])
def delete_record_for_script(record_id: int, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    record = db.query(UsageRecord).filter(UsageRecord.id == record_id, UsageRecord.user_id == user.id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在或无权操作")

    filament = db.query(Filament).filter(Filament.id == record.filament_id, Filament.user_id == user.id).first()
    if filament:
        prev_record = db.query(UsageRecord).filter(
            UsageRecord.filament_id == filament.id,
            UsageRecord.user_id == user.id,
            UsageRecord.id < record.id
        ).order_by(UsageRecord.id.desc()).first()

        if prev_record and prev_record.remaining_weight_g is not None:
            filament.current_weight_g = max(0.0, round(prev_record.remaining_weight_g, 2))
        else:
            filament.current_weight_g = round(filament.initial_weight_g, 2)

    db.delete(record)
    db.commit()
    return {"status": "success", "message": "记录已撤销，耗材余量已精准恢复到变动前快照状态"}

@app.post("/api/filaments/{filament_id}/adjust-weight", tags=["耗材台账"])
def adjust_filament_weight(filament_id: int, data: ManualAdjustWeightData, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    
    if filament:
        if refund_weight_g is not None:
            filament.current_weight_g = max(0.0, round(filament.current_weight_g + refund_weight_g, 2))
        else:
            prev_record = db.query(UsageRecord).filter(
                UsageRecord.filament_id == filament.id,
                UsageRecord.user_id == user.id,
                UsageRecord.id < record.id
            ).order_by(UsageRecord.id.desc()).first()

            if prev_record and prev_record.remaining_weight_g is not None:
                filament.current_weight_g = max(0.0, round(prev_record.remaining_weight_g, 2))
            else:
                filament.current_weight_g = round(filament.initial_weight_g, 2)

    db.delete(record)
    db.commit()
    return {"status": "success", "message": "记录已删除，已精确恢复耗材历史数据"}

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
def report_usage_from_script(data: ScriptReportData, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
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

# ----------------- 7. 公网/局域网环境识别与启动引导 -----------------
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_public_ip():
    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode('utf-8').strip()
    except Exception:
        return None

if __name__ == "__main__":
    local_ip = get_local_ip()
    pub_ip = get_public_ip()

    print("=" * 70)
    print("     拓竹 3D 打印耗材资产管理系统 - Windows 独立服务端 v2.2（适配3.0.5以上版本）")
    print("=" * 70)
    print(f"📁 数据库保存路径: {DB_FILE_PATH}")
    print(f"🏠 本机局域网 IP : {local_ip}")
    if pub_ip:
        print(f"🌐 检测到公网 IP : {pub_ip}")
    print("-" * 70)
    print("请选择运行模式：")
    print("  [1] 局域网/公网直连模式 (绑定 0.0.0.0, 推荐 Windows 云服务器/局域网使用)")
    print("  [2] 本地独占安全模式   (绑定 127.0.0.1, 仅供当前单台电脑使用)")
    print("  [3] 自定义端口公网模式 (可指定任意端口如 80, 8080, 18000)")
    print("-" * 70)
    
    choice = input("请输入选项 (1/2/3，默认 1): ").strip()
    
    port = 8000
    host_ip = "0.0.0.0"
    mode_str = "全网卡监听 (0.0.0.0)"

    if choice == "2":
        host_ip = "127.0.0.1"
        mode_str = "仅本机 (Localhost)"
    elif choice == "3":
        host_ip = "0.0.0.0"
        p_str = input("请输入希望监听的端口号 (默认 8000): ").strip()
        if p_str.isdigit():
            port = int(p_str)
        mode_str = f"自定义公网模式 (端口: {port})"

    print(f"\n🚀 服务端启动中... [{mode_str}]")
    print(f"📌 本机浏览器访问 : http://127.0.0.1:{port}")
    print(f"📌 局域网设备访问 : http://{local_ip}:{port}")
    if pub_ip:
        print(f"📌 公网远程访问   : http://{pub_ip}:{port} (请确保云服务器防火墙已放行 {port} 端口)")
    print("=" * 70 + "\n")
    
    uvicorn.run(app, host=host_ip, port=port, proxy_headers=True, forwarded_allow_ips="*")