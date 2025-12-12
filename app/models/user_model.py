from sqlalchemy import Column, String, DateTime, DECIMAL
from sqlalchemy.dialects.mysql import INTEGER
from app.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    uni = Column(String(32), nullable=False)
    student_name = Column(String(120), nullable=False)
    dept_name = Column(String(120))
    email = Column(String(255), nullable=False)
    phone = Column(String(32))
    avatar_url = Column(String(512))
    credibility_score = Column(DECIMAL(4, 2), nullable=False, default=0.00)
    last_seen_at = Column(DateTime)
    google_id = Column(String(255), unique=True, nullable=True)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "uni": self.uni,
            "student_name": self.student_name,
            "dept_name": self.dept_name,
            "email": self.email,
            "phone": self.phone,
            "avatar_url": self.avatar_url,
            "credibility_score": float(self.credibility_score or 0),
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "google_id": self.google_id,
        }
