from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.database import Base, engine
from models import models
from api import auth, sessions, auctions, analytics, dashboard, reports, ws, insights

Base.metadata.create_all(bind=engine)

app = FastAPI(title="صدى التمر API", version="1.0")

# ── CORS: مقيّد بقائمة محددة من core/config.py (CORS_ORIGINS في .env)
#    لا نستخدم allow_origins=["*"] لأن هذا يسمح لأي موقع بقراءة استجابات
#    تحتوي بيانات مزادات حقيقية ورموز مصادقة.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(sessions.router,  prefix="/api/sessions",  tags=["Sessions"])
app.include_router(auctions.router,  prefix="/api/auctions",  tags=["Auctions"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(reports.router,   prefix="/api/reports",   tags=["Reports"])
app.include_router(insights.router,  prefix="/api/insights",  tags=["Insights"])
app.include_router(ws.router,        prefix="/ws",            tags=["WebSocket"])

@app.get("/")
def root():
    return {"status": "صدى التمر يعمل ✅"}
