"""Queue scoring work for a submitted attempt (handlers are registered by the scoring pipeline)."""
from sqlalchemy.orm import Session

from ..jobs import enqueue

SCORE_SEGMENT = "score_segment"


def enqueue_attempt(db: Session, ref) -> None:
    for da in ref.dialogue_attempts:
        for sa in da.segment_attempts:
            enqueue(db, SCORE_SEGMENT, {"segment_attempt_id": str(sa.id)}, max_attempts=4)
