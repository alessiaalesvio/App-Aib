"""Admin-only routes: volunteer approval, roles, hour review, summary, Excel export."""

import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from lib.auth import full_name, require_admin
from lib.dates import today_iso
from lib.db import db
from models.schemas import (
    AdminCounts, BulkReviewIn, BulkReviewOut, EntryOut, MessageOut, ReviewIn, SummaryOut, SummaryRow,
    UserOut, UserRoleIn, UserStatusIn, UserUpdateIn, now_utc,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

CAT_LABEL = {"AIB": "AIB", "PC": "Protezione Civile"}
ACT_LABEL = {
    "intervento": "Intervento / Emergenza", "avvistamento": "Avvistamento / Pattugliamento",
    "esercitazione": "Esercitazione / Addestramento", "formazione": "Formazione / Corsi",
    "manutenzione": "Manutenzione mezzi / attrezzature", "sede": "Servizio in sede / Logistica", "altro": "Altro",
}
STATUS_LABEL = {"pending": "In attesa", "approved": "Approvata", "rejected": "Rifiutata"}


def period_query(year: Optional[int], month: Optional[int]) -> dict:
    if not year:
        return {}
    if month:
        return {"date": {"$regex": f"^{year}-{month:02d}-"}}
    return {"date": {"$regex": f"^{year}-"}}


# ---------- counts ----------
@router.get("/counts", response_model=AdminCounts)
async def counts():
    return AdminCounts(
        pending_entries=await db.entries.count_documents({"status": "pending"}),
        pending_users=await db.users.count_documents({"status": "pending"}),
    )


# ---------- users ----------
@router.get("/users", response_model=list[UserOut])
async def list_users(status: Optional[str] = None):
    q = {"status": status} if status else {}
    docs = await db.users.find(q, {"_id": 0, "password_hash": 0}).sort([("last_name", 1), ("first_name", 1)]).to_list(2000)
    return [UserOut(**d) for d in docs]


async def _get_user(user_id: str) -> dict:
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not u:
        raise HTTPException(404, "Utente non trovato")
    return u


async def _ensure_not_last_admin(target: dict) -> None:
    if target["role"] == "admin" and target["status"] == "active":
        if await db.users.count_documents({"role": "admin", "status": "active"}) <= 1:
            raise HTTPException(409, "Deve rimanere almeno un amministratore attivo")


@router.patch("/users/{user_id}/status", response_model=UserOut)
async def set_user_status(user_id: str, body: UserStatusIn, admin: dict = Depends(require_admin)):
    u = await _get_user(user_id)
    if u["id"] == admin["id"] and body.status != "active":
        raise HTTPException(409, "Non puoi disattivare il tuo account")
    if body.status != "active":
        await _ensure_not_last_admin(u)
    await db.users.update_one({"id": user_id}, {"$set": {"status": body.status}})
    return UserOut(**{**u, "status": body.status})


@router.patch("/users/{user_id}/role", response_model=UserOut)
async def set_user_role(user_id: str, body: UserRoleIn, admin: dict = Depends(require_admin)):
    u = await _get_user(user_id)
    if u["id"] == admin["id"] and body.role != "admin":
        raise HTTPException(409, "Non puoi rimuovere il tuo ruolo di amministratore")
    if body.role != "admin":
        await _ensure_not_last_admin(u)
    await db.users.update_one({"id": user_id}, {"$set": {"role": body.role}})
    return UserOut(**{**u, "role": body.role})


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: str, body: UserUpdateIn):
    u = await _get_user(user_id)
    email = body.email.lower()
    if email != u["email"] and await db.users.find_one({"email": email, "id": {"$ne": user_id}}):
        raise HTTPException(409, "Email già usata da un altro utente")
    upd = {"first_name": body.first_name.strip(), "last_name": body.last_name.strip(), "email": email, "phone": body.phone.strip()}
    await db.users.update_one({"id": user_id}, {"$set": upd})
    # keep the denormalised name on this user's entries in sync
    await db.entries.update_many({"user_id": user_id}, {"$set": {"user_name": f"{upd['first_name']} {upd['last_name']}"}})
    return UserOut(**{**u, **upd})


@router.delete("/users/{user_id}", response_model=MessageOut)
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    """Explicit admin action (confirmed in the UI): removes the account and that user's entries only."""
    u = await _get_user(user_id)
    if u["id"] == admin["id"]:
        raise HTTPException(409, "Non puoi eliminare il tuo account")
    await _ensure_not_last_admin(u)
    res = await db.entries.delete_many({"user_id": user_id})
    await db.users.delete_one({"id": user_id})
    return MessageOut(message=f"Utente eliminato ({res.deleted_count} registrazioni rimosse)")


# ---------- entries ----------
@router.get("/entries", response_model=list[EntryOut])
async def list_entries(
    status: Optional[str] = None, category: Optional[str] = None, user_id: Optional[str] = None,
    year: Optional[int] = None, month: Optional[int] = None,
):
    q = period_query(year, month)
    if status:
        q["status"] = status
    if category:
        q["category"] = category
    if user_id:
        q["user_id"] = user_id
    docs = await db.entries.find(q, {"_id": 0}).sort([("date", -1), ("start_time", -1)]).to_list(5000)
    return [EntryOut(**d) for d in docs]


async def _review(entry_id: str, status: str, reason: str, admin: dict) -> Optional[dict]:
    doc = await db.entries.find_one({"id": entry_id}, {"_id": 0})
    if not doc:
        return None
    if doc["user_id"] == admin["id"]:
        raise HTTPException(403, "Non puoi approvare le tue stesse ore: chiedi a un altro amministratore")
    upd = {"status": status, "reject_reason": reason.strip() if status == "rejected" else "",
           "reviewed_by_name": full_name(admin), "reviewed_at": now_utc()}
    await db.entries.update_one({"id": entry_id}, {"$set": upd})
    return {**doc, **upd}


