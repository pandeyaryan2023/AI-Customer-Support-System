"""Create an admin account:  python create_admin.py

Customers register themselves on their business's portal, but admins (and agents) must be
created by someone who already has access. This script is that first step. It asks which
business the admin belongs to, and creates the business if it does not exist yet.
(Data from before multi-tenancy is in the business with code "default".)
"""
import getpass

from pydantic import ValidationError
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import Business, Role
from app.schemas.business import BusinessSignup
from app.schemas.user import UserCreate
from app.services import business_service, user_service


def main() -> None:
    slug = input("Business code (for example acme): ").strip().lower()
    with SessionLocal() as db:
        business = db.scalar(select(Business).where(Business.slug == slug))
        business_name = None if business else input(f"New business '{slug}'. Its name: ")

        full_name = input("Admin full name: ")
        email = input("Admin email: ")
        password = getpass.getpass("Password (min 8 characters): ")
        try:
            if business is None:
                data = BusinessSignup(full_name=full_name, email=email, password=password,
                                      business_name=business_name, business_slug=slug)
            else:
                data = UserCreate(full_name=full_name, email=email, password=password)
        except ValidationError as error:
            print("Invalid input:")
            for problem in error.errors():
                print(f" - {problem['loc'][0]}: {problem['msg']}")
            return

        if business is None:
            business, user = business_service.signup(db, data)
        else:
            user = user_service.create_user(db, data, Role.ADMIN, business.id)
            db.commit()
        print(f"Admin created: {user.email} (id {user.id}) for business '{business.name}' ({business.slug})")


if __name__ == "__main__":
    main()
