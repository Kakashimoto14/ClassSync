"""Owner-authorized defense defaults for the seven CdM degree programs beyond BSIT.

Approved 27 November 2026 (docs/autonomy/APPROVALS.md, Phase B / Slice 4). These records reuse
the BSIT dataset's `REFERENCE` provenance. They are administrator-editable defaults, not
Registrar- or Facilities-verified data. TCP has no prospectus in the repository, so it keeps its
catalog program row only and gets no invented subjects or sections.

Everything is deterministic: identifiers are UUIDv5 values and every choice uses sorted input,
so a rebuild produces identical records.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from classync_contracts.academic import (
    AcademicFaculty,
    AcademicOffering,
    AcademicProgram,
    AcademicSection,
    AcademicSubject,
)
from classync_contracts.curriculum import PROGRAMS
from classync_contracts.scheduling import Enrollment, Window

ROOT = Path(__file__).resolve().parents[1]
CATALOGS = ROOT / "packages/api-contracts/classync_contracts/catalogs"
# Curriculum program names in seed order; BSIT is seeded by `build_academic_records`.
PROGRAM_ORDER = (
    "BSCPE", "BSED SCIENCE", "BEED GENERALIST", "BECED", "BTLED ICT", "BSBA HRM", "BS ENTREP",
)
COHORTS = {1: "2026", 2: "2025", 3: "2024", 4: "2023"}
# Home lecture-room clusters (building, floor) keep a program's classes close together and make
# programs compete for the same rooms. ICS stays in PRRC; ITE and IBE use the New Building.
CLUSTERS = {
    "BSCPE": [("PRRC", "Floor 2")],
    "BSED SCIENCE": [("PRRC", "Floor 1"), ("PRRC", "Floor 3")],
    "BEED GENERALIST": [("New Building", "Floor 1")],
    "BECED": [("New Building", "Floor 2")],
    "BTLED ICT": [("New Building", "Floor 3")],
    "BSBA HRM": [("New Building", "Floor 1"), ("New Building", "Floor 2")],
    "BS ENTREP": [("New Building", "Floor 3"), ("New Building", "Floor 2")],
}
ROOMS_PER_OFFERING = 4
POPULATION = 12
PE = re.compile(
    r"physical activit|path ?fit|pahfit|physical education|outdoor and adventure"
    r"|movement compet|rhythmic|\bdance\b|\bsports?\b"
)
NSTP = re.compile(r"\bnstp\b|national service training|\bcwts\b|\brotc\b")
FULL_WEEK = [Window(day=d, start=420, end=1260) for d in range(6)]
# Owner-approved part-time pattern: weekday evenings plus Saturday daytime.
PART_TIME = [Window(day=d, start=1020, end=1260) for d in (0, 2, 4)] + [
    Window(day=5, start=420, end=1020)
]
FULL_TIME_CAP, PART_TIME_CAP = 1440, 600
LOAD_SHARE = 0.75  # no faculty member is planned above 75% of the weekly cap
CONTINUOUS = 240
FIRST_NAMES = ["Aira", "Miguel", "Janelle", "Joshua", "Kyra", "Nathan", "Angel", "Gabriel",
               "Sofia", "Liam", "Trisha", "Ethan"]
SURNAMES = ["Dela Cruz", "Santos", "Reyes", "Garcia", "Mendoza", "Bautista", "Villanueva",
            "Ramos", "Flores", "Navarro", "Aquino", "Castro"]
FACULTY_NAMES = [
    "Rosario Lim", "Antonio Pascual", "Lourdes Tan", "Eduardo Mercado", "Carmela Ocampo",
    "Victor Salazar", "Imelda Domingo", "Rogelio Valdez", "Felicidad Corpuz", "Arturo Gonzales",
    "Marites Fernandez", "Benjamin Soriano", "Josefina Manalo", "Ricardo Panganiban",
    "Estela Rivera", "Fernando Castillo", "Leonora Aguilar", "Alfredo Miranda", "Corazon Vergara",
    "Rodrigo Bernardo", "Erlinda Javier", "Manuel Torres", "Aurora Dizon", "Gregorio Robles",
    "Milagros Esguerra", "Renato Padilla", "Natividad Sison", "Ernesto Lagman", "Remedios Cabral",
    "Danilo Francisco", "Purita Santiago", "Leandro Ignacio", "Gloria Pineda", "Romeo Velasco",
    "Rebecca Agustin", "Wilfredo Samson", "Editha Carreon", "Herminio Bautista", "Dolores Medina",
    "Teodoro Alcantara", "Perla Gatchalian", "Severino Ramos", "Amparo Lacson", "Isidro Belmonte",
    "Rosalinda Quiambao", "Crisanto Abad", "Zenaida Ferrer", "Bonifacio Luna", "Clarita Ventura",
    "Honorio Galang", "Evangeline Mallari", "Feliciano Tolentino",
]
PLANNING_MINUTES = 1000  # sizing slack below the 75% share (1080) so greedy packing never fails


def classify(title: str, lab_hours: int, program: str):
    """(required_room_type, activity_type) for one course; owner-approved mapping."""
    lowered = title.lower()
    if NSTP.search(lowered):
        # NSTP field activity: both athletic spaces (Court, Oval) allow "sports".
        return "athletic_space", "sports"
    if PE.search(lowered):
        return "athletic_space", "pahfit"
    if lab_hours and program in {"BSCPE", "BTLED ICT"}:
        return "computer_lab", "computer_lab_instruction"
    if lab_hours and program == "BSED SCIENCE":
        return "science_lab", "bse_science_instruction"
    # BEEd, BECEd and BSE lab hours stay in lecture rooms: the catalog has no matching lab.
    return "lecture_classroom", "academic_instruction"


def _hours(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _versions(catalog, program):
    """One curriculum version per year level; duplicates resolve to the latest printed AY."""
    chosen = {}
    for year, cohort in COHORTS.items():
        candidates = [
            v for v in catalog["versions"]
            if v["program"] == program and v["entry_cohort"] == cohort
        ]
        if candidates:
            chosen[year] = max(candidates, key=lambda v: (v["printed_curriculum_ay"], v["id"]))
    return chosen


def _title_key(title: str) -> str:
    return re.sub(r"\W+", " ", title.lower()).strip()


def build_program_records(period_id, rooms, stable_uuid, reference):
    """Programs, subjects, sections, faculty and offerings for the seven other degree programs.

    Returns (records, students). Records are ordered so references precede their users.
    """
    catalog = json.loads((CATALOGS / "curriculum-review.json").read_text(encoding="utf-8"))
    programs = {p["id"]: p for p in json.loads((CATALOGS / "programs.json").read_text("utf-8"))}
    courses = defaultdict(list)
    for course in catalog["courses"]:
        courses[course["curriculum_version_id"]].append(course)

    program_records, subjects, sections, offerings_plan = [], [], [], []
    for name in PROGRAM_ORDER:
        program_id = PROGRAMS[name]
        info = programs[program_id]
        program_records.append(AcademicProgram(
            id=program_id, kind="programs", acronym=info["acronym"], name=info["name"],
            institute=info["institute"], aliases=info.get("aliases", []),
            section_policy="degree", allowed_year_levels=[1, 2, 3, 4],
        ))
        for year, version in sorted(_versions(catalog, name).items()):
            section = AcademicSection(
                id=stable_uuid("section", f"{info['acronym']}-{year}A"),
                kind="sections", period_id=period_id, program_id=program_id, year_level=year,
                section_letter="A", entry_cohort_year=2027 - year,
                curriculum_version_id=version["id"], cohort_assignment_verified=True,
                identity_verified=True, population=POPULATION, population_verified=True,
                capacity=36 + year, verification_reference=reference,
            )
            sections.append(section)
            first = sorted(
                (c for c in courses[version["id"]]
                 if c["year_level"] == str(year) and c["semester"] == "1"),
                key=lambda c: (int(c.get("source_row") or 0), c["id"]),
            )
            for course in first:
                lec, lab = _hours(course["lec_hours_printed"]), _hours(course["lab_hours_printed"])
                weekly = max(30, (lec + lab) * 60)
                pattern = [weekly] if weekly <= CONTINUOUS else [weekly // 2, weekly - weekly // 2]
                # The code catches titles the source misspells ("Movement Compentency").
                room_type, activity = classify(
                    f"{course['subject_code']} {course['subject_title']}", lab, name
                )
                subject = AcademicSubject(
                    id=stable_uuid("subject", f"{version['id']}:{course['id']}"),
                    kind="subjects", code=course["subject_code"], name=course["subject_title"],
                    curriculum_version_id=version["id"], curriculum_course_id=course["id"],
                    curriculum_review_verified=True, curriculum_review_reference=reference,
                    contact_minutes_verified=True, contact_minutes_reference=reference,
                    year_level=year, semester="first", provenance="administrator-entered",
                    program_ids=[program_id], required_weekly_minutes=weekly,
                    patterns=[{
                        "id": stable_uuid("pattern", f"{version['id']}:{course['id']}"),
                        "durations": pattern, "distinct_days": True,
                    }],
                    required_room_type=room_type, lec_hours=lec, lab_hours=lab,
                    units=_hours(course["units_printed"]),
                )
                subjects.append(subject)
                offerings_plan.append((name, section, subject, activity))

    # Courses taught in three or more programs form the shared (GenEd) pool.
    spread = defaultdict(set)
    for name, _, subject, _ in offerings_plan:
        spread[_title_key(subject.name)].add(name)
    def pool_of(name, subject):
        if subject.required_room_type == "athletic_space":
            return "pe"
        return "gened" if len(spread[_title_key(subject.name)]) >= 3 else name

    demand = defaultdict(int)
    for name, _, subject, _ in offerings_plan:
        demand[pool_of(name, subject)] += subject.required_weekly_minutes
    # Each pool: part-time members (two for the large GenEd pool, else one) plus enough
    # full-time members to keep everyone at or under 75% of their weekly cap.
    faculty_specs = []  # (key, display, pool, part_time)
    names = iter(FACULTY_NAMES)
    labels = {"gened": ("GenEd", "GenEd"), "pe": ("PE", "PE/NSTP")}
    for pool in ("gened", "pe", *PROGRAM_ORDER):
        prefix, title = labels.get(pool) or (programs[PROGRAMS[pool]]["acronym"],) * 2
        part_time = 2 if pool == "gened" else 1
        covered = part_time * PART_TIME_CAP * LOAD_SHARE
        full_time = max(1, -(-int(demand[pool] - covered) // PLANNING_MINUTES))
        for index in range(full_time + part_time):
            faculty_specs.append((f"{prefix}-{index + 1:02}", f"{next(names)} · {title}", pool,
                                  index >= full_time))

    members = defaultdict(list)
    for key, display, pool, part_time in faculty_specs:
        members[pool].append((key, display, part_time))
    load = defaultdict(int)
    eligible = defaultdict(set)
    assignment = {}
    for name, section, subject, _ in offerings_plan:
        pool = pool_of(name, subject)
        minutes = subject.required_weekly_minutes
        options = []
        for key, _, part_time in members[pool]:
            cap = (PART_TIME_CAP if part_time else FULL_TIME_CAP) * LOAD_SHARE
            # Part-time windows are evenings and Saturday: sessions must fit 4-hour blocks.
            fits = not part_time or max(subject.patterns[0].durations) <= 210
            if fits and load[key] + minutes <= cap:
                options.append((load[key] / cap, key))
        if not options:
            raise ValueError(f"No {pool} faculty capacity left for {subject.code}")
        chosen = min(options)[1]
        load[chosen] += minutes
        assignment[(section.id, subject.id)] = chosen
        for key, _, _ in members[pool]:
            eligible[key].add(subject.id)

    faculty = []
    for key, display, _, part_time in faculty_specs:
        faculty.append(AcademicFaculty(
            id=stable_uuid("faculty", key), name=display,
            subject_ids=sorted(eligible[key]),
            availability=PART_TIME if part_time else FULL_WEEK,
            max_weekly_minutes=PART_TIME_CAP if part_time else FULL_TIME_CAP,
            max_daily_minutes=480, max_continuous_minutes=CONTINUOUS,
            weekly_unit_cap=12 if part_time else 21,
            eligibility_verified=True, availability_verified=True, workload_verified=True,
            verification_reference=reference,
        ))

    by_type = defaultdict(list)
    for room in rooms:
        by_type[room.room_type].append(room)
    offerings = []
    for name, section, subject, activity in offerings_plan:
        if subject.required_room_type == "lecture_classroom":
            cluster = [
                r for place in CLUSTERS[name] for r in by_type["lecture_classroom"]
                if (r.building, r.floor) == place
            ]
            start = (section.year_level - 1) % max(1, len(cluster))
            ordered = cluster[start:] + cluster[:start]
            room_ids = [r.id for r in ordered[:ROOMS_PER_OFFERING]]
        else:
            room_ids = [r.id for r in by_type[subject.required_room_type]
                        if r.allowed_program_ids is None
                        or PROGRAMS[name] in r.allowed_program_ids]
        offerings.append(AcademicOffering(
            id=stable_uuid("offering", f"{subject.id}:{section.id}"),
            subject_id=subject.id, section_id=section.id, activity_type=activity,
            teacher_ids=[stable_uuid("faculty", assignment[(section.id, subject.id)])],
            room_ids=room_ids, required_room_type=subject.required_room_type,
            minimum_capacity=section.population, term_offering_verified=True,
            verification_reference=reference,
        ))

    by_section = defaultdict(list)
    for offering in offerings:
        by_section[offering.section_id].append(offering.id)
    students = []
    for program_index, name in enumerate(PROGRAM_ORDER):
        for section in (s for s in sections if s.program_id == PROGRAMS[name]):
            prefix = str(section.entry_cohort_year)[-2:]
            for n in range(POPULATION):
                number = 201 + program_index * POPULATION + n
                student_id = f"{prefix}-{number:05}"
                students.append({
                    "id": student_id,
                    "person_id": stable_uuid("student-person", student_id),
                    "display_name": f"{FIRST_NAMES[n]} "
                    f"{SURNAMES[(n + section.year_level + program_index) % len(SURNAMES)]}",
                    "registered_email": f"student.{prefix}.{number:05}@student.pnm.edu.ph",
                    "section_id": section.id,
                    "enrollment": Enrollment(
                        student_id=student_id, offering_ids=by_section[section.id],
                        entry_cohort_year=section.entry_cohort_year,
                        curriculum_version_id=section.curriculum_version_id,
                    ),
                })
    records = [*program_records, *subjects, *sections, *faculty, *offerings]
    return records, students