@router.patch("/entries/{entry_id}/review", response_model=EntryOut)
async def review_entry(entry_id: str, body: ReviewIn, admin: dict = Depends(require_admin)):
    doc = await _review(entry_id, body.status, body.reject_reason, admin)
    if not doc:
        raise HTTPException(404, "Registrazione non trovata")
    return EntryOut(**doc)


@router.post("/entries/bulk-review", response_model=BulkReviewOut)
async def bulk_review(body: BulkReviewIn, admin: dict = Depends(require_admin)):
    ids = [i for i in body.ids if i]
    res = await db.entries.update_many(
        {"id": {"$in": ids}, "user_id": {"$ne": admin["id"]}, "status": "pending"},
        {"$set": {"status": body.status, "reject_reason": "", "reviewed_by_name": full_name(admin), "reviewed_at": now_utc()}},
    )
    return BulkReviewOut(updated=res.modified_count, skipped=len(ids) - res.modified_count)


@router.delete("/entries/{entry_id}", response_model=MessageOut)
async def admin_delete_entry(entry_id: str):
    res = await db.entries.delete_one({"id": entry_id})
    if not res.deleted_count:
        raise HTTPException(404, "Registrazione non trovata")
    return MessageOut(message="Eliminata")


# ---------- summary / export ----------
async def build_summary(year: int, month: Optional[int]) -> SummaryOut:
    q = {**period_query(year, month), "status": "approved"}
    pipeline = [
        {"$match": q},
        {"$group": {
            "_id": "$user_id",
            "user_name": {"$last": "$user_name"},
            "aib": {"$sum": {"$cond": [{"$eq": ["$category", "AIB"]}, "$hours", 0]}},
            "pc": {"$sum": {"$cond": [{"$eq": ["$category", "PC"]}, "$hours", 0]}},
            "n": {"$sum": 1},
        }},
    ]
    groups = {g["_id"]: g async for g in db.entries.aggregate(pipeline)}
    users = await db.users.find({"status": "active"}, {"_id": 0, "id": 1, "first_name": 1, "last_name": 1}).to_list(2000)
    names = {u["id"]: full_name(u) for u in users}
    rows: list[SummaryRow] = []
    for uid in set(names) | set(groups):
        g = groups.get(uid, {})
        aib, pc = round(g.get("aib", 0), 2), round(g.get("pc", 0), 2)
        rows.append(SummaryRow(user_id=uid, user_name=names.get(uid) or g.get("user_name", "—"),
                               aib_hours=aib, pc_hours=pc, total_hours=round(aib + pc, 2), entries=g.get("n", 0)))
    rows.sort(key=lambda r: (-r.total_hours, r.user_name))
    aib_t = round(sum(r.aib_hours for r in rows), 2)
    pc_t = round(sum(r.pc_hours for r in rows), 2)
    return SummaryOut(year=year, month=month, rows=rows, aib_total=aib_t, pc_total=pc_t, grand_total=round(aib_t + pc_t, 2))


@router.get("/summary", response_model=SummaryOut)
async def summary(year: Optional[int] = None, month: Optional[int] = None):
    return await build_summary(year or int(today_iso()[:4]), month)


@router.get("/export")
async def export_xlsx(year: Optional[int] = None, month: Optional[int] = None):
    y = year or int(today_iso()[:4])
    s = await build_summary(y, month)
    period = f"{month:02d}-{y}" if month else str(y)
    head_fill = PatternFill("solid", fgColor="10B981")
    bold = Font(bold=True, color="FFFFFF")

    wb = Workbook()
    ws = wb.active
    ws.title = "Riepilogo"
    ws.append([f"AIB Gattinara — Riepilogo ore approvate {period}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    ws.append(["Volontario", "Ore AIB", "Ore Protezione Civile", "Totale ore", "N. attività"])
    for c in ws[3]:
        c.fill, c.font = head_fill, bold
    for r in s.rows:
        ws.append([r.user_name, r.aib_hours, r.pc_hours, r.total_hours, r.entries])
    ws.append(["TOTALE", s.aib_total, s.pc_total, s.grand_total, sum(r.entries for r in s.rows)])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for col, w in zip("ABCDE", (32, 12, 22, 12, 12)):
        ws.column_dimensions[col].width = w

    ws2 = wb.create_sheet("Dettaglio")
    ws2.append(["Data", "Volontario", "Categoria", "Tipo attività", "Inizio", "Fine", "Ore", "Descrizione", "Stato", "Revisionato da"])
    for c in ws2[1]:
        c.fill, c.font = head_fill, bold
    docs = await db.entries.find(period_query(y, month), {"_id": 0}).sort([("date", 1), ("start_time", 1)]).to_list(10000)
    for d in docs:
        dd = d["date"]
        ws2.append([f"{dd[8:10]}/{dd[5:7]}/{dd[0:4]}", d["user_name"], CAT_LABEL[d["category"]],
                    ACT_LABEL.get(d["activity_type"], d["activity_type"]), d["start_time"], d["end_time"], d["hours"],
                    d.get("description", ""), STATUS_LABEL[d["status"]], d.get("reviewed_by_name", "")])
    for col, w in zip("ABCDEFGHIJ", (12, 28, 18, 32, 8, 8, 8, 50, 12, 24)):
        ws2.column_dimensions[col].width = w
    for row in ws2.iter_rows(min_row=2, min_col=8, max_col=8):
        row[0].alignment = Alignment(wrap_text=True)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"ore_aib_gattinara_{period}.xlsx"
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
