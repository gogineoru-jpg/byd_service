import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sqlalchemy import func

app = Flask(__name__)
app.config['SECRET_KEY'] = 'byd-help-service-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///service.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- МОДЕЛИ БАЗЫ ДАННЫХ ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin' или 'user'

class Owner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    cars = db.relationship('Car', backref='owner', lazy=True)

class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand_model = db.Column(db.String(100), nullable=False)
    plate_number = db.Column(db.String(20), nullable=False)
    vin_code = db.Column(db.String(50))
    mileage = db.Column(db.Integer, default=0)
    key_count = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0.0)  # Сумма заказа / ремонта
    status = db.Column(db.String(50), default='В работе')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('owner.id'), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- МАРШРУТЫ СТРАНИЦ ---

@app.route('/')
@login_required
def index():
    cars = Car.query.order_by(Car.created_at.desc()).all()
    return render_template('index.html', cars=cars)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверный логин или пароль')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/new', methods=['GET', 'POST'])
@login_required
def new_entry():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        brand_model = request.form.get('brand_model')
        plate_number = request.form.get('plate_number')
        vin_code = request.form.get('vin_code')
        mileage = request.form.get('mileage', 0)
        key_count = request.form.get('key_count', 1)
        price = request.form.get('price', 0.0)

        owner = Owner(full_name=full_name, phone=phone)
        db.session.add(owner)
        db.session.flush()

        car = Car(
            brand_model=brand_model,
            plate_number=plate_number,
            vin_code=vin_code,
            mileage=int(mileage) if mileage else 0,
            key_count=int(key_count) if key_count else 1,
            price=float(price) if price else 0.0,
            owner_id=owner.id
        )
        db.session.add(car)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('new_entry.html')

@app.route('/act/<int:id>')
@login_required
def act_print(id):
    car = Car.query.get_or_404(id)
    return render_template('act_print.html', car=car)

# --- API ДЛЯ АДМИНА: РАСЧЕТ ДНЕВНОЙ КАССЫ ---

@app.route('/api/admin/daily-sum', methods=['GET'])
@login_required
def get_daily_sum():
    if getattr(current_user, 'role', None) != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    selected_date = request.args.get('date')
    if not selected_date:
        return jsonify({'error': 'Date is required'}), 400

    total_sum = db.session.query(func.sum(Car.price))\
        .filter(func.date(Car.created_at) == selected_date)\
        .scalar() or 0

    return jsonify({
        'date': selected_date,
        'total': float(total_sum)
    })

# --- ЗАПУСК СЕРВЕРА И ИНИЦИАЛИЗАЦИЯ БД ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Автоматическое создание учетной записи admin, если ее нет
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', password='adminpassword', role='admin')
            db.session.add(admin_user)
            db.session.commit()
            print("Учетная запись администратора создана (Логин: admin, Пароль: adminpassword)")
            
    app.run(debug=True, host='0.0.0.0', port=5000)
