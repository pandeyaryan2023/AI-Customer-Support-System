"""Step 1 of the AI layer: prove that complaint classification works, in isolation.

This script is deliberately standalone. It does NOT touch the database, the API,
the ticket flow or the existing tests. Its only job is to answer four questions:

  1. Is the Anthropic API key readable from backend/.env?
  2. Does the anthropic SDK work?
  3. Does structured output come back as valid, typed data?
  4. Does the model pick a category from OUR list instead of inventing one?

Run it with:   python scripts/classify_complaint.py
"""
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env  (this file is backend/scripts/classify_complaint.py)
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

# The model is told to answer UNKNOWN rather than guess, because a wrong category
# sends the complaint to the wrong team, which is worse than no category at all.
UNKNOWN = "UNKNOWN"

# Hard-coded for this step. In the real feature these come from the categories
# table, because an admin can add or deactivate a category at any time.
CATEGORIES = ["Billing", "Delivery", "Technical Issue", "Account"]

# One hard-coded complaint, written the way a real customer would write it:
# it never uses the word "billing", so the model has to understand the meaning.
COMPLAINT_TITLE = "Charged twice for the same order"
COMPLAINT_DESCRIPTION = (
    "My account shows two payments of Rs 2,499 for order #55231 placed on 14 September. "
    "I only ordered once. Please return the extra amount."
)


class Settings(BaseSettings):
    """Reads ANTHROPIC_API_KEY from backend/.env, the same way the app reads its own settings."""

    anthropic_api_key: str = ""

    # extra="ignore" so the other keys in .env (DATABASE_URL, JWT_SECRET_KEY) are skipped.
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")


class Classification(BaseModel):
    """The exact shape we demand back from the model.

    Without this the model would reply in prose ("this looks like a billing issue,
    though..."), which cannot be stored in a database column. With it, the API
    guarantees we receive these three fields and nothing else.
    """

    category: str = Field(description=f"One of: {', '.join(CATEGORIES)}, or {UNKNOWN} if unclear")
    confidence: Literal["high", "medium", "low"]
    reason: str = Field(description="One short sentence explaining the choice")


PROMPT = f"""You are classifying a customer complaint for a support system.

Choose exactly one category from this list:
{chr(10).join('- ' + c for c in CATEGORIES)}

If the complaint does not clearly fit any of them, answer {UNKNOWN}.
Do not invent a category that is not in the list.

Complaint title: {COMPLAINT_TITLE}
Complaint description: {COMPLAINT_DESCRIPTION}"""


def main() -> int:
    settings = Settings()

    if not settings.anthropic_api_key:
        print("ERROR: no API key found.\n")
        print(f"Add this line to {ENV_FILE} and run again:\n")
        print("    ANTHROPIC_API_KEY=sk-ant-...your key...\n")
        print("Get a key from https://console.anthropic.com (Settings -> API keys).")
        print("The .env file is already in .gitignore, so the key will not reach GitHub.")
        return 1

    try:
        import anthropic
    except ImportError:
        print("ERROR: the anthropic package is not installed.\n")
        print("    pip install anthropic")
        return 1

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    print("Sending the complaint to Claude...\n")
    try:
        response = client.messages.parse(
            model="claude-opus-5",
            max_tokens=2048,
            messages=[{"role": "user", "content": PROMPT}],
            output_format=Classification,
        )
    except anthropic.AuthenticationError:
        print("ERROR: the API key was rejected (401).")
        print("Check that ANTHROPIC_API_KEY in .env is correct and has not been revoked.")
        return 1
    except anthropic.RateLimitError:
        print("ERROR: rate limited (429). Wait a moment and run again.")
        return 1
    except anthropic.APIStatusError as error:
        print(f"ERROR: the API returned {error.status_code} ({error.type}).")
        if error.status_code == 400 and "credit" in str(error).lower():
            print("This usually means the account has no credit. Add credit in the console.")
        return 1
    except anthropic.APIConnectionError:
        print("ERROR: could not reach the Anthropic API. Check your internet connection.")
        return 1

    result = response.parsed_output

    # The API guarantees the SHAPE of the reply. It does not guarantee that the
    # category actually exists in our system, so we check that ourselves.
    known = result.category in CATEGORIES or result.category == UNKNOWN

    print("--- AI classification result ---")
    print(f"Category:   {result.category}")
    print(f"Confidence: {result.confidence}")
    print(f"Reason:     {result.reason}")
    print()
    print(f"Category is one we recognise: {'yes' if known else 'NO - would be rejected'}")
    print(f"Tokens used: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
