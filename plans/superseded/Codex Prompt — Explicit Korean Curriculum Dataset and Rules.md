# Korean National Curriculum Constraint — Explicit Specification

> **Status:** Superseded reference only. This is the highest-ranked reference document, but `../HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is supreme and overrides every conflict.

Use the official Korean national curriculum as classification data. Do not infer, invent, rename, or fabricate subjects.

Authoritative curriculum basis:

```text
교육부 고시 제2022-33호
2022 개정 초·중등학교 교육과정

중학교 교육과정: 별책 3
고등학교 교육과정: 별책 4

교과 교육과정:
국어: 별책 5
도덕: 별책 6
사회: 별책 7
수학: 별책 8
과학: 별책 9
실과(기술·가정)/정보: 별책 10
체육: 별책 11
음악: 별책 12
미술: 별책 13
영어: 별책 14
제2외국어: 별책 16
한문: 별책 17
중학교 선택 교과: 별책 18
고등학교 교양 교과: 별책 19
과학 계열 선택: 별책 20
체육 계열 선택: 별책 21
예술 계열 선택: 별책 22
```

Curriculum implementation by school year:

```text
2025-03-01:
- Middle School Grade 1 → 2022 Revised Curriculum
- High School Grade 1 → 2022 Revised Curriculum

2026-03-01:
- Middle School Grade 2 → 2022 Revised Curriculum
- High School Grade 2 → 2022 Revised Curriculum

2027-03-01:
- Middle School Grade 3 → 2022 Revised Curriculum
- High School Grade 3 → 2022 Revised Curriculum
```

Therefore, for the current 2026 product state:

```text
Middle School Grade 1 → 2022 revised curriculum
Middle School Grade 2 → 2022 revised curriculum
Middle School Grade 3 → 2015 revised curriculum

High School Grade 1 → 2022 revised curriculum
High School Grade 2 → 2022 revised curriculum
High School Grade 3 → 2015 revised curriculum
```

The curriculum version must therefore be derived from:

```text
academic_year
+ school_level
+ grade
```

Do not assume every grade currently uses the same curriculum revision.

---

## Folder Hierarchy

The required organization hierarchy is:

```text
학생/
└── {중학교|고등학교}/
    └── {1학년|2학년|3학년}/
        └── {1학기|2학기}/
            └── {교과목}/
                └── {학업|과제|교내활동|교외활동|증빙서류}/
                    └── original_filename.ext
```

The five final templates are fixed:

```text
학업
과제
교내활동
교외활동
증빙서류
```

The classifier must never invent a sixth template.

---

# Middle School — Nationally Defined Subject Space

For the 2022 revised middle-school curriculum, use the following national subject/course groups as the base allowed curriculum space:

```text
국어

사회
- 사회
- 역사

도덕

수학

과학

기술·가정

정보

체육

음악

미술

영어
```

Middle-school national elective curriculum also exists. Support it as a separately represented curriculum category rather than merging invented elective names into the mandatory subject list.

Represent:

```text
MIDDLE_SCHOOL_CORE:
- 국어
- 사회
- 역사
- 도덕
- 수학
- 과학
- 기술·가정
- 정보
- 체육
- 음악
- 미술
- 영어

MIDDLE_SCHOOL_ELECTIVE:
- values loaded only from the official curriculum dataset for the applicable revision
```

Do not assume that every middle school teaches every subject in every semester.

The national curriculum does not provide a universal nationwide mapping such as:

```text
Middle School Grade 2 Semester 1
= fixed identical subject list for every Korean school
```

Therefore:

```text
school_level + grade + semester
```

must NOT be used to fabricate a subject timetable.

Use:

```text
national curriculum allowed subjects
∩
student/school active subject configuration, if available
```

If no school-specific subject configuration exists, use the legally permitted national subject space for that curriculum version rather than guessing semester allocation.

---

# High School — 2022 Revised Curriculum

The 2022 revised high-school curriculum distinguishes common courses and selectable courses.

The nationally defined common-course family includes:

```text
공통국어1
공통국어2

공통수학1
공통수학2

공통영어1
공통영어2

통합사회1
통합사회2

통합과학1
통합과학2

한국사1
한국사2

과학탐구실험1
과학탐구실험2
```

These exact common-course names must be represented as curriculum subjects.

Do not collapse:

```text
공통국어1
공통국어2
```

into an invented single stored course unless the UI intentionally displays a normalized alias while retaining the legal course identity internally.

The same applies to:

```text
공통수학1/2
공통영어1/2
통합사회1/2
통합과학1/2
한국사1/2
과학탐구실험1/2
```

---

# High School Subject Families

Represent the 2022 revised high-school curriculum using official curriculum families.

```text
국어

