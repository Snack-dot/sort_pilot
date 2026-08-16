# Sort Pilot — Korean Middle/High School Hybrid Educational Classifier

Upgrade the existing Sort Pilot architecture to the following target specification. Use the existing repository context for current modules, safety logic, extraction, preview, move, rollback, Undo, caching, and Gemma integration. Do not redesign unrelated infrastructure.

## Product Domain

Target only Korean middle-school and high-school students.

Onboarding:

```text
학생
├── 중학교
│   ├── 1학년
│   ├── 2학년
│   └── 3학년
└── 고등학교
    ├── 1학년
    ├── 2학년
    └── 3학년
```

Each grade contains:

```text
1학기
2학기
```

The folder hierarchy is:

```text
학생
→ 중학교/고등학교
→ 학년
→ 학기
→ 교과목
→ 고정 템플릿
```

Example:

```text
학생/
└── 고등학교/
    └── 1학년/
        └── 1학기/
            └── 수학/
                ├── 학업/
                ├── 과제/
                ├── 교내활동/
                ├── 교외활동/
                └── 증빙서류/
```

The five final template folders are fixed:

```text
학업
과제
교내활동
교외활동
증빙서류
```

Do not let the classifier invent additional top-level document-purpose folders.

## Korean Curriculum Constraint

Subjects must not be manually invented by the LLM.

For each:

```text
school_level
grade
semester
```

load the actual subject candidates from the real officially defined Korean middle/high-school curriculum represented by the repository's curriculum data.

Use the legally defined Korean curriculum as the source of truth for subject candidates.

The classifier may select only a subject valid for the active:

```text
중학교/고등학교
+ 학년
+ 학기
+ curriculum_version
```

Represent this as versioned curriculum data, conceptually:

```text
CurriculumProfile
- country = KR
- school_level
- grade
- semester
- curriculum_version
- allowed_subjects
```

The curriculum restricts the classification search space. It does not directly classify files.

Final path construction:

```text
school_level/
grade/
semester/
subject/
template/
filename
```

## Required Runtime / Tech Stack

```text
Language:
Python 3.11+

GUI:
PyQt6

Local state:
SQLite
JSON

Numerical operations:
NumPy

Inference runtime:
ONNX Runtime
CPUExecutionProvider
```

No PyTorch.

No TensorFlow.

No cloud classification API.

No large VLM.

All document analysis and classification must execute locally.

## Sentence Embedding Upgrade

Replace Word2Vec/fastText-style semantic classification where applicable with:

```text
Library:
FastEmbed

Model:
intfloat/multilingual-e5-small

Runtime:
ONNX Runtime CPU

Embedding dimension:
384
```

Use FastEmbed to produce semantic vectors from extracted document text.

Use cosine similarity through NumPy to compare document vectors against stored classification profile vectors.

Use embeddings for:

```text
subject semantic classification
document-purpose semantic evidence
personal-example similarity
```

Subject comparison must be restricted to the allowed curriculum subjects for the active school level, grade, and semester.

Return ranked candidates and similarity scores, not only the winner.

## Korean NLP Upgrade

Use:

```text
kiwipiepy
```

for:

```text
Korean morphology
tokenization
POS analysis
keyword extraction
lexical feature extraction
collocation preparation
```

Preserve coherent natural text for E5 sentence embedding. Do not replace E5 input with morphology tokens.

## Lexical / Collocation Engine

Use:

```text
collections.Counter
math
PMI
```

for bigram and trigram collocation analysis.

Use lexical/collocation evidence to distinguish document purpose when subject vocabulary overlaps.

Strong example signals include:

```text
과제:
과제
제출
제출 기한
마감
작성
보고서

교내활동:
학교
학년
반
학번
담임
교내
학생회
동아리
행사
대회

교외활동:
교외
외부
기관
공모전
봉사
캠프
대외활동
체험활동

증빙서류:
증명서
확인서
수료증
상장
인증서
성적표
출석
발급
증빙

학업:
학습
단원
개념
문제
정답
해설
필기
수업
교재
참고자료
```

These are evidence signals, not unconditional single-keyword rules.

## OCR Upgrade

Use:

```text
rapidocr-onnxruntime
```

Use OCR for image-based or non-native-text documents.

Extract:

```text
OCR text
mean confidence
confidence variance
bounding-box geometry
bounding-box variance
layout regularity
text density
region distribution
```

OCR metadata remains structured numeric evidence.

Do not convert OCR statistics into fake text for the embedding model.

Use OCR structural evidence to help distinguish:

```text
clean printed material
annotated printed material
personal handwritten material
```

Do not classify solely from one OCR threshold.

## Vision Upgrade

Use:

```text
onnxruntime
YOLO Nano-class ONNX model
LVIS vocabulary/model
CPUExecutionProvider
```

Use the LVIS-based YOLO model as a lightweight visual feature extractor.

For relevant images, extract:

```text
object labels
object confidence
object positions
spatial co-occurrences
pair:x+y relationships
```

Example:

```text
book
laptop
worksheet
pair:book+laptop
```

Visual information is supporting evidence only.

Do not make YOLO authoritative for subject or folder-template classification.

