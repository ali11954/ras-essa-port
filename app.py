from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import os
import json
import plotly
import plotly.express as px
import pandas as pd
from io import BytesIO
from functools import wraps
from config import Config
from forms import LoginForm, EmployeeForm, ShipForm, TeamForm, ReportForm, UserForm, UserEditForm, OperationForm
from datetime import datetime, timedelta
from models import db, User, Employee, Team, Ship, Berth, ShipOperation, Report, OperationTeam

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ============================================
# Helper Functions for Permissions
# ============================================

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def admin_or_self_required(user_id):
    """Decorator to require admin privileges or the user themselves"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_admin() and current_user.id != user_id:
                flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Create upload folder if not exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@app.route('/')
def index():
    # التحقق من تسجيل دخول المستخدم
    if current_user.is_authenticated:
        # إذا كان مسجل الدخول، اذهب إلى لوحة التحكم
        return redirect(url_for('dashboard'))
    else:
        # إذا لم يكن مسجل الدخول، اذهب إلى صفحة تسجيل الدخول
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(url_for('dashboard'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('login'))  # تغيير من 'index' إلى 'login'


@app.route('/dashboard')
@login_required
def dashboard():
    from sqlalchemy import func

    # Statistics for dashboard
    total_employees = Employee.query.count()
    total_teams = Team.query.count()

    # إحصائيات العمليات اليومية
    today = datetime.now().date()
    operations_today = ShipOperation.query.filter(
        func.date(ShipOperation.start_time) == today
    ).count()

    # إحصائيات العمليات حسب النوع
    total_operations = ShipOperation.query.count()
    completed_operations = ShipOperation.query.filter(ShipOperation.end_time != None).count()
    ongoing_operations = total_operations - completed_operations

    # إحصائيات عمليات التحميل والتفريغ
    loading_operations = ShipOperation.query.filter_by(operation_type='تحميل').count()
    unloading_operations = ShipOperation.query.filter_by(operation_type='تفريغ').count()

    # ============================================
    # إحصائيات الموظفين
    # ============================================

    # 1. توزيع الموظفين حسب سنة الميلاد (الأعمار)
    birth_year_stats = db.session.query(
        func.strftime('%Y', Employee.birth_date).label('year'),
        func.count(Employee.id)
    ).group_by('year').order_by('year').all()

    birth_year_labels = [str(int(item[0])) for item in birth_year_stats]
    birth_year_data = [item[1] for item in birth_year_stats]

    # حساب الأعمار
    current_year = datetime.now().year
    age_stats = []
    age_ranges = {
        'أقل من 20 سنة': 0,
        '20 - 30 سنة': 0,
        '31 - 40 سنة': 0,
        '41 - 50 سنة': 0,
        'أكثر من 50 سنة': 0
    }

    for employee in Employee.query.all():
        age = current_year - employee.birth_date.year
        if age < 20:
            age_ranges['أقل من 20 سنة'] += 1
        elif 20 <= age <= 30:
            age_ranges['20 - 30 سنة'] += 1
        elif 31 <= age <= 40:
            age_ranges['31 - 40 سنة'] += 1
        elif 41 <= age <= 50:
            age_ranges['41 - 50 سنة'] += 1
        else:
            age_ranges['أكثر من 50 سنة'] += 1

    age_labels = list(age_ranges.keys())
    age_data = list(age_ranges.values())

    # 2. إحصائيات مكان الميلاد (أكثر 5 أماكن)
    birth_places_stats = db.session.query(
        Employee.birth_place,
        func.count(Employee.id)
    ).group_by(Employee.birth_place).order_by(func.count(Employee.id).desc()).limit(5).all()

    birth_places_labels = [item[0] for item in birth_places_stats]
    birth_places_data = [item[1] for item in birth_places_stats]

    # 3. إحصائيات السكن الحالي (أكثر 5 أماكن)
    residence_stats = db.session.query(
        Employee.current_address,
        func.count(Employee.id)
    ).group_by(Employee.current_address).order_by(func.count(Employee.id).desc()).limit(5).all()

    residence_labels = [item[0] for item in residence_stats]
    residence_data = [item[1] for item in residence_stats]

    # 4. إحصائيات المهن
    profession_stats = db.session.query(
        Employee.profession,
        func.count(Employee.id)
    ).group_by(Employee.profession).order_by(func.count(Employee.id).desc()).limit(5).all()

    profession_labels = [item[0] for item in profession_stats]
    profession_data = [item[1] for item in profession_stats]

    # إجمالي عدد أماكن الميلاد المختلفة
    unique_birth_places = db.session.query(Employee.birth_place).distinct().count()

    # إجمالي عدد أماكن السكن المختلفة
    unique_residences = db.session.query(Employee.current_address).distinct().count()

    # ============================================
    # تصنيف السفن حسب حالتها
    # ============================================
    all_ships = Ship.query.all()

    # سفن نشطة (لديها عمليات جارية)
    active_ships = 0
    # سفن في حالة انتظار (واصلة ولا توجد لها عمليات جارية)
    waiting_ships = 0
    # سفن مغادرة (لديها عمليات منتهية)
    departed_ships = 0

    # قائمة الفرق النشطة (التي تعمل حالياً)
    active_teams_list = []
    active_teams_ids = set()

    for ship in all_ships:
        # التحقق من وجود عمليات جارية لهذه السفينة
        ongoing_operations = ShipOperation.query.filter(
            ShipOperation.ship_id == ship.id,
            ShipOperation.end_time == None
        ).all()

        # التحقق من وجود عمليات منتهية لهذه السفينة
        completed_operations_for_ship = ShipOperation.query.filter(
            ShipOperation.ship_id == ship.id,
            ShipOperation.end_time != None
        ).all()

        has_ongoing_operation = len(ongoing_operations) > 0
        has_completed_operation = len(completed_operations_for_ship) > 0

        # جمع الفرق التي تعمل على هذه السفينة
        if has_ongoing_operation:
            for op in ongoing_operations:
                for ot in op.operation_teams:
                    if ot.team_id not in active_teams_ids:
                        active_teams_ids.add(ot.team_id)
                        active_teams_list.append(ot.team)

        # تصنيف السفن بناءً على حالة العمليات
        if has_completed_operation and not has_ongoing_operation:
            # سفينة لديها عمليات منتهية ولا توجد عمليات جارية = مغادرة
            departed_ships += 1
            if ship.status != 'departed':
                ship.status = 'departed'
        elif has_ongoing_operation:
            # سفينة لديها عمليات جارية = نشطة
            active_ships += 1
            if ship.status != 'berthed':
                ship.status = 'berthed'
        else:
            # سفينة لا توجد لها أي عمليات = في انتظار
            waiting_ships += 1
            if ship.status != 'arrived':
                ship.status = 'arrived'

    # حفظ التغييرات إذا تم تحديث الحالات
    db.session.commit()

    # عدد الفرق النشطة
    active_teams = len(active_teams_list)

    # أضف هذه الأسطر لجلب البيانات للجداول
    ships = Ship.query.order_by(Ship.arrival_date.desc()).limit(5).all()
    employees = Employee.query.order_by(Employee.hire_date.desc()).limit(5).all()
    teams = Team.query.all()

    # إضافة معلومات العمليات الجارية لكل سفينة في القائمة
    ships_with_operations = []
    for ship in ships:
        ongoing_ops = ShipOperation.query.filter(
            ShipOperation.ship_id == ship.id,
            ShipOperation.end_time == None
        ).all()

        completed_ops = ShipOperation.query.filter(
            ShipOperation.ship_id == ship.id,
            ShipOperation.end_time != None
        ).all()

        ship_dict = {
            'id': ship.id,
            'name': ship.name,
            'imo_number': ship.imo_number,
            'ship_type': ship.ship_type,
            'arrival_date': ship.arrival_date,
            'berth_number': ship.berth_number,
            'status': ship.status,
            'ongoing_operations': ongoing_ops,
            'completed_operations': completed_ops,
            'has_ongoing': len(ongoing_ops) > 0,
            'has_completed': len(completed_ops) > 0
        }
        ships_with_operations.append(ship_dict)

    # إضافة معلومات العمليات الحالية لكل فريق في قائمة الفرق النشطة
    active_teams_with_ops = []
    for team in active_teams_list:
        team_dict = {
            'id': team.id,
            'name': team.name,
            'team_type': team.team_type,
            'members': team.members,
            'current_operations': []
        }
        for ot in team.operation_teams:
            if not ot.operation.end_time:
                team_dict['current_operations'].append(ot.operation)
        active_teams_with_ops.append(team_dict)

    # بيانات حقيقية للرسوم البيانية
    # توزيع السفن حسب النوع
    ships_by_type = db.session.query(
        Ship.ship_type,
        func.count(Ship.id)
    ).group_by(Ship.ship_type).all()

    ship_types_labels = []
    ship_types_data = []
    ship_type_names = {
        'cargo': 'بضائع',
        'tanker': 'ناقلة نفط',
        'container': 'حاويات',
        'passenger': 'ركاب',
        'other': 'أخرى'
    }

    for ship_type, count in ships_by_type:
        ship_types_labels.append(ship_type_names.get(ship_type, ship_type))
        ship_types_data.append(count)

    # حركة السفن خلال الشهر
    import calendar

    today = datetime.now()
    months_data = []
    months_labels = []

    for i in range(11, -1, -1):
        month = today.month - i
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        month_name = calendar.month_name[month]
        months_labels.append(month_name)

        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        count = Ship.query.filter(
            Ship.arrival_date >= start_date,
            Ship.arrival_date < end_date
        ).count()
        months_data.append(count)

    return render_template('dashboard.html',
                           total_employees=total_employees,
                           active_ships=active_ships,
                           waiting_ships=waiting_ships,
                           departed_ships=departed_ships,
                           total_teams=total_teams,
                           active_teams=active_teams,
                           active_teams_list=active_teams_with_ops,
                           operations_today=operations_today,
                           total_operations=total_operations,
                           completed_operations=completed_operations,
                           ongoing_operations=ongoing_operations,
                           loading_operations=loading_operations,
                           unloading_operations=unloading_operations,
                           ships=ships_with_operations,
                           employees=employees,
                           teams=teams,
                           ship_types_labels=ship_types_labels,
                           ship_types_data=ship_types_data,
                           months_labels=months_labels,
                           months_data=months_data,
                           # بيانات الموظفين الإضافية
                           birth_year_labels=birth_year_labels,
                           birth_year_data=birth_year_data,
                           age_labels=age_labels,
                           age_data=age_data,
                           birth_places_labels=birth_places_labels,
                           birth_places_data=birth_places_data,
                           residence_labels=residence_labels,
                           residence_data=residence_data,
                           profession_labels=profession_labels,
                           profession_data=profession_data,
                           unique_birth_places=unique_birth_places,
                           unique_residences=unique_residences)

@app.route('/employees')
@login_required
def employee_list():
    # أي موظف مسجل يمكنه رؤية القائمة
    employees = Employee.query.all()
    teams = Team.query.all()
    return render_template('employees/list.html', employees=employees, teams=teams)


@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
@admin_required  # فقط المشرف يمكنه الإضافة
def add_employee():
    form = EmployeeForm()
    teams = Team.query.filter_by(is_active=True).all()
    form.team_id.choices = [(0, 'اختر الفرقة')] + [(t.id, t.name) for t in teams]

    if form.validate_on_submit():
        employee = Employee(
            name=form.name.data,
            national_id=form.national_id.data,
            birth_place=form.birth_place.data,
            current_address=form.current_address.data,
            birth_date=form.birth_date.data,
            profession=form.profession.data,
            team_id=form.team_id.data if form.team_id.data != 0 else None,
            phone=form.phone.data,
        )
        db.session.add(employee)
        db.session.commit()
        flash('تم إضافة الموظف بنجاح', 'success')
        return redirect(url_for('employee_list'))

    return render_template('employees/add.html', form=form, teams=teams)


@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required  # فقط المشرف يمكنه التعديل
def edit_employee(id):
    employee = Employee.query.get_or_404(id)
    form = EmployeeForm(obj=employee)
    teams = Team.query.filter_by(is_active=True).all()
    form.team_id.choices = [(0, 'اختر الفرقة')] + [(t.id, t.name) for t in teams]

    if form.validate_on_submit():
        employee.name = form.name.data
        employee.national_id = form.national_id.data
        employee.birth_place = form.birth_place.data
        employee.current_address = form.current_address.data
        employee.birth_date = form.birth_date.data
        employee.profession = form.profession.data
        employee.team_id = form.team_id.data if form.team_id.data != 0 else None
        employee.phone = form.phone.data

        db.session.commit()
        flash('تم تحديث بيانات الموظف بنجاح', 'success')
        return redirect(url_for('employee_list'))

    return render_template('employees/edit.html', form=form, employee=employee)


@app.route('/employees/delete/<int:id>')
@login_required
@admin_required  # فقط المشرف يمكنه الحذف
def delete_employee(id):
    employee = Employee.query.get_or_404(id)
    db.session.delete(employee)
    db.session.commit()
    flash('تم حذف الموظف بنجاح', 'success')
    return redirect(url_for('employee_list'))


# ============================================
# User Management Routes (إدارة المستخدمين)
# ============================================

@app.route('/users')
@login_required
def user_list():
    """عرض قائمة المستخدمين"""
    # فقط المشرف يمكنه الوصول
    if not current_user.is_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))

    users = User.query.all()
    return render_template('users/list.html', users=users)


@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    """إضافة مستخدم جديد"""
    # فقط المشرف يمكنه الوصول
    if not current_user.is_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))

    from forms import UserForm  # استيراد النموذج

    form = UserForm()

    if form.validate_on_submit():
        # التحقق من عدم وجود اسم مستخدم مكرر
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('اسم المستخدم موجود بالفعل', 'danger')
            return render_template('users/add.html', form=form)

        # التحقق من عدم وجود بريد إلكتروني مكرر
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('البريد الإلكتروني موجود بالفعل', 'danger')
            return render_template('users/add.html', form=form)

        # إنشاء مستخدم جديد
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data,
            is_active=True
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash('تم إضافة المستخدم بنجاح', 'success')
        return redirect(url_for('user_list'))

    return render_template('users/add.html', form=form)


@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    """تعديل بيانات مستخدم"""
    # فقط المشرف يمكنه الوصول
    if not current_user.is_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(id)
    from forms import UserEditForm

    form = UserEditForm(obj=user)

    if form.validate_on_submit():
        # التحقق من عدم وجود اسم مستخدم مكرر (إذا تم تغييره)
        if form.username.data != user.username:
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user:
                flash('اسم المستخدم موجود بالفعل', 'danger')
                return render_template('users/edit.html', form=form, user=user)

        # التحقق من عدم وجود بريد إلكتروني مكرر (إذا تم تغييره)
        if form.email.data != user.email:
            existing_email = User.query.filter_by(email=form.email.data).first()
            if existing_email:
                flash('البريد الإلكتروني موجود بالفعل', 'danger')
                return render_template('users/edit.html', form=form, user=user)

        # تحديث البيانات
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data

        # تحديث كلمة المرور إذا تم إدخالها
        if form.password.data:
            user.set_password(form.password.data)

        db.session.commit()

        flash('تم تحديث بيانات المستخدم بنجاح', 'success')
        return redirect(url_for('user_list'))

    return render_template('users/edit.html', form=form, user=user)


@app.route('/users/toggle/<int:id>')
@login_required
def toggle_user(id):
    """تفعيل/تعطيل مستخدم"""
    # فقط المشرف يمكنه الوصول
    if not current_user.is_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(id)

    # منع تعطيل المشرف الرئيسي
    if user.username == 'admin' and id == 1:
        flash('لا يمكن تعطيل المستخدم الرئيسي', 'danger')
        return redirect(url_for('user_list'))

    user.is_active = not user.is_active
    db.session.commit()

    status = 'تفعيل' if user.is_active else 'تعطيل'
    flash(f'تم {status} المستخدم بنجاح', 'success')
    return redirect(url_for('user_list'))


@app.route('/users/delete/<int:id>')
@login_required
def delete_user(id):
    """حذف مستخدم"""
    # فقط المشرف يمكنه الوصول
    if not current_user.is_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(id)

    # منع حذف المشرف الرئيسي
    if user.username == 'admin' and id == 1:
        flash('لا يمكن حذف المستخدم الرئيسي', 'danger')
        return redirect(url_for('user_list'))

    # منع المستخدم من حذف نفسه
    if user.id == current_user.id:
        flash('لا يمكنك حذف حسابك الخاص', 'danger')
        return redirect(url_for('user_list'))

    db.session.delete(user)
    db.session.commit()

    flash('تم حذف المستخدم بنجاح', 'success')
    return redirect(url_for('user_list'))


# ============================================
# Berths Routes (إدارة الأرصفة)
# ============================================

@app.route('/berths')
@login_required
def berth_list():
    """عرض قائمة الأرصفة مع عدد السفن المرتبطة"""
    berths = Berth.query.all()

    # إحصائيات إضافية
    stats = {
        'total': len(berths),
        'active': sum(1 for b in berths if b.is_available),
        'occupied': sum(1 for b in berths if b.is_occupied),
        'total_ships': sum(b.ships_count for b in berths)
    }

    return render_template('berths/list.html', berths=berths, stats=stats)

@app.route('/berths/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_berth():
    """إضافة رصيف جديد"""
    from forms import BerthForm
    form = BerthForm()

    if form.validate_on_submit():
        try:
            berth = Berth(
                number=form.number.data,
                length=form.length.data,
                depth=form.depth.data,
                is_available=form.is_active.data,
                notes=form.notes.data
            )
            db.session.add(berth)
            db.session.commit()
            flash(f'✅ تم إضافة الرصيف "{berth.number}" بنجاح', 'success')
            return redirect(url_for('berth_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ حدث خطأ: {str(e)}', 'danger')

    return render_template('berths/add.html', form=form)


@app.route('/berths/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_berth(id):
    """تعديل بيانات رصيف"""
    berth = Berth.query.get_or_404(id)
    from forms import BerthForm
    form = BerthForm(obj=berth)

    if form.validate_on_submit():
        try:
            berth.number = form.number.data
            berth.length = form.length.data
            berth.depth = form.depth.data
            berth.is_available = form.is_active.data
            berth.notes = form.notes.data

            db.session.commit()
            flash(f'✅ تم تحديث بيانات الرصيف "{berth.number}" بنجاح', 'success')
            return redirect(url_for('berth_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ حدث خطأ: {str(e)}', 'danger')

    return render_template('berths/edit.html', form=form, berth=berth)


@app.route('/berths/delete/<int:id>')
@login_required
@admin_required
def delete_berth(id):
    """حذف رصيف"""
    berth = Berth.query.get_or_404(id)

    # التحقق من عدم وجود سفن مرتبطة
    if berth.current_ship_id:
        flash('❌ لا يمكن حذف الرصيف لوجود سفينة مرتبطة به حالياً', 'danger')
        return redirect(url_for('berth_list'))

    try:
        db.session.delete(berth)
        db.session.commit()
        flash(f'✅ تم حذف الرصيف "{berth.number}" بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ حدث خطأ: {str(e)}', 'danger')

    return redirect(url_for('berth_list'))


@app.route('/berths/toggle/<int:id>')
@login_required
@admin_required
def toggle_berth(id):
    """تفعيل/تعطيل رصيف"""
    berth = Berth.query.get_or_404(id)

    berth.is_available = not berth.is_available
    db.session.commit()

    status = 'متاح' if berth.is_available else 'غير متاح'
    flash(f'✅ تم تغيير حالة الرصيف "{berth.number}" إلى {status}', 'success')
    return redirect(url_for('berth_list'))


@app.route('/api/berths/<int:id>/ships')
@login_required
def berth_ships(id):
    """الحصول على قائمة السفن المرتبطة بالرصيف"""
    berth = Berth.query.get_or_404(id)

    # البحث عن السفن التي رست على هذا الرصيف
    ships = Ship.query.filter_by(berth_number=berth.number).order_by(Ship.arrival_date.desc()).all()

    ships_data = [{
        'id': s.id,
        'name': s.name,
        'imo_number': s.imo_number,
        'arrival_date': s.arrival_date.strftime('%Y-%m-%d %H:%M'),
        'departure_date': s.departure_date.strftime('%Y-%m-%d %H:%M') if s.departure_date else '—',
        'status': s.status,
        'cargo': s.cargo_capacity
    } for s in ships]

    return jsonify({
        'berth_number': berth.number,
        'ships_count': len(ships),
        'ships': ships_data
    })

@app.route('/ships')
@login_required
def ship_list():
    # أي موظف مسجل يمكنه رؤية القائمة
    ships = Ship.query.all()
    return render_template('ships/list.html', ships=ships)

@app.route('/ships/add', methods=['GET', 'POST'])
@login_required
@admin_required  # فقط المشرف يمكنه الإضافة
def add_ship():
    form = ShipForm()

    if form.validate_on_submit():
        ship = Ship(
            name=form.name.data,
            imo_number=form.imo_number.data,
            flag=form.flag.data,
            ship_type=form.ship_type.data,
            length=form.length.data,
            width=form.width.data,
            draft=form.draft.data,
            cargo_capacity=form.cargo_capacity.data,
            arrival_date=form.arrival_date.data,
            berth_number=form.berth_number.data,
            notes=form.notes.data
        )
        db.session.add(ship)
        db.session.commit()
        flash('تم إضافة السفينة بنجاح', 'success')
        return redirect(url_for('ship_list'))

    return render_template('ships/add.html', form=form)

@app.route('/ships/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required  # فقط المشرف يمكنه التعديل
def edit_ship(id):
    ship = Ship.query.get_or_404(id)
    form = ShipForm(obj=ship)

    if form.validate_on_submit():
        ship.name = form.name.data
        ship.imo_number = form.imo_number.data
        ship.flag = form.flag.data
        ship.ship_type = form.ship_type.data
        ship.length = form.length.data
        ship.width = form.width.data
        ship.draft = form.draft.data
        ship.cargo_capacity = form.cargo_capacity.data
        ship.arrival_date = form.arrival_date.data
        ship.berth_number = form.berth_number.data
        ship.notes = form.notes.data

        db.session.commit()
        flash('تم تحديث بيانات السفينة بنجاح', 'success')
        return redirect(url_for('ship_list'))

    return render_template('ships/edit.html', form=form, ship=ship)

@app.route('/ships/delete/<int:id>')
@login_required
@admin_required  # فقط المشرف يمكنه الحذف
def delete_ship(id):
    ship = Ship.query.get_or_404(id)
    db.session.delete(ship)
    db.session.commit()
    flash('تم حذف السفينة بنجاح', 'success')
    return redirect(url_for('ship_list'))


@app.route('/teams')
@login_required
def team_list():
    # أي موظف مسجل يمكنه رؤية القائمة
    teams = Team.query.all()
    return render_template('teams/list.html', teams=teams)


@app.route('/teams/add', methods=['GET', 'POST'])
@login_required
@admin_required  # فقط المشرف يمكنه الإضافة
def add_team():
    form = TeamForm()

    # قائمة الموظفين المتاحين (غير المنتمين لفرقة أو يمكن إضافتهم)
    available_employees = Employee.query.filter_by(is_active=True).all()
    form.leader_id.choices = [(0, 'اختر القائد')] + [(e.id, e.name) for e in available_employees]

    # إضافة خيارات متعددة للأعضاء
    if request.method == 'POST':
        member_ids = request.form.getlist('members')  # قائمة IDs الأعضاء المختارين

    if form.validate_on_submit():
        # إنشاء الفرقة
        team = Team(
            name=form.name.data,
            team_type=form.team_type.data,
            leader_id=form.leader_id.data if form.leader_id.data != 0 else None
        )
        db.session.add(team)
        db.session.flush()  # للحصول على ID الفرقة قبل إضافة الأعضاء

        # إضافة الأعضاء المختارين إلى الفرقة
        member_ids = request.form.getlist('members')
        if member_ids:
            for member_id in member_ids:
                employee = Employee.query.get(int(member_id))
                if employee:
                    employee.team_id = team.id
                    db.session.add(employee)

        db.session.commit()
        flash('تم إضافة الفرقة مع الأعضاء بنجاح', 'success')
        return redirect(url_for('team_list'))

    return render_template('teams/add.html', form=form, employees=available_employees)


@app.route('/teams/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_team(id):
    team = Team.query.get_or_404(id)
    form = TeamForm(obj=team)

    # جلب جميع الموظفين النشطين
    employees = Employee.query.filter_by(is_active=True).all()

    # خيارات قائد الفرقة
    form.leader_id.choices = [(0, 'اختر القائد')] + [(e.id, e.name) for e in employees]

    if form.validate_on_submit():
        # تحديث بيانات الفرقة
        team.name = form.name.data
        team.team_type = form.team_type.data
        team.leader_id = form.leader_id.data if form.leader_id.data != 0 else None
        team.is_active = 'is_active' in request.form

        # إزالة جميع الأعضاء الحاليين أولاً
        for member in team.members:
            member.team_id = None

        # إضافة الأعضاء المختارين
        member_ids = request.form.getlist('members')
        if member_ids:
            for member_id in member_ids:
                employee = Employee.query.get(int(member_id))
                if employee:
                    employee.team_id = team.id

        db.session.commit()

        # رسالة مناسبة حسب التغييرات
        members_count = len(member_ids)
        flash(f'✅ تم تحديث الفرقة "{team.name}" بنجاح ({members_count} عضو)', 'success')
        return redirect(url_for('team_list'))

    return render_template('teams/edit.html', form=form, team=team, employees=employees)


@app.route('/teams/delete/<int:id>')
@login_required
@admin_required
def delete_team(id):
    team = Team.query.get_or_404(id)

    # التحقق من عدم وجود موظفين في هذه الفرقة
    employees_in_team = Employee.query.filter_by(team_id=id).count()
    if employees_in_team > 0:
        flash('لا يمكن حذف فرقة بها موظفين', 'danger')
        return redirect(url_for('team_list'))

    db.session.delete(team)
    db.session.commit()
    flash('تم حذف الفرقة بنجاح', 'success')
    return redirect(url_for('team_list'))


@app.route('/api/teams/<int:id>')
@login_required
def get_team_details(id):
    """API للحصول على تفاصيل الفرقة"""
    team = Team.query.get_or_404(id)

    # تجهيز بيانات الأعضاء
    members_data = []
    for member in team.members:
        members_data.append({
            'id': member.id,
            'name': member.name,
            'profession': member.profession,
            'phone': member.phone,
            'is_leader': member.id == team.leader_id or 'رئيس' in member.profession
        })

    # تجهيز بيانات القائد
    leader_data = None
    if team.leader:
        leader_data = {
            'id': team.leader.id,
            'name': team.leader.name,
            'profession': team.leader.profession,
            'phone': team.leader.phone
        }
    elif members_data:
        # البحث عن رئيس الفرقة بين الأعضاء
        for member in members_data:
            if 'رئيس' in member['profession']:
                leader_data = member
                break

    return jsonify({
        'id': team.id,
        'name': team.name,
        'team_type': team.team_type,
        'is_active': team.is_active,
        'created_at': team.created_at.strftime('%Y-%m-%d'),
        'leader': leader_data,
        'members': members_data,
        'members_count': len(members_data)
    })


# ============================================
# Operations Routes (إدارة العمليات)
# ============================================
# ============================================
# Operations Routes (إدارة العمليات)
# ============================================

@app.route('/operations')
@login_required
def operation_list():
    """عرض قائمة العمليات"""
    operations = ShipOperation.query.order_by(ShipOperation.start_time.desc()).all()

    # إحصائيات للعرض
    from sqlalchemy import func
    today = datetime.now().date()

    stats = {
        'total': len(operations),
        'today': ShipOperation.query.filter(
            func.date(ShipOperation.start_time) == today
        ).count(),
        'loading': ShipOperation.query.filter_by(operation_type='تحميل').count(),
        'unloading': ShipOperation.query.filter_by(operation_type='تفريغ').count()
    }

    return render_template('operations/list.html', operations=operations, stats=stats)


@app.route('/operations/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_operation():
    """إضافة عملية جديدة"""
    form = OperationForm()

    # خيارات السفن
    ships = Ship.query.filter_by(status='arrived').all()
    form.ship_id.choices = [(0, 'اختر السفينة')] + [(s.id, f"{s.name} - {s.imo_number}") for s in ships]

    # خيارات الفرق - يجب تعيينها قبل validate_on_submit
    teams = Team.query.filter_by(is_active=True).all()
    form.team_ids.choices = [(t.id, t.name) for t in teams]  # هذا هو المهم

    if request.method == 'POST':
        # طباعة جميع البيانات المرسلة للتشخيص
        print("=" * 50)
        print("البيانات المرسلة:")
        for key, value in request.form.items():
            if key == 'team_ids':
                print(f"  {key}: {request.form.getlist(key)}")
            else:
                print(f"  {key}: {value}")
        print("=" * 50)

        # معالجة التواريخ
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')

        try:
            if start_time_str:
                form.start_time.data = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError) as e:
            flash('❌ تنسيق تاريخ البدء غير صحيح', 'danger')
            return render_template('operations/add.html', form=form, teams=teams)

        try:
            if end_time_str and end_time_str.strip():
                form.end_time.data = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            else:
                form.end_time.data = None
        except (ValueError, TypeError) as e:
            flash('❌ تنسيق تاريخ الانتهاء غير صحيح', 'danger')
            return render_template('operations/add.html', form=form, teams=teams)

    if form.validate_on_submit():
        try:
            # إنشاء العملية
            operation = ShipOperation(
                ship_id=form.ship_id.data,
                operation_type=form.operation_type.data,
                start_time=form.start_time.data,
                end_time=form.end_time.data,
                cargo_type=form.cargo_type.data if form.cargo_type.data else None,
                cargo_quantity=form.cargo_quantity.data if form.cargo_quantity.data else None,
                notes=form.notes.data if form.notes.data else None
            )
            db.session.add(operation)
            db.session.flush()  # للحصول على ID العملية

            # إضافة الفرق المشاركة
            team_ids = request.form.getlist('team_ids')
            print(f"📋 الفرق المختارة: {team_ids}")

            if team_ids and len(team_ids) > 0:
                for team_id in team_ids:
                    if team_id and team_id.isdigit():
                        operation_team = OperationTeam(
                            operation_id=operation.id,
                            team_id=int(team_id)
                        )
                        db.session.add(operation_team)
                        print(f"✅ تم إضافة فريق {team_id} للعملية {operation.id}")

                db.session.commit()
                flash(f'✅ تم إضافة العملية بنجاح مع {len(team_ids)} فرق', 'success')
            else:
                db.session.commit()
                flash('✅ تم إضافة العملية بنجاح بدون فرق', 'success')

            return redirect(url_for('operation_list'))

        except Exception as e:
            db.session.rollback()
            print(f"❌ خطأ في حفظ العملية: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'❌ حدث خطأ: {str(e)}', 'danger')
    else:
        if request.method == 'POST':
            print("❌ أخطاء النموذج:", form.errors)
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'❌ {getattr(form, field).label.text}: {error}', 'danger')

    return render_template('operations/add.html', form=form, teams=teams)

@app.route('/operations/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_operation(id):
    """تعديل عملية"""
    operation = ShipOperation.query.get_or_404(id)
    form = OperationForm(obj=operation)

    # خيارات السفن
    ships = Ship.query.all()
    form.ship_id.choices = [(0, 'اختر السفينة')] + [(s.id, f"{s.name} - {s.imo_number}") for s in ships]

    # خيارات الفرق - يجب تعيينها قبل validate_on_submit
    teams = Team.query.filter_by(is_active=True).all()
    form.team_ids.choices = [(t.id, t.name) for t in teams]

    # تعيين الفرق المحددة مسبقاً
    if request.method == 'GET':
        form.team_ids.data = [ot.team_id for ot in operation.operation_teams]

    if request.method == 'POST':
        # معالجة التواريخ
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')

        try:
            if start_time_str:
                form.start_time.data = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError):
            flash('❌ تنسيق تاريخ البدء غير صحيح', 'danger')
            return render_template('operations/edit.html', form=form, operation=operation, teams=teams)

        try:
            if end_time_str and end_time_str.strip():
                form.end_time.data = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            else:
                form.end_time.data = None
        except (ValueError, TypeError):
            flash('❌ تنسيق تاريخ الانتهاء غير صحيح', 'danger')
            return render_template('operations/edit.html', form=form, operation=operation, teams=teams)

    if form.validate_on_submit():
        try:
            # تحديث بيانات العملية
            operation.ship_id = form.ship_id.data
            operation.operation_type = form.operation_type.data
            operation.start_time = form.start_time.data
            operation.end_time = form.end_time.data
            operation.cargo_type = form.cargo_type.data if form.cargo_type.data else None
            operation.cargo_quantity = form.cargo_quantity.data if form.cargo_quantity.data else None
            operation.notes = form.notes.data if form.notes.data else None

            # حذف العلاقات القديمة
            OperationTeam.query.filter_by(operation_id=operation.id).delete()

            # إضافة العلاقات الجديدة
            team_ids = request.form.getlist('team_ids')
            for team_id in team_ids:
                if team_id and team_id.isdigit():
                    operation_team = OperationTeam(
                        operation_id=operation.id,
                        team_id=int(team_id)
                    )
                    db.session.add(operation_team)

            db.session.commit()
            flash(f'✅ تم تحديث العملية بنجاح مع {len(team_ids)} فرق', 'success')
            return redirect(url_for('operation_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ حدث خطأ: {str(e)}', 'danger')
    else:
        if request.method == 'POST':
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'❌ {getattr(form, field).label.text}: {error}', 'danger')

    return render_template('operations/edit.html', form=form, operation=operation, teams=teams)

@app.route('/operations/delete/<int:id>')
@login_required
@admin_required
def delete_operation(id):
    """حذف عملية"""
    operation = ShipOperation.query.get_or_404(id)

    # حذف العلاقات أولاً (cascade سيتعامل معها تلقائياً)
    db.session.delete(operation)
    db.session.commit()

    flash('✅ تم حذف العملية بنجاح', 'success')
    return redirect(url_for('operation_list'))


@app.route('/api/operations/stats')
@login_required
def operation_stats():
    """إحصائيات العمليات"""
    from sqlalchemy import func

    today = datetime.now().date()
    week_ago = today - timedelta(days=7)

    stats = {
        'today': ShipOperation.query.filter(
            func.date(ShipOperation.start_time) == today
        ).count(),
        'week': ShipOperation.query.filter(
            ShipOperation.start_time >= week_ago
        ).count(),
        'loading': ShipOperation.query.filter_by(operation_type='تحميل').count(),
        'unloading': ShipOperation.query.filter_by(operation_type='تفريغ').count(),
    }

    return jsonify(stats)


@app.route('/reports/teams-operations')
@login_required
def teams_operations_report():
    """تقرير فرق العمل مع العمليات"""

    # الحصول على جميع الفرق
    teams = Team.query.all()

    # الحصول على جميع العمليات الفريدة (بدون تكرار)
    all_operations = ShipOperation.query.order_by(ShipOperation.start_time.desc()).all()
    unique_operations_count = len(all_operations)

    # حساب إجمالي ساعات العمل الفريدة (مجموع مدد العمليات المختلفة)
    total_unique_hours = 0
    for op in all_operations:
        if op.duration:
            total_unique_hours += op.duration

    report_data = []
    for team in teams:
        # الحصول على العمليات التي شاركت فيها هذه الفرقة
        team_operations = team.operations

        # عدد العمليات التي شاركت فيها الفرقة
        total_ops = len(team_operations)

        # العمليات المكتملة
        completed_ops = [op for op in team_operations if op.end_time]
        completed_count = len(completed_ops)

        # إجمالي ساعات عمل الفرقة (مجموع مدد العمليات التي شاركت فيها)
        team_hours = 0
        for op in team_operations:
            if op.duration:
                team_hours += op.duration

        report_data.append({
            'team': team,
            'total_operations': total_ops,
            'completed_operations': completed_count,
            'total_hours': round(team_hours, 2),
            'avg_duration': round(team_hours / total_ops, 2) if total_ops > 0 else 0,
            'operations': sorted(team_operations, key=lambda x: x.start_time, reverse=True)[:10]  # آخر 10 عمليات
        })

    return render_template('reports/teams_operations.html',
                           report_data=report_data,
                           unique_operations=unique_operations_count,
                           unique_hours=round(total_unique_hours, 2))


@app.route('/api/teams/<int:team_id>/current-operations')
@login_required
def get_team_current_operations(team_id):
    """الحصول على العمليات الحالية للفرقة"""
    team = Team.query.get_or_404(team_id)

    # الحصول على العمليات التي تشارك فيها الفرقة ولم تنته بعد
    current_ops = []
    for ot in team.operation_teams:
        op = ot.operation
        if not op.end_time:  # عملية جارية
            current_ops.append({
                'id': op.id,
                'ship_name': op.ship.name if op.ship else '—',
                'operation_type': op.operation_type,
                'berth_number': op.ship.berth_number if op.ship else '—',
                'start_time': op.start_time.strftime('%Y-%m-%d %H:%M'),
                'cargo_type': op.cargo_type,
                'cargo_quantity': op.cargo_quantity
            })

    return jsonify(current_ops)

@app.route('/reports/operations-duration')
@login_required
def operations_duration_report():
    """تقرير مدة العمليات"""
    from sqlalchemy import func

    # الحصول على جميع العمليات
    operations = ShipOperation.query.order_by(ShipOperation.start_time.desc()).all()

    # إحصائيات
    total_operations = len(operations)
    completed_operations = len([op for op in operations if op.end_time])
    ongoing_operations = total_operations - completed_operations

    # حساب متوسط المدة
    total_duration = 0
    completed_count = 0
    for op in operations:
        if op.duration:
            total_duration += op.duration
            completed_count += 1

    avg_duration = round(total_duration / completed_count, 2) if completed_count > 0 else 0

    stats = {
        'total': total_operations,
        'completed': completed_operations,
        'ongoing': ongoing_operations,
        'avg_duration': avg_duration
    }

    return render_template('reports/operations_duration.html',
                           operations=operations,
                           stats=stats)


@app.route('/team-pass/<int:team_id>')
@login_required
def team_pass_page(team_id):
    """صفحة مستقلة لعرض تصريح الفرقة - مناسبة للطباعة"""
    team = Team.query.get_or_404(team_id)

    # الحصول على العمليات الحالية للفرقة
    current_ops = []
    for ot in team.operation_teams:
        if not ot.operation.end_time:
            current_ops.append(ot.operation)

    return render_template('team_pass.html',
                           team=team,
                           operations=current_ops,
                           now=datetime.now())

# ============================================
# Reports Routes (التقارير)
# ============================================
@app.route('/reports')
@login_required
def reports_index():
    """صفحة التقارير الرئيسية"""
    # إحصائيات سريعة للعرض
    stats = {
        'total_ships': Ship.query.count(),
        'total_employees': Employee.query.count(),
        'total_teams': Team.query.count(),
        'active_ships': Ship.query.filter_by(status='arrived').count()
    }
    return render_template('reports/index.html', stats=stats)


@app.route('/reports/charts')
@login_required
def reports_charts():
    # بيانات حقيقية من قاعدة البيانات

    # 1. توزيع السفن حسب النوع
    ships_by_type = db.session.query(
        Ship.ship_type,
        db.func.count(Ship.id)
    ).group_by(Ship.ship_type).all()

    ship_types_labels = []
    ship_types_data = []
    ship_type_names = {
        'cargo': 'بضائع',
        'tanker': 'ناقلات نفط',
        'container': 'حاويات',
        'passenger': 'ركاب',
        'other': 'أخرى'
    }

    for ship_type, count in ships_by_type:
        ship_types_labels.append(ship_type_names.get(ship_type, ship_type))
        ship_types_data.append(count)

    # 2. توزيع الموظفين حسب الفرق
    employees_by_team = db.session.query(
        Team.name,
        db.func.count(Employee.id)
    ).outerjoin(Employee, Team.id == Employee.team_id).group_by(Team.name).all()

    employees_by_team_labels = [item[0] for item in employees_by_team]
    employees_by_team_data = [item[1] for item in employees_by_team]

    # 3. حركة السفن الشهرية
    from datetime import datetime, timedelta
    import calendar

    today = datetime.now()
    months_labels = []
    months_data = []

    for i in range(11, -1, -1):
        month = today.month - i
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        month_name = calendar.month_name[month]
        months_labels.append(month_name)

        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        count = Ship.query.filter(
            Ship.arrival_date >= start_date,
            Ship.arrival_date < end_date
        ).count()
        months_data.append(count)

    # 4. العمليات اليومية
    days = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
    loading_data = []
    unloading_data = []

    for i, day in enumerate(days):
        # حساب عدد عمليات التحميل والتفريغ لكل يوم
        day_loading = ShipOperation.query.filter(
            ShipOperation.operation_type == 'تحميل',
            db.func.strftime('%w', ShipOperation.start_time) == str(i)
        ).count()

        day_unloading = ShipOperation.query.filter(
            ShipOperation.operation_type == 'تفريغ',
            db.func.strftime('%w', ShipOperation.start_time) == str(i)
        ).count()

        loading_data.append(day_loading)
        unloading_data.append(day_unloading)

    daily_operations_data = {
        'loading': loading_data,
        'unloading': unloading_data
    }

    # 5. إشغال الأرصفة
    berths = Berth.query.all()
    berth_occupancy_data = []

    for berth in berths:
        # بيانات إشغال الرصيف خلال اليوم (محاكاة)
        # يمكن تحسينها لبيانات حقيقية
        occupancy = [1, 1, 0, 1, 1, 1]  # مثال
        berth_occupancy_data.append({
            'number': berth.number,
            'occupancy': occupancy
        })

    berth_occupancy_labels = ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00']

    today_str = today.strftime('%Y-%m-%d')
    last_month_str = (today - timedelta(days=30)).strftime('%Y-%m-%d')

    return render_template('reports/charts.html',
                           today=today_str,
                           last_month=last_month_str,
                           ship_types_labels=ship_types_labels,
                           ship_types_data=ship_types_data,
                           employees_by_team_labels=employees_by_team_labels,
                           employees_by_team_data=employees_by_team_data,
                           monthly_ships_labels=months_labels,
                           monthly_ships_data=months_data,
                           daily_operations_data=daily_operations_data,
                           daily_operations_labels=days,
                           berth_occupancy_data=berth_occupancy_data,
                           berth_occupancy_labels=berth_occupancy_labels)

def generate_ships_report(date_from, date_to, format):
    """تقرير السفن"""
    data = Ship.query.filter(
        Ship.arrival_date.between(date_from, date_to)
    ).all()

    if format == 'excel':
        return generate_excel_report(data, 'ships', date_from, date_to)
    elif format == 'pdf':
        return generate_pdf_report(data, 'ships', date_from, date_to)
    else:
        # HTML report
        return render_template('reports/ships_report.html',
                               data=data,
                               date_from=date_from,
                               date_to=date_to)


def generate_employees_report(date_from, date_to, format):
    """تقرير الموظفين"""
    data = Employee.query.filter(
        Employee.hire_date.between(date_from, date_to)
    ).all()

    if format == 'excel':
        return generate_excel_report(data, 'employees', date_from, date_to)
    elif format == 'pdf':
        return generate_pdf_report(data, 'employees', date_from, date_to)
    else:
        return render_template('reports/employees_report.html',
                               data=data,
                               date_from=date_from,
                               date_to=date_to)


def generate_teams_report(date_from, date_to, format):
    """تقرير فرق العمل"""
    teams = Team.query.all()

    # تجميع بيانات الفرق
    teams_data = []
    for team in teams:
        members = Employee.query.filter_by(team_id=team.id).all()
        leaders = [m for m in members if 'رئيس' in m.profession]

        teams_data.append({
            'team': team,
            'members': members,
            'members_count': len(members),
            'leaders': leaders,
            'leader': leaders[0] if leaders else None
        })

    if format == 'excel':
        return generate_teams_excel(teams_data, date_from, date_to)
    elif format == 'pdf':
        return generate_teams_pdf(teams_data, date_from, date_to)
    else:
        return render_template('reports/teams_report.html',
                               teams_data=teams_data,
                               date_from=date_from,
                               date_to=date_to)


def generate_operations_report(date_from, date_to, format):
    """تقرير العمليات"""
    data = ShipOperation.query.filter(
        ShipOperation.start_time.between(date_from, date_to)
    ).all()

    if format == 'excel':
        return generate_excel_report(data, 'operations', date_from, date_to)
    elif format == 'pdf':
        return generate_pdf_report(data, 'operations', date_from, date_to)
    else:
        return render_template('reports/operations_report.html',
                               data=data,
                               date_from=date_from,
                               date_to=date_to)


@app.route('/export/berths/excel')
@login_required
def export_berths_excel():
    """تصدير تقرير الأرصفة إلى Excel"""
    import pandas as pd
    from io import BytesIO

    berths = Berth.query.all()

    # تجهيز البيانات
    data = []
    for berth in berths:
        ships_count = berth.ships_count
        current_ship = berth.current_ship.name if berth.current_ship else '—'

        data.append({
            'رقم الرصيف': berth.number,
            'الطول (م)': berth.length or '',
            'العمق (م)': berth.depth or '',
            'عدد السفن': ships_count,
            'السفينة الحالية': current_ship,
            'الحالة': 'متاح' if berth.is_available else 'غير متاح',
            'ملاحظات': berth.notes or ''
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='الأرصفة', index=False)

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f'تقرير_الأرصفة_{datetime.now().strftime("%Y%m%d")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/export/berths/pdf')
@login_required
def export_berths_pdf():
    """تصدير تقرير الأرصفة إلى PDF"""
    from weasyprint import HTML
    from datetime import datetime

    berths = Berth.query.all()
    stats = {
        'total': len(berths),
        'active': sum(1 for b in berths if b.is_available),
        'occupied': sum(1 for b in berths if b.is_occupied),
        'total_ships': sum(b.ships_count for b in berths)
    }

    html_string = render_template('reports/berths_pdf.html',
                                  berths=berths,
                                  stats=stats,
                                  current_date=datetime.now())

    pdf_file = BytesIO()
    HTML(string=html_string, encoding='utf-8').write_pdf(pdf_file)
    pdf_file.seek(0)

    return send_file(
        pdf_file,
        as_attachment=True,
        download_name=f'تقرير_الأرصفة_{datetime.now().strftime("%Y%m%d")}.pdf',
        mimetype='application/pdf'
    )


# ============================================
# Berth Reports (تقارير الأرصفة)
# ============================================

def generate_berths_report(date_from, date_to, format):
    """توليد تقرير الأرصفة"""
    berths = Berth.query.all()

    # تجهيز بيانات الأرصفة مع السفن المرتبطة
    berths_data = []
    for berth in berths:
        ships = Ship.query.filter_by(berth_number=berth.number).all()
        current_ship = berth.current_ship.name if berth.current_ship else '—'

        berths_data.append({
            'berth': berth,
            'ships': ships,
            'ships_count': len(ships),
            'current_ship': current_ship,
            'is_available': berth.is_available,
            'is_occupied': berth.is_occupied
        })

    # إحصائيات
    stats = {
        'total': len(berths),
        'available': sum(1 for b in berths if b.is_available),
        'occupied': sum(1 for b in berths if b.is_occupied),
        'total_ships': sum(len(ships) for ships in berths_data)
    }

    if format == 'excel':
        return generate_berths_excel(berths_data, stats, date_from, date_to)
    elif format == 'pdf':
        return generate_berths_pdf(berths_data, stats, date_from, date_to)
    else:
        return render_template('reports/berths_report.html',
                               berths_data=berths_data,
                               stats=stats,
                               date_from=date_from,
                               date_to=date_to)


def generate_berths_excel(berths_data, stats, date_from, date_to):
    """توليد تقرير الأرصفة Excel"""
    output = BytesIO()

    # بيانات الأرصفة
    berths_df = pd.DataFrame([{
        'رقم الرصيف': bd['berth'].number,
        'الطول (م)': bd['berth'].length or '',
        'العمق (م)': bd['berth'].depth or '',
        'عدد السفن': bd['ships_count'],
        'السفينة الحالية': bd['current_ship'],
        'الحالة': 'متاح' if bd['is_available'] else 'غير متاح',
        'ملاحظات': bd['berth'].notes or ''
    } for bd in berths_data])

    # إحصائيات
    stats_df = pd.DataFrame([{
        'البيان': 'إجمالي الأرصفة',
        'القيمة': stats['total']
    }, {
        'البيان': 'أرصفة متاحة',
        'القيمة': stats['available']
    }, {
        'البيان': 'أرصفة مشغولة',
        'القيمة': stats['occupied']
    }, {
        'البيان': 'إجمالي السفن',
        'القيمة': stats['total_ships']
    }])

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        stats_df.to_excel(writer, sheet_name='إحصائيات', index=False)
        berths_df.to_excel(writer, sheet_name='الأرصفة', index=False)

        # إضافة شيت للسفن لكل رصيف
        for bd in berths_data:
            if bd['ships']:
                ships_df = pd.DataFrame([{
                    'اسم السفينة': s.name,
                    'رقم IMO': s.imo_number,
                    'تاريخ الوصول': s.arrival_date.strftime('%Y-%m-%d'),
                    'تاريخ المغادرة': s.departure_date.strftime('%Y-%m-%d') if s.departure_date else '',
                    'الحالة': s.status
                } for s in bd['ships']])

                ships_df.to_excel(writer, sheet_name=f'رصيف {bd["berth"].number}', index=False)

    output.seek(0)
    filename = f'report_berths_{date_from.strftime("%Y%m%d")}_{date_to.strftime("%Y%m%d")}.xlsx'

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


def generate_berths_pdf(berths_data, stats, date_from, date_to):
    """توليد تقرير الأرصفة PDF"""
    from weasyprint import HTML
    from datetime import datetime

    html_string = render_template('reports/berths_pdf.html',
                                  berths_data=berths_data,
                                  stats=stats,
                                  date_from=date_from,
                                  date_to=date_to,
                                  current_date=datetime.now())

    pdf_file = BytesIO()
    HTML(string=html_string, encoding='utf-8').write_pdf(pdf_file)
    pdf_file.seek(0)

    filename = f'report_berths_{date_from.strftime("%Y%m%d")}_{date_to.strftime("%Y%m%d")}.pdf'

    return send_file(
        pdf_file,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )


# تحديث دالة generate_report لتشمل الأرصفة
@app.route('/reports/generate', methods=['POST'])
@login_required
def generate_report():
    """توليد التقرير حسب النوع والصيغة"""
    report_type = request.form.get('report_type')
    date_from = datetime.strptime(request.form.get('date_from'), '%Y-%m-%d')
    date_to = datetime.strptime(request.form.get('date_to'), '%Y-%m-%d')
    format = request.form.get('format')

    # توجيه حسب نوع التقرير
    if report_type == 'ships':
        return generate_ships_report(date_from, date_to, format)
    elif report_type == 'employees':
        return generate_employees_report(date_from, date_to, format)
    elif report_type == 'teams':
        return generate_teams_report(date_from, date_to, format)
    elif report_type == 'operations':
        return generate_operations_report(date_from, date_to, format)
    elif report_type == 'berths':
        return generate_berths_report(date_from, date_to, format)
    else:
        flash('نوع التقرير غير مدعوم', 'danger')
        return redirect(url_for('reports_index'))

def generate_excel_report(data, report_type, date_from, date_to):
    """توليد تقرير Excel"""
    output = BytesIO()

    if report_type == 'ships':
        df = pd.DataFrame([{
            'اسم السفينة': s.name,
            'رقم IMO': s.imo_number,
            'العلم': s.flag,
            'النوع': s.ship_type,
            'تاريخ الوصول': s.arrival_date.strftime('%Y-%m-%d'),
            'رقم الرصيف': s.berth_number or '',
            'الحالة': s.status
        } for s in data])

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='السفن', index=False)

    elif report_type == 'employees':
        df = pd.DataFrame([{
            'الاسم': e.name,
            'الرقم الوطني': e.national_id,
            'مكان الميلاد': e.birth_place,
            'السكن': e.current_address,
            'تاريخ الميلاد': e.birth_date.strftime('%Y-%m-%d'),
            'المهنة': e.profession,
            'الفرقة': e.team.name if e.team else '',
            'رقم الهاتف': e.phone or ''
        } for e in data])

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='الموظفين', index=False)

    output.seek(0)
    filename = f'report_{report_type}_{date_from.strftime("%Y%m%d")}_{date_to.strftime("%Y%m%d")}.xlsx'

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


def generate_teams_excel(teams_data, date_from, date_to):
    """توليد تقرير فرق العمل Excel"""
    output = BytesIO()

    # بيانات الفرق
    teams_df = pd.DataFrame([{
        'اسم الفرقة': td['team'].name,
        'نوع الفرقة': td['team'].team_type,
        'عدد الأعضاء': td['members_count'],
        'القائد': td['leader'].name if td['leader'] else '',
        'هاتف القائد': td['leader'].phone if td['leader'] else '',
        'الحالة': 'نشطة' if td['team'].is_active else 'غير نشطة',
        'تاريخ الإنشاء': td['team'].created_at.strftime('%Y-%m-%d')
    } for td in teams_data])

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        teams_df.to_excel(writer, sheet_name='فرق العمل', index=False)

        # إضافة شيت لأعضاء كل فرقة
        for td in teams_data:
            if td['members']:
                members_df = pd.DataFrame([{
                    'الاسم': m.name,
                    'المهنة': m.profession,
                    'رقم الهاتف': m.phone or '',
                    'قائد': 'نعم' if m.id == td['team'].leader_id else ''
                } for m in td['members']])

                members_df.to_excel(writer, sheet_name=td['team'].name[:20], index=False)

    output.seek(0)
    filename = f'report_teams_{date_from.strftime("%Y%m%d")}_{date_to.strftime("%Y%m%d")}.xlsx'

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )



def generate_teams_pdf(teams_data, date_from, date_to):
    """توليد تقرير فرق العمل PDF"""
    from weasyprint import HTML
    from datetime import datetime

    # حساب الإحصائيات مسبقاً
    total_members = sum(td['members_count'] for td in teams_data)
    active_teams = sum(1 for td in teams_data if td['team'].is_active)

    html_string = render_template('reports/teams_pdf.html',
                                   teams_data=teams_data,
                                   date_from=date_from,
                                   date_to=date_to,
                                   current_date=datetime.now(),
                                   total_members=total_members,
                                   active_teams=active_teams)

    pdf_file = BytesIO()
    HTML(string=html_string, encoding='utf-8').write_pdf(pdf_file)
    pdf_file.seek(0)

    filename = f'report_teams_{date_from.strftime("%Y%m%d")}_{date_to.strftime("%Y%m%d")}.pdf'

    return send_file(
        pdf_file,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

def generate_pdf_report(data, report_type, date_from, date_to):
    """توليد تقرير PDF باستخدام HTML"""
    from weasyprint import HTML
    from datetime import datetime

    # تجهيز البيانات حسب النوع
    if report_type == 'ships':
        html_string = render_template('reports/ships_pdf.html',
                                      data=data,
                                      date_from=date_from,
                                      date_to=date_to,
                                      current_date=datetime.now())
    elif report_type == 'employees':
        html_string = render_template('reports/employees_pdf.html',
                                      data=data,
                                      date_from=date_from,
                                      date_to=date_to,
                                      current_date=datetime.now())
    elif report_type == 'operations':
        html_string = render_template('reports/operations_pdf.html',
                                      data=data,
                                      date_from=date_from,
                                      date_to=date_to,
                                      current_date=datetime.now())
    else:
        html_string = '<h1>تقرير</h1><p>لا توجد بيانات</p>'

    # تحويل HTML إلى PDF
    pdf_file = BytesIO()
    HTML(string=html_string, encoding='utf-8').write_pdf(pdf_file)
    pdf_file.seek(0)

    filename = f'report_{report_type}_{date_from.strftime("%Y%m%d")}_{date_to.strftime("%Y%m%d")}.pdf'

    return send_file(
        pdf_file,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# API routes for AJAX requests
@app.route('/api/employees/search')
@login_required
def search_employees():
    # أي موظف مسجل يمكنه البحث
    query = request.args.get('q', '')
    employees = Employee.query.filter(Employee.name.contains(query)).limit(10).all()
    return jsonify([{'id': e.id, 'name': e.name, 'profession': e.profession} for e in employees])

@app.route('/api/ships/active')
@login_required
def active_ships():
    # أي موظف مسجل يمكنه عرض السفن النشطة
    ships = Ship.query.filter_by(status='arrived').all()
    return jsonify([{'id': s.id, 'name': s.name, 'berth': s.berth_number} for s in ships])

@app.route('/api/berths/status')
@login_required
def berths_status():
    # أي موظف مسجل يمكنه عرض حالة الأرصفة
    berths = Berth.query.all()
    return jsonify([{
        'number': b.number,
        'available': b.is_available,
        'current_ship': b.current_ship_id
    } for b in berths])


@app.route('/reset-admin')
def reset_admin():
    """إعادة تعيين مستخدم admin"""
    # حذف المستخدم القديم إذا وجد
    User.query.filter_by(username='admin').delete()

    # إنشاء مستخدم جديد
    admin = User(
        username='admin',
        email='admin@rasessa.gov',
        role='admin'
    )
    admin.set_password('admin123')
    db.session.add(admin)
    db.session.commit()

    # التحقق من أن المستخدم تم حفظه
    user = User.query.filter_by(username='admin').first()

    if user and user.check_password('admin123'):
        return '''
        <html dir="rtl">
        <head>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <style>
                body { font-family: Arial; text-align: center; padding: 50px; background: #f5f7fa; }
                .success { color: #27ae60; }
                .card { background: white; border-radius: 10px; padding: 30px; max-width: 400px; margin: 0 auto; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
                .btn { display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 10px; }
            </style>
        </head>
        <body>
            <div class="card">
                <i class="fas fa-check-circle fa-4x success"></i>
                <h2 class="success">تم إنشاء المستخدم بنجاح!</h2>
                <p><strong>اسم المستخدم:</strong> admin</p>
                <p><strong>كلمة المرور:</strong> admin123</p>
                <hr>
                <a href="/login" class="btn"><i class="fas fa-sign-in-alt"></i> الذهاب لتسجيل الدخول</a>
                <a href="/test-password" class="btn" style="background: #3498db;">اختبار كلمة المرور</a>
            </div>
        </body>
        </html>
        '''
    else:
        return '''
        <html dir="rtl">
        <head>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <style>
                body { font-family: Arial; text-align: center; padding: 50px; background: #f5f7fa; }
                .error { color: #e74c3c; }
                .card { background: white; border-radius: 10px; padding: 30px; max-width: 400px; margin: 0 auto; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
            </style>
        </head>
        <body>
            <div class="card">
                <i class="fas fa-times-circle fa-4x error"></i>
                <h2 class="error">خطأ في إنشاء المستخدم</h2>
                <p>يرجى التحقق من قاعدة البيانات</p>
            </div>
        </body>
        </html>
        '''

@app.route('/create-admin')
def create_admin():
    """مسار مؤقت لإنشاء مستخدم admin"""
    with app.app_context():
        # حذف المستخدم القديم إذا وجد
        User.query.filter_by(username='admin').delete()

        # إنشاء مستخدم جديد
        admin = User(
            username='admin',
            email='admin@rasessa.gov',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

        return '''
        <html>
        <head>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        </head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <i class="fas fa-check-circle" style="color: green; font-size: 50px;"></i>
            <h1 style="color: green;">تم إنشاء المستخدم بنجاح!</h1>
            <p>اسم المستخدم: <strong>admin</strong></p>
            <p>كلمة المرور: <strong>admin123</strong></p>
            <a href="/login" style="display: inline-block; margin-top: 20px; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px;">
                <i class="fas fa-sign-in-alt"></i> الذهاب إلى تسجيل الدخول
            </a>
        </body>
        </html>
        '''


@app.route('/diagnose-login')
def diagnose_login():
    """تشخيص مشكلة تسجيل الدخول"""
    output = []
    output.append("<h2>تشخيص مشكلة تسجيل الدخول</h2>")

    # 1. التحقق من وجود المستخدمين
    users = User.query.all()
    output.append(f"<h3>1. عدد المستخدمين: {len(users)}</h3>")

    if users:
        output.append("<ul>")
        for user in users:
            output.append(f"<li>المستخدم: {user.username}, الدور: {user.role}, البريد: {user.email}</li>")
        output.append("</ul>")
    else:
        output.append("<p style='color:red'>⚠ لا يوجد مستخدمين في قاعدة البيانات!</p>")

    # 2. التحقق من نموذج تسجيل الدخول
    try:
        from forms import LoginForm
        output.append("<h3>2. نموذج تسجيل الدخول: موجود ✅</h3>")
    except Exception as e:
        output.append(f"<h3 style='color:red'>2. خطأ في نموذج تسجيل الدخول: {str(e)}</h3>")

    # 3. التحقق من مسار تسجيل الدخول
    from flask import url_for
    try:
        login_url = url_for('login')
        output.append(f"<h3>3. مسار تسجيل الدخول: {login_url} ✅</h3>")
    except Exception as e:
        output.append(f"<h3 style='color:red'>3. خطأ في مسار تسجيل الدخول: {str(e)}</h3>")

    # 4. اقتراح حلول
    output.append("<h3>4. الحلول المقترحة:</h3>")
    output.append("<ul>")
    output.append(
        "<li><a href='/reset-admin-final' style='color:blue; font-weight:bold'>🔧 الضغط هنا لإعادة تعيين المستخدم admin</a></li>")
    output.append("<li><a href='/debug-users' style='color:blue;'>👥 عرض جميع المستخدمين</a></li>")
    output.append("<li><a href='/simple-login' style='color:green;'>🚪 الدخول المباشر (بدون كلمة مرور)</a></li>")
    output.append("</ul>")

    return "<br>".join(output)


@app.route('/reset-admin-final')
def reset_admin_final():
    """إعادة تعيين المستخدم admin بشكل نهائي"""
    try:
        # حذف جميع المستخدمين
        num_deleted = User.query.delete()

        # إنشاء مستخدم جديد
        admin = User(
            username='admin',
            email='admin@rasessa.gov',
            role='admin',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

        # التحقق
        user = User.query.filter_by(username='admin').first()
        if user and user.check_password('admin123'):
            return '''
            <html dir="rtl">
            <head>
                <style>
                    body { font-family: Arial; text-align: center; padding: 50px; background: #f0f8ff; }
                    .success { color: #27ae60; }
                    .card { background: white; border-radius: 15px; padding: 30px; max-width: 500px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
                    .btn { display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 8px; margin: 10px; font-weight: bold; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1 class="success">✅ تم بنجاح!</h1>
                    <h2>تم إعادة تعيين المستخدم</h2>
                    <p style="font-size: 18px;"><strong>اسم المستخدم:</strong> admin</p>
                    <p style="font-size: 18px;"><strong>كلمة المرور:</strong> admin123</p>
                    <hr>
                    <a href="/login" class="btn">🔐 الذهاب لتسجيل الدخول</a>
                </div>
            </body>
            </html>
            '''
        else:
            return "❌ خطأ في إنشاء المستخدم"

    except Exception as e:
        return f"❌ خطأ: {str(e)}"


@app.route('/simple-login')
def simple_login():
    """تسجيل دخول مباشر بدون كلمة مرور"""
    from flask_login import login_user
    from flask import redirect

    # البحث عن مستخدم أو إنشاء واحد
    user = User.query.first()
    if not user:
        user = User(username='admin', email='admin@test.com', role='admin')
        user.set_password('admin123')
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect(url_for('dashboard'))



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@rasessa.gov',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

    app.run(debug=True)