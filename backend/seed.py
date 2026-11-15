"""Idempotent seed: 3 admins, 4 active volunteers, 1 pending volunteer, sample entries.
Run: cd /app/backend && python seed.py"""

import asyncio
import random
from datetime import date, timedelta

from lib.auth import hash_password
from lib.db import db, ensure_indexes
from models.schemas import new_id, now_utc
from routers.entries import compute_hours

USERS = [
    ("Marco", "Bianchi", "admin@aibgattinara.it", "admin", "active", "Admin2024!"),
    ("Luca", "Ferraris", "luca.ferraris@aibgattinara.it", "admin", "active", "Admin2024!"),
    ("Giulia", "Rossetti", "giulia.rossetti@aibgattinara.it", "admin", "active", "Admin2024!"),
    ("Paolo", "Vercellone", "volontario@aibgattinara.it", "volunteer", "active", "Volontario2024!"),
    ("Elena", "Gallo", "elena.gallo@aibgattinara.it", "volunteer", "active", "Volontario2024!"),
    ("Stefano", "Barbero", "stefano.barbero@aibgattinara.it", "volunteer", "active", "Volontario2024!"),
    ("Chiara", "Mondino", "chiara.mondino@aibgattinara.it", "volunteer", "active", "Volontario2024!"),
    ("Davide", "Colombo", "davide.colombo@example.it", "volunteer", "pending", "Volontario2024!"),
]

SAMPLES = [
    ("AIB", "intervento", "08:00", "14:30", "Incendio boschivo zona Monte Barone"),
    ("AIB", "avvistamento", "13:00", "19:00", "Pattugliamento colline Gattinara"),
    ("AIB", "manutenzione", "09:00", "12:00", "Manutenzione modulo antincendio pick-up"),
    ("AIB", "esercitazione", "08:30", "13:00", "Esercitazione regionale stendimento manichette"),
    ("PC", "intervento", "20:00", "02:00", "Allerta meteo: presidio argini Sesia"),
    ("PC", "sede", "09:00", "12:30", "Servizio logistico manifestazione comunale"),
    ("PC", "formazione", "18:00", "22:00", "Corso radio comunicazioni"),
]


async def main():
    ids = {}
    for fn, ln, email, role, status, pwd in USERS:
        existing = await db.users.find_one({"email": email})
        if existing:
            ids[email] = existing["id"]
            continue
        uid = new_id()
        ids[email] = uid
        await db.users.insert_one({"id": uid, "first_name": fn, "last_name": ln, "email": email, "phone": "",
                                   "password_hash": hash_password(pwd), "role": role, "status": status,
                                   "created_at": now_utc()})

    if await db.entries.count_documents({}) == 0:
        rnd = random.Random(42)
        today = date.today()
        reviewer = "Marco Bianchi"
        for fn, ln, email, role, status, _ in USERS:
            if status != "active":
                continue
            for i in range(6):
                cat, act, s, e, desc = rnd.choice(SAMPLES)
                d = today - timedelta(days=rnd.randint(1, 120))
                st = "approved" if i < 4 else "pending"
                await db.entries.insert_one({
                    "id": new_id(), "user_id": ids[email], "user_name": f"{fn} {ln}", "date": d.isoformat(),
                    "start_time": s, "end_time": e, "hours": compute_hours(s, e), "category": cat,
                    "activity_type": act, "description": desc, "status": st, "reject_reason": "",
                    "reviewed_by_name": reviewer if st == "approved" else "",
                    "reviewed_at": now_utc() if st == "approved" else None, "created_at": now_utc(),
                })
    await ensure_indexes()
    print("seed ok")


if __name__ == "__main__":
    asyncio.run(main())
