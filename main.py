import os
import uvicorn
import secrets
from datetime import datetime, date
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, or_, text, func
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

# Полные названия филиалов
FILIALS = ["Филиал Сергели", "Филиал Циолковский"]

USERS = {
    "master1": {
        "password": os.environ.get("MASTER1_PASS", "byd101"),
        "name": "Абдулазиз (Мастер-приёмщик)",
        "is_admin": False
    },
    "master2": {
        "password": os.environ.get("MASTER2_PASS", "byd102"),
        "name": "Ровшан (Мастер-приёмщик)",
        "is_admin": False
    },
    "master3": {
        "password": os.environ.get("MASTER3_PASS", "byd103"),
        "name": "Шохрух (Мастер-приёмщик)",
        "is_admin": False
    },
    "master4": {
        "password": os.environ.get("MASTER4_PASS", "byd104"),
        "name": "Ориф (Филиал Циолковский)",
        "is_admin": False
    },
    "admin": {
        "password": os.environ.get("ADMIN_PASSWORD", "byd2026"),
        "name": "Администратор",
        "is_admin": True
    }
}

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    username = credentials.username
    password = credentials.password
    
    if username in USERS:
        user_info = USERS[username]
        if secrets.compare_digest(password, user_info["password"]):
            return {
                "username": username,
                "display_name": user_info["name"],
                "is_admin": user_info["is_admin"]
            }

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
    ev_mileage = Column(Integer, default=0)
    hev_mileage = Column(Integer, default=0)
    soh_percent = Column(Float, default=100.0)
    manufacture_year = Column(Integer, default=2023)
    status = Column(String, default="Принято")
    filial = Column(String, default="Филиал Сергели")
    created_by = Column(String, default="Мастер-приёмщик")
    created_at = Column(DateTime, default=datetime.now)
    discount_percent = Column(Float, default=0.0)
    owner = relationship("Client", back_populates="cars")
    works = relationship("WorkItem", back_populates="car", cascade="all, delete-orphan")
    parts = relationship("SparePart", back_populates="car", cascade="all, delete-orphan")

class WorkItem(Base):
    __tablename__ = "work_items"
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"))
    description = Column(String, nullable=False)
    price = Column(Float, default=0.0)
    car = relationship("Car", back_populates="works")

class SparePart(Base):
    __tablename__ = "spare_parts"
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"))
    name = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    price = Column(Float, default=0.0)
    car = relationship("Car", back_populates="parts")

class WarehousePart(Base):
    __tablename__ = "warehouse_parts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    part_code = Column(String, index=True, nullable=True)
    quantity = Column(Integer, default=0)
    price = Column(Float, default=0.0)
    filial = Column(String, default="Филиал Сергели")

Base.metadata.create_all(bind=engine)

migrations = [
    "ALTER TABLE cars ADD COLUMN IF NOT EXISTS created_by VARCHAR DEFAULT 'Мастер-приёмщик';",
    "ALTER TABLE cars ADD COLUMN IF NOT EXISTS created_at TIMESTAMP;",
    "UPDATE cars SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;",
    "ALTER TABLE cars ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'Принято';",
    "UPDATE cars SET status = 'Принято' WHERE status IS NULL;",
    "ALTER TABLE cars ADD COLUMN IF NOT EXISTS filial VARCHAR DEFAULT 'Филиал Сергели';",
    "UPDATE cars SET filial = 'Филиал Сергели' WHERE filial IS NULL;",
    "ALTER TABLE cars ADD COLUMN IF NOT EXISTS discount_percent FLOAT DEFAULT 0.0;",
    "ALTER TABLE cars ADD COLUMN IF NOT EXISTS ev_mileage INTEGER DEFAULT 0;",
    "ALTER TABLE cars ADD COLUMN IF NOT EXISTS hev_mileage INTEGER DEFAULT 0;",
    "UPDATE cars SET filial = 'Филиал Циолковский' WHERE filial = 'Циолковский' OR filial = 'Филиал Савковский';",
    "UPDATE warehouse_parts SET filial = 'Филиал Циолковский' WHERE filial = 'Циолковский' OR filial = 'Филиал Савковский';"
]

