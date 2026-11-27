"""CP-SAT hard model: one pattern and instructor per offering, optional intervals."""

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from ortools.sat.python import cp_model

from .readiness import placements
from .validation import REST_BREAK_MINUTES


@dataclass
class Session:
    offering: object
    pattern_index: int
    index: int
    duration: int
    present: object
    start: object
    day: object
    room: object
    teacher: object


def indicator(model, variable, value, present, name):
    selected = model.new_bool_var(name)
    model.add(variable == value).only_enforce_if(selected)
    model.add(variable != value).only_enforce_if([present, selected.Not()])
    model.add_implication(selected, present)
    return selected


def build_model(inputs):
    model = cp_model.CpModel()
    sessions = []
    buckets = defaultdict(list)
    room_ids = {r.id: i for i, r in enumerate(inputs.rooms)}
    teacher_ids = {t.id: i for i, t in enumerate(inputs.teachers)}
    # Students with the same offering set share one no-overlap group, and a set taken from a
    # single section is already covered by that section's group. Both are exact reductions.
    section_of = {o.id: o.section_id for o in inputs.offerings}
    groups = sorted({
        frozenset(student.offering_ids) for student in inputs.enrollments
        if len({section_of.get(oid) for oid in student.offering_ids}) > 1
    }, key=sorted)
    enrollments = defaultdict(list)
    for index, group in enumerate(groups):
        for oid in group:
            enrollments[oid].append(f"group-{index}")
    tuple_count = 0
    choices = {}

    # A buffer can only reach into next week's sessions when a session may end within one
    # buffer of the week's end; otherwise the wrap-around copies are redundant.
    windows = [(w.day * 1440 + w.start, w.day * 1440 + w.end) for w in inputs.operating_windows]
    wraps = bool(windows) and (
        max(end for _, end in windows) + inputs.transition_buffer_minutes
        > 10080 + min(start for start, _ in windows)
    )

    def weekly_intervals(start, length, present, name):
        values = [model.new_optional_fixed_size_interval_var(start, length, present, name)]
        if inputs.transition_buffer_minutes and wraps:
            values.append(
                model.new_optional_fixed_size_interval_var(
                    start + 10080, length, present, f"next-week:{name}"
                )
            )
        return values

    for o in inputs.offerings:
        teacher = model.new_int_var_from_domain(
            cp_model.Domain.from_values([teacher_ids[tid] for tid in o.eligible_teacher_ids]),
            f"teacher:{o.id}",
        )
        patterns = []
        cache = {}
        for pi, pattern in enumerate(o.patterns):
            present = model.new_bool_var(f"pattern:{o.id}:{pi}")
            patterns.append(present)
            pattern_sessions = []
            for si, duration in enumerate(pattern.durations):
                name = f"{o.id}:{pi}:{si}"
                if duration not in cache:
                    cache[duration] = placements(inputs, o, duration)
                tuples = cache[duration]
                tuple_count += len(tuples)
                if tuple_count > 500_000:
                    raise ValueError(
                        "This run exceeds the v1 limit of 500,000 legal placement "
                        "tuples. Narrow explicit eligibility/time windows or deploy "
                        "a larger-capacity solver; no offerings were dropped."
                    )
                start = model.new_int_var(0, 10079, f"start:{name}")
                day = model.new_int_var(0, 6, f"day:{name}")
                room = model.new_int_var(0, len(inputs.rooms) - 1, f"room:{name}")
                model.add_division_equality(day, start, 1440)
                model.add(start == 0).only_enforce_if(present.Not())
                if tuples:
                    starts, rooms, teachers = (sorted({t[k] for t in tuples}) for k in range(3))
                    if len(tuples) == len(starts) * len(rooms) * len(teachers):
                        # A full cartesian product: plain domains are equivalent to the table
                        # and avoid CP-SAT presolving hundreds of large tables.
                        for variable, values in ((start, starts), (room, rooms),
                                                 (teacher, teachers)):
                            model.add_linear_expression_in_domain(
                                variable, cp_model.Domain.from_values(values)
                            ).only_enforce_if(present)
                    else:
                        model.add_allowed_assignments(
                            [start, room, teacher], tuples
                        ).only_enforce_if(present)
                else:
                    model.add(present == 0)
                s = Session(o, pi, si, duration, present, start, day, room, teacher)
                sessions.append(s)
                pattern_sessions.append(s)
                length = duration + inputs.transition_buffer_minutes
                intervals = weekly_intervals(start, length, present, name)
                buckets[("section", o.section_id)].extend(intervals)
                for student_id in enrollments[o.id]:
                    buckets[("student", student_id)].extend(intervals)
                for rid in o.eligible_room_ids:
                    ri = room_ids[rid]
                    chosen = indicator(model, room, ri, present, f"room-choice:{name}:{ri}")
                    buckets[("room", rid)].extend(
                        weekly_intervals(start, length, chosen, f"room-interval:{name}:{ri}")
                    )
                for tid in o.eligible_teacher_ids:
                    ti = teacher_ids[tid]
                    chosen = indicator(model, teacher, ti, present, f"teacher-choice:{name}:{ti}")
                    choices[(len(sessions) - 1, tid)] = chosen
                    buckets[("teacher", tid)].extend(
                        weekly_intervals(start, length, chosen, f"teacher-interval:{name}:{ti}")
                    )
            if pattern.distinct_days:
                for i, a in enumerate(pattern_sessions):
                    for b in pattern_sessions[i + 1 :]:
                        model.add(a.day != b.day).only_enforce_if(present)
                        if len(set(pattern.durations)) == 1:
                            model.add(a.start < b.start).only_enforce_if(present)
        model.add_exactly_one(patterns)
    for intervals in buckets.values():
        if len(intervals) > 1:
            model.add_no_overlap(intervals)
    for tid, ti in teacher_ids.items():
        teacher_record = inputs.teachers[ti]
        if teacher_record.max_weekly_minutes is None and teacher_record.max_daily_minutes is None:
            continue
        chosen = [
            (s, indicator(model, s.teacher, ti, s.present, f"workload:{tid}:{i}"))
            for i, s in enumerate(sessions)
            if tid in s.offering.eligible_teacher_ids
        ]
        if teacher_record.max_weekly_minutes is not None:
            model.add(
                sum(s.duration * active for s, active in chosen)
                <= teacher_record.max_weekly_minutes
            )
        if teacher_record.max_daily_minutes is not None:
            for day in range(7):
                loads = [
                    s.duration
                    * indicator(model, s.day, day, active, f"daily-workload:{tid}:{day}:{i}")
                    for i, (s, active) in enumerate(chosen)
                ]
                model.add(sum(loads) <= teacher_record.max_daily_minutes)
    for tid, ti in teacher_ids.items():
        limit = inputs.teachers[ti].max_continuous_minutes
        if limit is not None:
            add_continuous_limit(model, sessions, choices, tid, limit)
    for locked in inputs.locked_assignments:
        matches = matching_sessions(model, sessions, locked, room_ids, teacher_ids)
        model.add(sum(matches) == 1)
    return model, sessions


