"""Phase 6: hand a question the AI could not answer over to a human, through the EXISTING tickets.

    /ai/ask -> NOT_ENOUGH_INFORMATION -> issue_token(): a signed, short-lived note of who
               asked what, and why the AI stopped. Nothing is stored at this point.
    customer clicks "Talk to Human Support" -> POST /tickets with the token
             -> read_token() checks the signature, the expiry and that it belongs to this
                customer -> the normal ticket service creates the ticket with this context.

The context comes from the token, which only the server can sign, so a customer cannot
invent what "the AI said", and cannot use another customer's handoff.
"""
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.models import User
from app.services.rag_service import Answer, AnswerStatus

# Only a token issued for this purpose is accepted here; and because it carries an audience,
# the login code rejects it too. A handoff token can never be used to log in.
AUDIENCE = "ai-handoff"

# Why the AI stopped, in words an agent understands. The internal codes stay internal.
REASONS = {
    "NO_MATCH": "No help article matched the question.",
    "NO_INDEXED_DOCUMENTS": "The knowledge base has no articles yet.",
    "NO_USABLE_CONTEXT": "The matching articles contained no usable text.",
    "MODEL_DECLINED": "Related articles were found, but they do not answer the question.",
    "UNSUPPORTED_NUMBERS": "The AI's draft answer could not be checked against the articles, so it was not shown.",
    "COMPLAINT": "The customer reported a problem rather than asking a question.",
    "HUMAN_REQUESTED": "The customer asked to speak to a person.",
}


class HandoffError(Exception):
    """The handoff cannot be used. The message is safe to show to the customer."""


@dataclass(frozen=True)
class Handoff:
    handoff_id: str
    question: str
    ai_status: str
    reason: str
    sources: list[dict]  # articles the AI looked at: title, part, similarity. Never their text.
    asked_at: str

    def ticket_context(self) -> dict:
        """What is saved on the ticket for the agent."""
        context = asdict(self)
        del context["handoff_id"]  # kept in its own unique column instead
        return context


def issue_token(user: User, question: str, answer: Answer) -> str | None:
    """A handoff token when the AI could not answer; None when it did."""
    if answer.status != AnswerStatus.NOT_ENOUGH_INFORMATION:
        return None
    now = datetime.now(timezone.utc)
    payload = {
        "aud": AUDIENCE,
        "sub": str(user.id),
        "bid": user.business_id,  # the business the question was asked in
        "jti": uuid.uuid4().hex,  # this handoff's id: one ticket at most per handoff
        "iat": now,
        "exp": now + timedelta(minutes=settings.handoff_token_expire_minutes),
        "question": question,
        "ai_status": answer.status.value,
        "reason": REASONS.get(answer.reason, "The AI assistant could not answer."),
        "sources": [asdict(source) for source in answer.considered_sources],
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def read_token(token: str, user: User) -> Handoff:
    """Check a token and return its handoff, or raise HandoffError."""
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
                            audience=AUDIENCE, options={"require": ["exp", "sub", "bid", "jti"]})
    except jwt.ExpiredSignatureError as error:
        raise HandoffError("This AI conversation has expired. Please ask your question again.") from error
    except jwt.PyJWTError as error:
        raise HandoffError("This AI handoff is not valid.") from error
    # Someone else's handoff gets the same answer as a forged one: nothing is revealed about it.
    if claims["sub"] != str(user.id) or claims["bid"] != user.business_id:
        raise HandoffError("This AI handoff is not valid.")
    try:
        return Handoff(
            handoff_id=str(claims["jti"])[:32],
            question=str(claims["question"]),
            ai_status=str(claims["ai_status"]),
            reason=str(claims["reason"]),
            sources=list(claims.get("sources") or []),
            asked_at=datetime.fromtimestamp(claims["iat"], timezone.utc).isoformat(),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise HandoffError("This AI handoff is not valid.") from error