Do not run YOLO unnecessarily.

Routing:

```text
native text available
→ extract native text
→ no OCR/YOLO unless required

image or image-only content
→ OCR

OCR/text evidence sufficient
→ continue

visual evidence needed
→ YOLO LVIS
```

## Structured Evidence

Do not concatenate all features into one fake sentence and use that as the only classifier input.

Maintain separate structured evidence:

```text
native_text
ocr_text
filename_features
semantic_embedding
Kiwi lexical features
PMI collocations
OCR statistics
layout statistics
YOLO/LVIS visual evidence
curriculum context
personal-example similarity
```

E5 should embed meaningful linguistic text.

Engineered numerical/visual features remain separate classifier inputs.

## Classification Tasks

Perform two independent classifications.

### 1. Subject Classification

Input:

```text
active CurriculumProfile
filename
native/OCR text
E5 vector
lexical subject evidence
personal-example evidence
```

Candidate set:

```text
only subjects legally valid for the active
school level + grade + semester
```

Output:

```text
ranked subject candidates
similarity/scores
winner
confidence
candidate margin
```

### 2. Template Classification

Choose exactly one:

```text
학업
과제
교내활동
교외활동
증빙서류
```

Use:

```text
semantic intent
Kiwi lexical features
PMI collocations
filename evidence
OCR/layout evidence
visual evidence when relevant
personal-example evidence
```

Output:

```text
ranked template candidates
scores
winner
confidence
candidate margin
```

## Primary Local Classifier

The lightweight classifier is the primary decision engine.

It combines:

```text
FastEmbed E5 semantic similarity
+
Kiwi lexical evidence
+
PMI collocations
+
OCR/layout features
+
optional YOLO LVIS visual evidence
+
curriculum constraints
+
personal correction similarity
```

Keep feature weights and confidence policy centralized and configurable.

Preserve per-feature evidence so classification decisions are inspectable.

## Hybrid Decision Policy

```text
Local result clearly confident
→ accept local result
→ do not invoke Gemma

Local result ambiguous
→ invoke Gemma fallback

Insufficient evidence
→ Needs Review

Gemma unresolved
→ Needs Review
```

Confidence must account for both:

```text
top candidate score
top1-top2 candidate separation
```

Do not let Gemma override clearly confident local classification.

## Gemma Fallback

Use the existing local Gemma + llama.cpp/llama-server implementation only as a constrained fallback.

Gemma receives:

```text
school level
grade
semester
curriculum version

allowed curriculum subjects

top local subject candidates
subject scores

five fixed template candidates
template scores

filename
bounded extracted text
lexical evidence
PMI evidence
OCR/layout evidence
visual evidence when available
```

Gemma may return only:

```text
one supplied subject
+
one of:
학업
과제
교내활동
교외활동
증빙서류

or:
Needs Review
```

Gemma must not invent:

```text
new subjects
new templates
new folder roots
arbitrary hierarchy
absolute paths
path traversal
```

Final path generation remains deterministic:

```text
school_level
/ grade
/ semester
/ selected_subject
/ selected_template
/ original_filename
```

## Personalization

When the user changes a proposed destination during preview, store the correction locally as a personal classification example.

Store:

```text
file fingerprint
document embedding
subject
template
original prediction
user-approved prediction
lexical evidence
relevant metadata
model/profile/policy versions
```

For future files:

```text
new document
→ embedding
→ nearest similar corrected examples
→ personal similarity evidence
→ local classifier
```

Do not fine-tune E5.

Do not fine-tune Gemma.

Do not mutate the global/base subject profile from one user correction.

Maintain separate:

```text
CurriculumProfile
SubjectProfile
TemplateProfile
PersonalExample
```

## Final Runtime Flow

```text
Onboarding
↓
중/고 + 학년 + 학기
↓
real Korean curriculum profile
↓
allowed subject candidates
↓
scan Desktop / Downloads
↓
existing safety filters
↓
native extraction
↓
OCR when required
↓
optional YOLO LVIS when required
↓
FastEmbed multilingual-e5-small
↓
Kiwi lexical extraction
↓
PMI collocation evidence
↓
structured feature evidence
↓
Subject Classifier
+
Five-Template Classifier
↓
confidence + top1/top2 margin
↓
confident
    → local result

ambiguous
    → constrained local Gemma fallback

unresolved
    → Needs Review
↓
construct deterministic destination

school/grade/semester/subject/template/file
↓
existing editable preview
↓
user correction if needed
↓
store personal example
↓
existing transactional move
↓
existing rollback / persistent Undo
```

## Required Final Folder Contract

Every normal classified educational file must resolve to this structure:

```text
학생/
└── {중학교|고등학교}/
    └── {1학년|2학년|3학년}/
        └── {1학기|2학기}/
            └── {실제 해당 교육과정의 교과목}/
                └── {학업|과제|교내활동|교외활동|증빙서류}/
                    └── original_filename.ext
```

The subject node is curriculum-defined.

The final template node is always exactly one of the five fixed templates.

The lightweight ONNX classification engine is primary.

Gemma is fallback-only.

All inference remains local.