"""Allowlisted local text extraction. No enrollment, sections or times are inferred."""

import re

LABELS = {
    "academic_year": (
        r"Academic\s+Year(?:\s*/\s*(?:Semester|Term))?\s*[:\-]?\s*"
        r"(\d{4}\s*[-–/]\s*\d{4})"
    ),
    "student_identifier": (
        r"\bStudent\s*(?:ID\b|Number\b|No\b\.?)\s*[:#\-]?\s*"
        r"([A-Za-z0-9][A-Za-z0-9-]{0,127})(?![A-Za-z0-9-])"
    ),
    "program": (
        r"\bProgram\b\s*[:\-]?\s*(.+?)(?=\s{2,}|"
        r"\s+(?:Form|Student|Year|Name|Tuition|Fees?|Assessed|Payment|Signature|"
        r"Address|Birthday|Sex|Email|Contact|Nationality)\b|"
        r"\s+[A-Za-z][A-Za-z /.-]{0,35}:|$)"
    ),
    "year_level": r"Year\s*Level\s*[:\-]?\s*(\d{1,2})(?:st|nd|rd|th)?",
}


def normalized_code(value):
    # Preserve punctuation; no code aliases or academic equivalencies are guessed.
    value = re.sub(r"\s+", "", value.strip())
    return value.upper() if value.isascii() else value


def field(value, *, page, line, label):
    return {
        "value": value,
        "confidence": None,
        "review_required": True,
        "evidence": {
            "page": page,
            "line": line,
            "label": label,
            "excerpt": f"{label}: {value}"[:300],
        },
    }


def parse_pages(pages, method):
    fields, courses, warnings, seen = {}, [], [], set()
    for page_number, page_text in enumerate(pages, 1):
        in_courses = False
        lines = page_text.splitlines()
        for line_number, line in enumerate(lines, 1):
            for name, pattern in LABELS.items():
                match = re.search(pattern, line, re.I)
                if match and name not in fields:
                    value = match[1].strip()
                    if name == "program" and len(value) > 160:
                        continue
                    if name == "academic_year":
                        value = re.sub(r"\s*[-–/]\s*", "-", value)
                    if name == "year_level":
                        value = int(value)
                        if not 1 <= value <= 20:
                            continue
                    fields[name] = field(value, page=page_number, line=line_number, label=name)
            if "semester" not in fields:
                semester = re.search(r"\b(first|second|1st|2nd)\s*(?:semester|sem\b)", line, re.I)
                if not semester:
                    semester = re.search(
                        r"Semester\s*[:\-]?\s*(first|second|1st|2nd|1|2)\b", line, re.I
                    )
                if semester:
                    value = "first" if semester[1].lower() in {"first", "1st", "1"} else "second"
                    fields["semester"] = field(
                        value, page=page_number, line=line_number, label="semester"
                    )
            if all(
                re.search(r"\b" + label + r"\b", line, re.I)
                for label in ("Code", "Description", "Section")
            ):
                in_courses = True
                continue
            if not in_courses or not line.strip():
                continue
            if re.match(
                r"\s*(?:Total|Assessment|Assessed|Tuition|Payment|Signature)\b", line, re.I
            ):
                in_courses = False
                continue
            cells = re.split(r"\s{2,}|\t+|\s*\|\s*", line.strip())
            if len(cells) < 3:
                # OCR may provide a single spaced line: only an explicit course
                # token + description + section + hours/units tail is accepted.
                match = re.fullmatch(
                    r"([A-Za-z][A-Za-z0-9_-]{1,39})\s+(.+?)\s+"
                    r"([A-Za-z0-9_-]+)(?:\s+\d+(?:\.\d+)?){3,8}",
                    line.strip(),
                )
                if match:
                    cells = list(match.groups())
            if len(cells) < 3:
                continue
            code, description, section = cells[:3]
            if (
                not re.fullmatch(r"[A-Za-z][A-Za-z0-9 _-]{1,39}", code)
                or not re.search(r"[A-Za-z]", description)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,79}", section)
            ):
                continue
            key = (code, section)
            if key in seen:
                continue
            seen.add(key)
            courses.append(
                {
                    name: field(value, page=page_number, line=line_number, label=name)
                    for name, value in {
                        "code": code,
                        "description": description[:240],
                        "section": section,
                    }.items()
                }
            )
            if len(courses) > 60:
                raise ValueError("course_limit")
    if any(c["section"]["value"].isdigit() for c in courses):
        warnings.append(
            "Numeric enrollment sections require university mapping; no named section was inferred."
        )
    if not courses:
        warnings.append(
            "No reliable course rows were found. Enter your courses in the review form."
        )
    missing = [
        name for name in ("academic_year", "semester", "student_identifier") if name not in fields
    ]
    if missing:
        warnings.append("Some academic fields need manual entry.")
    return {
        "method": method,
        "fields": fields,
        "courses": courses,
        "warnings": warnings,
        "status": "needs-review",
        "confidence_available": False,
    }
