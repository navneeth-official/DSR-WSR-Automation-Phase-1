from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

tables = db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))
print("Tables:", [r[0] for r in tables])

db.close()
