"""
Feedback model for storing student feedback, ratings, and portal suggestions.
"""

import uuid
from datetime import datetime, timezone
from . import db, GUID


class Feedback(db.Model):
    """Student feedback and experience ratings for the Smart NoDues AI platform."""

    __tablename__ = "feedbacks"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(GUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = db.Column(GUID, db.ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
    application_id = db.Column(GUID, db.ForeignKey("no_dues_applications.id", ondelete="SET NULL"), nullable=True, index=True)

    # Core Experience Ratings
    overall_rating = db.Column(db.Integer, nullable=False, default=5)  # 1 to 5 Stars
    ease_of_use = db.Column(db.String(50), nullable=True)  # 'very_easy', 'easy', 'moderate', 'difficult'
    ai_helpfulness = db.Column(db.String(50), nullable=True)  # 'extremely_helpful', 'good', 'not_used', 'needs_improvement'
    upload_experience = db.Column(db.String(50), nullable=True)  # 'smooth', 'acceptable', 'had_issues'
    nps_score = db.Column(db.Integer, nullable=True, default=10)  # 1 to 10 scale (Net Promoter Score)

    # Feedback comments and suggestions
    comments = db.Column(db.Text, nullable=True)
    sentiment = db.Column(db.String(50), nullable=False, default="positive")  # 'positive', 'neutral', 'constructive'

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    user = db.relationship("User", backref=db.backref("feedbacks", lazy="dynamic"))
    student = db.relationship("Student", backref=db.backref("feedbacks", lazy="dynamic"))
    application = db.relationship("NoDuesApplication", backref=db.backref("feedbacks", lazy="dynamic"))

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "student_id": str(self.student_id) if self.student_id else None,
            "application_id": str(self.application_id) if self.application_id else None,
            "student_name": self.user.full_name if self.user else "Student",
            "student_email": self.user.email if self.user else None,
            "roll_number": self.student.roll_number if self.student else None,
            "course_name": self.student.course_name if self.student else None,
            "branch": self.student.branch if self.student else None,
            "overall_rating": self.overall_rating,
            "ease_of_use": self.ease_of_use,
            "ai_helpfulness": self.ai_helpfulness,
            "upload_experience": self.upload_experience,
            "nps_score": self.nps_score,
            "comments": self.comments,
            "sentiment": self.sentiment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Feedback {self.id} - {self.overall_rating} Stars>"
