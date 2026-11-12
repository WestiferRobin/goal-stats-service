"""User accounts prepared for future scenario ownership."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Identity, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        # Prevents two users from sharing the same email.
        UniqueConstraint("email", name="unique_user_email"),

        # Prevents the email from being empty. checks for atleast one character
        CheckConstraint(
            "length(trim(email)) > 0",
            name="email_nonblank",
        ),
    )

    #column 1 user ID - to identify each user this is the primary Key
    user_id: Mapped[int] = mapped_column( Identity(), primary_key=True,)

    # column 2 email - nullable=False: every user must have an email.
    email: Mapped[str] = mapped_column( String(254), nullable=False,)

     #column 3 created at - date of account creation
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )