"""Bounded, deterministic draft repair: one move, or a two-step swap with a flexible lecture.

Candidates are screened with cheap local checks (only the moved sessions against the rest);
every returned option is then confirmed by the full independent `validate_timetable`.
"""

from collections import defaultdict

from classync_contracts.scheduling import ActivityType

from .readiness import contains, eligible_room, intersects
from .validation import validate_timetable

EVALUATION_LIMIT = 200


def placements_for(inputs, assignment, offering):
    """Every (day, start, teacher, room) for one session, in a stable order."""
    duration = assignment.end - assignment.start
    for window in sorted(inputs.operating_windows, key=lambda w: (w.day, w.start)):
        for start in range(window.start, window.end - duration + 1, 30):
            for teacher_id in sorted(offering.eligible_teacher_ids):
                for room_id in sorted(offering.eligible_room_ids):
                    yield assignment.model_copy(
                        update={
                            "day": window.day,
                            "start": start,
                            "end": start + duration,
                            "teacher_id": teacher_id,
                            "room_id": room_id,
                        }
                    )


class Repair:
    def __init__(self, inputs, assignments):
        self.inputs = inputs
        self.assignments = assignments
        self.offerings = {o.id: o for o in inputs.offerings}
        self.rooms = {r.id: r for r in inputs.rooms}
        self.teachers = {t.id: t for t in inputs.teachers}
        self.sections = {s.id: s for s in inputs.sections}
        self.locked = {a.id for a in inputs.locked_assignments}
        self.students = defaultdict(set)
        for enrollment in inputs.enrollments:
            for offering_id in enrollment.offering_ids:
                self.students[offering_id].add(enrollment.student_id)
        self.evaluations = 0

    def unary(self, a):
        offering = self.offerings[a.offering_id]
        room, teacher = self.rooms[a.room_id], self.teachers[a.teacher_id]
        return (
            eligible_room(room, offering, self.sections[offering.section_id].program_id)
            and contains(self.inputs.operating_windows, a.day, a.start, a.end)
            and contains(teacher.availability, a.day, a.start, a.end)
            and not intersects(teacher.unavailable, a.day, a.start, a.end)
            and contains(room.availability, a.day, a.start, a.end)
            and not intersects(room.blocked, a.day, a.start, a.end)
        )

    def clashes(self, a, others):
        """Other sessions that overlap `a` (with buffer) on a shared resource or student."""
        buffer = self.inputs.transition_buffer_minutes
        start, end = a.day * 1440 + a.start, a.day * 1440 + a.end
        found = []
        for b in others:
            if b.id == a.id:
                continue
            b_start, b_end = b.day * 1440 + b.start, b.day * 1440 + b.end
            if b.offering_id == a.offering_id and b.day == a.day:
                found.append(b)  # sessions of one pattern stay on distinct days
                continue
            if not any(
                start < b_end + offset + buffer and b_start + offset < end + buffer
                for offset in (-10080, 0, 10080)
            ):
                continue
            if (
                a.room_id == b.room_id
                or a.teacher_id == b.teacher_id
                or a.section_id == b.section_id
                or self.students[a.offering_id] & self.students[b.offering_id]
            ):
                found.append(b)
        return found

    def confirmed(self, moves):
        candidate = [moves.get(item.id, item) for item in self.assignments]
        return validate_timetable(self.inputs, candidate).valid

    def flexible(self, a):
        return (
            a.id not in self.locked
            and self.offerings[a.offering_id].activity_type == ActivityType.ACADEMIC_INSTRUCTION
        )

    def suggest(self, target, limit=3):
        """Up to `limit` validated options; each is {target_id: move[, other_id: move]}."""
        options = []
        offering = self.offerings[target.offering_id]
        pending = []
        for move in placements_for(self.inputs, target, offering):
            if self.evaluations >= EVALUATION_LIMIT or len(options) >= limit:
                return options
            if move == target or not self.unary(move):
                continue
            self.evaluations += 1
            blocking = self.clashes(move, self.assignments)
            if not blocking and self.confirmed({target.id: move}):
                options.append({target.id: move})
            elif len(blocking) == 1 and self.flexible(blocking[0]):
                pending.append((move, blocking[0]))
        for move, other in pending:
            rest = [move if item.id == target.id else item for item in self.assignments]
            for second in placements_for(self.inputs, other, self.offerings[other.offering_id]):
                if self.evaluations >= EVALUATION_LIMIT or len(options) >= limit:
                    return options
                if second == other or not self.unary(second):
                    continue
                self.evaluations += 1
                if not self.clashes(second, rest) and self.confirmed(
                    {target.id: move, other.id: second}
                ):
                    options.append({target.id: move, other.id: second})
                    break
        return options
