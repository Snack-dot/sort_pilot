"""Static subject catalog and onboarding constraints for student sorting."""

from .catalog import (
    DEFAULT_CATALOG_PATH,
    OCCUPATION,
    SUBJECT_CATALOG_VERSION,
    StudentType,
    SubjectCatalog,
    load_subject_catalog,
)
from .profiles import (
    Semester,
    StudentProfile,
    StudentProfileStore,
    default_profile,
)

__all__ = [
    "DEFAULT_CATALOG_PATH",
    "OCCUPATION",
    "SUBJECT_CATALOG_VERSION",
    "Semester",
    "StudentProfile",
    "StudentProfileStore",
    "StudentType",
    "SubjectCatalog",
    "default_profile",
    "load_subject_catalog",
]
