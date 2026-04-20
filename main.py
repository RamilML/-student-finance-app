from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from datetime import datetime
class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str
    date: datetime
class Expense(BaseModel):
    id: int
    title: str
    amount: float
    category: str
    date: datetime
current_id = 0
expenses: List[Expense] = []
app = FastAPI()

@app.post("/expenses")
def add_expense(expense: ExpenseCreate):
    global current_id
    current_id += 1
    
    new_expense = Expense(
        id=current_id,
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        date=expense.date
    )
    
    expenses.append(new_expense)
    return new_expense
@app.get("/expenses")
def get_expenses():
    return expenses

@app.get("/")
def home():
    return {"message": "Hello, student finance app!"}

@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int):
    for i, expense in enumerate(expenses):
        if expense.id == expense_id:
            deleted = expenses.pop(i)
            return {"message": "Deleted", "expense": deleted}
    
    return {"error": "Expense not found"}

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

@app.get("/top-category")
def get_top_category():
    if not expenses:
        return {"message": "No expenses yet"}
    
    result = {}
    
    for expense in expenses:
        category = expense.category
        
        if category not in result:
            result[category] = 0
        
        result[category] += expense.amount
    
    top_category = None
    max_amount = 0
    
    for category, amount in result.items():
        if amount > max_amount:
            max_amount = amount
            top_category = category
    
    return {
        "top_category": top_category,
        "amount": max_amount
    }