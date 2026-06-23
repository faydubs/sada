from core.database import SessionLocal
from core.security import hash_password
from models.models import User, UserRole

db = SessionLocal()
user = User(username='admin', password_hash=hash_password('admin123'), role=UserRole.admin)
db.add(user)
db.commit()
print('✅ تم إنشاء المستخدم!')
db.close()
