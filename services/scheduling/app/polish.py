"""Bounded, deterministic polish of a feasible timetable for commuter-friendly days.

Local search over an already valid timetable. Times are 30-minute slots and each resource's week
is one integer bitmask, so a candidate placement is screened against the hard constraints it can
affect (H1-H9, H11-H15; instructors never change, so H10 and weekly workload cannot change) with
a few integer operations. The caller still runs the full independent validator on the result and
discards it on any violation. No randomness and no solver variables: the same input always yields
the same timetable unless the wall-clock safety cap is reached, which is reported.
"""

from collections import Counter, defaultdict
from time import perf_counter

from classync_contracts.scheduling import (
    Assignment,
    GenerationInput,
    PolishReport,
    SectionDayIssue,
    ShapeMetrics,
)

from .objectives import EARLY_START, LATE_END, SPECIALIZED_ROOM_TYPES
from .readiness import eligible_room
from .validation import REST_BREAK_MINUTES, validate_timetable

# The deterministic bound: about 0.7 s on the 247-offering campus set. The wall cap is only a
# safety net for a much slower machine, and is reported when it fires.
EVALUATION_BUDGET = 80_000
WALL_SECONDS = 1.0
MAX_ROUNDS = 8
EJECTIONS_PER_SESSION = 24
SLOT = 30
DAY = 48
WEEK = 7 * DAY
WEEK_MASK = (1 << WEEK) - 1
DAY_MASK = (1 << DAY) - 1
LATE_SLOT, EARLY_SLOT = LATE_END // SLOT, (EARLY_START + SLOT - 1) // SLOT
# Score components, compared lexicographically (earlier components matter more):
# sessions missing from short days, slots over the daily span, sessions over the daily
# maximum, lectures holding specialized rooms, instructor late-then-early days, idle slots.
SHAPE = 3
ZERO = (0, 0, 0, 0, 0, 0)


def add(*vectors):
    return tuple(map(sum, zip(*vectors, strict=True)))


def minus(a, b):
    return tuple(x - y for x, y in zip(a, b, strict=True))


class Meeting:
    __slots__ = ("id", "offering", "section", "teacher", "room", "day", "slot", "length", "fixed",
                 "source")

    def __init__(self, source: Assignment):
        self.source = source
        self.id, self.offering = source.id, source.offering_id
        self.section, self.teacher = source.section_id, source.teacher_id
        self.room, self.day = source.room_id, source.day
        self.slot, self.length = source.start // SLOT, (source.end - source.start) // SLOT
        self.fixed = False

    def assignment(self):
        return self.source.model_copy(
            update={
                "id": self.id,
                "room_id": self.room,
                "day": self.day,
                "start": self.slot * SLOT,
                "end": (self.slot + self.length) * SLOT,
            }
        )


