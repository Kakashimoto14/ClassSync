"""Documented integer proxies; hard feasibility never depends on objective weights."""

from collections import defaultdict
from itertools import combinations

from .constraint_model import indicator, matching_sessions


def add_objectives(model, sessions, inputs):
    weights = inputs.options.weights
    terms = []
    sections = {s.id: s for s in inputs.sections}
    days = sorted({w.day for w in inputs.operating_windows})
    teacher_index = {t.id: i for i, t in enumerate(inputs.teachers)}
    groups = defaultdict(list)
    for n, s in enumerate(sessions):
        groups[("section", s.offering.section_id)].append((s, s.present))
        for tid in s.offering.eligible_teacher_ids:
            selected = indicator(
                model, s.teacher, teacher_index[tid], s.present, f"objective-t:{n}:{tid}"
            )
            groups[("teacher", tid)].append((s, selected))
        for ri, room in enumerate(inputs.rooms):
            if room.id in s.offering.eligible_room_ids:
                selected = indicator(model, s.room, ri, s.present, f"objective-r:{n}:{ri}")
                groups[("room", room.id)].append((s, selected))
        for day in days:
            on_day = indicator(model, s.day, day, s.present, f"preference:{n}:{day}")
            preferred = sections[s.offering.section_id].preferred_days
            if preferred and day not in preferred:
                terms.append(weights.preferences * on_day)
            for tid in s.offering.eligible_teacher_ids:
                preferred = inputs.teachers[teacher_index[tid]].preferred_days
                if preferred and day not in preferred:
                    selected = indicator(
                        model, s.teacher, teacher_index[tid], on_day, f"pref-t:{n}:{day}:{tid}"
                    )
                    terms.append(weights.preferences * selected)
    for (kind, entity), entries in groups.items():
        for day in days:
            starts, ends, loads = [], [], []
            for n, (s, active) in enumerate(entries):
                selected = indicator(model, s.day, day, active, f"day:{kind}:{entity}:{day}:{n}")
                start = model.new_int_var(0, 1440, "daily-start")
                end = model.new_int_var(0, 1440, "daily-end")
                model.add(start == s.start - day * 1440).only_enforce_if(selected)
                model.add(end == s.start - day * 1440 + s.duration).only_enforce_if(selected)
                model.add(start == 1440).only_enforce_if(selected.Not())
                model.add(end == 0).only_enforce_if(selected.Not())
                starts.append(start)
                ends.append(end)
                loads.append(selected * (s.duration // 30))
            load = model.new_int_var(0, 48, "daily-load")
            model.add(load == sum(loads))
            if (
                kind == "room"
                and weights.room_balance
                or kind == "section"
                and weights.daily_balance
            ):
                square = model.new_int_var(0, 48 * 48, "load-square")
                model.add_multiplication_equality(square, [load, load])
                terms.append(
                    (weights.room_balance if kind == "room" else weights.daily_balance) * square
                )
            if kind != "room" and weights.idle_gaps:
                first = model.new_int_var(0, 1440, "first")
                last = model.new_int_var(0, 1440, "last")
                gap = model.new_int_var(0, 1440, "gap")
                model.add_min_equality(first, starts)
                model.add_max_equality(last, ends)
                model.add_max_equality(gap, [0, last - first - load * 30])
                terms.append(weights.idle_gaps * gap)
        if kind == "room" or not weights.building_changes:
            continue
        buildings = sorted({r.building for r in inputs.rooms})
        room_buildings = [buildings.index(r.building) for r in inputs.rooms]
        # Same-day mixed-building pairs are a compact proxy for campus transitions.
        # This deliberately does not claim shortest-path walking optimization.
        if len(buildings) > 1:
            for (a, active_a), (b, active_b) in combinations(entries, 2):
                if a.offering.id == b.offering.id and a.pattern_index != b.pattern_index:
                    continue
                ba = model.new_int_var(0, len(buildings) - 1, "building-a")
                bb = model.new_int_var(0, len(buildings) - 1, "building-b")
                model.add_element(a.room, room_buildings, ba)
                model.add_element(b.room, room_buildings, bb)
                together = model.new_bool_var("same-day")
                different = model.new_bool_var("different-building")
                model.add(a.day == b.day).only_enforce_if(together)
                model.add(a.day != b.day).only_enforce_if(together.Not())
                model.add(ba != bb).only_enforce_if(different)
                model.add(ba == bb).only_enforce_if(different.Not())
                mix = model.new_bool_var("building-mix")
                model.add_min_equality(mix, [active_a, active_b, together, different])
                terms.append(weights.building_changes * mix)
    if weights.disruption:
        for prior in inputs.previous_assignments:
            matches = matching_sessions(
                model, sessions, prior, {r.id: i for i, r in enumerate(inputs.rooms)}, teacher_index
            )
            kept = model.new_bool_var("prior-preserved")
            model.add(sum(matches) == kept)
            terms.append(weights.disruption * (1 - kept))
    model.minimize(sum(terms))
