from time import perf_counter
from uuid import uuid4

import ortools
from classync_contracts.scheduling import (
    Assignment,
    Coverage,
    Diagnostic,
    GenerationInput,
    GenerationResult,
    RunMetadata,
    scheduling_input_hash,
)
from ortools.sat.python import cp_model

from .constraint_model import build_model
from .objectives import add_objectives
from .polish import polish_timetable
from .readiness import infeasibility_diagnostics, readiness
from .validation import same_placement, validate_timetable

STATUSES = {
    cp_model.OPTIMAL: "optimal",
    cp_model.FEASIBLE: "feasible",
    cp_model.INFEASIBLE: "infeasible",
    cp_model.MODEL_INVALID: "invalid_model",
    cp_model.UNKNOWN: "unknown",
}


FEASIBILITY_SHARE = 0.6
# Above this many candidate sessions the soft phase cannot improve on the feasible timetable
# inside the budget: measured on the 247-offering campus dataset, loading the soft model alone
# took about 4 s and returned the phase-1 timetable unchanged at every budget tried.
SOFT_PHASE_SESSION_LIMIT = 150
# Wall-clock ceiling as a multiple of the budget. Search is bounded by CP-SAT deterministic
# time, so one input yields the same timetable on any machine unless this ceiling is hit.
WALL_CLOCK_CEILING = 3


def configure(solver, inputs, deterministic_seconds, started):
    elapsed = perf_counter() - started
    solver.parameters.max_deterministic_time = max(0.000001, deterministic_seconds)
    solver.parameters.max_time_in_seconds = max(
        0.000001, inputs.options.time_limit_seconds * WALL_CLOCK_CEILING - elapsed
    )
    solver.parameters.random_seed = inputs.options.seed
    solver.parameters.num_search_workers = 1
    # Timetabling here is propagation-driven: LP relaxations and probing cost seconds of wall
    # time on the full campus model for no search benefit. Results are validated either way.
    solver.parameters.linearization_level = 0
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.max_presolve_iterations = 1


def restrict_patterns(inputs: GenerationInput):
    """Above the soft-phase limit, offer CP-SAT each unlocked offering's first pattern only.

    The full flexible campus model does not solve within the budget; polish may still switch.
    """
    if (
        sum(len(p.durations) for o in inputs.offerings for p in o.patterns)
        <= SOFT_PHASE_SESSION_LIMIT
        or all(len(o.patterns) == 1 for o in inputs.offerings)
    ):
        return inputs
    locked = {a.offering_id for a in inputs.locked_assignments}
    return inputs.model_copy(
        update={
            "offerings": [
                o
                if o.id in locked or len(o.patterns) == 1
                else o.model_copy(update={"patterns": o.patterns[:1]})
                for o in inputs.offerings
            ]
        }
    )