수학

영어

사회
- 역사
- 지리
- 일반사회
- 윤리

과학
- 물리학
- 화학
- 생명과학
- 지구과학

체육

예술
- 음악
- 미술
- 연극 등 officially defined subjects

기술·가정

정보

제2외국어

한문

교양

과학 계열 선택

체육 계열 선택

예술 계열 선택

전문 교과, when explicitly supported
```

Do not generate course names from these family names.

Actual selectable course names must come from the versioned official curriculum dataset.

---

# High School Common Courses — Explicit Allowed Set

For the 2022 revised curriculum, encode at minimum the following exact common-course identifiers:

```json
{
  "2022_HIGH_COMMON": [
    "공통국어1",
    "공통국어2",
    "공통수학1",
    "공통수학2",
    "공통영어1",
    "공통영어2",
    "통합사회1",
    "통합사회2",
    "통합과학1",
    "통합과학2",
    "한국사1",
    "한국사2",
    "과학탐구실험1",
    "과학탐구실험2"
  ]
}
```

Do not substitute older 2015-revised names where the 2022 curriculum applies.

---

# Semester Rule

Do NOT hard-code:

```text
1학기 → all "*1" courses
2학기 → all "*2" courses
```

unless the student's actual school curriculum confirms that assignment.

A course suffix `1` or `2` is part of the official course name and must not automatically be interpreted as the user's current semester.

School curriculum organization may place courses differently.

Therefore maintain two different concepts:

```text
semester
```

and:

```text
official_course_name
```

They are not interchangeable.

---

# Active Subject Configuration

Curriculum filtering must use this model:

```text
OfficialCurriculum
        ↓
all legally available subjects for curriculum version
        ↓
optional SchoolSubjectProfile
        ↓
subjects actually taken by this student
        ↓
classification candidates
```

Conceptual data:

```json
{
  "academic_year": 2026,
  "school_level": "high_school",
  "grade": 2,
  "semester": 1,
  "curriculum_revision": "2022",
  "official_subjects": [],
  "active_subjects": []
}
```

`official_subjects` comes only from the versioned national curriculum dataset.

`active_subjects`, if configured, is the subset actually taken by the user.

If `active_subjects` is empty:

```text
classifier candidates = official_subjects
```

If `active_subjects` exists:

```text
classifier candidates = active_subjects
```

Never ask Gemma to invent missing subjects.

---

# Curriculum Data Files

Store curriculum data separately from classifier logic.

Required conceptual structure:

```text
curriculum/
├── metadata.json
├── 2015/
│   ├── middle_school.json
│   └── high_school.json
└── 2022/
    ├── middle_school.json
    └── high_school.json
```

Each curriculum file must represent legally defined course names for that revision.

Example schema:

```json
{
  "revision": "2022",
  "school_level": "high_school",
  "subject_families": {},
  "common_courses": [],
  "elective_courses": [],
  "source": {
    "authority": "교육부/국가교육위원회",
    "notification": "교육부 고시 제2022-33호"
  }
}
```

Do not put curriculum course lists inside:

```text
Gemma prompts
classifier source code
UI code
hard-coded conditional chains
```

Load them from the versioned curriculum data layer.

---

# Curriculum Update Rule

The code must treat curriculum data as versioned external domain data.

Do not assume:

```text
2022 curriculum = permanent
```

Classification cache identity must include:

```text
curriculum_revision
curriculum_data_version
school_level
grade
```

A curriculum data revision must invalidate curriculum-dependent classification cache entries.

---

# Classification Constraint

Subject classification flow:

```text
academic year
+ school level
+ grade
        ↓
resolve curriculum revision
        ↓
load legally defined subject/course set
        ↓
apply active student subject subset if configured
        ↓
generate subject embeddings/candidates
        ↓
classify only among those candidates
```

Gemma fallback receives the same candidate list.

Gemma may output only:

```text
one exact candidate from allowed_subjects
```

or:

```text
Needs Review
```

Any other subject returned by Gemma is invalid.

---

# Mandatory Rule: No Curriculum Inference

Do not infer curriculum facts.

Do not generate additional course names from model knowledge.

Do not map courses to grades or semesters unless that mapping is explicitly represented in official curriculum data or the user's SchoolSubjectProfile.

Do not assume all Korean schools have identical semester schedules.

Do not convert subject-family names into specific courses.

Do not silently use the 2022 revision for grades that still use the 2015 revision in the active academic year.

The national curriculum dataset is authoritative for what courses exist.

The student's configured subject profile is authoritative for which of those courses are active for that student.

The classifier only selects among those candidates.
