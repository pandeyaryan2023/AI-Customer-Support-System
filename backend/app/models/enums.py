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


class IndexStatus(StrEnum):
    """Whether a document's text has been chunked and embedded, ready for search.

    Rule: a document has chunks if and only if it is INDEXED.
    """

    NOT_INDEXED = "NOT_INDEXED"  # no text yet, or not processed yet
    INDEXED = "INDEXED"          # chunks and embeddings stored
    FAILED = "FAILED"            # chunking or embedding failed; the reason is in index_error
