from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from typing import Optional
import os
import time
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from supabase import create_client, Client

from src.llm.schema import EnrichmentResult, Category
from src.llm.models import EnrichRequest
import random


class TaskCreate(BaseModel):
    title: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

class AuthCredentials(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None

from fastapi.security import HTTPBearer

security_scheme = HTTPBearer()
app = FastAPI(title="Task API", version="1.0", description="A simple to-do list API built for FlyRank W2/W3")

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Server running and connected to Supabase")


def get_db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    for attempt in range(10):
        try:
            conn = get_db()
            break
        except psycopg.OperationalError:
            print(f"Database not ready yet, retrying... ({attempt + 1}/10)")
            time.sleep(2)
    else:
        raise RuntimeError("Could not connect to database after 10 attempts")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            done BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    count = conn.execute("SELECT COUNT(*) AS count FROM tasks").fetchone()["count"]
    if count == 0:
        conn.execute("INSERT INTO tasks (title, done) VALUES (%s, %s)", ("Buy milk", False))
        conn.execute("INSERT INTO tasks (title, done) VALUES (%s, %s)", ("Walk the dog", False))
        conn.execute("INSERT INTO tasks (title, done) VALUES (%s, %s)", ("Write README", True))
    conn.commit()
    conn.close()

init_db()  # <-- called once here, at module level, not inside itself


def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Access token required")
    token = auth_header.split(" ")[1]

    try:
        user_response = supabase.auth.get_user(token)
        user = user_response.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user, token


@app.get("/")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks")
def get_tasks(done: Optional[bool] = None, search: Optional[str] = None):
    conn = get_db()
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if done is not None:
        query += " AND done = %s"
        params.append(done)
    if search:
        query += " AND title LIKE %s"
        params.append(f"%{search}%")
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = %s", (task_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return row


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    if not task.title or not task.title.strip():
        raise HTTPException(status_code=400, detail="title is required and cannot be empty")
    conn = get_db()
    row = conn.execute(
        "INSERT INTO tasks (title, done) VALUES (%s, %s) RETURNING *",
        (task.title, False)
    ).fetchone()
    conn.commit()
    conn.close()
    return row


@app.put("/tasks/{task_id}")
def update_task(task_id: int, update: TaskUpdate):
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = %s", (task_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    new_title = row["title"]
    new_done = row["done"]
    if update.title is not None:
        if not update.title.strip():
            conn.close()
            raise HTTPException(status_code=400, detail="title cannot be empty")
        new_title = update.title
    if update.done is not None:
        new_done = update.done

    updated = conn.execute(
        "UPDATE tasks SET title = %s, done = %s WHERE id = %s RETURNING *",
        (new_title, new_done, task_id)
    ).fetchone()
    conn.commit()
    conn.close()
    return updated


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = %s", (task_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    conn.commit()
    conn.close()


@app.get("/stats")
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS count FROM tasks").fetchone()["count"]
    done = conn.execute("SELECT COUNT(*) AS count FROM tasks WHERE done = TRUE").fetchone()["count"]
    conn.close()
    return {"total": total, "done": done, "open": total - done}


@app.post("/reset")
def reset_tasks():
    conn = get_db()
    conn.execute("DELETE FROM tasks")
    conn.execute("INSERT INTO tasks (title, done) VALUES (%s, %s)", ("Buy milk", False))
    conn.execute("INSERT INTO tasks (title, done) VALUES (%s, %s)", ("Walk the dog", False))
    conn.execute("INSERT INTO tasks (title, done) VALUES (%s, %s)", ("Write README", True))
    conn.commit()
    rows = conn.execute("SELECT * FROM tasks").fetchall()
    conn.close()
    return {"message": "Tasks reset", "tasks": rows}


@app.post("/auth/signup", status_code=201)
def signup(credentials: AuthCredentials):
    if not credentials.email or not credentials.password:
        raise HTTPException(status_code=400, detail="email and password are required")
    try:
        result = supabase.auth.sign_up({
            "email": credentials.email,
            "password": credentials.password
        })
        return result.user.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/login")
def login(credentials: AuthCredentials):
    if not credentials.email or not credentials.password:
        raise HTTPException(status_code=400, detail="email and password are required")
    try:
        result = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        return {
            "access_token": result.session.access_token,
            "refresh_token": result.session.refresh_token
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid login credentials")


@app.get("/public/info")
def public_info():
    return {"message": "Welcome stranger! This info is public."}


@app.get("/protected/profile")
def protected_profile(user_and_token: tuple = Depends(get_current_user), _: str = Depends(security_scheme)):
    user, token = user_and_token
    return {
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at
    }


@app.post("/auth/logout", status_code=204)
def logout(user_and_token: tuple = Depends(get_current_user), _: str = Depends(security_scheme)):
    user, token = user_and_token
    supabase.auth.sign_out()


@app.get("/protected/dashboard")
def protected_dashboard(user_and_token: tuple = Depends(get_current_user), _: str = Depends(security_scheme)):
    user, token = user_and_token
    return {"message": f"Welcome to your dashboard, {user.email}"}

from src.llm.enrich import enrich_book

@app.post("/enrich", response_model=EnrichmentResult)
def enrich(request: EnrichRequest):
    if os.environ.get("LLM_STUB") == "1":
        return EnrichmentResult(
            category=Category.OTHER,
            summary="Stub response — no model was called.",
            quality_flags=[],
            confidence=0.42
        )

    try:
        return enrich_book(request.title, request.description, request.price_gbp)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))