from pydantic import BaseModel


class Stats(BaseModel):
    total_tickets: int
    unassigned_tickets: int
    tickets_by_status: dict[str, int]
    tickets_by_priority: dict[str, int]
    users_by_role: dict[str, int]
