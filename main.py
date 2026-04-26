from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import jwt
from passlib.context import CryptContext

from database import SessionLocal, engine, Base
import models

# Секретный ключ для JWT (в продакшене хранить в .env)
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

Base.metadata.create_all(bind=engine)

app = FastAPI()

# Добавляем CORS middleware для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Pydantic Schemas ---

class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str
    date: Optional[datetime] = None

class ExpenseResponse(ExpenseCreate):
    id: int
    user_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class BudgetLimitCreate(BaseModel):
    category: Optional[str] = None
    limit_amount: float
    period: str = "monthly"

class BudgetLimitResponse(BudgetLimitCreate):
    id: int
    user_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class UserBudgetCreate(BaseModel):
    budget_amount: float

class UserBudgetResponse(UserBudgetCreate):
    id: int
    user_id: Optional[int] = None
    
    class Config:
        from_attributes = True

# --- Helper functions ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    # Ограничиваем длину пароля 72 символами для совместимости с bcrypt
    return pwd_context.hash(password[:72])

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

@app.post("/expenses")
def add_expense(expense: ExpenseCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_expense = models.Expense(
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        date=expense.date or datetime.utcnow(),
        user_id=current_user.id
    )
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


@app.get("/expenses")
def get_expenses(
    category: Optional[str] = None,
    min_amount: Optional[float] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    sort_by: Optional[str] = "date",
    order: Optional[str] = "desc",
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    query = db.query(models.Expense).filter(models.Expense.user_id == current_user.id)
    
    # Фильтр по категории
    if category:
        query = query.filter(models.Expense.category == category)
    
    # Фильтр по минимальной сумме
    if min_amount:
        query = query.filter(models.Expense.amount >= min_amount)
    
    # Фильтр по дате (start_date)
    if start_date:
        query = query.filter(models.Expense.date >= start_date)
    
    # Фильтр по дате (end_date)
    if end_date:
        query = query.filter(models.Expense.date <= end_date)
    
    # Сортировка
    if sort_by == "amount":
        if order == "asc":
            query = query.order_by(models.Expense.amount.asc())
        else:
            query = query.order_by(models.Expense.amount.desc())
    elif sort_by == "title":
        if order == "asc":
            query = query.order_by(models.Expense.title.asc())
        else:
            query = query.order_by(models.Expense.title.desc())
    else:  # date
        if order == "asc":
            query = query.order_by(models.Expense.date.asc())
        else:
            query = query.order_by(models.Expense.date.desc())
    
    # Лимит записей
    if limit:
        query = query.limit(limit)
    
    return query.all()

@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    expense = db.query(models.Expense).filter(
        models.Expense.id == expense_id,
        models.Expense.user_id == current_user.id
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"message": "Deleted"}

@app.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Получить общую статистику"""
    expenses = db.query(models.Expense).filter(models.Expense.user_id == current_user.id).all()
    total = sum(e.amount for e in expenses)
    return {"total": total}

# --- Авторизация и регистрация ---

@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username}

@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Бюджетные лимиты ---

@app.post("/budget-limits", response_model=BudgetLimitResponse)
def create_budget_limit(
    budget_limit: BudgetLimitCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_budget = models.BudgetLimit(
        category=budget_limit.category,
        limit_amount=budget_limit.limit_amount,
        period=budget_limit.period,
        user_id=current_user.id
    )
    db.add(db_budget)
    db.commit()
    db.refresh(db_budget)
    return db_budget

@app.get("/budget-limits", response_model=List[BudgetLimitResponse])
def get_budget_limits(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.BudgetLimit).filter(
        models.BudgetLimit.user_id == current_user.id
    ).all()

@app.get("/budget-status")
def get_budget_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Проверяет превышение бюджетных лимитов"""
    limits = db.query(models.BudgetLimit).filter(
        models.BudgetLimit.user_id == current_user.id
    ).all()
    
    result = []
    now = datetime.utcnow()
    
    for limit in limits:
        # Определяем период
        if limit.period == "daily":
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif limit.period == "weekly":
            period_start = now - timedelta(days=now.weekday())
        else:  # monthly
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Считаем расходы за период
        query = db.query(func.sum(models.Expense.amount)).filter(
            models.Expense.user_id == current_user.id,
            models.Expense.date >= period_start
        )
        
        if limit.category:
            query = query.filter(models.Expense.category == limit.category)
        
        spent = query.scalar() or 0
        
        result.append({
            "category": limit.category or "Общий",
            "limit": limit.limit_amount,
            "spent": spent,
            "remaining": limit.limit_amount - spent,
            "period": limit.period,
            "exceeded": spent > limit.limit_amount
        })
    
    return result

# --- Графики / Статистика ---

@app.get("/charts/by-category")
def get_chart_by_category(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Данные для графика расходов по категориям"""
    query = db.query(
        models.Expense.category,
        func.sum(models.Expense.amount).label("total")
    ).filter(
        models.Expense.user_id == current_user.id
    )
    
    if start_date:
        query = query.filter(models.Expense.date >= start_date)
    if end_date:
        query = query.filter(models.Expense.date <= end_date)
    
    results = query.group_by(models.Expense.category).all()
    
    return [{"category": r.category or "Без категории", "total": r.total} for r in results]

@app.get("/charts/by-date")
def get_chart_by_date(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Данные для графика расходов по датам"""
    from sqlalchemy import extract
    
    query = db.query(
        extract('year', models.Expense.date).label('year'),
        extract('month', models.Expense.date).label('month'),
        extract('day', models.Expense.date).label('day'),
        func.sum(models.Expense.amount).label("total")
    ).filter(
        models.Expense.user_id == current_user.id
    )
    
    if start_date:
        query = query.filter(models.Expense.date >= start_date)
    if end_date:
        query = query.filter(models.Expense.date <= end_date)
    
    results = query.group_by(
        extract('year', models.Expense.date),
        extract('month', models.Expense.date),
        extract('day', models.Expense.date)
    ).order_by(
        extract('year', models.Expense.date),
        extract('month', models.Expense.date),
        extract('day', models.Expense.date)
    ).all()
    
    return [{"date": f"{int(r.year)}-{int(r.month):02d}-{int(r.day):02d}", "total": r.total} for r in results]

# Алиасы для фронтенда
@app.get("/charts/categories")
def get_categories_alias(start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return get_chart_by_category(start_date, end_date, db, current_user)

@app.get("/charts/daily")
def get_daily_alias(start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return get_chart_by_date(start_date, end_date, db, current_user)

@app.get("/budget/status")
def get_budget_status_alias(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return get_budget_status(db, current_user)

@app.post("/budget/limit")
def create_budget_limit_alias(budget_limit: BudgetLimitCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return create_budget_limit(budget_limit, db, current_user)

# --- Управление общим бюджетом пользователя ---

@app.get("/user-budget", response_model=UserBudgetResponse)
def get_user_budget(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Получить общий бюджет пользователя"""
    budget = db.query(models.UserBudget).filter(
        models.UserBudget.user_id == current_user.id
    ).first()
    
    if not budget:
        # Создаем бюджет по умолчанию если нет
        budget = models.UserBudget(budget_amount=0.0, user_id=current_user.id)
        db.add(budget)
        db.commit()
        db.refresh(budget)
    
    return budget

@app.put("/user-budget", response_model=UserBudgetResponse)
def update_user_budget(
    budget_data: UserBudgetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Обновить общий бюджет пользователя"""
    budget = db.query(models.UserBudget).filter(
        models.UserBudget.user_id == current_user.id
    ).first()
    
    if budget:
        budget.budget_amount = budget_data.budget_amount
    else:
        budget = models.UserBudget(budget_amount=budget_data.budget_amount, user_id=current_user.id)
        db.add(budget)
    
    db.commit()
    db.refresh(budget)
    return budget

@app.get("/user-budget/status")
def get_user_budget_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Получить статус общего бюджета (бюджет vs расходы)"""
    # Получаем бюджет
    budget = db.query(models.UserBudget).filter(
        models.UserBudget.user_id == current_user.id
    ).first()
    budget_amount = budget.budget_amount if budget else 0.0
    
    # Считаем общие расходы за месяц
    now = datetime.utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    total_spent = db.query(func.sum(models.Expense.amount)).filter(
        models.Expense.user_id == current_user.id,
        models.Expense.date >= period_start
    ).scalar() or 0.0
    
    remaining = budget_amount - total_spent
    percent = (total_spent / budget_amount * 100) if budget_amount > 0 else 0
    
    return {
        "budget": budget_amount,
        "spent": total_spent,
        "remaining": remaining,
        "percent_used": min(percent, 100),
        "exceeded": total_spent > budget_amount
    }

@app.get("/")
async def home():
    return FileResponse("frontend.html")
