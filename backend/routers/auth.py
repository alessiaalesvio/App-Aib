from fastapi import APIRouter, Depends, HTTPException, Response

from lib.auth import clear_session, current_user, hash_password, set_session, verify_password
from lib.db import db
from models.schemas import ChangePasswordIn, LoginIn, MessageOut, RegisterIn, UserOut, new_id, now_utc

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=MessageOut, status_code=201)
async def register(body: RegisterIn):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "Email già registrata")
    await db.users.insert_one({
        "id": new_id(),
        "first_name": body.first_name.strip(),
        "last_name": body.last_name.strip(),
        "email": email,
        "phone": body.phone.strip(),
        "password_hash": hash_password(body.password),
        "role": "volunteer",   # never from the body
        "status": "pending",   # an admin must approve
        "created_at": now_utc(),
    })
    return MessageOut(message="Registrazione inviata. Attendi l'approvazione di un amministratore.")


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, response: Response):
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Email o password errati")
    if user["status"] == "pending":
        raise HTTPException(403, "Account in attesa di approvazione da parte di un amministratore")
    if user["status"] == "rejected":
        raise HTTPException(403, "Account non abilitato. Contatta un amministratore")
    set_session(response, user["id"])
    return UserOut(**user)


@router.post("/logout", response_model=MessageOut)
async def logout(response: Response):
    clear_session(response)
    return MessageOut(message="ok")


@router.post("/change-password", response_model=MessageOut)
async def change_password(body: ChangePasswordIn, user: dict = Depends(current_user)):
    doc = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 1})
    if not doc or not verify_password(body.current_password, doc["password_hash"]):
        raise HTTPException(400, "La password attuale non è corretta")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    return MessageOut(message="Password aggiornata")


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(current_user)):
    return UserOut(**user)
