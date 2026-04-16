import abc

from domain.trade.common.schedules.schedules import ExplicitSchedule, RuleBasedSchedule


class ScheduleService(abc.ABC):
    def convert_to_explicit_schedule(rule_based_schedule: RuleBasedSchedule) -> ExplicitSchedule:
        """This depends on some library."""
        pass
