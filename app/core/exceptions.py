from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    formatted_errors = {}
    for error in exc.errors():
        field_name = ".".join(map(str, error["loc"]))
        message = error["msg"]
        formatted_errors[field_name] = message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": {
                "message": "Request body validation failed. Please check the errors",
                "errors": formatted_errors,
            }
        },
    )
