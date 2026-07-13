from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from engine.save_manager import save_hint

router = APIRouter()


class SaveHintsReq(BaseModel):
    username: str


@router.post("/hints")
def get_hints(body: SaveHintsReq):
    return {
        "tournament": save_hint(body.username, "tournament"),
        "duo_ai":     save_hint(body.username, "duo_ai"),
    }
