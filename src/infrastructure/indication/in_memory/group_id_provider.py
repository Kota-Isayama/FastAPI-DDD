from application_service.indication.indication_service import IIndicationGroupIdProvider, IIndicationSequentialNumberProvider


current_number = 0


class InMemoryIndicationGroupIdProvider(IIndicationGroupIdProvider):
    def group_id(count):
        global current_number
        current_number += 1
        return current_number
    