import os
import asyncio
import aiosmtplib
from email.message import EmailMessage
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from contextlib import asynccontextmanager
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

DB_HOST = os.getenv("DB_HOST", "localhost")
DATABASE_URL = f"postgresql+asyncpg://postgres:postgres@{DB_HOST}:5432/deadline_db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class DeadlineModel(Base):
    __tablename__ = "deadlines"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False)
    title = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    priority = Column(Integer, nullable=False)
    category = Column(String, nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)


class DeadlineCreate(BaseModel):
    user_id: int
    title: str
    end_date: str
    priority: int
    category: str


class DeadlineResponse(BaseModel):
    id: int
    user_id: int
    title: str
    end_date: str
    priority: int
    category: str
    is_completed: bool

    model_config = {"from_attributes": True}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Deadline Manager API", lifespan=lifespan)


async def send_deadline_notification(email: str, title: str, end_date: str):
    """Асинхронная фоновая задача отправки уведомления (SMTP)"""
    message = EmailMessage()
    message["Subject"] = f"Новый дедлайн: {title}"
    message["From"] = "notifications@deadline-manager.local"
    message["To"] = email
    message.set_content(f"Напоминание: у вас есть дедлайн '{title}' до {end_date}.")

    try:
        async with aiosmtplib.SMTP(hostname="localhost", port=1025) as smtp:
            await smtp.send_message(message)
        print(f"[BACKGROUND TASK] Уведомление успешно отправлено на {email}")
    except Exception as e:
        print(f"[BACKGROUND TASK] Ошибка отправки уведомления (SMTP не запущен): {e}")


@app.post("/deadlines", response_model=DeadlineResponse, status_code=201)
async def create_deadline(data: DeadlineCreate, db: AsyncSession = Depends(get_db)):
    new_deadline = DeadlineModel(
        user_id=data.user_id,
        title=data.title,
        end_date=data.end_date,
        priority=data.priority,
        category=data.category,
        is_completed=False,
    )
    db.add(new_deadline)
    await db.commit()
    await db.refresh(new_deadline)

    asyncio.create_task(
        send_deadline_notification(
            "user@example.com", new_deadline.title, new_deadline.end_date
        )
    )

    return new_deadline


@app.get("/deadlines/{user_id}", response_model=list[DeadlineResponse])
async def get_user_deadlines(
    user_id: int,
    category: Optional[str] = None,
    priority: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(DeadlineModel).where(DeadlineModel.user_id == user_id)

    if category is not None:
        query = query.where(DeadlineModel.category == category)
    if priority is not None:
        query = query.where(DeadlineModel.priority == priority)

    result = await db.execute(query)
    deadlines = result.scalars().all()

    if not deadlines:
        raise HTTPException(status_code=404, detail="No deadlines found for this user")
    return deadlines


@app.delete("/deadlines/{deadline_id}", status_code=204)
async def delete_deadline(deadline_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DeadlineModel).where(DeadlineModel.id == deadline_id)
    )
    deadline = result.scalars().first()

    if not deadline:
        raise HTTPException(status_code=404, detail="Deadline not found")

    await db.delete(deadline)
    await db.commit()


@app.patch("/deadlines/{deadline_id}/complete")
async def complete_deadline(deadline_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DeadlineModel).where(DeadlineModel.id == deadline_id)
    )
    deadline = result.scalars().first()

    if not deadline:
        raise HTTPException(status_code=404, detail="Deadline not found")

    deadline.is_completed = True
    await db.commit()
    await db.refresh(deadline)

    return {"message": "Deadline marked as completed", "deadline": deadline}
