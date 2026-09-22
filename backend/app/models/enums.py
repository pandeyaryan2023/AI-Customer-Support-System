from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    ADMIN = "ADMIN"


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class DocumentStatus(StrEnum):
    """Where a knowledge-base document is in processing."""

    PENDING = "PENDING"      # stored, text not extracted yet
    EXTRACTED = "EXTRACTED"  # text extracted and saved
    FAILED = "FAILED"        # extraction failed; the reason is in extraction_error