def add_continuous_limit(model, sessions, choices, tid, limit):
    """Exact for blocks of up to three sessions; the validator re-checks longer blocks.

    Two of one instructor's sessions are "near" when the same-day gap between them is under
    the rest break. Any block of three sessions contains at least two near pairs.
    """
    mine = [(i, s) for i, s in enumerate(sessions) if (i, tid) in choices]
    for i, s in mine:
        if s.duration > limit:
            model.add(choices[(i, tid)] == 0)
    near = {}

    def far(a, b, condition):
        (i, sa), (j, sb) = a, b
        order = model.new_bool_var(f"rest-order:{tid}:{i}:{j}")
        gap = REST_BREAK_MINUTES
        model.add(sb.start >= sa.start + sa.duration + gap).only_enforce_if([*condition, order])
        model.add(sa.start >= sb.start + sb.duration + gap).only_enforce_if(
            [*condition, order.Not()]
        )

    for a, b in combinations(mine, 2):
        (i, sa), (j, sb) = a, b
        if sa.offering.id == sb.offering.id:
            continue  # same-pattern sessions are on distinct days; patterns are exclusive
        both = [choices[(i, tid)], choices[(j, tid)]]
        if sa.duration + sb.duration > limit:
            far(a, b, both)
        else:
            flag = model.new_bool_var(f"rest-near:{tid}:{i}:{j}")
            far(a, b, [*both, flag.Not()])
            near[(i, j)] = flag
    for a, b, c in combinations(mine, 3):
        (i, sa), (j, sb), (k, sc) = a, b, c
        # Pairs absent from `near` are already forced apart, so they are never near.
        pairs = [pair for pair in ((i, j), (i, k), (j, k)) if pair in near]
        if len(pairs) >= 2 and sa.duration + sb.duration + sc.duration > limit:
            model.add(sum(near[pair] for pair in pairs) <= 1)


def matching_sessions(model, sessions, assignment, room_ids, teacher_ids):
    matches = []
    for s in sessions:
        if (
            s.offering.id != assignment.offering_id
            or s.duration != assignment.end - assignment.start
        ):
            continue
        match = model.new_bool_var(f"match:{assignment.id}:{s.pattern_index}:{s.index}")
        model.add_implication(match, s.present)
        model.add(s.start == assignment.day * 1440 + assignment.start).only_enforce_if(match)
        model.add(s.room == room_ids[assignment.room_id]).only_enforce_if(match)
        model.add(s.teacher == teacher_ids[assignment.teacher_id]).only_enforce_if(match)
        matches.append(match)
    return matches
