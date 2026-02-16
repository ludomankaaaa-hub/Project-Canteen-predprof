# single_file_app.py
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Инициализация приложения
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school_canteen.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'

# Инициализация базы данных
db = SQLAlchemy(app)


# ================== МОДЕЛИ БАЗЫ ДАННЫХ ==================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student, cook, admin
    email = db.Column(db.String(120), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    grade = db.Column(db.String(10), nullable=False)
    allergies = db.Column(db.Text, nullable=True)
    preferences = db.Column(db.Text, nullable=True)
    balance = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f'<Student {self.id}>'


class Menu(db.Model):
    __tablename__ = 'menus'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)  # breakfast, lunch
    dish_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    available_count = db.Column(db.Integer, default=100)

    def __repr__(self):
        return f'<Menu {self.dish_name} ({self.date})>'

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'meal_type': self.meal_type,
            'meal_type_display': 'Завтрак' if self.meal_type == 'breakfast' else 'Обед',
            'dish_name': self.dish_name,
            'description': self.description,
            'price': self.price,
            'available_count': self.available_count
        }


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    menu_id = db.Column(db.Integer, db.ForeignKey('menus.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, paid, issued
    payment_type = db.Column(db.String(20), nullable=True)  # single, subscription

    def __repr__(self):
        return f'<Order {self.id} ({self.status})>'


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    method = db.Column(db.String(50), nullable=False)  # card, cash
    status = db.Column(db.String(20), default='completed')

    def __repr__(self):
        return f'<Payment {self.id} ({self.amount})>'


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.String(20), nullable=False)  # кг, л, шт
    current_quantity = db.Column(db.Float, default=0)
    min_quantity = db.Column(db.Float, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Product {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'unit': self.unit,
            'current_quantity': self.current_quantity,
            'min_quantity': self.min_quantity,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_low_stock': self.is_low_stock,
            'progress_percentage': self.progress_percentage
        }

    @property
    def is_low_stock(self):
        return self.current_quantity < self.min_quantity

    @property
    def progress_percentage(self):
        max_quantity = self.min_quantity * 3
        if max_quantity <= 0:
            return 0
        percentage = (self.current_quantity / max_quantity) * 100
        return min(percentage, 100)


class PurchaseRequest(db.Model):
    __tablename__ = 'purchase_requests'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    request_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def __repr__(self):
        return f'<PurchaseRequest {self.id} ({self.status})>'


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    dish_name = db.Column(db.String(200), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text, nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Review {self.id} ({self.rating} stars)>'


# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

def get_current_user():
    """Получить текущего пользователя из сессии"""
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return user
    return None


def login_required(f):
    """Декоратор для проверки авторизации"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# Контекстный процессор для шаблонов
@app.context_processor
def utility_processor():
    import math
    return dict(
        get_current_user=get_current_user,
        datetime=datetime,
        min=min,
        max=max,
        round=round,
        len=len,
        str=str,
        int=int,
        float=float,
        abs=abs
    )


# ================== СОЗДАНИЕ БАЗЫ ДАННЫХ ==================

def create_database():
    """Создание базы данных с тестовыми данными"""
    with app.app_context():
        # Создаем все таблицы
        db.create_all()
        logger.info("✅ Таблицы созданы")

        # Создаем тестовых пользователей, если их нет
        if not User.query.first():
            # Повар
            cook = User(
                username='cook',
                password=generate_password_hash('cook123'),
                role='cook',
                email='cook@school.ru'
            )
            db.session.add(cook)

            # Администратор
            admin = User(
                username='admin',
                password=generate_password_hash('admin123'),
                role='admin',
                email='admin@school.ru'
            )
            db.session.add(admin)

            # Ученик
            student_user = User(
                username='student',
                password=generate_password_hash('student123'),
                role='student',
                email='student@school.ru'
            )
            db.session.add(student_user)
            db.session.commit()

            # Профиль ученика
            student = Student(
                user_id=student_user.id,
                grade='10A',
                allergies='Нет',
                preferences='Вегетарианец',
                balance=1000.0
            )
            db.session.add(student)

            # Тестовые продукты
            products = [
                Product(name='Мука пшеничная', unit='кг', current_quantity=10.0, min_quantity=5.0),
                Product(name='Сахар', unit='кг', current_quantity=5.0, min_quantity=3.0),
                Product(name='Яйца', unit='шт', current_quantity=50.0, min_quantity=30.0),
                Product(name='Молоко', unit='л', current_quantity=20.0, min_quantity=10.0),
                Product(name='Картофель', unit='кг', current_quantity=30.0, min_quantity=20.0),
            ]

            for product in products:
                db.session.add(product)

            # Меню на сегодня
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)

            # Создаем меню на 2 дня
            menu_items = []

            for day_date in [today, tomorrow]:
                # Завтрак
                breakfast_items = [
                    ("Каша овсяная с ягодами", "Овсяная каша с свежими ягодами и медом", 150.0),
                    ("Омлет с овощами", "Пышный омлет с помидорами, болгарским перцем и зеленью", 180.0),
                    ("Блины с творогом", "Тонкие блины с начинкой из творога и изюма", 200.0),
                ]

                for name, desc, price in breakfast_items:
                    menu_item = Menu(
                        date=day_date,
                        meal_type='breakfast',
                        dish_name=name,
                        description=desc,
                        price=price,
                        available_count=50
                    )
                    menu_items.append(menu_item)

                # Обед
                lunch_items = [
                    ("Суп куриный с лапшой", "Ароматный куриный бульон с домашней лапшой и зеленью", 200.0),
                    ("Котлета куриная с картофельным пюре", "Нежная куриная котлета с картофельным пюре", 250.0),
                    ("Рыба запеченная с овощами", "Филе рыбы, запеченное с картофелем и морковью", 280.0),
                ]

                for name, desc, price in lunch_items:
                    menu_item = Menu(
                        date=day_date,
                        meal_type='lunch',
                        dish_name=name,
                        description=desc,
                        price=price,
                        available_count=50
                    )
                    menu_items.append(menu_item)

            db.session.add_all(menu_items)
            db.session.commit()

            logger.info("✅ Тестовые данные созданы")
            print("\n" + "=" * 60)
            print("🎉 БАЗА ДАННЫХ ГОТОВА!")
            print("=" * 60)
            print("\n🔑 ДАННЫЕ ДЛЯ ВХОДА:")
            print("👨‍🍳 Повар: cook / cook123")
            print("👨‍💼 Админ: admin / admin123")
            print("👨‍🎓 Ученик: student / student123")
            print("=" * 60)


# ================== МАРШРУТЫ ==================

@app.route('/')
def index():
    """Главная страница"""
    user = get_current_user()
    return render_template('index.html', user=user)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if 'user_id' in session:
        user = get_current_user()
        if user:
            if user.role == 'student':
                return redirect(url_for('student_dashboard'))
            elif user.role == 'cook':
                return redirect(url_for('cook_dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role

            flash(f'Добро пожаловать, {user.username}!', 'success')

            if user.role == 'student':
                return redirect(url_for('student_dashboard'))
            elif user.role == 'cook':
                return redirect(url_for('cook_dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin_dashboard'))

        flash('Неверный логин или пароль', 'danger')
        return render_template('login.html', error='Неверный логин или пароль')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        email = request.form.get('email')
        grade = request.form.get('grade', '')
        allergies = request.form.get('allergies', '')
        preferences = request.form.get('preferences', '')

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'danger')
            return render_template('register.html', error='Пользователь с таким именем уже существует')

        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            password=hashed_password,
            role=role,
            email=email
        )

        db.session.add(new_user)
        db.session.commit()

        if role == 'student':
            student = Student(
                user_id=new_user.id,
                grade=grade,
                allergies=allergies,
                preferences=preferences,
                balance=0.0
            )
            db.session.add(student)
            db.session.commit()

        session['user_id'] = new_user.id
        session['username'] = new_user.username
        session['role'] = new_user.role

        flash('Регистрация прошла успешно!', 'success')

        if role == 'student':
            return redirect(url_for('student_dashboard'))
        elif role == 'cook':
            return redirect(url_for('cook_dashboard'))
        elif role == 'admin':
            return redirect(url_for('admin_dashboard'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    """Выход из системы"""
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


# Кабинет ученика
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    """Личный кабинет ученика"""
    user = get_current_user()

    if user.role != 'student':
        flash('Доступ запрещен. Требуется роль ученика.', 'danger')
        return redirect(url_for('index'))

    student = Student.query.filter_by(user_id=user.id).first()
    if not student:
        flash('Профиль ученика не найден', 'danger')
        return redirect(url_for('logout'))

    today = datetime.now().date()

    # Заказы ученика
    today_orders = Order.query.filter(
        Order.student_id == student.id,
        db.func.date(Order.order_date) == today
    ).all()

    # Меню на сегодня
    today_menu = Menu.query.filter_by(date=today).order_by(Menu.meal_type, Menu.dish_name).all()

    return render_template('student_dashboard.html',
                           student=student,
                           user=user,
                           today_orders=today_orders,
                           today_menu=today_menu,
                           today_date=today)


@app.route('/order/create', methods=['POST'])
@login_required
def create_order_frontend():
    """Создание заказа через фронтенд"""
    try:
        user = get_current_user()

        if user.role != 'student':
            flash('Только ученики могут создавать заказы', 'danger')
            return redirect(url_for('index'))

        menu_id = request.form.get('menu_id')

        student = Student.query.filter_by(user_id=user.id).first()
        if not student:
            flash('Профиль ученика не найден', 'danger')
            return redirect(url_for('student_dashboard'))

        menu = Menu.query.get(menu_id)
        if not menu:
            flash('Блюдо не найдено', 'danger')
            return redirect(url_for('student_dashboard'))

        if menu.available_count <= 0:
            flash('Это блюдо закончилось', 'warning')
            return redirect(url_for('student_dashboard'))

        # Проверяем баланс
        if student.balance < menu.price:
            flash('Недостаточно средств на балансе', 'warning')
            return redirect(url_for('student_dashboard'))

        # Создаем заказ
        new_order = Order(
            student_id=student.id,
            menu_id=menu.id,
            status='pending'
        )

        db.session.add(new_order)
        menu.available_count -= 1
        student.balance -= menu.price  # Списание средств
        db.session.commit()

        flash(f'Заказ "{menu.dish_name}" создан! Средства списаны с баланса.', 'success')
        return redirect(url_for('student_dashboard'))

    except Exception as e:
        logger.error(f"Ошибка при создании заказа: {e}")
        flash('Произошла ошибка при создании заказа', 'danger')
        return redirect(url_for('student_dashboard'))

# Кабинет повара
@app.route('/cook/dashboard')
@login_required
def cook_dashboard():
    """Личный кабинет повара"""
    user = get_current_user()

    if user.role != 'cook':
        flash('Доступ запрещен. Требуется роль повара.', 'danger')
        return redirect(url_for('index'))

    today = datetime.now().date()
    today_orders = Order.query.filter(db.func.date(Order.order_date) == today).all()
    products = Product.query.order_by(Product.name).all()
    purchase_requests = PurchaseRequest.query.filter_by(status='pending').all()

    # Получаем информацию о меню для заказов
    orders_with_menu = []
    for order in today_orders:
        menu_item = Menu.query.get(order.menu_id) if order.menu_id else None
        orders_with_menu.append({
            'id': order.id,
            'menu_item': menu_item,
            'status': order.status,
            'menu_id': order.menu_id
        })

    return render_template('cook_dashboard.html',
                           user=user,
                           today_orders=orders_with_menu,  # Используем новую структуру
                           products=products,
                           purchase_requests=purchase_requests,
                           today_date=today,
                           Menu=Menu)  # Добавляем модель Menu в контекст

# Кабинет администратора
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Личный кабинет администратора"""
    user = get_current_user()

    if user.role != 'admin':
        flash('Доступ запрещен. Требуется роль администратора.', 'danger')
        return redirect(url_for('index'))

    total_users = User.query.count()
    total_students = User.query.filter_by(role='student').count()
    total_cooks = User.query.filter_by(role='cook').count()
    total_admins = User.query.filter_by(role='admin').count()

    total_orders = Order.query.count()
    today = datetime.now().date()
    today_orders = Order.query.filter(db.func.date(Order.order_date) == today).count()

    total_payments = Payment.query.count()
    total_revenue = db.session.query(db.func.sum(Payment.amount)).scalar() or 0

    total_reviews = Review.query.count()
    avg_rating = db.session.query(db.func.avg(Review.rating)).scalar() or 0

    purchase_requests = PurchaseRequest.query.all()
    pending_requests = PurchaseRequest.query.filter_by(status='pending').all()

    recent_users = User.query.order_by(User.id.desc()).limit(5).all()
    recent_reviews = Review.query.order_by(Review.date.desc()).limit(5).all()

    return render_template('admin_dashboard.html',
                           user=user,
                           total_users=total_users,
                           total_students=total_students,
                           total_cooks=total_cooks,
                           total_admins=total_admins,
                           total_orders=total_orders,
                           today_orders=today_orders,
                           total_payments=total_payments,
                           total_revenue=total_revenue,
                           total_reviews=total_reviews,
                           avg_rating=avg_rating,
                           purchase_requests=purchase_requests,
                           pending_requests=pending_requests,
                           recent_users=recent_users,
                           recent_reviews=recent_reviews,
                           today_date=datetime.now().date())


# Меню
@app.route('/menu')
@login_required
def menu():
    """Страница с меню"""
    user = get_current_user()
    date_str = request.args.get('date')

    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date = datetime.now().date()
    else:
        date = datetime.now().date()

    menus = Menu.query.filter_by(date=date).order_by(Menu.meal_type, Menu.dish_name).all()

    return render_template('menu.html',
                           user=user,
                           menus=menus,
                           current_date=date)


# Статистика закупок
@app.route('/purchase-statistics')
@login_required
def purchase_statistics():
    """Статистика закупок для повара"""
    user = get_current_user()

    if user.role != 'cook':
        flash('Доступ запрещен. Требуется роль повара.', 'danger')
        return redirect(url_for('index'))

    products = Product.query.all()
    purchase_requests = PurchaseRequest.query.order_by(PurchaseRequest.request_date.desc()).all()

    total_products = len(products)
    low_stock_count = len([p for p in products if p.current_quantity < p.min_quantity])
    total_requests = len(purchase_requests)
    pending_requests = len([r for r in purchase_requests if r.status == 'pending'])
    approved_requests = len([r for r in purchase_requests if r.status == 'approved'])
    low_stock_products = [p for p in products if p.current_quantity < p.min_quantity]
    recent_requests = purchase_requests[:10]

    return render_template('purchase_statistics.html',
                           user=user,
                           products=products,
                           purchase_requests=purchase_requests,
                           total_products=total_products,
                           low_stock_count=low_stock_count,
                           total_requests=total_requests,
                           pending_requests=pending_requests,
                           approved_requests=approved_requests,
                           low_stock_products=low_stock_products,
                           recent_requests=recent_requests)


# API для продуктов
@app.route('/api/products', methods=['GET'])
def api_get_products():
    """Получить все продукты"""
    products = Product.query.order_by(Product.name).all()
    result = [product.to_dict() for product in products]
    return jsonify(result), 200


@app.route('/api/products', methods=['POST'])
@login_required
def api_create_product():
    """Создать новый продукт"""
    try:
        user = get_current_user()
        if user.role != 'cook':
            return jsonify({'error': 'Требуется роль повара'}), 403

        data = request.get_json()

        name = data.get('name', '').strip()
        unit = data.get('unit', '').strip()
        current_quantity = data.get('current_quantity', 0)
        min_quantity = data.get('min_quantity', 10)

        if not name:
            return jsonify({'error': 'Название продукта обязательно'}), 400
        if not unit:
            return jsonify({'error': 'Единица измерения обязательна'}), 400

        try:
            current_qty = float(current_quantity)
            min_qty = float(min_quantity)
        except (ValueError, TypeError):
            return jsonify({'error': 'Количество должно быть числом'}), 400

        product = Product(
            name=name,
            unit=unit,
            current_quantity=current_qty,
            min_quantity=min_qty
        )

        db.session.add(product)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Продукт успешно добавлен',
            'product': product.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# API для заказов
@app.route('/api/orders/<int:order_id>/issue', methods=['POST'])
@login_required
def api_issue_order(order_id):
    """Отметить заказ как выданный"""
    user = get_current_user()
    if user.role != 'cook':
        return jsonify({'message': 'Требуется роль повара'}), 403

    order = Order.query.get(order_id)
    if not order:
        return jsonify({'message': 'Заказ не найден'}), 404

    if order.status != 'paid':
        return jsonify({'message': 'Заказ еще не оплачен'}), 400

    order.status = 'issued'
    db.session.commit()

    return jsonify({'message': 'Заказ отмечен как выданный'}), 200


# ================== ЗАПУСК ==================

if __name__ == '__main__':
    # Создаем новую базу данных
    create_database()

    # Запускаем приложение
    print("\n🚀 Запуск приложения...")
    print("🌐 Откройте в браузере: http://127.0.0.1:5000")
    app.run(debug=True, port=5000, host='0.0.0.0')
