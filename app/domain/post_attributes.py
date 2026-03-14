from dataclasses import dataclass

from app.enums.duration_type import DurationType
from app.enums.work_type import WorkType


@dataclass
class PostAttributes:
    duration: DurationType
    work_type: WorkType

    payment: str | None
    address: str | None