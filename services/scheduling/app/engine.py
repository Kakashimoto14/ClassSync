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
from .readiness import infeasibility_diagnostics, readiness
from .validation import same_placement, validate_timetable

STATUSES = {
    cp_model.OPTIMAL: "optimal",
    cp_model.FEASIBLE: "feasible",
    cp_model.INFEASIBLE: "infeasible",
    cp_model.MODEL_INVALID: "invalid_model",
    cp_model.UNKNOWN: "unknown",
}


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
    try:
        model, sessions = build_model(inputs)
    except ValueError as error:
        result.diagnostics = [Diagnostic(code="run_limit", message=str(error))]
        return finish()
    invalid = model.validate()
    if invalid:
        result.solver_status = "invalid_model"
        result.diagnostics = [Diagnostic(code="invalid_model", message=invalid)]
        return finish()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = inputs.options.time_limit_seconds
    solver.parameters.random_seed = inputs.options.seed
    solver.parameters.num_search_workers = 1
    # Find a complete feasible incumbent before optimizing expensive soft proxies.
    # Both phases use CP-SAT. A satisfaction proof is never labelled objective-optimal.
    solver.parameters.max_time_in_seconds = inputs.options.time_limit_seconds * 0.6
    status = solver.solve(model)
    optimized = False
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        incumbent = solver
        values = [
            incumbent.value(model.get_int_var_from_proto_index(i))
            for i in range(len(model.proto.variables))
        ]
        add_objectives(model, sessions, inputs)
        for i, value in enumerate(values):
            model.add_hint(model.get_int_var_from_proto_index(i), value)
        remaining = inputs.options.time_limit_seconds - incumbent.wall_time
        optimizing = cp_model.CpSolver()
        optimizing.parameters.max_time_in_seconds = max(0.000001, remaining)
        optimizing.parameters.random_seed = inputs.options.seed
        optimizing.parameters.num_search_workers = 1
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
    ]
    if not optimized:
        result.diagnostics.append(
            Diagnostic(
                code="optimization_limit",
                message=(
                    "The complete feasible timetable was independently validated. "
                    "Soft optimization did not establish a scored incumbent before its limit; "
                    "no optimum is claimed."
                ),
            )
        )
    return finish()