def generate_week(inputs: GenerationInput):
    started = perf_counter()
    digest = scheduling_input_hash(inputs)
    result = GenerationResult(
        run_id=str(uuid4()),
        period_id=inputs.period_id,
        input_hash=digest,
        data_version=inputs.data_version,
        solver_status="invalid_input",
        assignments=[],
        total_offerings_requested=len(inputs.offerings),
        total_offerings_scheduled=0,
        coverage=[
            Coverage(
                offering_id=o.id, required_minutes=o.required_weekly_minutes, allocated_minutes=0
            )
            for o in inputs.offerings
        ],
        hard_conflict_count=None,
        diagnostics=readiness(inputs),
        validation=None,
        metadata=RunMetadata(
            solver_version=ortools.__version__,
            seed=inputs.options.seed,
            wall_time_seconds=0,
            time_limit_seconds=inputs.options.time_limit_seconds,
        ),
    )

    def finish():
        result.metadata.wall_time_seconds = round(perf_counter() - started, 6)
        return result

    if result.diagnostics:
        return finish()
    locked_validation = validate_timetable(inputs, inputs.locked_assignments, partial=True)
    if not locked_validation.valid:
        result.solver_status = "infeasible"
        result.diagnostics = locked_validation.conflicts
        return finish()
    budget = inputs.options.time_limit_seconds
    # Campus-scale runs keep CP-SAT small: one pattern per unlocked offering. The polish
    # pass may switch patterns afterwards, and an unsolved restricted model is retried whole.
    restricted = restrict_patterns(inputs)
    try:
        model, sessions = build_model(restricted)
    except ValueError as error:
        result.diagnostics = [Diagnostic(code="run_limit", message=str(error))]
        return finish()
    invalid = model.validate()
    if invalid:
        result.solver_status = "invalid_model"
        result.diagnostics = [Diagnostic(code="invalid_model", message=invalid)]
        return finish()
    solver = cp_model.CpSolver()
    configure(solver, inputs, budget * FEASIBILITY_SHARE, started)
    # Find a complete feasible incumbent before optimizing expensive soft proxies.
    # Both phases use CP-SAT. A satisfaction proof is never labelled objective-optimal.
    status = solver.solve(model)
    if restricted is not inputs and status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Infeasibility of the restricted model proves nothing about the permitted patterns.
        model, sessions = build_model(inputs)
        solver = cp_model.CpSolver()
        configure(solver, inputs, budget * FEASIBILITY_SHARE, started)
        status = solver.solve(model)
    optimized = False
    soft_skipped = len(sessions) > SOFT_PHASE_SESSION_LIMIT
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) and soft_skipped:
        status = cp_model.FEASIBLE
    elif status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        incumbent = solver
        values = [
            incumbent.value(model.get_int_var_from_proto_index(i))
            for i in range(len(model.proto.variables))
        ]
        add_objectives(model, sessions, inputs)
        for i, value in enumerate(values):
            model.add_hint(model.get_int_var_from_proto_index(i), value)
        optimizing = cp_model.CpSolver()
        configure(optimizing, inputs, budget * (1 - FEASIBILITY_SHARE), started)
        optimizing.parameters.cp_model_presolve = False
        optimized_status = optimizing.solve(model)
        if optimized_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            solver, status, optimized = optimizing, optimized_status, True
        elif optimized_status in (cp_model.MODEL_INVALID, cp_model.INFEASIBLE):
            result.solver_status = "invalid_model"
            result.diagnostics = [
                Diagnostic(code="invalid_model", message="Soft-objective model rejected by CP-SAT.")
            ]
            return finish()
        else:
            # Preserve a validated incumbent if optimization exhausted its budget.
            solver, status = incumbent, cp_model.FEASIBLE
    result.solver_status = STATUSES.get(status, "unknown")
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        message = (
            "CP-SAT proved the complete supplied batch infeasible. No requirements were "
            "dropped. Check shared section/teacher/student time, eligible rooms, distinct "
            "days and locked sessions; this is not a minimal unsatisfiable core."
            if status == cp_model.INFEASIBLE
            else "No validated timetable was found before search stopped. Infeasibility "
            "has not been proven; increase the time limit or review the input."
        )
        result.diagnostics = [Diagnostic(code=result.solver_status, message=message)]
        if status == cp_model.INFEASIBLE:
            result.diagnostics += infeasibility_diagnostics(inputs)
        return finish()
    if optimized:
        result.metadata.objective = solver.objective_value
        result.metadata.best_bound = solver.best_objective_bound
    reserved = {a.id for a in inputs.locked_assignments}
    used = set()
    for s in sessions:
        if not solver.boolean_value(s.present):
            continue
        absolute = solver.value(s.start)
        a = Assignment(
            id=f"generated:{s.offering.id}:{s.index}",
            offering_id=s.offering.id,
            day=absolute // 1440,
            start=absolute % 1440,
            end=absolute % 1440 + s.duration,
            room_id=inputs.rooms[solver.value(s.room)].id,
            teacher_id=inputs.teachers[solver.value(s.teacher)].id,
            section_id=s.offering.section_id,
            subject_id=s.offering.subject_id,
        )
        locked = next((item for item in inputs.locked_assignments if same_placement(a, item)), None)
        if locked:
            a.id = locked.id
        else:
            while a.id in reserved or a.id in used:
                a.id += ":generated"
        used.add(a.id)
        result.assignments.append(a)
    result.assignments.sort(key=lambda a: (a.day, a.start, a.offering_id, a.id))
    polish_notes = []
    # Without configured rules a gap-closing search would scatter classes into one-class
    # days, so periods with no daily-shape rules keep the solver timetable unchanged.
    if inputs.daily_shape is not None:
        original = result.assignments
        polished, report = polish_timetable(inputs, original)
        checked = validate_timetable(inputs, polished)
        if checked.valid:
            result.assignments, result.validation = polished, checked
            result.metadata.polish = report
            if report.moves and optimized:
                # The reported objective described the unpolished timetable.
                optimized, result.solver_status = False, "feasible"
                result.metadata.objective = result.metadata.best_bound = None
            if report.truncated:
                polish_notes.append(
                    Diagnostic(
                        code="polish_truncated",
                        message="Commuter polish stopped at its search limit; the timetable "
                        "is valid but some preferences may still be improvable.",
                    )
                )
        else:
            polish_notes.append(
                Diagnostic(
                    code="polish_rejected",
                    message="Commuter polish was discarded because independent validation "
                    "rejected it; the solver timetable is shown unchanged.",
                )
            )
    if result.validation is None:
        result.validation = validate_timetable(inputs, result.assignments)
    result.coverage = result.validation.coverage
    result.hard_conflict_count = result.validation.hard_conflict_count
    if not result.validation.valid:
        result.solver_status = "validation_failed"
        result.diagnostics = result.validation.conflicts
        result.assignments = []
        return finish()
    result.total_offerings_scheduled = len(inputs.offerings)
    result.diagnostics = [
        Diagnostic(
            code="scope",
            message=(
                "Validated coverage applies only to the supplied offerings. "
                + inputs.scope_description
                + (
                    " Administrator declares all intended offerings supplied."
                    if inputs.all_intended_offerings_supplied
                    else " Complete school-wide coverage has not been declared."
                )
            ),
        )
    ] + polish_notes
    if not optimized:
        result.diagnostics.append(
            Diagnostic(
                code="optimization_limit",
                message=(
                    "The complete feasible timetable was independently validated. "
                    + (
                        f"Soft preferences were not scored: {len(sessions)} candidate sessions "
                        f"exceed the in-budget limit of {SOFT_PHASE_SESSION_LIMIT}. "
                        if soft_skipped
                        else "Soft optimization did not establish a scored incumbent before "
                        "its limit; "
                    )
                    + "No optimum is claimed."
                    + (
                        " Set daily shape rules to apply the commuter-day polish."
                        if soft_skipped and inputs.daily_shape is None
                        else ""
                    )
                ),
            )
        )
    return finish()
