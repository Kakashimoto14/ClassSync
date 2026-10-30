"""Dated room moves must retain the weekly validator's physical eligibility rules."""

from datetime import date

import pytest
from classync_contracts.calendar import AcademicCalendar, CalendarException
from classync_contracts.scheduling import Assignment

from services.scheduling.app.draft_rules import DraftError
from services.scheduling.app.occurrences import dated_occurrences
from services.scheduling.app.validation import validate_timetable
from services.scheduling.tests.test_engine import tiny


@pytest.mark.parametrize("change", [
    {"capacity": 10}, {"capacity_verified": False},
    {"room_type": "laboratory"}, {"type_verified": False},
    {"equipment": []}, {"equipment_verified": False},
    {"allowed_program_ids": []}, {"building": "Other invented building"},
    {"availability": []},
    {},
])
def test_room_move_preserves_all_supplied_eligibility_constraints(change):
    inputs = tiny()
    offering, original = inputs.offerings[0], inputs.rooms[0]
    program = inputs.sections[0].program_id
    original.capacity, original.capacity_verified = 50, True
    original.room_type, original.type_verified = "classroom", True
    original.equipment, original.equipment_verified = ["projector"], True
    original.allowed_program_ids = [program]
    original.building = "Invented teaching building"
    alternate = original.model_copy(update={"id": "invented-alternate", **change}, deep=True)
    inputs.rooms.append(alternate)
    offering.eligible_room_ids.append(alternate.id)
    offering.minimum_capacity, offering.required_room_type = 20, "classroom"
    offering.required_equipment = ["projector"]
    offering.allowed_buildings = [original.building]
    window = next(w for w in inputs.operating_windows if w.day == 0)
    assignment = Assignment(id="manual-valid-session", offering_id=offering.id,
        subject_id=offering.subject_id, section_id=offering.section_id,
        teacher_id=offering.eligible_teacher_ids[0], room_id=original.id,
        day=0, start=window.start, end=window.start + offering.required_weekly_minutes)
    assert validate_timetable(inputs, [assignment]).valid
    day = date(2026, 10, 5)
    calendar = AcademicCalendar(academic_year="2026-2027", semester="first",
        effective_start=day, effective_end=day, exceptions=[CalendarException(
            date=day, assignment_id=assignment.id, cancelled=False, moved_to=day,
            room_id=alternate.id, reason="Invented room move regression")])
    if change:
        with pytest.raises(DraftError) as denied:
            dated_occurrences(inputs, [assignment], calendar, day, day)
        assert (denied.value.status, denied.value.code) == (422, "dated_constraints")
    else:
        events = dated_occurrences(inputs, [assignment], calendar, day, day)
        assert len(events) == 1 and events[0]["room"]["id"] == alternate.id
