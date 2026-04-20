from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from datetime import datetime
class Expense(BaseModel):
    title: str
    amount: float
    category: str
    date: datetime
expenses: List[Expense] = []
app = FastAPI()
@app.post("/expenses")
def add_expense(expense: Expense):
    expenses.append(expense)
    return {"message": "Expense added"}
@app.get("/expenses")
def get_expenses():
    return expenses

@app.get("/")
def home():
    return {"message": "Hello, student finance app!"}

@app.delete("/expenses/{index}")
def delete_expense(index: int):
    if index < 0 or index >= len(expenses):
        return {"error": "Invalid index"}
    
    deleted = expenses.pop(index)
    return {"message": "Deleted", "expense": deleted}

@app.get("/total")
def get_total():
    total = 0
    
    for expense in expenses:
        total += expense.amount
    
    return {"total": total}

@app.get("/by-category")
def expenses_by_category():
    result = {}
    
    for expense in expenses:
        category = expense.category
        
        if category not in result:
            result[category] = 0
        
        result[category] += expense.amount
    
    return result