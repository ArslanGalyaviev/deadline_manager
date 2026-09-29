from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime


class DeadlineRepository:
    def __init__(self):
        self._deadlines = {}
        self._next_id = 1

    def add(self, deadline):
        deadline.id = self._next_id
        self._deadlines[deadline.id] = deadline
        self._next_id += 1
        return deadline.id

    def get_by_id(self, id):
        return self._deadlines.get(id)

    def get_all_by_user(self, id):
        return [d for d in self._deadlines.values() if d.user_id == id]

    def delete(self, id):
        if id in self._deadlines:
            del self._deadlines[id]


class Deadline:
    def __init__(self, user_id, title, end_date, priority, category):
        self.id = None
        self.user_id = user_id
        self.title = title
        self.end_date = end_date
        self.priority = priority
        self.category = category
        self.is_completed = False

    def complete(self):
        self.is_completed = True

    def __str__(self):
        status = "Выполнено" if self.is_completed else "Не выполнено"
        return f"[{self.category}] {self.title} (До: {self.end_date}) - Приоритет: {self.priority} [{status}]"


class User:
    def __init__(self, user_id, nickname, repo):
        self.user_id = user_id
        self.nickname = nickname
        self.repo = repo
        self.deadline_ids = []

    def create_deadline(self, title, end_date, priority, category):
        deadline = Deadline(self.user_id, title, end_date, priority, category)
        deadline_id = self.repo.add(deadline)
        self.deadline_ids.append(deadline_id)
        return deadline_id

    def del_deadline(self, id):
        if id in self.deadline_ids:
            self.deadline_ids.remove(id)
            self.repo.delete(id)

    def get_deadlines(self):
        return self.repo.get_all_by_user(self.user_id)


app = FastAPI(title="Deadline Manager API")
repo = DeadlineRepository()


class DeadlineCreate(BaseModel):
    user_id: int
    title: str
    end_date: str
    priority: int
    category: str


class DeadlineResponse(BaseModel):
    id: int
    title: str
    end_date: str
    priority: int
    category: str
    is_completed: bool


@app.post("/deadlines", response_model=DeadlineResponse)
def create_deadline(data: DeadlineCreate):
    d = Deadline(
        user_id=data.user_id,
        title=data.title,
        end_date=data.end_date,
        priority=data.priority,
        category=data.category,
    )
    repo.add(d)
    return d


@app.get("/deadlines/{user_id}", response_model=list[DeadlineResponse])
def show_deadlines(user_id: int):
    deadlines = repo.get_all_by_user(user_id)
    if not deadlines:
        raise HTTPException(status_code=404, detail="No deadlines found for this user")
    return deadlines


@app.delete("/deadlines/{deadline_id}", status_code=204)
def delete_deadline(deadline_id: int):
    deadline = repo.get_by_id(deadline_id)
    if not deadline:
        raise HTTPException(status_code=404, detail="Deadline not found")
    repo.delete(deadline_id)


@app.patch("/deadlines/{deadline_id}/complete")
def complete_deadline(deadline_id: int):
    deadline = repo.get_by_id(deadline_id)
    if not deadline:
        raise HTTPException(status_code=404, detail="Deadline not found")
    deadline.complete()
    return {"message": "Deadline marked as completed", "deadline": deadline}


if __name__ == "__main__":
    r = DeadlineRepository()
    u = User(1, "Arslan", r)

    u.create_deadline("wash the dish", "30.09.2026", 1, "home")
    u.create_deadline("do H/W", "20.09.2026", 2, "school")
    u.create_deadline("travel to Turkey", "10.12.2026", 3, "traveling")

    for d in u.get_deadlines():
        print(d)

    deadlines = u.get_deadlines()
    deadlines[0].complete()

    u.del_deadline(deadlines[1].id)

    for d in u.get_deadlines():
        print(d)
