"""Volunteer-facing hour entries — always scoped to the caller (user_id from the session)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import current_user, full_name
from lib.dates import today_iso
from lib.db import db
from models.schemas import EntryIn, EntryOut, MessageOut, MyStats, new_id, now_utc

router = APIRouter(prefix="/entries", tags=["entries"])


def compute_hours(start: str, end: str) -> float:
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    mins = (eh * 60 + em) - (sh * 60 + sm)
    if mins <= 0:
        mins += 24 * 60  # shift past midnight
    return round(mins / 60, 2)


def validate_entry(body: EntryIn) -> float:
    try:
        datetime.strptime(body.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(422, "Data non valida")
    if body.date > today_iso():
        raise HTTPException(422, "Non puoi registrare ore in una data futura")
    if body.start_time == body.end_time:
        raise HTTPException(422, "Orario di inizio e fine coincidono")
    return compute_hours(body.start_time, body.end_time)


@router.post("", response_model=EntryOut, status_code=201)
async def create_entry(body: EntryIn, user: dict = Depends(current_user)):
    hours = validate_entry(body)
    doc = {
        "id": new_id(),
        "user_id": user["id"],
        "user_name": full_name(user),
        **body.model_dump(),
        "description": body.description.strip(),
        "hours": hours,
        "status": "pending",
        "reject_reason": "",
        "reviewed_by_name": "",
        "reviewed_at": None,
        "created_at": now_utc(),
    }
    await db.entries.insert_one(doc)
    doc.pop("_id", None)
    return EntryOut(**doc)


@router.get("/mine", response_model=list[EntryOut])
async def my_entries(year: Optional[int] = None, user: dict = Depends(current_user)):
    q: dict = {"user_id": user["id"]}
    if year:
        q["date"] = {"$regex": f"^{year}-"}
    docs = await db.entries.find(q, {"_id": 0}).sort([("date", -1), ("start_time", -1)]).to_list(2000)
    return [EntryOut(**d) for d in docs]


@router.get("/mine/stats", response_model=MyStats)
async def my_stats(year: Optional[int] = None, user: dict = Depends(current_user)):
    y = year or int(today_iso()[:4])
    docs = await db.entries.find({"user_id": user["id"], "date": {"$regex": f"^{y}-"}}, {"_id": 0}).to_list(5000)
    appr = [d for d in docs if d["status"] == "approved"]
    pend = [d for d in docs if d["status"] == "pending"]
    aib = round(sum(d["hours"] for d in appr if d["category"] == "AIB"), 2)
    pc = round(sum(d["hours"] for d in appr if d["category"] == "PC"), 2)
    return MyStats(year=y, today=today_iso(), aib_hours=aib, pc_hours=pc, total_hours=round(aib + pc, 2),
                   pending_hours=round(sum(d["hours"] for d in pend), 2), pending_count=len(pend))


@router.put("/{entry_id}", response_model=EntryOut)
async def update_entry(entry_id: str, body: EntryIn, user: dict = Depends(current_user)):
    doc = await db.entries.find_one({"id": entry_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Registrazione non trovata")
    if doc["status"] == "approved":
        raise HTTPException(403, "Le ore approvate non possono essere modificate")
    hours = validate_entry(body)
    upd = {**body.model_dump(), "description": body.description.strip(), "hours": hours,
           "status": "pending", "reject_reason": "", "reviewed_by_name": "", "reviewed_at": None}
    await db.entries.update_one({"id": entry_id}, {"$set": upd})
    return EntryOut(**{**doc, **upd})


@router.delete("/{entry_id}", response_model=MessageOut)
async def delete_entry(entry_id: str, user: dict = Depends(current_user)):
    doc = await db.entries.find_one({"id": entry_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Registrazione non trovata")
    if doc["status"] == "approved":
        raise HTTPException(403, "Le ore approvate non possono essere eliminate")
    await db.entries.delete_one({"id": entry_id})
    return MessageOut(message="Eliminata")
