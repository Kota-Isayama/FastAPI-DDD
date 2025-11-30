from fastapi import FastAPI
from presentation.api.router.indication import router as indication_router
import uvicorn

app = FastAPI()

app.include_router(indication_router)


def start() -> None:
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    start()
