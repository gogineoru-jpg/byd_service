import os
import uvicorn
from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, or_
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

DATABASE_URL = "sqlite:///./byd_service.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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

Base.metadata.create_all(bind=engine)

app = FastAPI(title="BYD Service CRM")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def index(request: Request, search: str = "", db: Session = Depends(get_db)):
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
    return templates.TemplateResponse("index.html", {"request": request, "cars": cars, "search": search})

@app.get("/new-entry", response_class=HTMLResponse)
def new_entry_page(request: Request):
    return templates.TemplateResponse("new_entry.html", {"request": request})

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
    db: Session = Depends(get_db)
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

@app.get("/act/{car_id}", response_class=HTMLResponse)
def print_act(request: Request, car_id: int, db: Session = Depends(get_db)):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        return HTMLResponse(content="Запись не найдена", status_code=404)
    return templates.TemplateResponse("act_print.html", {"request": request, "car": car})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
    uvicorn.run("main:app", host="0.0.0.0", port=port)