class Polisher:
    def __init__(
        self,
        inputs: GenerationInput,
        assignments,
        *,
        budget=EVALUATION_BUDGET,
        wall_seconds=WALL_SECONDS,
        verify=False,
    ):
        self.started = perf_counter()
        self.inputs, self.verify = inputs, verify
        self.budget, self.wall_seconds = budget, wall_seconds
        rules = inputs.daily_shape
        self.low = rules.min_sessions_per_active_day if rules else None
        self.high = rules.max_sessions_per_day if rules else None
        span = rules.max_daily_span_minutes if rules else None
        self.span = None if span is None else span // SLOT
        # With 30-minute aligned sessions, any buffer up to one slot reserves that slot.
        self.gap = -(-inputs.transition_buffer_minutes // SLOT)
        self.offerings = {o.id: o for o in inputs.offerings}
        self.rooms = {r.id: r for r in inputs.rooms}
        self.teachers = {t.id: t for t in inputs.teachers}
        self.sections = {s.id: s for s in inputs.sections}
        self.days = sorted({w.day for w in inputs.operating_windows})

        self.items = {}
        self.room_mask = defaultdict(int)
        self.teacher_mask = defaultdict(int)
        self.offering_mask = defaultdict(int)
        self.section_day = defaultdict(list)
        self.teacher_day = defaultdict(list)
        self.by_room = defaultdict(set)
        self.by_offering = defaultdict(set)
        self.by_section = defaultdict(set)
        self.by_teacher = defaultdict(set)
        for assignment in assignments:
            self.insert(Meeting(assignment))

        # Offerings that may never overlap: same section, or at least one shared student.
        neighbors = defaultdict(set)
        in_section = defaultdict(set)
        for o in inputs.offerings:
            in_section[o.section_id].add(o.id)
        for o in inputs.offerings:
            neighbors[o.id] |= in_section[o.section_id]
        for enrollment in inputs.enrollments:
            for offering_id in enrollment.offering_ids:
                neighbors[offering_id].update(enrollment.offering_ids)
        self.neighbors = {oid: tuple(sorted(values)) for oid, values in neighbors.items()}

        previous = {
            (a.offering_id, a.day, a.start, a.end, a.room_id, a.teacher_id)
            for a in inputs.previous_assignments
        }
        locked = {a.id for a in inputs.locked_assignments}
        for a in assignments:
            key = (a.offering_id, a.day, a.start, a.end, a.room_id, a.teacher_id)
            self.items[a.id].fixed = a.id in locked or key in previous

        self.room_choices = {
            o.id: sorted(
                (
                    rid
                    for rid in o.eligible_room_ids
                    if rid in self.rooms
                    and eligible_room(
                        self.rooms[rid], o, self.sections[o.section_id].program_id
                    )
                ),
                key=lambda rid: (self.misuse(o.id, rid), rid),
            )
            for o in inputs.offerings
        }
        self.pattern = {}
        for offering_id, ids in self.by_offering.items():
            lengths = Counter(self.items[i].length * SLOT for i in ids)
            self.pattern[offering_id] = next(
                (
                    p
                    for p in self.offerings[offering_id].patterns
                    if Counter(p.durations) == lengths
                ),
                None,
            )
        self.teacher_starts = {}
        self.room_starts = {}
        # A session is not searched again until its section or instructor has changed.
        self.version = Counter()
        self.settled = {}
        self.moves = 0
        self.evaluations = 0
        self.truncated = False

    # -- indexes ---------------------------------------------------------------------------
    def bits(self, day, slot, length):
        """Occupied week slots including the transition buffer, wrapping Sunday to Monday."""
        value = ((1 << (length + self.gap)) - 1) << (day * DAY + slot)
        return (value & WEEK_MASK) | (value >> WEEK)

    def toggle(self, m):
        value = self.bits(m.day, m.slot, m.length)
        self.room_mask[m.room] ^= value
        self.teacher_mask[m.teacher] ^= value
        self.offering_mask[m.offering] ^= value

    def insert(self, m):
        self.items[m.id] = m
        self.toggle(m)
        self.section_day[m.section, m.day].append(m)
        self.teacher_day[m.teacher, m.day].append(m)
        self.by_room[m.room].add(m.id)
        self.by_offering[m.offering].add(m.id)
        self.by_section[m.section].add(m.id)
        self.by_teacher[m.teacher].add(m.id)

    def remove(self, m):
        del self.items[m.id]
        self.toggle(m)
        self.section_day[m.section, m.day].remove(m)
        self.teacher_day[m.teacher, m.day].remove(m)
        self.by_room[m.room].discard(m.id)
        self.by_offering[m.offering].discard(m.id)
        self.by_section[m.section].discard(m.id)
        self.by_teacher[m.teacher].discard(m.id)

    def spend(self):
        self.evaluations += 1
        if not self.evaluations & 255 and perf_counter() - self.started > self.wall_seconds:
            self.truncated = True
        return not self.stopped

    @property
    def stopped(self):
        return self.truncated or self.evaluations > self.budget

    # -- hard constraints ------------------------------------------------------------------
    def starts_within(self, windows, blocked, length):
        """Week positions where `length` slots fit inside one window and miss every block."""
        value = 0
        for w in windows:
            first, last = -(-w.start // SLOT), w.end // SLOT - length
            if w.day in self.days and last >= first:
                value |= ((1 << (last - first + 1)) - 1) << (w.day * DAY + first)
        for w in blocked:
            first = max(0, w.start // SLOT - length + 1)
            last = min(DAY - 1, -(-w.end // SLOT) - 1)
            if last >= first:
                value &= ~(((1 << (last - first + 1)) - 1) << (w.day * DAY + first))
        return value

    def teacher_legal(self, teacher_id, length):
        value = self.teacher_starts.get((teacher_id, length))
        if value is None:
            teacher = self.teachers[teacher_id]
            value = self.starts_within(
                self.inputs.operating_windows, (), length
            ) & self.starts_within(teacher.availability, teacher.unavailable, length)
            self.teacher_starts[teacher_id, length] = value
        return value

    def room_legal(self, room_id, length):
        value = self.room_starts.get((room_id, length))
        if value is None:
            room = self.rooms[room_id]
            value = self.starts_within(room.availability, room.blocked, length)
            self.room_starts[room_id, length] = value
        return value

    def forbidden(self, m):
        """Slots the absent session `m` may not touch: its instructor and shared students."""
        value = self.teacher_mask[m.teacher]
        for offering_id in self.neighbors[m.offering]:
            value |= self.offering_mask[offering_id]
        return value

    def sibling_days(self, offering_id):
        pattern = self.pattern.get(offering_id)
        if pattern is not None and not pattern.distinct_days:
            return ()
        return {self.items[i].day for i in self.by_offering[offering_id]}

    def within_limits(self, m, day, slot):
        teacher = self.teachers[m.teacher]
        daily, continuous = teacher.max_daily_minutes, teacher.max_continuous_minutes
        if daily is None and continuous is None:
            return True
        spans = [(o.slot, o.length) for o in self.teacher_day[m.teacher, day]]
        if daily is not None and (sum(n for _, n in spans) + m.length) * SLOT > daily:
            return False
        if continuous is None:
            return True
        spans.append((slot, m.length))
        spans.sort()
        block, end, contains_new = 0, None, False
        for start, length in spans:
            if end is not None and (start - end) * SLOT >= REST_BREAK_MINUTES:
                if contains_new:
                    break
                block = 0
            block += length
            end = start + length
            contains_new = contains_new or (start, length) == (slot, m.length)
        return block * SLOT <= continuous

    def free_room(self, m, day, slot, bits):
        position = day * DAY + slot
        rooms = self.room_choices[m.offering]
        if not self.misuse(m.offering, m.room):
            rooms = (m.room, *rooms)
        masks, cached, length = self.room_mask, self.room_starts, m.length
        for room_id in rooms:
            if not masks[room_id] & bits:
                legal = cached.get((room_id, length))
                if legal is None:
                    legal = self.room_legal(room_id, length)
                if legal >> position & 1:
                    return room_id
        return None

    def keeps_preferred_days(self, m, day):
        original = m.source.day
        for preferred in (
            self.sections[m.section].preferred_days,
            self.teachers[m.teacher].preferred_days,
        ):
            if preferred and original in preferred and day not in preferred:
                return False
        return True

    # -- soft score ------------------------------------------------------------------------
    def misuse(self, offering_id, room_id):
        room_type = self.rooms[room_id].room_type
        return int(
            room_type in SPECIALIZED_ROOM_TYPES
            and self.offerings[offering_id].required_room_type != room_type
        )

    def day_value(self, count, first, last, busy, total):
        """(short, over span, over max, idle) for one section-day, in sessions and slots."""
        if not count:
            return 0, 0, 0, 0
        span = last - first
        # Closing gaps must never be bought with a one-class commuting day.
        lonely = DAY if count == 1 and total >= 2 else 0
        short = (
            self.low - count
            if self.low is not None and total >= self.low and count < self.low
            else 0
        )
        over_span = span - self.span if self.span is not None and span > self.span else 0
        over_max = count - self.high if self.high is not None and count > self.high else 0
        return short, over_span, over_max, span - busy + lonely

    def day_stats(self, section_id, day):
        meetings = self.section_day[section_id, day]
        if not meetings:
            return 0, DAY, 0, 0
        return (
            len(meetings),
            min(m.slot for m in meetings),
            max(m.slot + m.length for m in meetings),
            sum(m.length for m in meetings),
        )

    def section_score(self, section_id):
        total = len(self.by_section[section_id])
        short = over_span = over_max = idle = 0
        for day in range(7):
            stats = self.day_stats(section_id, day)
            a, b, c, d = self.day_value(*stats, total)
            short, over_span, over_max, idle = short + a, over_span + b, over_max + c, idle + d
        return short, over_span, over_max, 0, 0, idle

    def rest_days(self, teacher_id):
        """(days ending late, days starting early) as bitmasks over weekdays."""
        late = early = 0
        for day in range(7):
            for m in self.teacher_day[teacher_id, day]:
                if m.slot + m.length >= LATE_SLOT:
                    late |= 1 << day
                if m.slot < EARLY_SLOT:
                    early |= 1 << day
        return late, early

    def clopenings(self, teacher_id):
        late, early = self.rest_days(teacher_id)
        return (late & early >> 1).bit_count()

    def score(self, section_ids, teacher_ids, offering_ids):
        rooms = sum(
            self.misuse(oid, self.items[i].room)
            for oid in offering_ids
            for i in self.by_offering[oid]
        )
        rest = sum(self.clopenings(tid) for tid in teacher_ids)
        return add(
            (0, 0, 0, rooms, rest, 0), *(self.section_score(sid) for sid in section_ids)
        )

    # -- placement search ------------------------------------------------------------------
    def evaluator(self, m, total):
        """Score added by putting the absent session `m` at (day, slot), ignoring rooms."""
        days = {}
        for day in self.days:
            stats = self.day_stats(m.section, day)
            days[day] = stats, self.day_value(*stats, total)
        late, early = self.rest_days(m.teacher)
        base_rest = (late & early >> 1).bit_count()

        def floor(day):
            """A lower bound of the shape components for any start on `day`."""
            (count, first, last, busy), old = days[day]
            shortest = max(last - first, m.length) if count else m.length
            new = self.day_value(count + 1, 0, shortest, busy + m.length, total)
            return new[0] - old[0], new[1] - old[1], new[2] - old[2]

        def delta(day, slot, misused=0):
            (count, first, last, busy), old = days[day]
            end = slot + m.length
            new = self.day_value(
                count + 1,
                slot if slot < first else first,
                end if end > last else last,
                busy + m.length,
                total,
            )
            later = late | (1 << day) if end >= LATE_SLOT else late
            earlier = early | (1 << day) if slot < EARLY_SLOT else early
            return (
                new[0] - old[0],
                new[1] - old[1],
                new[2] - old[2],
                misused,
                (later & earlier >> 1).bit_count() - base_rest,
                new[3] - old[3],
            )

        delta.floor = floor
        return delta

    def search(self, m, limit, delta, blocked=None):
        """Best feasible (score, day, slot, room) strictly below `limit`, or None.

        Positions that would improve but are occupied are collected into `blocked`.
        """
        best = None
        forbidden = self.forbidden(m)
        legal = self.teacher_legal(m.teacher, m.length)
        taken = self.sibling_days(m.offering)
        for day in self.days:
            if (
                day in taken
                or delta.floor(day) > limit[:SHAPE]
                or not self.keeps_preferred_days(m, day)
            ):
                continue
            positions = legal >> (day * DAY) & DAY_MASK
            while positions:
                lowest = positions & -positions
                positions ^= lowest
                slot = lowest.bit_length() - 1
                if not self.spend():
                    return best
                value = delta(day, slot)
                if value >= limit:
                    continue
                bits = self.bits(day, slot, m.length)
                room = None if forbidden & bits else self.free_room(m, day, slot, bits)
                if room is None:
                    if blocked is not None:
                        blocked.append((value, day, slot))
                    continue
                if not self.within_limits(m, day, slot):
                    continue
                if self.misuse(m.offering, room):
                    value = delta(day, slot, 1)
                    if value >= limit:
                        continue
                limit, best = value, (value, day, slot, room)
        return best

    def place(self, m, day, slot, room):
        m.day, m.slot, m.room = day, slot, room
        self.insert(m)

    def accept(self, sections, teachers):
        self.moves += 1
        self.version.update([*sections, *teachers])
        if self.verify:
            result = validate_timetable(self.inputs, self.assignments())
            if not result.valid:
                raise AssertionError(f"Polish move broke a hard constraint: {result.conflicts[0]}")

    # -- moves -----------------------------------------------------------------------------
    def move(self, m, eject=False):
        if m.fixed or self.stopped:
            return False
        state = (self.version[m.section], self.version[m.teacher], eject)
        if self.settled.get(m.id) == state:
            return False
        original = (m.day, m.slot, m.room)
        total = len(self.by_section[m.section])
        self.remove(m)
        delta = self.evaluator(m, total)
        current = delta(original[0], original[1], self.misuse(m.offering, original[2]))
        blocked = [] if eject else None
        best = self.search(m, current, delta, blocked)
        if best:
            self.place(m, *best[1:])
            self.accept([m.section], [m.teacher])
            return True
        self.place(m, *original)
        if blocked:
            for _, day, slot in sorted(blocked)[:EJECTIONS_PER_SESSION]:
                if self.eject(m, day, slot):
                    return True
        self.settled[m.id] = state
        return False

    def blockers(self, m, day, slot):
        """Sessions standing between the absent `m` and (day, slot) via teacher or students."""
        bits = self.bits(day, slot, m.length)
        found = {}
        candidates = set(self.by_teacher[m.teacher])
        for offering_id in self.neighbors[m.offering]:
            candidates |= self.by_offering[offering_id]
        for identity in sorted(candidates):
            other = self.items[identity]
            if self.bits(other.day, other.slot, other.length) & bits:
                found[identity] = other
        if not found:  # only rooms are in the way: any one occupant of an eligible room
            for room_id in self.room_choices[m.offering]:
                occupants = [
                    self.items[i]
                    for i in sorted(self.by_room[room_id])
                    if self.bits(self.items[i].day, self.items[i].slot, self.items[i].length)
                    & bits
                ]
                if len(occupants) == 1 and not occupants[0].fixed:
                    return occupants
        return list(found.values())

    def eject(self, m, day, slot):
        """Move `m` to an occupied position by relocating the single session in the way."""
        original = (m.day, m.slot, m.room)
        self.remove(m)
        blockers = self.blockers(m, day, slot)
        if len(blockers) != 1 or blockers[0].fixed or not self.spend():
            self.place(m, *original)
            return False
        other = blockers[0]
        other_original = (other.day, other.slot, other.room)
        sections = {m.section, other.section}
        teachers = {m.teacher, other.teacher}
        offerings = {m.offering, other.offering}
        self.place(m, *original)
        before = self.score(sections, teachers, offerings)
        self.remove(m)
        total = len(self.by_section[other.section])
        self.remove(other)
        bits = self.bits(day, slot, m.length)
        room = None
        if (
            not self.forbidden(m) & bits
            and day not in self.sibling_days(m.offering)
            and self.within_limits(m, day, slot)
        ):
            room = self.free_room(m, day, slot, bits)
        if room is not None:
            self.place(m, day, slot, room)
            # `other` must add less than what moving `m` alone has freed up.
            limit = minus(before, self.score(sections, teachers, offerings))
            evaluator = self.evaluator(other, total)
            found = self.search(other, limit, evaluator) if limit > ZERO else None
            if found:
                self.place(other, *found[1:])
                if self.score(sections, teachers, offerings) < before:
                    self.accept(sections, teachers)
                    return True
                self.remove(other)
            self.remove(m)
        self.place(other, *other_original)
        self.place(m, *original)
        return False

    def relay_pattern(self, offering_id, pattern):
        """Replace one offering's sessions with `pattern`, each at its best free position."""
        originals = [self.items[i] for i in sorted(self.by_offering[offering_id])]
        template = originals[0]
        for m in originals:
            self.remove(m)
        self.pattern[offering_id] = pattern
        total = len(self.by_section[template.section]) + len(pattern.durations)
        for index, duration in enumerate(pattern.durations):
            m = Meeting(template.source)
            m.id = (
                originals[index].id if index < len(originals) else self.new_id(offering_id, index)
            )
            m.length, m.room = duration // SLOT, template.room
            found = self.search(m, (10**9,) * 6, self.evaluator(m, total))
            if not found:
                return False
            self.place(m, *found[1:])
        return True

    def other_patterns(self, offering_id):
        current = self.pattern.get(offering_id)
        return [
            p
            for p in self.offerings[offering_id].patterns
            if current is None or Counter(p.durations) != Counter(current.durations)
        ]

    def relocate(self, m):
        """Move `m` to its best position on a different day, better or not."""
        day, slot, room = m.day, m.slot, m.room
        total = len(self.by_section[m.section])
        self.remove(m)
        delta = self.evaluator(m, total)

        def elsewhere(d, s, misused=0):
            return (10**9,) * 6 if d == day else delta(d, s, misused)

        elsewhere.floor = delta.floor
        found = self.search(m, (10**9,) * 6, elsewhere)
        self.place(m, *(found[1:] if found else (day, slot, room)))
        return found is not None

    def rebalance(self, section_id, offering_id, pattern=None):
        """A compound move: disturb one offering, let the section settle, keep only a gain.

        With a `pattern`, split or join its sessions (180 <-> 90+90); without one, push it to
        another day even though that alone looks worse. Only this section's sessions move.
        """
        if self.stopped or any(self.items[i].fixed for i in self.by_offering[offering_id]):
            return False
        meetings = [self.items[i] for i in sorted(self.by_section[section_id])]
        snapshot = [(m, m.day, m.slot, m.room) for m in meetings]
        teachers = {m.teacher for m in meetings}
        offerings = {m.offering for m in meetings}
        kept_pattern, kept_moves = self.pattern.get(offering_id), self.moves
        before = self.score([section_id], teachers, offerings)
        if pattern is not None:
            complete = self.relay_pattern(offering_id, pattern)
        else:
            complete = self.relocate(self.items[min(self.by_offering[offering_id])])
        if complete:
            for _ in range(2):
                for identity in sorted(self.by_section[section_id]):
                    if identity in self.items:
                        self.move(self.items[identity])
            if self.score([section_id], teachers, offerings) < before:
                self.moves = kept_moves
                self.accept([section_id], teachers)
                return True
        for identity in list(self.by_section[section_id]):
            self.remove(self.items[identity])
        for m, day, slot, room in snapshot:
            self.place(m, day, slot, room)
        self.pattern[offering_id], self.moves = kept_pattern, kept_moves
        return False

    def new_id(self, offering_id, index):
        identity = f"generated:{offering_id}:polish:{index}"
        while identity in self.items:
            identity += ":generated"
        return identity

    # -- search ----------------------------------------------------------------------------
    def troubled(self):
        scored = ((self.section_score(sid)[:SHAPE], sid) for sid in sorted(self.by_section))
        return [
            sid
            for value, sid in sorted(scored, key=lambda p: (tuple(-v for v in p[0]), p[1]))
            if any(value)
        ]

    def clean(self, section_id):
        return not any(self.section_score(section_id)[:SHAPE])

    def shape_pass(self):
        """Cheap single moves for every troubled section first, then ejections."""
        for eject in (False, True):
            for section_id in self.troubled():
                for identity in sorted(self.by_section[section_id]):
                    if self.clean(section_id):
                        break
                    if identity in self.items:
                        self.move(self.items[identity], eject)

    def rebalance_pass(self):
        """Costlier compound moves for the sections single moves could not fix."""
        for section_id in self.troubled():
            offerings = sorted({self.items[i].offering for i in self.by_section[section_id]})
            for offering_id in offerings:
                for pattern in self.other_patterns(offering_id):
                    if not self.clean(section_id):
                        self.rebalance(section_id, offering_id, pattern)
            for offering_id in offerings:
                if not self.clean(section_id):
                    self.rebalance(section_id, offering_id)

    def tidy_pass(self):
        """Specialized rooms, late-then-early instructors and idle gaps."""
        for identity in sorted(self.items):
            m = self.items.get(identity)
            if m and (
                self.misuse(m.offering, m.room)
                or self.clopenings(m.teacher)
                or self.section_score(m.section)[5]
            ):
                self.move(m)

    def run(self):
        for _ in range(MAX_ROUNDS):
            before = self.moves
            self.shape_pass()
            self.rebalance_pass()
            self.tidy_pass()
            if self.moves == before or self.stopped:
                break

    def assignments(self):
        return sorted(
            (m.assignment() for m in self.items.values()),
            key=lambda a: (a.day, a.start, a.offering_id, a.id),
        )

    # -- reporting -------------------------------------------------------------------------
    def metrics(self):
        orphan = short = over_span = over_max = longest = idle = 0
        unmet = []
        for section_id in sorted(self.by_section):
            total = len(self.by_section[section_id])
            for day in range(7):
                count, first, last, busy = self.day_stats(section_id, day)
                if not count:
                    continue
                a, b, c, _ = self.day_value(count, first, last, busy, total)
                gap = last - first - busy
                span = (last - first) * SLOT
                orphan += count == 1 and total >= 2
                short += bool(a)
                over_span += bool(b)
                over_max += bool(c)
                longest = max(longest, span)
                idle += gap * SLOT
                if a or b or c:
                    unmet.append(
                        SectionDayIssue(
                            section_id=section_id,
                            day=day,
                            sessions=count,
                            span_minutes=span,
                            issues=[
                                name
                                for name, hit in (
                                    ("below_min_sessions", a),
                                    ("over_max_sessions", c),
                                    ("over_span", b),
                                )
                                if hit
                            ],
                        )
                    )
        values = ShapeMetrics(
            orphan_section_days=orphan,
            short_section_days=short,
            over_span_section_days=over_span,
            over_max_section_days=over_max,
            max_span_minutes=longest,
            lectures_in_specialized_rooms=sum(
                self.misuse(m.offering, m.room) for m in self.items.values()
            ),
            faculty_clopenings=sum(self.clopenings(tid) for tid in sorted(self.by_teacher)),
            idle_gap_minutes=idle,
        )
        return values, unmet


def polish_timetable(inputs: GenerationInput, assignments, **options):
    """Return (assignments, report). `assignments` must already satisfy every hard rule."""
    started = perf_counter()
    polisher = Polisher(inputs, assignments, **options)
    before, _ = polisher.metrics()
    polisher.run()
    after, unmet = polisher.metrics()
    return polisher.assignments(), PolishReport(
        moves=polisher.moves,
        evaluations=min(polisher.evaluations, polisher.budget),
        elapsed_ms=int((perf_counter() - started) * 1000),
        truncated=polisher.truncated,
        before=before,
        after=after,
        unmet=unmet,
    )