for statement in migrations:
    try:
        with engine.begin() as conn:
            conn.execute(text(statement))
    except Exception:
        if "IF NOT EXISTS" in statement:
            try:
                alt_statement = statement.replace(" IF NOT EXISTS", "")
                with engine.begin() as conn:
                    conn.execute(text(alt_statement))
            except Exception:
                pass

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

@app.get("/api/admin/daily-sum")
def get_daily_sum(
    date_str: str = "",
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin)
):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    cars = db.query(Car).filter(func.date(Car.created_at) == date_str).all()
    total_sum = 0.0
    for car in cars:
        works_sum = sum(w.price for w in car.works if w.price)
        parts_sum = sum(p.price * p.quantity for p in car.parts if p.price and p.quantity)
        subtotal = works_sum + parts_sum
        disc = min(10.0, max(0.0, car.discount_percent or 0.0))
        disc_amount = (subtotal * disc) / 100.0
        total_sum += (subtotal - disc_amount)

    return {
        "date": date_str,
        "total": total_sum,
        "cars_count": len(cars)
    }

@app.get("/warehouse", response_class=HTMLResponse)
def warehouse_page(
    request: Request,
    search: str = "",
    filial: str = "all",
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    query = db.query(WarehousePart)
    if filial and filial != "all":
        query = query.filter(WarehousePart.filial == filial)
    if search:
        s = f"%{search}%"
        query = query.filter(
            or_(
                WarehousePart.name.ilike(s),
                WarehousePart.part_code.ilike(s)
            )
        )
    parts = query.order_by(WarehousePart.id.asc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="warehouse.html",
        context={
            "parts": parts,
            "search": search,
            "current_filial": filial,
            "filials": FILIALS,
            "current_user": user
        }
    )

@app.post("/warehouse/add")
def add_warehouse_part(
    name: str = Form(...),
    part_code: str = Form(""),
    quantity: int = Form(0),
    price: float = Form(0.0),
    filial: str = Form("Филиал Сергели"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin)
):
    part = WarehousePart(
        name=name.strip(),
        part_code=part_code.strip().upper(),
        quantity=quantity,
        price=price,
        filial=filial
    )
    db.add(part)
    db.commit()
    return RedirectResponse(url="/warehouse", status_code=303)

@app.post("/warehouse/update/{part_id}")
def update_warehouse_part(
    part_id: int,
    quantity: int = Form(...),
    price: float = Form(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin)
):
    part = db.query(WarehousePart).filter(WarehousePart.id == part_id).first()
    if part:
        part.quantity = quantity
        part.price = price
        db.commit()
    return RedirectResponse(url="/warehouse", status_code=303)

@app.post("/warehouse/delete/{part_id}")
def delete_warehouse_part(
    part_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin)
):
    part = db.query(WarehousePart).filter(WarehousePart.id == part_id).first()
    if part:
        db.delete(part)
        db.commit()
    return RedirectResponse(url="/warehouse", status_code=303)

@app.get("/", response_class=HTMLResponse)
def index(
    request: Request, 
    search: str = "", 
    filial: str = "all", 
    db: Session = Depends(get_db), 
    user: dict = Depends(get_current_user)
):
    query = db.query(Car).join(Client)
    
    if filial and filial != "all":
        query = query.filter(Car.filial == filial)
        
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
    cars = query.order_by(Car.id.desc()).all()

    grouped_cars = {}
    for car in cars:
        if car.created_at and hasattr(car.created_at, 'strftime'):
            date_str = car.created_at.strftime("%d.%m.%Y")
        elif car.created_at:
            date_str = str(car.created_at)[:10]
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
        
        if date_str not in grouped_cars:
            grouped_cars[date_str] = []
        grouped_cars[date_str].append(car)

    today_str = datetime.now().strftime("%d.%m.%Y")
    today_date_iso = datetime.now().strftime("%Y-%m-%d")
    today_cars = grouped_cars.get(today_str, [])
    today_count = len(today_cars)
    total_count = len(cars)

    today_revenue = 0.0
    if user["is_admin"]:
        for car in today_cars:
            w_sum = sum(w.price for w in car.works if w.price)
            p_sum = sum(p.price * p.quantity for p in car.parts if p.price and p.quantity)
            subt = w_sum + p_sum
            disc = min(10.0, max(0.0, car.discount_percent or 0.0))
            today_revenue += (subt - (subt * disc / 100.0))

    accepted_count = sum(1 for c in cars if (c.status == "Принято" or not c.status))
    in_progress_count = sum(1 for c in cars if c.status == "В работе")
    ready_count = sum(1 for c in cars if c.status == "Готово")
    in_service_count = accepted_count + in_progress_count + ready_count

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "grouped_cars": grouped_cars, 
            "search": search, 
            "current_filial": filial,
            "filials": FILIALS,
            "current_user": user,
            "today_count": today_count,
            "today_revenue": today_revenue,
            "today_date_iso": today_date_iso,
            "total_count": total_count,
            "today_str": today_str,
            "in_service_count": in_service_count,
            "accepted_count": accepted_count,
            "in_progress_count": in_progress_count,
            "ready_count": ready_count
        }
    )

