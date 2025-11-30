from application_service.indication.indication_service import IIndicationSequentialNumberProvider


current_number = 1


class InMemoryIndicationSequentialNumberProvider(IIndicationSequentialNumberProvider):
    def sequential_numbers(self, count: int) -> list[int]:
        global current_number
        numbers = list(range(current_number, count))

        current_number += count

        return numbers
    
    