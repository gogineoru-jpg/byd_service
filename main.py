import os
import uvicorn
import secrets
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, or_
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./byd_service.db")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL and DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

security = HTTPBasic()

# Настройки доступа
STAFF_USER = os.environ.get("STAFF_USER", "staff")
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "byd123")

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "byd2026")

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    is_admin_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    is_admin_pass = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if is_admin_user and is_admin_pass:
        return {"username": credentials.username, "is_admin": True}

    is_staff_user = secrets.compare_digest(credentials.username, STAFF_USER)
    is_staff_pass = secrets.compare_digest(credentials.password, STAFF_PASSWORD)
    if is_staff_user and is_staff_pass:
        return {"username": credentials.username, "is_admin": False}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверный логин или пароль",
        headers={"WWW-Authenticate": "Basic"},
    )

def require_admin(user: dict = Depends(get_current_user)):
    if not user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуются права администратора",
            headers={"WWW-Authenticate": "Basic realm='Admin area'"},
        )
    return user

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    phone = Column(String, index=True)
    cars = relationship("Car", back_populates="owner")

class Car(Base):
    __tablename__ = "cars"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("clients.id"))
    brand_model = Column(String, default="BYD")
    plate_number = Column(String, index=True)
    vin_code = Column(String, index=True)
    engine_type = Column(String)
    mileage = Column(Integer, default=0)
    soh_percent = Column(Float, default=100.0)
    manufacture_year = Column(Integer, default=2023)
    owner = relationship("Client", back_populates="cars")
    works = relationship("WorkItem", back_populates="car", cascade="all, delete-orphan")

class WorkItem(Base):
    __tablename__ = "work_items"
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"))
    description = Column(String, nullable=False)
    price = Column(Float, default=0.0)
    car = relationship("Car", back_populates="works")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="BYD help CRM")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/admin")
def admin_login(user: dict = Depends(require_admin)):
    return RedirectResponse(url="/", status_code=303)

@app.get("/", response_class=HTMLResponse)
def index(request: Request, search: str = "", db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    query = db.query(Car).join(Client)
    if search:
        s = f"%{search}%"
        query = query.filter(
            or_(
                Car.plate_number.ilike(s),
                Car.vin_code.ilike(s),
                Client.full_name.ilike(s),
                Client.phone.ilike(s)
            )
        )
    cars = query.all()
    return templates.TemplateResponse(request=request, name="index.html", context={"cars": cars, "search": search, "is_admin": user["is_admin"]})

@app.get("/new-entry", response_class=HTMLResponse)
def new_entry_page(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="new_entry.html")

@app.post("/create-entry")
def create_entry(
    full_name: str = Form(...),
    phone: str = Form(...),
    brand_model: str = Form(...),
    plate_number: str = Form(...),
    vin_code: str = Form(...),
    engine_type: str = Form(...),
    mileage: int = Form(0),
    manufacture_year: int = Form(2023),
    soh_percent: float = Form(100.0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    client = db.query(Client).filter(Client.phone == phone).first()
    if not client:
        client = Client(full_name=full_name, phone=phone)
        db.add(client)
        db.commit()
        db.refresh(client)

    car = Car(
        owner_id=client.id,
        brand_model=brand_model,
        plate_number=plate_number,
        vin_code=vin_code,
        engine_type=engine_type,
        mileage=mileage,
        manufacture_year=manufacture_year,
        soh_percent=soh_percent
    )
    db.add(car)
    db.commit()
    db.refresh(car)

    return RedirectResponse(url=f"/act/{car.id}", status_code=303)

@app.post("/add-work/{car_id}")
def add_work(
    car_id: int,
    description: str = Form(...),
    price: float = Form(0.0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    work = WorkItem(car_id=car_id, description=description, price=price)
    db.add(work)
    db.commit()
    return RedirectResponse(url=f"/act/{car_id}", status_code=303)

@app.post("/delete-work/{work_id}")
def delete_work(work_id: int, db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    work = db.query(WorkItem).filter(WorkItem.id == work_id).first()
    car_id = work.car_id if work else 1
    if work:
        db.delete(work)
        db.commit()
    return RedirectResponse(url=f"/act/{car_id}", status_code=303)

@app.post("/delete-car/{car_id}")
def delete_car(car_id: int, db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    car = db.query(Car).filter(Car.id == car_id).first()
    if car:
        db.delete(car)
        db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/act/{car_id}", response_class=HTMLResponse)
def print_act(request: Request, car_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        return HTMLResponse(content="Запись не найдена", status_code=404)
    total_sum = sum(w.price for w in car.works)
    return templates.TemplateResponse(request=request, name="act_print.html", context={"car": car, "total_sum": total_sum, "is_admin": user["is_admin"]})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
