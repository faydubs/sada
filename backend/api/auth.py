"""
api/auth.py – المصادقة وإنشاء JWT لمشروع صدى التمر
"""

import random
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from agent.voiceprint import create_voiceprint, save_embedding_to_file
from core.config import settings
from core.database import get_db
from core.regions import REGION_NAMES_AR
from core.security import create_access_token, hash_password, verify_password
from models.models import User, UserRole
from schemas.schemas import AdminRegister, LoginRequest, ProfileUpdate, Token, UserCreate, UserResponse
from crud.crud import get_user_by_username

# مجلد تخزين ملفات البصمة الصوتية (.npy) — مستثنى من git في .gitignore
VOICEPRINT_DIR = Path("voiceprints")
ALLOWED_VOICEPRINT_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".mp4"}

router = APIRouter()

# ✅ HTTPBearer بدل OAuth2PasswordBearer – يعطي زر Authorize بسيط
#    يقبل لصق التوكن مباشرة بدل نموذج username/password المعقد
bearer_scheme = HTTPBearer()


# ---------------------------------------------------------------------------
# Dependencies
# (موضوعة قبل الـ Endpoints لأن /admin/create-user يحتاج get_current_admin
#  وقت تعريف الـ route نفسه — Depends() يُحلَّل عند تحميل الموديول)
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency تُستخدم في أي endpoint يحتاج مستخدماً مسجلاً.
    تقرأ التوكن من header: Authorization: Bearer <token>

    مثال:
        @router.get("/me")
        def me(user: User = Depends(get_current_user)):
            return {"username": user.username}
    """
    token = credentials.credentials

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="التوكن غير صالح أو منتهي الصلاحية",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_error

    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """
    Dependency للمسارات المخصصة للـ admin فقط.

    مثال:
        @router.delete("/users/{id}")
        def delete_user(user: User = Depends(get_current_admin)):
            ...
    """
    if user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذا المسار للمديرين فقط",
        )
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """
    تسجيل ذاتي للدلّال من التطبيق (يطابق مسار الدلّال بالعرض: "إنشاء حساب الدلّال").

    ⚠️ أمان مهم: نتجاهل أي قيمة لـ role يرسلها العميل ونفرض "dallal" دائماً —
    قبل هذا التعديل كان أي مستخدم يقدر يسجّل نفسه admin مباشرة عبر body الطلب.
    لإنشاء admin إضافي استخدم /admin/create-user (يتطلب admin حالي).
    """
    existing = get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="اسم المستخدم موجود بالفعل",
        )

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=UserRole.dallal,
        # تعيين منطقة تلقائياً للدلّال الجديد (خيار "seed/demo" — لا تُطلب في شاشة التسجيل)
        region=random.choice(REGION_NAMES_AR),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/register-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_admin(data: AdminRegister, db: Session = Depends(get_db)):
    """
    تسجيل ذاتي لحساب مسؤول من شاشة التسجيل — محمي برمز المسؤول.

    بخلاف /register (الذي يفرض dallal دائماً)، يسمح هذا المسار بإنشاء admin
    لكن فقط لمن يملك ADMIN_SIGNUP_CODE الصحيح، حتى لا يستطيع أي زائر ترقية نفسه.
    إذا كان ADMIN_SIGNUP_CODE فارغاً في الإعدادات، يكون تسجيل المسؤول معطّلاً.
    """
    if not settings.ADMIN_SIGNUP_CODE or data.code != settings.ADMIN_SIGNUP_CODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="رمز المسؤول غير صحيح",
        )

    existing = get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="اسم المستخدم موجود بالفعل",
        )

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=UserRole.admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/admin/create-user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """
    إنشاء مستخدم بأي صلاحية (بما فيها admin) — لـ admin فقط.
    هذا هو المسار الوحيد المسموح فيه بتحديد role من الطلب.
    """
    existing = get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="اسم المستخدم موجود بالفعل",
        )

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/voiceprint", status_code=status.HTTP_201_CREATED)
async def register_voiceprint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    سجّل بصمة الدلال الصوتية من تسجيل صوتي (10-30 ثانية كافية، صوت واضح بدون ضجيج).

    تُحفظ البصمة محلياً كملف .npy ويُربط مسارها بحساب المستخدم الحالي.
    تُستخدم لاحقاً تلقائياً في POST /api/auctions/process-audio للتحقق
    من أن صوت المزاد يطابق صوت الدلال المسجَّل (agent/voiceprint.py).

    ملاحظة: إذا SpeechBrain غير مثبّت في البيئة، يرجع 503 بدل فشل غامض.
    """
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_VOICEPRINT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"صيغة غير مدعومة: {suffix}. المسموح: {', '.join(ALLOWED_VOICEPRINT_EXTENSIONS)}",
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        embedding = create_voiceprint(tmp_path)
        if embedding is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="تعذّر استخراج البصمة الصوتية (SpeechBrain غير متاح أو تعذّر تحليل الصوت)",
            )

        VOICEPRINT_DIR.mkdir(parents=True, exist_ok=True)
        npy_path = str(VOICEPRINT_DIR / f"user_{current_user.id}.npy")
        save_embedding_to_file(embedding, npy_path)

        current_user.voiceprint_path = npy_path
        db.commit()

        return {"status": "تم تسجيل البصمة الصوتية بنجاح", "voiceprint_registered": True}
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()


@router.get("/voiceprint/status")
def voiceprint_status(current_user: User = Depends(get_current_user)):
    """تحقق سريع: هل عند المستخدم الحالي بصمة صوتية مسجَّلة؟"""
    return {"voiceprint_registered": bool(current_user.voiceprint_path)}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """بيانات المستخدم الحالي — لشاشة الحساب."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role.value,
        "region": getattr(current_user, "region", None),
        "voiceprint_registered": bool(current_user.voiceprint_path),
    }


@router.patch("/me")
def update_me(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    تعديل الدلّال لبياناته الشخصية (اسم المستخدم و/أو كلمة المرور).
    يُصدر توكناً جديداً لأن اسم المستخدم قد يتغيّر (مضمّن في الـ JWT).
    """
    if data.username and data.username.strip() and data.username.strip() != current_user.username:
        new_username = data.username.strip()
        if get_user_by_username(db, new_username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="اسم المستخدم موجود بالفعل")
        current_user.username = new_username

    if data.password:
        if len(data.password) < 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="كلمة المرور 6 أحرف على الأقل")
        current_user.password_hash = hash_password(data.password)

    db.commit()
    db.refresh(current_user)

    token = create_access_token({
        "sub": str(current_user.id),
        "username": current_user.username,
        "role": current_user.role.value,
    })
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role.value,
        "region": getattr(current_user, "region", None),
        "access_token": token,
    }


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """
    قائمة بكل المستخدمين — لـ admin فقط (تُستخدم في لوحة المسؤول).
    تُرجع الدور وحالة البصمة الصوتية لكل مستخدم.
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role.value,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "voiceprint_registered": bool(u.voiceprint_path),
        }
        for u in users
    ]


@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    استقبل username + password وأرجع JWT إذا كانت البيانات صحيحة.
    """
    user = get_user_by_username(db, data.username)

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة المرور غير صحيحة",
        )

    token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
    })

    return Token(access_token=token)
