"""Enumerations from docs/DATA_MODEL.md. Stored as VARCHAR (non-native) so adding a value needs no migration of
a Postgres enum type."""
from enum import StrEnum

from sqlalchemy import Enum as SAEnum


def enum_col(enum_cls: type[StrEnum]) -> SAEnum:
    return SAEnum(enum_cls, native_enum=False, length=30, values_callable=lambda e: [m.value for m in e],
                  validate_strings=True)


class UserRole(StrEnum):
    STUDENT = "student"
    ADMIN = "admin"


class SubscriptionStatus(StrEnum):
    ACTIVE = "Active"
    TRIAL = "Trial"
    EXPIRED = "Expired"
    INACTIVE = "Inactive"


class LanguageType(StrEnum):
    ENGLISH = "English"
    LOTE = "LOTE"


class RecordStatus(StrEnum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class ContentStatus(StrEnum):
    DRAFT = "Draft"
    PUBLISHED = "Published"
    ARCHIVED = "Archived"


class Difficulty(StrEnum):
    EASY = "Easy"
    INTERMEDIATE = "Intermediate"
    DIFFICULT = "Difficult"


class AttemptStatus(StrEnum):
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    ABANDONED = "Abandoned"


class ScoringStatus(StrEnum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class AttemptResult(StrEnum):
    PASS = "Pass"
    FAIL = "Fail"


class EvaluationType(StrEnum):
    MEANING_UNIT = "MeaningUnit"
    INSERTION = "Insertion"


class AccuracyResult(StrEnum):
    CORRECT = "Correct"
    OMISSION = "Omission"
    DISTORTION = "Distortion"
    INSERTION = "Insertion"


class LanguageQualityType(StrEnum):
    GRAMMAR = "Grammar"
    UNIDIOMATIC_USAGE = "UnidiomaticUsage"
    PRONUNCIATION = "Pronunciation"
    REGISTER = "Register"
    SENTENCE_STRUCTURE = "SentenceStructure"


class FluencyType(StrEnum):
    PAUSE = "Pause"
    START_DELAY = "StartDelay"
    HESITATION = "Hesitation"
    SELF_CORRECTION = "SelfCorrection"


class DetectionMethod(StrEnum):
    AI = "AI"
    AUDIO_ANALYSIS = "AudioAnalysis"
    MANUAL = "Manual"


class RunStatus(StrEnum):
    PENDING = "Pending"
    SUCCESS = "Success"
    FAILED = "Failed"


class ReviewStatus(StrEnum):
    PENDING = "Pending"
    REVIEWED = "Reviewed"
    APPROVED = "Approved"


class ImportType(StrEnum):
    DIALOGUES = "dialogues"
    COURSES = "courses"


class ImportStatus(StrEnum):
    VALIDATED = "Validated"      # dry run done, report available
    INVALID = "Invalid"          # dry run found errors
    COMMITTING = "Committing"
    PROCESSING_MEDIA = "ProcessingMedia"
    COMPLETED = "Completed"
    FAILED = "Failed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class EmailStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"


class Direction(StrEnum):
    EN_TO_LOTE = "EN>LOTE"
    LOTE_TO_EN = "LOTE>EN"