@app.get("/new-entry", response_class=HTMLResponse)
def new_entry_page(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request,
        name="new_entry.html",
        context={"current_user": user, "filials": FILIALS}
    )

@app.post("/create-entry")
def create_entry(
    full_name: str = Form(...),
    phone: str = Form(...),
    brand_model: str = Form(...),
    plate_number: str = Form(...),
    vin_code: str = Form(...),
    engine_type: str = Form(...),
    ev_mileage: int = Form(0),
    hev_mileage: int = Form(0),
    mileage: int = Form(0),
    manufacture_year: int = Form(2023),
    soh_percent: float = Form(100.0),
    filial: str = Form("Филиал Сергели"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    plate_number = plate_number.strip().upper()
    vin_code = vin_code.strip().upper()

    total_odo = mileage if mileage > 0 else (ev_mileage + hev_mileage)

    client = db.query(Client).filter(Client.phone == phone).first()
    if not client:
        client = Client(full_name=full_name, phone=phone)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client.full_name = full_name
        db.commit()

    car = Car(
        owner_id=client.id,
        brand_model=brand_model,
        plate_number=plate_number,
        vin_code=vin_code,
        engine_type=engine_type,
        ev_mileage=ev_mileage,
        hev_mileage=hev_mileage,
        mileage=total_odo,
        manufacture_year=manufacture_year,
        soh_percent=soh_percent,
        status="Принято",
        filial=filial,
        created_by=user["display_name"],
        created_at=datetime.now()
    )
    db.add(car)
    db.commit()
    db.refresh(car)

    return RedirectResponse(url=f"/act/{car.id}", status_code=303)

@app.post("/update-discount/{car_id}")
def update_discount(
    car_id: int,
    discount_percent: float = Form(0.0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    if discount_percent < 0:
        discount_percent = 0.0
    if discount_percent > 10.0:
        discount_percent = 10.0

    car = db.query(Car).filter(Car.id == car_id).first()
    if car:
        car.discount_percent = discount_percent
        db.commit()
    return RedirectResponse(url=f"/act/{car_id}", status_code=303)

@app.post("/update-status/{car_id}")
def update_status(
    car_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    car = db.query(Car).filter(Car.id == car_id).first()
    if car:
        car.status = status
        db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/edit-car/{car_id}", response_class=HTMLResponse)
def edit_car_page(request: Request, car_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        return HTMLResponse(content="Запись не найдена", status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="edit_car.html",
        context={"car": car, "current_user": user, "filials": FILIALS}
    )

@app.post("/update-car/{car_id}")
def update_car(
    car_id: int,
    full_name: str = Form(...),
    phone: str = Form(...),
    brand_model: str = Form(...),
    plate_number: str = Form(...),
    vin_code: str = Form(...),
    engine_type: str = Form(...),
    ev_mileage: int = Form(0),
    hev_mileage: int = Form(0),
    mileage: int = Form(0),
    manufacture_year: int = Form(2023),
    soh_percent: float = Form(100.0),
    status: str = Form("Принято"),
    filial: str = Form("Филиал Сергели"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        return HTMLResponse(content="Запись не найдена", status_code=404)
    
    total_odo = mileage if mileage > 0 else (ev_mileage + hev_mileage)

    car.brand_model = brand_model
    car.plate_number = plate_number.strip().upper()
    car.vin_code = vin_code.strip().upper()
    car.engine_type = engine_type
    car.ev_mileage = ev_mileage
    car.hev_mileage = hev_mileage
    car.mileage = total_odo
    car.manufacture_year = manufacture_year
    car.soh_percent = soh_percent
    car.status = status
    car.filial = filial
    
    if car.owner:
        car.owner.full_name = full_name
        car.owner.phone = phone

    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/add-work/{car_id}")
def add_work(
    car_id: int,
    description: str = Form(...),
    price: str = Form("0"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    try:
        parsed_price = float(str(price).replace(",", ".").replace(" ", "")) if price else 0.0
    except ValueError:
        parsed_price = 0.0

    work = WorkItem(car_id=car_id, description=description.strip(), price=parsed_price)
    db.add(work)
    db.commit()
    return RedirectResponse(url=f"/act/{car_id}", status_code=303)

@app.post("/add-part/{car_id}")
def add_part(
    car_id: int,
    name: str = Form(...),
    quantity: int = Form(1),
    price: str = Form("0"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    name_clean = name.strip()
    
    try:
        parsed_price = float(str(price).replace(",", ".").replace(" ", "")) if price else 0.0
    except ValueError:
        parsed_price = 0.0

    car = db.query(Car).filter(Car.id == car_id).first()
    car_filial = car.filial if car else "Филиал Сергели"

    wh_part = db.query(WarehousePart).filter(
        or_(
            func.lower(WarehousePart.name) == name_clean.lower(),
            func.lower(WarehousePart.part_code) == name_clean.lower()
        ),
        WarehousePart.filial == car_filial
    ).first()

    if not wh_part:
        wh_part = db.query(WarehousePart).filter(
            or_(
                func.lower(WarehousePart.name) == name_clean.lower(),
                func.lower(WarehousePart.part_code) == name_clean.lower()
            )
        ).first()

    part_display_name = name_clean

    if wh_part:
        part_display_name = wh_part.name
        if parsed_price == 0.0:
            parsed_price = wh_part.price
        wh_part.quantity = max(0, wh_part.quantity - quantity)

    part = SparePart(car_id=car_id, name=part_display_name, quantity=quantity, price=parsed_price)
    db.add(part)
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

@app.post("/delete-part/{part_id}")
def delete_part(part_id: int, db: Session = Depends(get_db), user: dict = Depends(require_admin)):
    part = db.query(SparePart).filter(SparePart.id == part_id).first()
    if part:
        car_id = part.car_id
        car = db.query(Car).filter(Car.id == car_id).first()
        car_filial = car.filial if car else "Филиал Сергели"

        wh_part = db.query(WarehousePart).filter(
            or_(
                func.lower(WarehousePart.name) == part.name.lower(),
                func.lower(WarehousePart.part_code) == part.name.lower()
            ),
            WarehousePart.filial == car_filial
        ).first()
        if not wh_part:
            wh_part = db.query(WarehousePart).filter(
                or_(
                    func.lower(WarehousePart.name) == part.name.lower(),
                    func.lower(WarehousePart.part_code) == part.name.lower()
                )
            ).first()

        if wh_part:
            wh_part.quantity += part.quantity

        db.delete(part)
        db.commit()
        return RedirectResponse(url=f"/act/{car_id}", status_code=303)
    return RedirectResponse(url="/", status_code=303)

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
    
    works_sum = sum(w.price for w in car.works if w.price)
    parts_sum = sum(p.price * p.quantity for p in car.parts if p.price and p.quantity)
    subtotal = works_sum + parts_sum
    
    discount_percent = min(10.0, max(0.0, car.discount_percent or 0.0))
    discount_amount = (subtotal * discount_percent) / 100.0
    total_sum = subtotal - discount_amount
    
    return templates.TemplateResponse(
        request=request,
        name="act_print.html",
        context={
            "car": car, 
            "works_sum": works_sum,
            "parts_sum": parts_sum,
            "subtotal": subtotal,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "total_sum": total_sum, 
            "current_user": user
        }
    )

@app.get("/inspection/{car_id}", response_class=HTMLResponse)
def print_inspection(request: Request, car_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        return HTMLResponse(content="Запись не найдена", status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="inspection_act.html",
        context={"car": car, "current_user": user}
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
