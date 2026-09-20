"""Create the first admin account:  python create_admin.py

Customers can register themselves, but admins (and agents) must be created by someone
who already has access. This script is that first step.
"""
import getpass

from pydantic import ValidationError

from app.database.session import SessionLocal
from app.models import Role
from app.schemas.user import UserCreate
from app.services import user_service


def main() -> None:
    full_name = input("Full name: ")
    email = input("Email: ")
    password = getpass.getpass("Password (min 8 characters): ")

    try:
        data = UserCreate(full_name=full_name, email=email, password=password)
    except ValidationError as error:
        print("Invalid input:")
        for problem in error.errors():
            print(f" - {problem['loc'][0]}: {problem['msg']}")
        return

    with SessionLocal() as db:
        user = user_service.create_user(db, data, Role.ADMIN)
        db.commit()
        print(f"Admin created: {user.email} (id {user.id})")


if __name__ == "__main__":
    main()
