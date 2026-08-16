"""Versioned curriculum constraints for the student-focused classifier."""

from .profiles import (
    CURRICULUM_VERSION,
    CurriculumProfile,
    CurriculumProfileStore,
    SchoolLevel,
    Semester,
    default_profile,
)

__all__ = [
    "CURRICULUM_VERSION",
    "CurriculumProfile",
    "CurriculumProfileStore",
    "SchoolLevel",
    "Semester",
    "default_profile",
]
