from pydantic import BaseModel


class Arg(BaseModel):
    sleep_seconds: int
    value: str
