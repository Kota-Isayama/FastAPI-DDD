from typing import Any
from pydantic import AwareDatetime
from domain.solver_task.value_object import GreeksOutcome, MarketId, SolveOutcome, SolverResultId, SolverTaskId, SolverTaskStatus, TradeId


class SolverResult:
    def __init__(
            self,
            solver_result_id: SolverResultId,
            solve_outcome: SolveOutcome | None,
            greeks_outcome: GreeksOutcome | None,
            solver_solution: list | None,
            solver_greeks: list,
            solve_error: Any | None,
            greeks_error: Any | None,
            text_artifact_ids: list,
            binary_artifact_ids: list,
            json_artifact_ids: list,
        ) -> None:
        self._solver_result_id = solver_result_id

        # MetaInformation
        self._solve_outcome = solve_outcome
        self._greeks_outcome = greeks_outcome

        self.solver_solution = solver_solution
        self._solver_greeks = solver_greeks

        self._solve_error = solve_error
        self._greeks_error = greeks_error

        self._text_artifact_ids = text_artifact_ids
        self._binary_artifact_ids = binary_artifact_ids
        self._json_artifact_ids = json_artifact_ids

    def register_solver_solution(
            self,
            solve_outcome: SolveOutcome,
            solver_solution,
            ) -> None:
        self._solve_outcome = solve_outcome
        self._solver_slution = solver_solution

    def register_solver_greeks(
            self,
            greeks_outcome: GreeksOutcome,
            solver_greeks,
        ) -> None:
        self._greeks_outcome = greeks_outcome
        self._solver_greeks = solver_greeks
        

class SolverTask:
    def __init__(
            self,
            solver_task_id: SolverTaskId,
            requested_greeks: bool,
            requested_at: AwareDatetime,
            requested_by: str,
            variables: list,
            trade_json_id: ...,
            market_json_id: ...,
            solver_task_status: SolverTaskStatus,
            started_at: AwareDatetime|None,
            solved_at: AwareDatetime|None,
            greeks_started_at: AwareDatetime|None,
            greeks_ended_at: AwareDatetime|None,
            solver_task_result: SolverResult
        ) -> None:
        self._solver_task_id = solver_task_id
        self._requested_greeks = requested_greeks

        self._requested_at = requested_at
        self._requested_by = requested_by

        # The parameters of the solver problem (The references to the parameters).
        self._variables = variables
        self._trade_json_id = trade_json_id
        self._market_json_id = market_json_id

        self._solver_task_status = solver_task_status

        # Time information.
        self._started_at = started_at
        self._solved_at = solved_at
        self._greeks_started_at = greeks_started_at
        self._greeks_ended_at = greeks_ended_at

        self._solver_task_result = solver_task_result

    def can_start_solver_task(self) -> bool:
        return self._solver_task_status == SolverTaskStatus.QUEUED
    
    def change_solver_task_running(self, started_at: AwareDatetime) -> None:
        if not self.can_start_solver_task():
            raise RuntimeError
        
        self._started_at = started_at
        self._solver_task_status = SolverTaskStatus.SOLVING

    def can_register_solver_solution(self) -> bool:
        return self._solver_task_status == SolverTaskStatus.SOLVING

    def register_solver_solution(
            self, 
            solved_at: AwareDatetime,
            solve_outcome: SolveOutcome, 
            solver_solution,
        ) -> None:
        if not self.can_register_solver_solution():
            raise RuntimeError
        
        self._solved_at = solved_at
        self._solver_task_result.register_solver_solution(solve_outcome, solver_solution)

        if self._requested_greeks:
            self._solver_task_status = SolverTaskStatus.CALCULATING_GREEKS
        else:
            self._solver_task_status = SolverTaskStatus.COMPLETED

    def can_register_solver_greeks(self) -> bool:
        return self._solver_task_status == SolverTaskStatus.CALCULATED_GREEKS

    def register_solver_greeks(self, greeks_outcome: GreeksOutcome, solver_greeks) -> None:
        if not self.can_register_solver_greeks():
            raise RuntimeError
        
        self._solver_task_result.register_solver_greeks(greeks_outcome, solver_greeks)
        self._solver_task_status = SolverTaskStatus.COMPLETED

    
class Market:
    def __init__(
            self,
            market_id: MarketId,
            market_json: dict,
            ):
        self._market_id = market_id
        self._market_json = market_json


class Trade:
    def __init__(
            self,
            trade_id: TradeId,
            trade_json: dict,
            ) -> None:
        self._trade_id = trade_id
        self._trade_json = trade_json
