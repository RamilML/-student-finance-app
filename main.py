from fastapi import FastAPI, Depends
from pydantic import BaseModel
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
import models

Base.metadata.create_all(bind=engine)

class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str
    date: datetime

app = FastAPI()

# Dependency

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/expenses")
def add_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    db_expense = models.Expense(
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        date=expense.date
    )
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.get("/expenses")
def get_expenses(db: Session = Depends(get_db)):
    return db.query(models.Expense).all()

@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not expense:
        return {"error": "Expense not found"}
    db.delete(expense)
    db.commit()
    return {"message": "Deleted"}

@app.get("/total")
def get_total(db: Session = Depends(get_db)):
    expenses = db.query(models.Expense).all()
    total = sum(e.amount for e in expenses)
    return {"total": total}

@app.get("/")
def home():
    return {"message": "Hello, student finance app with DB!"}
