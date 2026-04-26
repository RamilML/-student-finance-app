from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from database import Base
from datetime import datetime

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    amount = Column(Float)
    category = Column(String)
    date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

class Income(Base):
    __tablename__ = "incomes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    amount = Column(Float)
    source = Column(String)  # Источник дохода (зарплата, фриланс и т.д.)
    date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class BudgetLimit(Base):
    __tablename__ = "budget_limits"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=True)  # NULL = общий лимит
    limit_amount = Column(Float)
    period = Column(String, default="monthly")  # daily, weekly, monthly
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

class UserBudget(Base):
    __tablename__ = "user_budgets"

    id = Column(Integer, primary_key=True, index=True)
    budget_amount = Column(Float, default=0.0)  # Общий бюджет пользователя
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)