from fastapi import APIRouter, Depends, status

from application_service.indication.indication_service import IndicationApplicationService
from presentation.api.dependency import get_indication_application_service
from presentation.api.router.schema import IndicationGetResponseBody, IndicationRegisterRequestBody, IndicationRegisterResponseBody

router = APIRouter(prefix="/indications", tags=["indications"])

@router.post(
    "",
    status_code=status.HTTP_200_OK,
    response_model=IndicationRegisterResponseBody,
)
def register_indication(request_body: IndicationRegisterRequestBody, service: IndicationApplicationService=Depends(get_indication_application_service)):
    result = service.register_indication(command=request_body)
    return result

    
@router.get(
    "/{indiation_id}",
    status_code=status.HTTP_200_OK,
    response_model=IndicationGetResponseBody
)
def get_indication_by_id(indication_id: str, service: IndicationApplicationService=Depends(get_indication_application_service)):
    result = service.get_by_id(indication_id)
    return result
