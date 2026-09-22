from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints

from app.schemas.user import UserCreate, UserOut

# A business's public code, used in its customer sign-up link: register.html?business=acme
# Trimmed and lower-cased first, then checked: letters, digits and single hyphens.
Slug = Annotated[str, BeforeValidator(lambda v: v.strip().lower() if isinstance(v, str) else v),
                 StringConstraints(min_length=3, max_length=50, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
BusinessName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]


class BusinessBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class BusinessPublic(BaseModel):
    """What anyone may know about a business: enough to show "You are joining Acme Store"."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str


class BusinessSignup(UserCreate):
    """Create a business together with its first admin: the person signing up."""

    business_name: BusinessName
    business_slug: Slug


class BusinessSignupOut(BaseModel):
    business: BusinessBrief
    admin: UserOut


class CustomerRegister(UserCreate):
    # The business whose support portal the customer is joining, by its public code.
    business: Slug


class MeOut(UserOut):
    """The signed-in user, with the business they are working in."""

    business: BusinessBrief
