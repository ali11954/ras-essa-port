from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import os
from sqlalchemy import func
import json
import plotly
import plotly.express as px
import pandas as pd
from io import BytesIO
from functools import wraps
from config import Config
from forms import LoginForm, EmployeeForm, ShipForm, TeamForm, ReportForm, UserForm, UserEditForm, OperationForm, BerthForm, FingerprintDeviceForm, EnrollFingerprintForm, AttendanceFilterForm
from datetime import datetime, timedelta
from models import db, User, Employee, Team, Ship, Berth, ShipOperation, Report, OperationTeam, FingerprintDevice, FingerprintEnrollment, AttendanceLog, ShipOperationTeamPermission
from flask import request  # إذا لم يكن موجوداً

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ============================================
# Helper Functions for Permissions (يجب أن تكون قبل استخدامها)
# ============================================

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('الرجاء تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('login'))
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
            if not current_user.is_authenticated:
                flash('الرجاء تسجيل الدخول أولاً', 'warning')
                return redirect(url_for('login'))
            if not current_user.is_admin() and current_user.id != user_id:
                flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ============================================
# Context Processors (يجب أن تكون بعد الدوال المساعدة)
# ============================================

@app.context_processor
def inject_now():
    """إتاحة دالة now() في جميع القوالب"""
    from datetime import datetime
    return {'now': datetime.now}

@app.context_processor
def inject_utilities():
    """إتاحة دوال مساعدة في جميع القوالب"""
    from datetime import datetime

    def format_date(date, format='%Y-%m-%d'):
        """تنسيق التاريخ"""
        if date:
            return date.strftime(format)
        return ''

    def format_datetime(date, format='%Y-%m-%d %H:%M'):
        """تنسيق التاريخ والوقت"""
        if date:
            return date.strftime(format)
        return ''

    def calculate_age(birth_date):
        """حساب العمر من تاريخ الميلاد"""
        if birth_date:
            today = datetime.now().date()
            age = today.year - birth_date.year
            if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
                age -= 1
            return age
        return ''

    return {
        'now': datetime.now,
        'format_date': format_date,
        'format_datetime': format_datetime,
        'calculate_age': calculate_age
    }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create upload folder if not exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

import traceback
import sys
import os

# ============================================
# باقي مسارات التطبيق تبدأ من هنا
# ============================================

# ... باقي الكود ...
# أضف هذه المسارات في ملف app.py بعد مسارات العمليات

# ============================================
# Fingerprint Management Routes (إدارة البصمة)
# ============================================

@app.route('/fingerprint/devices')
@login_required
def fingerprint_devices_list():
    """عرض أجهزة البصمة"""
    if not current_user.is_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))

    devices = FingerprintDevice.query.all()
    return render_template('fingerprint/devices.html', devices=devices)


@app.route('/fingerprint/devices/add', methods=['GET', 'POST'])
@login_required
@admin_required
def fingerprint_device_add():
    """إضافة جهاز بصمة جديد"""
    form = FingerprintDeviceForm()

    # تعيين خيارات الأرصفة
    berths = Berth.query.all()
    form.berth_id.choices = [(0, 'غير مرتبط برصيف')] + [(b.id, f'رصيف {b.number}') for b in berths]

    if form.validate_on_submit():
        device = FingerprintDevice(
            device_name=form.device_name.data,
            device_ip=form.device_ip.data,
            device_port=form.device_port.data,
            device_type=form.device_type.data,
            berth_id=form.berth_id.data if form.berth_id.data != 0 else None,
            is_active=form.is_active.data
        )
        db.session.add(device)
        db.session.commit()
        flash(f'✅ تم إضافة جهاز "{device.device_name}" بنجاح', 'success')
        return redirect(url_for('fingerprint_devices_list'))

    return render_template('fingerprint/device_add.html', form=form)


@app.route('/fingerprint/devices/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def fingerprint_device_edit(id):
    """تعديل جهاز بصمة"""
    device = FingerprintDevice.query.get_or_404(id)
    form = FingerprintDeviceForm(obj=device)

    berths = Berth.query.all()
    form.berth_id.choices = [(0, 'غير مرتبط برصيف')] + [(b.id, f'رصيف {b.number}') for b in berths]

    if form.validate_on_submit():
        device.device_name = form.device_name.data
        device.device_ip = form.device_ip.data
        device.device_port = form.device_port.data
        device.device_type = form.device_type.data
        device.berth_id = form.berth_id.data if form.berth_id.data != 0 else None
        device.is_active = form.is_active.data

        db.session.commit()
        flash(f'✅ تم تحديث جهاز "{device.device_name}" بنجاح', 'success')
        return redirect(url_for('fingerprint_devices_list'))

    return render_template('fingerprint/device_edit.html', form=form, device=device)


@app.route('/fingerprint/devices/delete/<int:id>')
@login_required
@admin_required
def fingerprint_device_delete(id):
    """حذف جهاز بصمة"""
    device = FingerprintDevice.query.get_or_404(id)

    # التحقق من وجود تسجيلات بصمة
    enrollments_count = FingerprintEnrollment.query.filter_by(device_id=id).count()
    if enrollments_count > 0:
        flash(f'❌ لا يمكن حذف الجهاز لوجود {enrollments_count} بصمة مسجلة', 'danger')
        return redirect(url_for('fingerprint_devices_list'))

    db.session.delete(device)
    db.session.commit()
    flash(f'✅ تم حذف جهاز "{device.device_name}" بنجاح', 'success')
    return redirect(url_for('fingerprint_devices_list'))


@app.route('/fingerprint/enroll')
@login_required
@admin_required
def fingerprint_enroll_list():
    """عرض تسجيلات البصمة"""
    enrollments = FingerprintEnrollment.query.all()
    return render_template('fingerprint/enrollments.html', enrollments=enrollments)



@app.route('/fingerprint/attendance')
@login_required
def fingerprint_attendance_list():
    """عرض سجلات الحضور"""
    form = AttendanceFilterForm()

    # تعيين خيارات الفلترة
    employees = Employee.query.all()
    form.employee_id.choices = [(0, 'الكل')] + [(e.id, e.name) for e in employees]

    operations = ShipOperation.query.all()
    form.operation_id.choices = [(0, 'الكل')] + [(op.id, f'{op.ship.name} - {op.operation_type}') for op in operations]

    # بناء الاستعلام
    query = AttendanceLog.query

    if form.date_from.data:
        query = query.filter(AttendanceLog.timestamp >= form.date_from.data)
    if form.date_to.data:
        query = query.filter(AttendanceLog.timestamp <= form.date_to.data + timedelta(days=1))
    if form.employee_id.data and form.employee_id.data != 0:
        query = query.filter(AttendanceLog.employee_id == form.employee_id.data)
    if form.operation_id.data and form.operation_id.data != 0:
        query = query.filter(AttendanceLog.operation_id == form.operation_id.data)
    if form.status.data:
        query = query.filter(AttendanceLog.status == form.status.data)

    logs = query.order_by(AttendanceLog.timestamp.desc()).all()

    # إحصائيات
    stats = {
        'total': len(logs),
        'success': len([l for l in logs if l.status == 'success']),
        'denied': len([l for l in logs if l.status == 'denied']),
        'error': len([l for l in logs if l.status == 'error']),
        'today': len([l for l in logs if l.timestamp.date() == datetime.now().date()])
    }

    return render_template('fingerprint/attendance.html', logs=logs, stats=stats, form=form)


@app.route('/api/fingerprint/verify', methods=['POST'])
@login_required
def fingerprint_verify_api():
    """API للتحقق من البصمة (يتم استدعاؤها من جهاز البصمة)"""
    data = request.get_json()

    # بيانات من الجهاز
    device_id = data.get('device_id')
    fingerprint_data = data.get('fingerprint_data')
    timestamp = datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat()))

    device = FingerprintDevice.query.get(device_id)
    if not device or not device.is_active:
        return jsonify({'success': False, 'error': 'جهاز غير معروف أو غير نشط'}), 401

    # البحث عن الموظف الذي تطابق بصمته
    enrollment = FingerprintEnrollment.query.filter_by(
        device_id=device_id,
        fingerprint_template=fingerprint_data
    ).first()

    if not enrollment:
        # تسجيل محاولة فاشلة
        log = AttendanceLog(
            employee_id=None,
            device_id=device_id,
            timestamp=timestamp,
            attendance_type='check_in',
            status='denied',
            reason='بصمة غير مسجلة',
            fingerprint_data=fingerprint_data
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': False, 'error': 'بصمة غير معروفة'}), 403

    employee = enrollment.employee

    # التحقق من أن الموظف نشط
    if not employee.is_active:
        log = AttendanceLog(
            employee_id=employee.id,
            device_id=device_id,
            timestamp=timestamp,
            attendance_type='check_in',
            status='denied',
            reason='الموظف غير نشط',
            fingerprint_data=fingerprint_data
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': False, 'error': 'الموظف غير نشط'}), 403

    # التحقق من وجود عملية نشطة على هذا الرصيف
    current_operation = None
    if device.berth_id:
        # البحث عن عملية نشطة على هذا الرصيف
        current_operation = ShipOperation.query.filter(
            ShipOperation.ship.has(berth_number=device.berth.number),
            ShipOperation.end_time == None
        ).first()

    # التحقق من صلاحية الفريق للعمل على هذه العملية
    if current_operation:
        # التحقق من أن الموظف ينتمي لفريق
        if employee.team:
            # التحقق من أن الفريق مصرح له بالعمل
            permission = ShipOperationTeamPermission.query.filter_by(
                operation_id=current_operation.id,
                team_id=employee.team.id,
                is_allowed=True
            ).first()

            if not permission:
                log = AttendanceLog(
                    employee_id=employee.id,
                    device_id=device_id,
                    operation_id=current_operation.id,
                    timestamp=timestamp,
                    attendance_type='check_in',
                    status='denied',
                    reason=f'الفريق {employee.team.name} غير مصرح له بالعمل على هذه السفينة',
                    fingerprint_data=fingerprint_data
                )
                db.session.add(log)
                db.session.commit()
                return jsonify({'success': False, 'error': 'فريقك غير مصرح له بالعمل على هذه السفينة'}), 403
        else:
            log = AttendanceLog(
                employee_id=employee.id,
                device_id=device_id,
                operation_id=current_operation.id,
                timestamp=timestamp,
                attendance_type='check_in',
                status='denied',
                reason='الموظف لا ينتمي لأي فريق',
                fingerprint_data=fingerprint_data
            )
            db.session.add(log)
            db.session.commit()
            return jsonify({'success': False, 'error': 'أنت لا تنتمي لأي فريق'}), 403

    # تسجيل الحضور الناجح
    log = AttendanceLog(
        employee_id=employee.id,
        device_id=device_id,
        operation_id=current_operation.id if current_operation else None,
        timestamp=timestamp,
        attendance_type='check_in',
        status='success',
        fingerprint_data=fingerprint_data
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'success': True,
        'employee': {
            'id': employee.id,
            'name': employee.name,
            'team': employee.team.name if employee.team else None,
            'profession': employee.profession
        },
        'operation': {
            'id': current_operation.id,
            'ship_name': current_operation.ship.name,
            'berth': current_operation.ship.berth_number
        } if current_operation else None
    })


@app.route('/api/fingerprint/enroll', methods=['POST'])
def fingerprint_enroll_from_device():
    """استقبال تسجيل بصمة جديدة من جهاز البصمة الفعلي"""
    import json

    # تسجيل الطلب للتشخيص
    with open('fingerprint_enroll_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"\n{'=' * 50}\n")
        f.write(f"الوقت: {datetime.now()}\n")
        f.write(f"البيانات: {request.get_data(as_text=True)}\n")

    try:
        # قراءة البيانات
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        # استخراج البيانات
        device_id = data.get('device_id')
        employee_code = data.get('employee_code')
        fingerprint_data = data.get('fingerprint_data')
        finger_index = data.get('finger_index', 1)

        # البحث عن الجهاز
        device = None
        if device_id:
            device = FingerprintDevice.query.get(device_id)

        if not device:
            device = FingerprintDevice.query.first()

        if not device:
            return jsonify({'success': False, 'error': 'لا توجد أجهزة بصمة في النظام'}), 401

        # البحث عن الموظف
        employee = None
        if employee_code:
            employee = Employee.query.filter_by(employee_code=employee_code, is_active=True).first()

        if not employee:
            return jsonify({
                'success': False,
                'error': f'موظف بالكود {employee_code} غير موجود في النظام'
            }), 404

        # التحقق من عدم وجود تسجيل مسبق
        existing = FingerprintEnrollment.query.filter_by(
            employee_id=employee.id,
            device_id=device.id,
            fingerprint_index=finger_index
        ).first()

        if existing:
            return jsonify({
                'success': False,
                'error': f'بصمة {get_finger_name(finger_index)} للموظف {employee.name} مسجلة مسبقاً'
            }), 409

        # تسجيل البصمة في قاعدة البيانات
        enrollment = FingerprintEnrollment(
            employee_id=employee.id,
            device_id=device.id,
            fingerprint_template=fingerprint_data,
            fingerprint_index=finger_index,
            is_active=True
        )
        db.session.add(enrollment)
        db.session.commit()

        with open('fingerprint_enroll_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"✅ تم تسجيل بصمة {get_finger_name(finger_index)} للموظف {employee.name}\n")

        return jsonify({
            'success': True,
            'message': f'تم تسجيل بصمة {get_finger_name(finger_index)} للموظف {employee.name}',
            'employee': {
                'id': employee.id,
                'name': employee.name,
                'code': employee.employee_code
            },
            'enrollment_id': enrollment.id
        })

    except Exception as e:
        import traceback
        with open('fingerprint_enroll_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"❌ خطأ: {traceback.format_exc()}\n")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/test-enroll-from-device', methods=['GET', 'POST'])
def test_enroll_from_device():
    """اختبار تسجيل بصمة من جهاز البصمة"""
    if request.method == 'POST':
        try:
            device_id = int(request.form.get('device_id', 1))
            employee_code = request.form.get('employee_code', '3456')
            finger_index = int(request.form.get('finger_index', 1))

            test_data = {
                'device_id': device_id,
                'employee_code': employee_code,
                'fingerprint_data': f'template_{employee_code}_{finger_index}_{datetime.now().strftime("%H%M%S")}',
                'finger_index': finger_index
            }

            # استدعاء API التسجيل
            with app.test_client() as client:
                response = client.post('/api/fingerprint/enroll',
                                       json=test_data,
                                       headers={'Content-Type': 'application/json'})
                response_data = response.get_json()
                status_code = response.status_code

            return f"""
            <html dir="rtl">
                <head>
                    <style>
                        body {{ font-family: Arial; padding: 20px; direction: rtl; background: #f5f7fa; }}
                        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; }}
                        .success {{ color: green; }}
                        .error {{ color: red; }}
                        pre {{ background: #f0f0f0; padding: 10px; border-radius: 5px; }}
                        .btn {{ display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>🔬 نتيجة تسجيل بصمة من جهاز البصمة</h2>

                        <h4>📤 البيانات المرسلة:</h4>
                        <pre>{json.dumps(test_data, indent=2, ensure_ascii=False)}</pre>

                        <h4>📥 الرد من الخادم:</h4>
                        <pre>حالة HTTP: {status_code}</pre>
                        <pre>{json.dumps(response_data, indent=2, ensure_ascii=False)}</pre>

                        <div class="alert alert-{'success' if response_data and response_data.get('success') else 'danger'}">
                            {'✅ تم تسجيل البصمة بنجاح!' if response_data and response_data.get('success') else '❌ فشل التسجيل: ' + (response_data.get('error', 'خطأ غير معروف') if response_data else 'لا توجد استجابة')}
                        </div>

                        <hr>
                        <a href="/test-enroll-from-device" class="btn">🔙 العودة للاختبار</a>
                        <a href="/fingerprint/enroll" class="btn">📋 عرض تسجيلات البصمة</a>
                    </div>
                </body>
            </html>
            """
        except Exception as e:
            return f"<h1 style='color:red'>خطأ: {str(e)}</h1>"

    # عرض نموذج الاختبار
    devices = FingerprintDevice.query.all()
    employees = Employee.query.filter(Employee.employee_code.isnot(None)).all()

    device_options = ''.join([f'<option value="{d.id}">{d.device_name} (ID: {d.id})</option>' for d in devices])
    employee_options = ''.join(
        [f'<option value="{e.employee_code}">{e.name} - كود: {e.employee_code}</option>' for e in employees])

    return f"""
    <html dir="rtl">
        <head>
            <style>
                body {{ font-family: Arial; padding: 20px; direction: rtl; background: #f5f7fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; }}
                input, select {{ width: 100%; padding: 8px; margin: 5px 0 15px; border: 1px solid #ddd; border-radius: 5px; }}
                button {{ background: #667eea; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }}
                .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🔬 اختبار تسجيل بصمة من جهاز البصمة</h2>
                <p>محاكاة لما يرسله جهاز البصمة عند تسجيل بصمة جديدة</p>

                <form method="POST">
                    <label>📟 معرف الجهاز:</label>
                    <select name="device_id">
                        {device_options}
                    </select>

                    <label>👤 كود الموظف:</label>
                    <select name="employee_code">
                        {employee_options}
                    </select>

                    <label>🖐️ رقم الإصبع:</label>
                    <select name="finger_index">
                        <option value="1">الإبهام</option>
                        <option value="2">السبابة</option>
                        <option value="3">الوسطى</option>
                        <option value="4">البنصر</option>
                        <option value="5">الخنصر</option>
                    </select>

                    <button type="submit">🚀 محاكاة تسجيل بصمة</button>
                </form>

                <div class="info">
                    <strong>📌 ملاحظات:</strong>
                    <ul>
                        <li>هذا الاختبار يحاكي ما يرسله جهاز البصمة عند تسجيل بصمة جديدة</li>
                        <li>يجب أن يكون الموظف موجوداً في النظام وله <code>employee_code</code></li>
                        <li>بعد التسجيل، ستظهر البصمة في صفحة <a href="/fingerprint/enroll">تسجيلات البصمة</a></li>
                    </ul>
                </div>

                <hr>
                <a href="/fingerprint/enroll">📋 عرض تسجيلات البصمة</a>
                <a href="/fingerprint/diagnose">🔍 تشخيص النظام</a>
            </div>
        </body>
    </html>
    """


from zk import ZK
from datetime import datetime, timedelta


def fetch_fingerprint_from_device(device_ip, device_port=4370, timeout=30):
    """
    جلب بيانات البصمة من جهاز مباشرة - مثل النظام الثاني
    """
    try:
        zk = ZK(device_ip, port=device_port, timeout=timeout)
        conn = zk.connect()
        conn.disable_device()

        attendance = conn.get_attendance()

        conn.enable_device()
        conn.disconnect()

        return attendance
    except Exception as e:
        print(f"❌ خطأ في الاتصال بالجهاز {device_ip}: {e}")
        return []


def sync_fingerprint_from_devices(start_date=None, end_date=None):
    """
    مزامنة البصمات من جميع الأجهزة - مثل النظام الثاني
    """
    devices = FingerprintDeviceConfig.query.filter_by(enabled=True).all()

    if not start_date:
        start_date = datetime.now().date()
    if not end_date:
        end_date = datetime.now().date()

    all_records = []

    for device in devices:
        print(f"🔌 الاتصال بجهاز: {device.name} ({device.ip})")

        attendance = fetch_fingerprint_from_device(device.ip, device.port, device.timeout)

        for att in attendance:
            att_date = att.timestamp.date()

            # فلترة حسب التاريخ
            if start_date <= att_date <= end_date:
                all_records.append({
                    'employee_code': str(att.user_id),
                    'timestamp': att.timestamp,
                    'device_id': device.id,
                    'device_name': device.name,
                    'check_in': att.timestamp.strftime('%H:%M'),
                    'check_out': None
                })

    return merge_attendance_records(all_records)


def merge_attendance_records(records):
    """
    دمج سجلات الدخول والخروج - مثل النظام الثاني
    """
    merged = {}

    for rec in records:
        emp_code = rec['employee_code']
        date_key = rec['timestamp'].strftime('%Y-%m-%d')
        key = (emp_code, date_key)

        if key not in merged:
            merged[key] = {
                'employee_code': emp_code,
                'date': rec['timestamp'].date(),
                'check_in': rec['check_in'],
                'check_out': rec['check_out'],
                'device_name': rec.get('device_name', 'غير معروف')
            }
        else:
            # تحديث وقت الخروج
            if rec['check_in'] > merged[key]['check_in']:
                merged[key]['check_out'] = rec['check_in']

    return list(merged.values())


@app.route('/fingerprint/sync')
@login_required
@admin_required
def fingerprint_sync():
    """مزامنة البصمات من الأجهزة مباشرة - مثل النظام الثاني"""
    try:
        # جلب الأجهزة من التكوين الجديد
        devices = FingerprintDeviceConfig.query.filter_by(enabled=True).all()

        if not devices:
            flash('❌ لا توجد أجهزة بصمة مفعلة', 'danger')
            return redirect(url_for('fingerprint_devices_list'))

        # مزامنة البيانات من الأجهزة
        records = sync_fingerprint_from_devices()

        saved_count = 0
        for rec in records:
            # البحث عن الموظف
            employee = Employee.query.filter_by(employee_code=rec['employee_code']).first()

            if employee:
                # تسجيل الحضور في AttendanceLog
                log = AttendanceLog(
                    employee_id=employee.id,
                    device_id=1,  # معرف افتراضي
                    timestamp=datetime.combine(rec['date'], datetime.strptime(rec['check_in'], '%H:%M').time()),
                    attendance_type='check_in',
                    status='success',
                    reason='مزامنة من جهاز البصمة'
                )
                db.session.add(log)
                saved_count += 1

        db.session.commit()

        flash(f'✅ تم مزامنة {saved_count} سجل حضور من الأجهزة', 'success')

    except Exception as e:
        flash(f'❌ خطأ في المزامنة: {str(e)}', 'danger')

    return redirect(url_for('fingerprint_attendance_list'))


@app.route('/fingerprint/sync-all')
@login_required
@admin_required
def fingerprint_sync_all():
    """مزامنة جميع البيانات مع عرض النتائج - مثل النظام الثاني"""
    devices = FingerprintDeviceConfig.query.filter_by(enabled=True).all()
    results = []

    for device in devices:
        try:
            attendance = fetch_fingerprint_from_device(device.ip, device.port, device.timeout)

            results.append({
                'device_name': device.name,
                'device_ip': device.ip,
                'status': 'success',
                'records_count': len(attendance)
            })

        except Exception as e:
            results.append({
                'device_name': device.name,
                'device_ip': device.ip,
                'status': 'error',
                'error': str(e)
            })

    return render_template('fingerprint/sync_results.html', results=results)

@app.route('/fingerprint/operations')
@login_required
@admin_required
def fingerprint_operation_teams_list():
    """عرض قائمة العمليات لإدارة صلاحيات البصمة"""
    operations = ShipOperation.query.order_by(ShipOperation.start_time.desc()).all()

    # تجهيز بيانات العمليات مع معلومات الصلاحيات
    operations_data = []
    for op in operations:
        allowed_teams = [p.team_id for p in op.team_permissions]
        operations_data.append({
            'operation': op,
            'allowed_teams': allowed_teams,
            'allowed_teams_count': len(allowed_teams),
            'ship_name': op.ship.name if op.ship else '—',
            'is_active': op.end_time is None
        })

    return render_template('fingerprint/operations_list.html',
                           operations=operations_data)


@app.route('/fingerprint/operations/<int:operation_id>/teams', methods=['GET', 'POST'])
@login_required
@admin_required
def fingerprint_operation_teams(operation_id):
    """إدارة الفرق المسموح لها بالعمل على عملية معينة"""
    # التحقق من وجود العملية
    operation = ShipOperation.query.get(operation_id)
    if not operation:
        flash('⚠️ العملية غير موجودة', 'warning')
        return redirect(url_for('fingerprint_operation_teams_list'))

    if request.method == 'POST':
        # تحديث الصلاحيات
        team_ids = request.form.getlist('team_ids')

        # حذف الصلاحيات القديمة
        ShipOperationTeamPermission.query.filter_by(operation_id=operation_id).delete()

        # إضافة الصلاحيات الجديدة
        for team_id in team_ids:
            if team_id and team_id.isdigit():
                permission = ShipOperationTeamPermission(
                    operation_id=operation_id,
                    team_id=int(team_id),
                    granted_by=current_user.id
                )
                db.session.add(permission)

        db.session.commit()
        flash(f'✅ تم تحديث الفرق المسموح لها بالعمل على عملية {operation.id}', 'success')
        return redirect(url_for('fingerprint_operation_teams', operation_id=operation_id))

    # عرض الصلاحيات الحالية
    all_teams = Team.query.filter_by(is_active=True).all()
    allowed_teams = [p.team_id for p in operation.team_permissions]

    return render_template('fingerprint/operation_teams.html',
                           operation=operation,
                           all_teams=all_teams,
                           allowed_teams=allowed_teams)

# دوال مساعدة للاتصال بأجهزة البصمة
def enroll_fingerprint_to_device(device_id, employee_id, finger_index):
    """تسجيل بصمة على جهاز فعلي"""
    # هذه دالة محاكاة - في التطبيق الفعلي ستتصل بالجهاز عبر SDK
    device = FingerprintDevice.query.get(device_id)

    # محاكاة الاتصال بالجهاز
    if device and device.is_active:
        # هنا يتم الاتصال الفعلي بجهاز البصمة
        return {
            'success': True,
            'template': f'TEMPLATE_{employee_id}_{finger_index}'
        }
    else:
        return {
            'success': False,
            'error': 'الجهاز غير متاح'
        }


def delete_fingerprint_from_device(device_id, employee_id, finger_index):
    """حذف بصمة من جهاز فعلي"""
    # دالة محاكاة
    return {'success': True}


def get_finger_name(index):
    """الحصول على اسم الإصبع بالعربية"""
    fingers = {
        1: 'الإبهام',
        2: 'السبابة',
        3: 'الوسطى',
        4: 'البنصر',
        5: 'الخنصر'
    }
    return fingers.get(index, f'إصبع {index}')


# أضف هذه الدالة بعد دوال البصمة المساعدة

def check_device_connection(device_id):
    """التحقق من اتصال جهاز البصمة بالشبكة"""
    device = FingerprintDevice.query.get(device_id)

    if not device:
        return {
            'connected': False,
            'error': 'الجهاز غير موجود في قاعدة البيانات',
            'status': 'not_found'
        }

    if not device.is_active:
        return {
            'connected': False,
            'error': 'الجهاز غير نشط في النظام',
            'status': 'inactive'
        }

    if not device.device_ip:
        return {
            'connected': False,
            'error': 'لم يتم تعيين عنوان IP للجهاز',
            'status': 'no_ip'
        }

    # محاولة الاتصال بالجهاز عبر ping أو HTTP
    import subprocess
    import platform
    import socket

    try:
        # طريقة 1: محاولة ping
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        result = subprocess.run(['ping', param, '1', device.device_ip],
                                capture_output=True,
                                timeout=5)

        if result.returncode == 0:
            # ping ناجح
            return {
                'connected': True,
                'status': 'online',
                'ip': device.device_ip,
                'port': device.device_port,
                'method': 'ping'
            }

        # طريقة 2: محاولة اتصال TCP على المنفذ
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((device.device_ip, device.device_port))
        sock.close()

        if result == 0:
            return {
                'connected': True,
                'status': 'online',
                'ip': device.device_ip,
                'port': device.device_port,
                'method': 'tcp'
            }

        return {
            'connected': False,
            'error': f'لا يمكن الاتصال بالجهاز {device.device_ip}:{device.device_port}',
            'status': 'offline'
        }

    except subprocess.TimeoutExpired:
        return {
            'connected': False,
            'error': 'انتهت مهلة الاتصال بالجهاز',
            'status': 'timeout'
        }
    except Exception as e:
        return {
            'connected': False,
            'error': f'خطأ في الاتصال: {str(e)}',
            'status': 'error'
        }


def get_device_status(device_id):
    """الحصول على حالة الجهاز بشكل مفصل"""
    connection = check_device_connection(device_id)

    device = FingerprintDevice.query.get(device_id)

    # حساب عدد البصمات المسجلة
    enrollments_count = FingerprintEnrollment.query.filter_by(
        device_id=device_id,
        is_active=True
    ).count()

    # آخر تسجيل حضور
    last_attendance = AttendanceLog.query.filter_by(
        device_id=device_id
    ).order_by(AttendanceLog.timestamp.desc()).first()

    return {
        'connection': connection,
        'device': {
            'id': device.id,
            'name': device.device_name,
            'ip': device.device_ip,
            'port': device.device_port,
            'type': device.device_type,
            'berth': device.berth.number if device.berth else None,
            'is_active': device.is_active
        },
        'statistics': {
            'enrollments_count': enrollments_count,
            'last_attendance': last_attendance.timestamp.strftime('%Y-%m-%d %H:%M:%S') if last_attendance else None,
            'total_attendance': AttendanceLog.query.filter_by(device_id=device_id).count()
        }
    }


# إضافة مسار API للتحقق من حالة الجهاز
@app.route('/api/fingerprint/device/<int:device_id>/status')
@login_required
def api_device_status(device_id):
    """API للتحقق من حالة جهاز البصمة"""
    if not current_user.is_admin():
        return jsonify({'error': 'غير مصرح'}), 403

    status = get_device_status(device_id)
    return jsonify(status)


# إضافة مسار لعرض حالة جميع الأجهزة
@app.route('/fingerprint/devices/status')
@login_required
def fingerprint_devices_status():
    """عرض حالة جميع أجهزة البصمة"""
    if not current_user.is_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard'))

    devices = FingerprintDevice.query.all()
    devices_status = []

    for device in devices:
        status = get_device_status(device.id)
        devices_status.append(status)

    return render_template('fingerprint/devices_status.html', devices_status=devices_status)



# تحديث دالة تسجيل البصمة لتشمل التحقق من الاتصال
@app.route('/fingerprint/enroll/add', methods=['GET', 'POST'])
@login_required
@admin_required
def fingerprint_enroll_add():
    """تسجيل بصمة جديدة مع التحقق من اتصال الجهاز"""
    form = EnrollFingerprintForm()

    # تعيين خيارات الموظفين
    employees = Employee.query.filter_by(is_active=True).all()
    form.employee_id.choices = [(e.id, f'{e.name} ({e.national_id})') for e in employees]

    # تعيين خيارات الأجهزة
    devices = FingerprintDevice.query.filter_by(is_active=True).all()
    form.device_id.choices = [(d.id, d.device_name) for d in devices]

    if form.validate_on_submit():
        # التحقق من اتصال الجهاز قبل محاولة التسجيل
        device_check = check_device_connection(form.device_id.data)

        if not device_check['connected']:
            flash(f'❌ لا يمكن الاتصال بالجهاز: {device_check["error"]}', 'danger')
            return render_template('fingerprint/enroll_add.html', form=form)

        # التحقق من عدم وجود تسجيل مسبق
        existing = FingerprintEnrollment.query.filter_by(
            employee_id=form.employee_id.data,
            device_id=form.device_id.data,
            fingerprint_index=form.finger_index.data
        ).first()

        if existing:
            flash('⚠️ هذا الموظف مسجل بنفس الإصبع على هذا الجهاز مسبقاً', 'warning')
            return render_template('fingerprint/enroll_add.html', form=form)

        try:
            # استدعاء دالة الاتصال بالجهاز
            result = enroll_fingerprint_to_device(
                device_id=form.device_id.data,
                employee_id=form.employee_id.data,
                finger_index=form.finger_index.data
            )

            if result['success']:
                enrollment = FingerprintEnrollment(
                    employee_id=form.employee_id.data,
                    device_id=form.device_id.data,
                    fingerprint_template=result['template'],
                    fingerprint_index=form.finger_index.data,
                    is_active=True
                )
                db.session.add(enrollment)
                db.session.commit()

                employee = Employee.query.get(form.employee_id.data)
                flash(f'✅ تم تسجيل بصمة {get_finger_name(form.finger_index.data)} للموظف {employee.name}', 'success')
            else:
                flash(f'❌ فشل تسجيل البصمة: {result["error"]}', 'danger')

        except Exception as e:
            flash(f'❌ خطأ في الاتصال بالجهاز: {str(e)}', 'danger')

        return redirect(url_for('fingerprint_enroll_list'))

    return render_template('fingerprint/enroll_add.html', form=form)


@app.route('/fingerprint/enroll/delete/<int:id>')
@login_required
@admin_required
def fingerprint_enroll_delete(id):
    """حذف تسجيل بصمة"""
    enrollment = FingerprintEnrollment.query.get_or_404(id)

    # حفظ معلومات للتأكيد
    employee_name = enrollment.employee.name
    device_name = enrollment.device.device_name
    finger_name = get_finger_name(enrollment.fingerprint_index)

    try:
        # محاولة حذف البصمة من الجهاز الفعلي
        result = delete_fingerprint_from_device(
            device_id=enrollment.device_id,
            employee_id=enrollment.employee_id,
            finger_index=enrollment.fingerprint_index
        )

        # حذف من قاعدة البيانات
        db.session.delete(enrollment)
        db.session.commit()

        if result['success']:
            flash(f'✅ تم حذف بصمة {finger_name} للموظف {employee_name} من الجهاز {device_name}', 'success')
        else:
            flash(f'⚠️ تم حذف البصمة من قاعدة البيانات لكن فشل الحذف من الجهاز: {result["error"]}', 'warning')

    except Exception as e:
        # حتى لو فشل الاتصال بالجهاز، نحذف من قاعدة البيانات
        db.session.delete(enrollment)
        db.session.commit()
        flash(f'⚠️ تم حذف البصمة من قاعدة البيانات مع خطأ في الاتصال بالجهاز: {str(e)}', 'warning')

    return redirect(url_for('fingerprint_enroll_list'))


@app.route('/fingerprint/enroll/delete-multiple', methods=['POST'])
@login_required
@admin_required
def fingerprint_enroll_delete_multiple():
    """حذف عدة تسجيلات بصمة"""
    try:
        data = request.get_json()
        ids = data.get('ids', [])

        deleted_count = 0
        for id in ids:
            enrollment = FingerprintEnrollment.query.get(id)
            if enrollment:
                db.session.delete(enrollment)
                deleted_count += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'deleted': deleted_count
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/fingerprint/enroll/delete-all', methods=['POST'])
@login_required
@admin_required
def fingerprint_enroll_delete_all():
    """حذف جميع تسجيلات البصمة"""
    try:
        count = FingerprintEnrollment.query.count()
        FingerprintEnrollment.query.delete()
        db.session.commit()

        return jsonify({
            'success': True,
            'deleted': count
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def generate_employee_code():
    """توليد كود موظف فريد"""
    # البحث عن أكبر كود موجود
    last_employee = Employee.query.order_by(Employee.id.desc()).first()

    if last_employee and last_employee.employee_code:
        # استخراج الرقم من الكود
        try:
            code_num = int(last_employee.employee_code)
            new_num = code_num + 1
        except:
            new_num = 100001
    else:
        # أول موظف يبدأ من 100001
        new_num = 100001

    # التأكد من عدم التكرار
    while True:
        code = str(new_num)
        existing = Employee.query.filter_by(employee_code=code).first()
        if not existing:
            break
        new_num += 1

    return code

# app.py - إضافة مسار لإضافة موظف تجريبي
# app.py - تحديث مسار إضافة الموظف التجريبي

@app.route('/add-test-employee')
def add_test_employee():
    """إضافة موظف تجريبي للاختبار بكود 3456"""
    try:
        # التحقق من عدم وجود الموظف مسبقاً
        existing = Employee.query.filter_by(employee_code='3456').first()
        if existing:
            return f"""
            <html dir="rtl">
                <head>
                    <style>
                        body {{ font-family: Arial; padding: 40px; background: #f5f7fa; text-align: center; }}
                        .warning {{ color: #ffc107; font-size: 24px; }}
                        .card {{ background: white; padding: 30px; border-radius: 15px; max-width: 500px; margin: 0 auto; }}
                        .btn {{ display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 10px; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2 class="warning">⚠️ الموظف موجود مسبقاً</h2>
                        <p><strong>الكود:</strong> <span style="font-size: 24px; font-weight: bold;">{existing.employee_code}</span></p>
                        <p><strong>الاسم:</strong> {existing.name}</p>
                        <p><strong>الرقم الوطني:</strong> {existing.national_id}</p>
                        <a href="/employees" class="btn">عرض الموظفين</a>
                    </div>
                </body>
            </html>
            """

        # التحقق من عدم وجود كود 3456
        code_exists = Employee.query.filter_by(employee_code='3456').first()
        if code_exists:
            return f"""
            <html dir="rtl">
                <body>
                    <h1>⚠️ الكود 3456 مستخدم من قبل موظف آخر</h1>
                    <a href="/employees">عرض الموظفين</a>
                </body>
            </html>
            """

        # إنشاء الموظف التجريبي بالكود 3456
        test_employee = Employee(
            employee_code='3456',  # الكود المطلوب
            name='علي أحمد علي مبارك',
            national_id='34567890123456',
            birth_place='عدن',
            current_address='المعلا - عدن',
            birth_date=datetime(1985, 5, 15).date(),
            profession='عامل',
            team_id=None,
            phone='777123456',
            hire_date=datetime.now().date(),
            is_active=True
        )

        db.session.add(test_employee)
        db.session.commit()

        return f"""
        <html dir="rtl">
            <head>
                <style>
                    body {{ font-family: Arial; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; }}
                    .card {{ background: white; padding: 40px; border-radius: 20px; max-width: 600px; width: 90%; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }}
                    .success {{ color: #28a745; font-size: 28px; margin-bottom: 20px; }}
                    .employee-code {{ background: #667eea; color: white; padding: 15px; border-radius: 10px; text-align: center; margin: 20px 0; }}
                    .employee-code span {{ font-size: 48px; font-weight: bold; letter-spacing: 5px; }}
                    .info {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; }}
                    .info-item {{ display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #eee; }}
                    .info-item:last-child {{ border-bottom: none; }}
                    .badge {{ background: #28a745; color: white; padding: 5px 10px; border-radius: 5px; font-size: 14px; }}
                    .btn {{ display: inline-block; padding: 12px 25px; background: #28a745; color: white; text-decoration: none; border-radius: 8px; margin: 5px; font-weight: bold; }}
                    .btn-secondary {{ background: #667eea; }}
                    .fingerprint-icon {{ font-size: 24px; margin-left: 10px; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1 class="success">✅ تم إضافة الموظف التجريبي بنجاح!</h1>

                    <div class="employee-code">
                        <i class="fas fa-qrcode fingerprint-icon"></i>
                        <span>{test_employee.employee_code}</span>
                        <br>
                        <small>كود الموظف للبصمة</small>
                    </div>

                    <div class="info">
                        <h3>📋 بيانات الموظف:</h3>
                        <div class="info-item">
                            <strong>الاسم:</strong>
                            <span>{test_employee.name}</span>
                        </div>
                        <div class="info-item">
                            <strong>الرقم الوطني:</strong>
                            <span>{test_employee.national_id}</span>
                        </div>
                        <div class="info-item">
                            <strong>مكان الميلاد:</strong>
                            <span>{test_employee.birth_place}</span>
                        </div>
                        <div class="info-item">
                            <strong>السكن الحالي:</strong>
                            <span>{test_employee.current_address}</span>
                        </div>
                        <div class="info-item">
                            <strong>المهنة:</strong>
                            <span>{test_employee.profession}</span>
                        </div>
                        <div class="info-item">
                            <strong>رقم الهاتف:</strong>
                            <span>{test_employee.phone}</span>
                        </div>
                        <div class="info-item">
                            <strong>تاريخ الميلاد:</strong>
                            <span>{test_employee.birth_date.strftime('%Y-%m-%d')}</span>
                        </div>
                    </div>

                    <div style="text-align: center;">
                        <a href="/employees" class="btn">👥 عرض جميع الموظفين</a>
                        <a href="/fingerprint/enroll/add?employee_id={test_employee.id}" class="btn btn-secondary">
                            🔐 تسجيل بصمة للموظف
                        </a>
                    </div>

                    <hr>
                    <div style="text-align: center; margin-top: 20px; color: #6c757d; font-size: 12px;">
                        <i class="fas fa-info-circle"></i>
                        ملاحظة: كود الموظف <strong>3456</strong> هو الكود الذي سيتم استخدامه في جهاز البصمة
                    </div>
                </div>
            </body>
        </html>
        """

    except Exception as e:
        import traceback
        return f"""
        <html dir="rtl">
            <head>
                <style>
                    body {{ font-family: Arial; padding: 40px; background: #f8f9fa; }}
                    .error {{ color: #dc3545; }}
                    pre {{ background: #f0f0f0; padding: 15px; border-radius: 5px; overflow-x: auto; }}
                </style>
            </head>
            <body>
                <h1 class="error">❌ خطأ في إضافة الموظف</h1>
                <pre>{str(e)}</pre>
                <pre>{traceback.format_exc()}</pre>
                <a href="/">🏠 العودة للرئيسية</a>
            </body>
        </html>
        """, 500

# ============================================
# نهاية مسارات البصمة
# ============================================

# ============================================
# Helper Functions for Permissions
# ============================================
@app.context_processor
def inject_now():
    """إتاحة دالة now() في جميع القوالب"""
    from datetime import datetime
    return {'now': datetime.now}

@app.context_processor
def inject_utilities():
    """إتاحة دوال مساعدة في جميع القوالب"""
    from datetime import datetime

    def format_date(date, format='%Y-%m-%d'):
        """تنسيق التاريخ"""
        if date:
            return date.strftime(format)
        return ''

    def format_datetime(date, format='%Y-%m-%d %H:%M'):
        """تنسيق التاريخ والوقت"""
        if date:
            return date.strftime(format)
        return ''

    def calculate_age(birth_date):
        """حساب العمر من تاريخ الميلاد"""
        if birth_date:
            today = datetime.now().date()
            age = today.year - birth_date.year
            if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
                age -= 1
            return age
        return ''

    return {
        'now': datetime.now,
        'format_date': format_date,
        'format_datetime': format_datetime,
        'calculate_age': calculate_age
    }

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

import traceback
import sys
import os


# صفحة تشخيص شاملة
@app.route('/diagnose-all')
def diagnose_all():
    """تشخيص شامل للتطبيق"""
    output = []
    output.append("<html dir='rtl'><head><title>🔍 تشخيص التطبيق</title>")
    output.append(
        "<style>body{font-family:Arial;padding:20px;background:#f5f7fa;} pre{background:#fff;padding:15px;border-radius:5px;}</style>")
    output.append("</head><body>")
    output.append("<h1>🔍 تشخيص التطبيق</h1>")

    # 1. معلومات البيئة
    output.append("<h2>1. معلومات البيئة:</h2>")
    output.append(f"<p>Python: {sys.version}</p>")
    output.append(f"<p>المجلد الحالي: {os.getcwd()}</p>")

    # 2. الملفات الموجودة
    output.append("<h2>2. الملفات المهمة:</h2>")
    important_files = ['app.py', 'models.py', 'init_db.py', 'import_data.py', 'config.py', 'forms.py']
    for file in important_files:
        exists = os.path.exists(file)
        status = "✅ موجود" if exists else "❌ غير موجود"
        output.append(f"<p>{file}: {status}</p>")

    # 3. قاعدة البيانات
    output.append("<h2>3. حالة قاعدة البيانات:</h2>")
    try:
        from models import db, User, Employee, Team, Ship, Berth
        with app.app_context():
            # عدد الجداول
            tables = db.engine.table_names()
            output.append(f"<p>الجداول الموجودة: {', '.join(tables) if tables else 'لا توجد جداول'}</p>")

            # عدد المستخدمين
            users_count = User.query.count()
            output.append(f"<p>عدد المستخدمين: {users_count}</p>")

            if users_count > 0:
                users = User.query.all()
                for user in users:
                    output.append(f"<p> - {user.username} ({user.role})</p>")
    except Exception as e:
        output.append(f"<p style='color:red'>❌ خطأ في قاعدة البيانات: {str(e)}</p>")

    # 4. اختبار المسارات
    output.append("<h2>4. اختبار المسارات:</h2>")
    routes_to_test = [
        ('/', 'الصفحة الرئيسية'),
        ('/login', 'تسجيل الدخول'),
        ('/dashboard', 'لوحة التحكم'),
        ('/employees', 'الموظفين'),
        ('/teams', 'الفرق'),
        ('/ships', 'السفن'),
        ('/berths', 'الأرصفة'),
        ('/init-db?key=123456', 'تهيئة قاعدة البيانات'),
        ('/import-employees?key=123456', 'استيراد الموظفين')
    ]

    for route, name in routes_to_test:
        from flask import url_for
        try:
            with app.test_request_context():
                url = url_for(route.strip('/').replace('?', '_').split('_')[0] or 'index')
                output.append(f"<p>✅ {name}: {url}</p>")
        except Exception as e:
            output.append(f"<p style='color:orange'>⚠️ {name}: غير متاح</p>")

    # 5. اختبار تسجيل الدخول
    output.append("<h2>5. اختبار تسجيل الدخول:</h2>")
    try:
        from forms import LoginForm
        output.append("<p>✅ نموذج تسجيل الدخول موجود</p>")
    except Exception as e:
        output.append(f"<p style='color:red'>❌ خطأ في نموذج تسجيل الدخول: {str(e)}</p>")

    # 6. روابط سريعة
    output.append("<h2>6. روابط سريعة:</h2>")
    base_url = request.host_url.rstrip('/')
    output.append(f"""
    <ul>
        <li><a href="{base_url}/init-db?key=123456" target="_blank">🔧 تهيئة قاعدة البيانات</a></li>
        <li><a href="{base_url}/import-employees?key=123456" target="_blank">📥 استيراد الموظفين</a></li>
        <li><a href="{base_url}/reset-admin-final" target="_blank">👑 إعادة تعيين admin</a></li>
        <li><a href="{base_url}/simple-login" target="_blank">🚪 دخول مباشر</a></li>
        <li><a href="{base_url}/login" target="_blank">🔐 صفحة تسجيل الدخول</a></li>
    </ul>
    """)

    output.append("</body></html>")
    return "".join(output)


@app.errorhandler(Exception)
def handle_all_exceptions(e):
    """معالج شامل لجميع الأخطاء"""
    import traceback
    error_trace = traceback.format_exc()

    return f"""
    <html dir="rtl">
        <head>
            <title>❌ خطأ في التطبيق</title>
            <style>
                body {{ font-family: Arial; padding: 40px; background: #f5f7fa; }}
                .error-box {{ background: white; border-radius: 10px; padding: 30px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }}
                h1 {{ color: #e74c3c; }}
                pre {{ background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
                .btn {{ display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
            </style>
        </head>
        <body>
            <div class="error-box">
                <h1>❌ حدث خطأ في الخادم</h1>
                <p><strong>نوع الخطأ:</strong> {type(e).__name__}</p>
                <p><strong>الرسالة:</strong> {str(e)}</p>
                <h3>تفاصيل الخطأ:</h3>
                <pre>{error_trace}</pre>
                <hr>
                <a href="/diagnose-all" class="btn">🔍 تشخيص شامل</a>
                <a href="/" class="btn">🏠 الرئيسية</a>
                <a href="/login" class="btn">🔐 تسجيل الدخول</a>
            </div>
        </body>
    </html>
    """, 500

@app.route('/')
def index():
    # التحقق من تسجيل دخول المستخدم
    if current_user.is_authenticated:
        # إذا كان مسجل الدخول، اذهب إلى لوحة التحكم
        return redirect(url_for('dashboard'))
    else:
        # إذا لم يكن مسجل الدخول، اذهب إلى صفحة تسجيل الدخول
        return redirect(url_for('login'))


@app.route('/about')
@login_required
def about():
    """صفحة عن النظام والمصمم"""
    # إحصائيات سريعة للعرض
    from models import Employee, Team, Ship, Berth

    stats = {
        'total_employees': Employee.query.count(),
        'total_teams': Team.query.count(),
        'total_ships': Ship.query.count(),
        'total_berths': Berth.query.count()
    }

    return render_template('about.html', stats=stats)

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
    from sqlalchemy import extract

    # 1. توزيع الموظفين حسب سنة الميلاد (الأعمار) - متوافق مع PostgreSQL
    birth_year_stats = db.session.query(
        extract('year', Employee.birth_date).label('year'),
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
    """عرض قائمة الموظفين"""
    employees = Employee.query.all()
    teams = Team.query.all()

    # تجهيز بيانات الموظفين للإرسال إلى JavaScript
    employees_data = {}
    fingerprint_count = 0

    for emp in employees:
        # حساب البصمات النشطة
        active_enrollments = [e for e in emp.fingerprint_enrollments if e.is_active]
        has_fingerprint = len(active_enrollments) > 0
        fingerprints_count = len(active_enrollments)

        if has_fingerprint:
            fingerprint_count += 1

        employees_data[emp.id] = {
            'id': emp.id,
            'code': emp.employee_code if hasattr(emp, 'employee_code') else '100001',
            'name': emp.name,
            'national_id': emp.national_id,
            'profession': emp.profession,
            'team': emp.team.name if emp.team else "غير موزع",
            'birth_place': emp.birth_place or "غير محدد",
            'current_address': emp.current_address or "غير محدد",
            'birth_date': emp.birth_date.strftime('%Y-%m-%d') if emp.birth_date else '',
            'phone': emp.phone or "غير محدد",
            'has_fingerprint': has_fingerprint,
            'fingerprints_count': fingerprints_count
        }

    # حساب عدد قادة الفرق
    leaders_count = len([e for e in employees if e.profession == 'رئيس فرقة'])

    # حساب عدد الأكواد المخصصة
    custom_codes_count = 0
    for e in employees:
        if hasattr(e, 'employee_code') and e.employee_code:
            try:
                if e.employee_code.isdigit() and int(e.employee_code) < 100000:
                    custom_codes_count += 1
            except (ValueError, TypeError):
                pass

    # تجميع أماكن الميلاد الفريدة
    birth_places = []
    for emp in employees:
        if emp.birth_place and emp.birth_place not in birth_places:
            birth_places.append(emp.birth_place)
    birth_places.sort()

    stats = {
        'fingerprint_count': fingerprint_count,
        'leaders_count': leaders_count,
        'custom_codes_count': custom_codes_count,
        'total_employees': len(employees),
        'birth_places': birth_places
    }

    return render_template('employees/list.html',
                           employees=employees,
                           teams=teams,
                           stats=stats,
                           employees_data=employees_data)

# app.py - تحديث add_employee للسماح بإدخال كود مخصص

@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_employee():
    form = EmployeeForm()
    teams = Team.query.filter_by(is_active=True).all()
    form.team_id.choices = [(0, 'اختر الفرقة')] + [(t.id, t.name) for t in teams]

    if form.validate_on_submit():
        # التحقق من الكود المدخل
        employee_code = form.employee_code.data if form.employee_code.data else generate_employee_code()

        # التحقق من عدم تكرار الكود
        existing = Employee.query.filter_by(employee_code=employee_code).first()
        if existing:
            flash(f'⚠️ الكود {employee_code} مستخدم من قبل موظف آخر', 'danger')
            return render_template('employees/add.html', form=form, teams=teams)

        employee = Employee(
            employee_code=employee_code,
            name=form.name.data,
            national_id=form.national_id.data,
            birth_place=form.birth_place.data,
            current_address=form.current_address.data,
            birth_date=form.birth_date.data,
            profession=form.profession.data,
            team_id=form.team_id.data if form.team_id.data != 0 else None,
            phone=form.phone.data,
            hire_date=datetime.now().date(),
            is_active=True
        )
        db.session.add(employee)
        db.session.commit()

        flash(f'✅ تم إضافة الموظف {employee.name} برقم كود: {employee.employee_code}', 'success')
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

    # خيارات الفرق
    teams = Team.query.filter_by(is_active=True).all()
    form.team_ids.choices = [(t.id, t.name) for t in teams]

    # تعيين الفرق المحددة مسبقاً
    current_team_ids = [ot.team_id for ot in operation.operation_teams]

    if request.method == 'GET':
        # تعيين البيانات الافتراضية للنموذج
        form.team_ids.data = current_team_ids
        print(f"📋 الفرق الحالية للعملية {id}: {current_team_ids}")  # للتشخيص

    if request.method == 'POST':
        # معالجة التواريخ
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')

        try:
            if start_time_str:
                form.start_time.data = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError):
            flash('❌ تنسيق تاريخ البدء غير صحيح', 'danger')
            return render_template('operations/edit.html',
                                   form=form,
                                   operation=operation,
                                   teams=teams,
                                   selected_teams=current_team_ids)

        try:
            if end_time_str and end_time_str.strip():
                form.end_time.data = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            else:
                form.end_time.data = None
        except (ValueError, TypeError):
            flash('❌ تنسيق تاريخ الانتهاء غير صحيح', 'danger')
            return render_template('operations/edit.html',
                                   form=form,
                                   operation=operation,
                                   teams=teams,
                                   selected_teams=current_team_ids)

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
            print(f"📋 الفرق المختارة في التعديل: {team_ids}")  # للتشخيص

            for team_id in team_ids:
                if team_id and team_id.isdigit():
                    operation_team = OperationTeam(
                        operation_id=operation.id,
                        team_id=int(team_id)
                    )
                    db.session.add(operation_team)

            db.session.commit()

            # تحديث صلاحيات البصمة إذا لزم الأمر
            # حذف الصلاحيات القديمة للفرق التي لم تعد موجودة
            new_team_ids = [int(tid) for tid in team_ids if tid.isdigit()]
            old_team_ids = current_team_ids

            # حذف الصلاحيات للفرق التي تم إزالتها
            for team_id in old_team_ids:
                if team_id not in new_team_ids:
                    ShipOperationTeamPermission.query.filter_by(
                        operation_id=operation.id,
                        team_id=team_id
                    ).delete()

            # إضافة صلاحيات للفرق الجديدة (اختياري - يمكن تعطيلها)
            for team_id in new_team_ids:
                if team_id not in old_team_ids:
                    # لا نضيف صلاحية تلقائياً، بل تترك لإدارة البصمة
                    pass

            db.session.commit()

            flash(f'✅ تم تحديث العملية بنجاح مع {len(team_ids)} فرق', 'success')
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

    # إعادة عرض النموذج مع البيانات
    return render_template('operations/edit.html',
                           form=form,
                           operation=operation,
                           teams=teams,
                           selected_teams=current_team_ids)  # تمرير الفرق المحددة

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
    from datetime import datetime, timedelta

    # استلام التواريخ من الـ request
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # تعيين التواريخ الافتراضية (آخر 30 يوم)
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = datetime.now().strftime('%Y-%m-%d')

    # تحويل التواريخ إلى كائنات datetime
    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)

    # الحصول على جميع الفرق
    teams = Team.query.all()

    # الحصول على جميع العمليات في التاريخ المحدد
    all_operations = ShipOperation.query.filter(
        ShipOperation.start_time.between(date_from_obj, date_to_obj)
    ).order_by(ShipOperation.start_time.desc()).all()

    unique_operations_count = len(all_operations)

    # حساب إجمالي ساعات العمل الفريدة (مجموع مدد العمليات المختلفة)
    total_unique_hours = 0
    for op in all_operations:
        if op.duration:
            total_unique_hours += op.duration

    report_data = []
    teams_summary = {}  # إضافة ملخص الفرق للرسوم البيانية

    for team in teams:
        # الحصول على العمليات التي شاركت فيها هذه الفرقة في التاريخ المحدد
        team_operations = []
        for op in all_operations:
            for ot in op.operation_teams:
                if ot.team_id == team.id:
                    team_operations.append(op)
                    break

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

        # إضافة إلى ملخص الفرق
        if total_ops > 0:
            teams_summary[team.id] = {
                'name': team.name,
                'type': team.team_type,
                'count': total_ops,
                'hours': round(team_hours, 2),
                'avg_duration': round(team_hours / total_ops, 2) if total_ops > 0 else 0
            }

        report_data.append({
            'team': team,
            'total_operations': total_ops,
            'completed_operations': completed_count,
            'total_hours': round(team_hours, 2),
            'avg_duration': round(team_hours / total_ops, 2) if total_ops > 0 else 0,
            'operations': sorted(team_operations, key=lambda x: x.start_time, reverse=True)[:10]  # آخر 10 عمليات
        })

    # ترتيب البيانات حسب عدد العمليات
    report_data.sort(key=lambda x: x['total_operations'], reverse=True)

    return render_template('reports/teams_operations.html',
                           report_data=report_data,
                           unique_operations=unique_operations_count,
                           unique_hours=round(total_unique_hours, 2),
                           teams_summary=teams_summary,
                           date_from=date_from_obj,
                           date_to=date_to_obj)

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


@app.route('/reports/performance')
@login_required
def performance_report():
    """تقرير الأداء والكفاءة"""
    from sqlalchemy import func
    from datetime import datetime, timedelta
    from collections import defaultdict

    # استلام التواريخ
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # تعيين التواريخ الافتراضية
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = datetime.now().strftime('%Y-%m-%d')

    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)

    # جلب العمليات في الفترة
    operations = ShipOperation.query.filter(
        ShipOperation.start_time.between(date_from_obj, date_to_obj)
    ).all()

    total_days = (date_to_obj - date_from_obj).days

    # إحصائيات عامة
    total_operations = len(operations)
    completed_operations = len([op for op in operations if op.end_time])
    total_hours = sum([op.duration for op in operations if op.duration])
    avg_duration = total_hours / total_operations if total_operations > 0 else 0

    summary = {
        'total_operations': total_operations,
        'completed_operations': completed_operations,
        'total_hours': total_hours,
        'avg_duration': avg_duration,
        'completion_rate': (completed_operations / total_operations * 100) if total_operations > 0 else 0
    }

    # تحليل أداء الفرق
    team_stats = defaultdict(lambda: {'count': 0, 'hours': 0, 'operations': []})

    for op in operations:
        for ot in op.operation_teams:
            if ot.team:
                team_stats[ot.team.id]['name'] = ot.team.name
                team_stats[ot.team.id]['count'] += 1
                if op.duration:
                    team_stats[ot.team.id]['hours'] += op.duration
                team_stats[ot.team.id]['operations'].append(op)

    team_performance = []
    for team_id, stats in team_stats.items():
        team_performance.append({
            'id': team_id,
            'name': stats['name'],
            'operations_count': stats['count'],
            'total_hours': stats['hours'],
            'avg_duration': stats['hours'] / stats['count'] if stats['count'] > 0 else 0,
            'participation_rate': (stats['count'] / total_operations * 100) if total_operations > 0 else 0
        })

    # ترتيب الفرق حسب عدد العمليات
    team_performance.sort(key=lambda x: x['operations_count'], reverse=True)

    # تحليل أداء السفن
    ship_stats = defaultdict(lambda: {'count': 0, 'hours': 0, 'cargo': 0})

    for op in operations:
        if op.ship:
            ship_stats[op.ship.id]['name'] = op.ship.name
            ship_stats[op.ship.id]['count'] += 1
            if op.duration:
                ship_stats[op.ship.id]['hours'] += op.duration
            if op.cargo_quantity:
                ship_stats[op.ship.id]['cargo'] += op.cargo_quantity

    ship_performance = []
    for ship_id, stats in ship_stats.items():
        ship_performance.append({
            'id': ship_id,
            'name': stats['name'],
            'operations_count': stats['count'],
            'total_hours': stats['hours'],
            'avg_duration': stats['hours'] / stats['count'] if stats['count'] > 0 else 0,
            'total_cargo': stats['cargo']
        })

    ship_performance.sort(key=lambda x: x['operations_count'], reverse=True)

    # تحليل الأداء اليومي
    daily_stats = defaultdict(lambda: {'count': 0, 'hours': 0, 'ships': []})

    for op in operations:
        day = op.start_time.date()
        daily_stats[day]['count'] += 1
        if op.duration:
            daily_stats[day]['hours'] += op.duration
        if op.ship and op.ship.name not in daily_stats[day]['ships']:
            daily_stats[day]['ships'].append(op.ship.name)

    daily_performance = []
    for day, stats in sorted(daily_stats.items()):
        daily_performance.append({
            'date': day,
            'operations_count': stats['count'],
            'total_hours': stats['hours'],
            'avg_duration': stats['hours'] / stats['count'] if stats['count'] > 0 else 0,
            'most_active_ship': stats['ships'][0] if stats['ships'] else None
        })

    return render_template('reports/performance_report.html',
                           date_from=date_from_obj,
                           date_to=date_to_obj,
                           total_days=total_days,
                           summary=summary,
                           team_performance=team_performance,
                           ship_performance=ship_performance,
                           daily_performance=daily_performance)

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

    from sqlalchemy import extract

    for i, day in enumerate(days):
        # في PostgreSQL: extract(dow from date)
        # الأحد = 0، السبت = 6
        # نحتاج لتعديل الأرقام لتتناسب مع ترتيب الأيام العربية

        # حساب عدد عمليات التحميل والتفريغ لكل يوم
        day_loading = ShipOperation.query.filter(
            ShipOperation.operation_type == 'تحميل',
            extract('dow', ShipOperation.start_time) == i  # i يتراوح من 0 إلى 6
        ).count()

        day_unloading = ShipOperation.query.filter(
            ShipOperation.operation_type == 'تفريغ',
            extract('dow', ShipOperation.start_time) == i
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


# ============================================
# Reports Routes - صفحات التقارير المنفصلة
# ============================================
@app.route('/reports/ships', methods=['GET'])
@login_required
def ships_report_page():
    """صفحة تقرير السفن"""
    # استلام التواريخ
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # تعيين التواريخ الافتراضية
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = datetime.now().strftime('%Y-%m-%d')

    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)

    # جلب البيانات
    data = Ship.query.filter(
        Ship.arrival_date.between(date_from_obj, date_to_obj)
    ).all()

    # ✅ تعريف stats هنا
    stats = {
        'total_ships': len(data),
        'arrived_ships': len([s for s in data if s.status == 'arrived']),
        'berthed_ships': len([s for s in data if s.status == 'berthed']),
        'departed_ships': len([s for s in data if s.status == 'departed']),
        'total_cargo': sum(s.cargo_capacity or 0 for s in data)
    }

    return render_template('reports/ships_report.html',
                           data=data,
                           stats=stats,
                           date_from=date_from_obj,
                           date_to=date_to_obj)

@app.route('/reports/employees', methods=['GET'])
@login_required
def employees_report_page():
    """صفحة تقرير الموظفين"""
    # استلام التواريخ
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # تعيين التواريخ الافتراضية
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = datetime.now().strftime('%Y-%m-%d')

    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)

    # جلب البيانات
    data = Employee.query.filter(
        Employee.hire_date.between(date_from_obj, date_to_obj)
    ).all()

    return render_template('reports/employees_report.html',
                           data=data,
                           date_from=date_from_obj,
                           date_to=date_to_obj)


@app.route('/reports/teams', methods=['GET'])
@login_required
def teams_report_page():
    """صفحة تقرير فرق العمل"""
    # استلام التواريخ
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # تعيين التواريخ الافتراضية
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = datetime.now().strftime('%Y-%m-%d')

    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)

    # تجميع بيانات الفرق
    teams = Team.query.all()
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

    return render_template('reports/teams_report.html',
                           teams_data=teams_data,
                           date_from=date_from_obj,
                           date_to=date_to_obj)


@app.route('/reports/operations', methods=['GET'])
@login_required
def operations_report_page():
    """صفحة تقرير العمليات"""
    # استلام التواريخ
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # تعيين التواريخ الافتراضية
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = datetime.now().strftime('%Y-%m-%d')

    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)

    # جلب البيانات
    data = ShipOperation.query.filter(
        ShipOperation.start_time.between(date_from_obj, date_to_obj)
    ).order_by(ShipOperation.start_time.desc()).all()

    return render_template('reports/operations_report.html',
                           data=data,
                           date_from=date_from_obj,
                           date_to=date_to_obj)


@app.route('/reports/berths', methods=['GET'])
@login_required
def berths_report_page():
    """صفحة تقرير الأرصفة"""
    from datetime import datetime, timedelta

    # استلام التواريخ
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # تعيين التواريخ الافتراضية (آخر 30 يوم)
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = datetime.now().strftime('%Y-%m-%d')

    # تحويل التواريخ
    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)

    # جلب جميع الأرصفة
    berths = Berth.query.all()

    # إحصائيات
    total_berths = len(berths)
    available_berths = sum(1 for b in berths if b.is_available)
    occupied_berths = sum(1 for b in berths if b.is_occupied)

    # حساب عدد السفن في الفترة المحددة فقط
    ships_in_period = Ship.query.filter(
        Ship.arrival_date.between(date_from_obj, date_to_obj)
    ).count()

    print("=" * 50)
    print(f"📊 تقرير الأرصفة - الفترة: {date_from} إلى {date_to}")
    print(f"إجمالي الأرصفة: {total_berths}")
    print(f"السفن في الفترة: {ships_in_period}")
    print(f"إجمالي السفن في قاعدة البيانات: {Ship.query.count()}")
    print("=" * 50)

    # تجهيز بيانات الأرصفة
    berths_data = []
    for berth in berths:
        # جلب السفن التي وصلت في الفترة المحددة فقط
        ships = Ship.query.filter_by(berth_number=berth.number).filter(
            Ship.arrival_date.between(date_from_obj, date_to_obj)
        ).all()

        current_ship = berth.current_ship.name if berth.current_ship else '—'

        berths_data.append({
            'berth': berth,
            'ships': ships,
            'ships_count': len(ships),
            'current_ship': current_ship,
            'is_available': berth.is_available,
            'is_occupied': berth.is_occupied
        })

    stats = {
        'total': total_berths,
        'available': available_berths,
        'occupied': occupied_berths,
        'total_ships': ships_in_period  # استخدام عدد السفن في الفترة
    }

    return render_template('reports/berths_report.html',
                           berths_data=berths_data,
                           stats=stats,
                           date_from=date_from_obj,
                           date_to=date_to_obj)

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
    # تأكد من أن التواريخ تشمل كامل اليوم
    date_from_start = datetime.combine(date_from, datetime.min.time())
    date_to_end = datetime.combine(date_to, datetime.max.time())

    # جلب جميع العمليات في التاريخ المحدد
    data = ShipOperation.query.filter(
        ShipOperation.start_time.between(date_from_start, date_to_end)
    ).order_by(ShipOperation.start_time.desc()).all()

    print(f"📊 عدد العمليات في التقرير: {len(data)}")  # للتشخيص

    if format == 'excel':
        return generate_excel_report(data, 'operations', date_from, date_to)
    elif format == 'pdf':
        return generate_pdf_report(data, 'operations', date_from, date_to)
    else:
        return render_template('reports/operations_report.html',
                               data=data,
                               date_from=date_from,
                               date_to=date_to)


@app.route('/reports/operations-duration')
@login_required
def operations_duration_report():
    """تقرير مدة العمليات"""
    from sqlalchemy import func
    from datetime import datetime, timedelta

    # استلام التواريخ من الـ request
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')

    # تعيين التواريخ الافتراضية (آخر 30 يوم)
    if not date_from_str:
        date_from_str = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to_str:
        date_to_str = datetime.now().strftime('%Y-%m-%d')

    # تحويل التواريخ إلى كائنات datetime للاستعلام
    date_from_obj = datetime.strptime(date_from_str, '%Y-%m-%d')
    date_to_obj = datetime.strptime(date_to_str, '%Y-%m-%d') + timedelta(days=1)

    # الاحتفاظ بالتواريخ للعرض في القالب
    date_from_display = date_from_obj
    date_to_display = date_to_obj - timedelta(days=1)

    # جلب العمليات في التاريخ المحدد
    operations = ShipOperation.query.filter(
        ShipOperation.start_time.between(date_from_obj, date_to_obj)
    ).order_by(ShipOperation.start_time.desc()).all()

    # إحصائيات
    total_operations = len(operations)
    completed_operations = len([op for op in operations if op.end_time])
    ongoing_operations = total_operations - completed_operations

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
                           stats=stats,
                           date_from=date_from_display,
                           date_to=date_to_display)
    # لا ترسل now هنا
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

    # تجهيز بيانات السفن لكل رصيف
    for berth in berths:
        berth.ships_list = Ship.query.filter_by(berth_number=berth.number).order_by(Ship.arrival_date.desc()).all()

    stats = {
        'total': len(berths),
        'active': sum(1 for b in berths if b.is_available),
        'occupied': sum(1 for b in berths if b.is_occupied),
        'total_ships': sum(b.ships_count for b in berths)
    }

    html_string = render_template('reports/berths_pdf.html',
                                  berths=berths,
                                  stats=stats,
                                  current_date=datetime.now(),
                                  current_user=current_user)

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

    try:
        # حساب الإحصائيات الأساسية
        total_cargo = 0
        total_hours = 0
        durations = []
        ships_set = set()
        teams_set = set()

        # تجهيز البيانات وحساب الإحصائيات
        for item in data:
            if report_type == 'operations':
                if hasattr(item, 'cargo_quantity') and item.cargo_quantity:
                    try:
                        total_cargo += float(item.cargo_quantity)
                    except:
                        pass
                if hasattr(item, 'duration') and item.duration:
                    try:
                        total_hours += float(item.duration)
                        durations.append(float(item.duration))
                    except:
                        pass
                if hasattr(item, 'ship') and item.ship:
                    ships_set.add(item.ship.id)
                if hasattr(item, 'operation_teams'):
                    for ot in item.operation_teams:
                        if hasattr(ot, 'team') and ot.team:
                            teams_set.add(ot.team.id)

            elif report_type == 'employees':
                if hasattr(item, 'team') and item.team:
                    teams_set.add(item.team.id)

            elif report_type == 'ships':
                if hasattr(item, 'berth_number') and item.berth_number:
                    ships_set.add(item.id)

        # حساب الإحصائيات
        completed_items = len([item for item in data if hasattr(item, 'end_time') and item.end_time])
        ongoing_items = len([item for item in data if hasattr(item, 'end_time') and not item.end_time])

        stats = {
            'total': len(data),
            'completed': completed_items,
            'ongoing': ongoing_items,
            'avg_duration': round(total_hours / len(durations), 2) if durations else 0
        }

        # تجهيز البيانات حسب النوع
        if report_type == 'ships':
            html_string = render_template('reports/ships_pdf.html',
                                          data=data,
                                          stats=stats,
                                          date_from=date_from,
                                          date_to=date_to,
                                          current_date=datetime.now(),
                                          ships_count=len(ships_set))
        elif report_type == 'employees':
            html_string = render_template('reports/employees_pdf.html',
                                          data=data,
                                          stats=stats,
                                          date_from=date_from,
                                          date_to=date_to,
                                          current_date=datetime.now(),
                                          teams_count=len(teams_set))
        elif report_type == 'operations':
            html_string = render_template('reports/operations_pdf.html',
                                          data=data,
                                          stats=stats,
                                          date_from=date_from,
                                          date_to=date_to,
                                          current_date=datetime.now(),
                                          total_cargo=round(total_cargo, 2),
                                          total_hours=round(total_hours, 2),
                                          max_duration=round(max(durations), 2) if durations else 0,
                                          min_duration=round(min(durations), 2) if durations else 0,
                                          completion_rate=round((completed_items / len(data) * 100), 2) if len(
                                              data) > 0 else 0,
                                          ships_count=len(ships_set),
                                          teams_count=len(teams_set))
        elif report_type == 'teams':
            html_string = render_template('reports/teams_pdf.html',
                                          data=data,
                                          stats=stats,
                                          date_from=date_from,
                                          date_to=date_to,
                                          current_date=datetime.now())
        elif report_type == 'berths':
            html_string = render_template('reports/berths_pdf.html',
                                          data=data,
                                          stats=stats,
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

    except Exception as e:
        print(f"❌ خطأ في إنشاء PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'❌ حدث خطأ في إنشاء ملف PDF: {str(e)}', 'danger')
        return redirect(url_for('reports_index'))

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


# 🌟 نقطة نهاية لتهيئة قاعدة البيانات (استخدمها مرة واحدة فقط)
@app.route('/init-db', methods=['GET'])
def initialize_database():
    """تهيئة قاعدة البيانات مع التحقق من المفتاح السري"""
    # مفتاح سري بسيط للتحقق (غيّره بكلمة من اختيارك)
    SECRET_INIT_KEY = "123456"  # غير هذا الرقم

    # التحقق من المفتاح
    key = request.args.get('key', '')
    if key != SECRET_INIT_KEY:
        return "❌ خطأ: مفتاح التهيئة غير صحيح", 401

    try:
        # استيراد دالة التهيئة
        import sys
        import os
        from pathlib import Path

        # إضافة المسار الحالي إلى PATH
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))

        # استيراد وتشغيل init_db
        import init_db

        # إعادة تحميل الوحدة إذا كانت مستوردة مسبقاً
        if 'init_db' in sys.modules:
            import importlib
            init_db = importlib.reload(init_db)

        # تشغيل التهيئة
        with app.app_context():
            result = init_db.init_db()

        return """
        <html>
            <head>
                <title>✅ تهيئة قاعدة البيانات</title>
                <style>
                    body { font-family: Arial; padding: 40px; background: #f0f8ff; text-align: center; }
                    .success { color: green; font-size: 24px; margin: 20px; }
                    .info { background: white; padding: 20px; border-radius: 10px; margin: 20px auto; max-width: 600px; }
                    .details { text-align: right; direction: rtl; }
                </style>
            </head>
            <body>
                <div class="success">✅ تم تهيئة قاعدة البيانات بنجاح!</div>
                <div class="info">
                    <div class="details">
                        <h3>📊 ملخص التهيئة:</h3>
                        <p>👤 مستخدم admin: admin/admin123</p>
                        <p>🏢 فرق العمل: 5</p>
                        <p>👥 الموظفين: 20</p>
                        <p>🚢 السفن: 5</p>
                        <p>⚓ الأرصفة: 5</p>
                    </div>
                </div>
                <div class="info">
                    <p>🔐 <strong>تذكر إزالة نقطة النهاية هذه بعد الاستخدام!</strong></p>
                    <p><a href="/login">🔑 الذهاب إلى صفحة تسجيل الدخول</a></p>
                </div>
            </body>
        </html>
        """, 200

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"""
        <html>
            <head><title>❌ خطأ</title></head>
            <body>
                <h1 style="color:red;">❌ فشل تهيئة قاعدة البيانات</h1>
                <pre style="background:#f0f0f0; padding:20px; text-align:left;">{str(e)}</pre>
                <pre style="background:#f0f0f0; padding:20px; text-align:left;">{error_details}</pre>
            </body>
        </html>
        """, 500

@app.errorhandler(405)
def method_not_allowed(e):
    """معالج خطأ 405 - Method Not Allowed"""
    return f"""
    <html dir="rtl">
        <head>
            <title>405 - طريقة غير مسموحة</title>
            <style>
                body {{
                    font-family: 'Cairo', Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    height: 100vh;
                    margin: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    text-align: center;
                }}
                .error-container {{
                    background: white;
                    border-radius: 20px;
                    padding: 50px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 500px;
                    width: 90%;
                }}
                h1 {{
                    font-size: 80px;
                    margin: 0;
                    color: #667eea;
                    line-height: 1;
                }}
                h2 {{
                    color: #333;
                    margin: 15px 0;
                }}
                p {{
                    color: #666;
                    margin-bottom: 25px;
                    line-height: 1.6;
                }}
                .btn {{
                    display: inline-block;
                    padding: 12px 30px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-decoration: none;
                    border-radius: 50px;
                    font-weight: bold;
                    transition: transform 0.3s;
                    margin: 5px;
                }}
                .btn:hover {{
                    transform: translateY(-3px);
                }}
                .btn-secondary {{
                    background: #6c757d;
                }}
                i {{
                    margin-left: 8px;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <h1>405</h1>
                <h2><i class="fas fa-ban" style="color: #dc3545;"></i> طريقة غير مسموحة</h2>
                <p>عذراً، الطريقة التي استخدمتها غير مسموحة لهذه الصفحة.</p>
                <p><small>ربما حاولت الدخول إلى صفحة بطريقة خاطئة.</small></p>
                <div>
                    <a href="javascript:history.back()" class="btn btn-secondary">
                        <i class="fas fa-arrow-right"></i> العودة
                    </a>
                    <a href="/login" class="btn">
                        <i class="fas fa-sign-in-alt"></i> تسجيل الدخول
                    </a>
                </div>
            </div>
        </body>
    </html>
    """, 405

# 📥 نقطة نهاية لاستيراد بيانات الموظفين من Excel
@app.route('/import-employees', methods=['GET', 'POST'])
def import_employees():
    """استيراد بيانات الموظفين من ملف Excel"""
    # مفتاح سري للتحقق
    SECRET_KEY = "123456"  # استخدم نفس المفتاح

    # التحقق من المفتاح
    key = request.args.get('key', '')
    if key != SECRET_KEY:
        return "❌ خطأ: مفتاح التهيئة غير صحيح", 401

    if request.method == 'POST':
        try:
            # التحقق من رفع ملف
            if 'file' not in request.files:
                return "❌ لم يتم رفع ملف", 400

            file = request.files['file']
            if file.filename == '':
                return "❌ لم يتم اختيار ملف", 400

            if not file.filename.endswith(('.xlsx', '.xls')):
                return "❌ الملف يجب أن يكون Excel (.xlsx أو .xls)", 400

            # حفظ الملف مؤقتاً
            import tempfile
            import os

            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, 'port_employees.xlsx')
            file.save(temp_path)

            # استيراد البيانات
            from import_data import import_from_excel

            with app.app_context():
                result = import_from_excel(temp_path)

            # حذف الملف المؤقت
            os.remove(temp_path)

            return f"""
            <html dir="rtl">
                <head>
                    <title>✅ نتيجة الاستيراد</title>
                    <style>
                        body {{ font-family: 'Arial', sans-serif; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; margin: 0; display: flex; justify-content: center; align-items: center; }}
                        .container {{ background: white; padding: 40px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 600px; width: 90%; }}
                        .success {{ color: #28a745; font-size: 24px; margin: 20px 0; text-align: center; }}
                        .stats {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; direction: rtl; }}
                        .stat-item {{ display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #eee; }}
                        .stat-item:last-child {{ border-bottom: none; }}
                        .btn {{ display: inline-block; background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="success">✅ تم استيراد البيانات بنجاح!</div>
                        <div class="stats">
                            <h3>📊 النتائج:</h3>
                            <div class="stat-item"><span>➕ موظفين جدد:</span> <strong>{result['imported']}</strong></div>
                            <div class="stat-item"><span>🔄 موظفين محدثين:</span> <strong>{result['updated']}</strong></div>
                            <div class="stat-item"><span>⚠️ موظفين متخطين:</span> <strong>{result['skipped']}</strong></div>
                            <div class="stat-item"><span>👥 إجمالي الموظفين:</span> <strong>{result['total']}</strong></div>
                        </div>
                        <div style="text-align: center;">
                            <a href="/employees" class="btn">👥 عرض الموظفين</a>
                            <a href="/login" class="btn" style="background: #28a745;">🔑 تسجيل الدخول</a>
                        </div>
                    </div>
                </body>
            </html>
            """, 200

        except Exception as e:
            import traceback
            return f"""
            <html>
                <body>
                    <h1 style="color:red;">❌ خطأ</h1>
                    <pre>{str(e)}</pre>
                    <pre>{traceback.format_exc()}</pre>
                </body>
            </html>
            """, 500

    # عرض نموذج رفع الملف
    return """
    <html dir="rtl">
        <head>
            <title>📥 استيراد الموظفين</title>
            <style>
                body { font-family: 'Arial', sans-serif; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; margin: 0; display: flex; justify-content: center; align-items: center; }
                .container { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 500px; width: 90%; }
                h1 { color: #333; text-align: center; margin-bottom: 30px; }
                .form-group { margin-bottom: 20px; }
                label { display: block; margin-bottom: 10px; font-weight: bold; }
                input[type=file] { width: 100%; padding: 10px; border: 2px dashed #667eea; border-radius: 5px; }
                button { background: #667eea; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; width: 100%; }
                button:hover { background: #764ba2; }
                .note { background: #fff3cd; color: #856404; padding: 15px; border-radius: 5px; margin-top: 20px; font-size: 14px; }
                .note h3 { margin-top: 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📥 استيراد بيانات الموظفين</h1>
                <form method="post" enctype="multipart/form-data">
                    <div class="form-group">
                        <label>اختر ملف Excel:</label>
                        <input type="file" name="file" accept=".xlsx,.xls" required>
                    </div>
                    <button type="submit">رفع واستيراد</button>
                </form>
                <div class="note">
                    <h3>📌 ملاحظات:</h3>
                    <ul>
                        <li>الملف يجب أن يكون بصيغة Excel (.xlsx أو .xls)</li>
                        <li>يجب أن يحتوي على شيت باسم "الكشف الكلي (9)"</li>
                        <li>البيانات تبدأ من الصف الثالث</li>
                        <li>الأعمدة: الرقم الوطني، الاسم، سنة الميلاد، مكان الميلاد، العنوان الحالي، المهنة، رقم الفرقة</li>
                    </ul>
                </div>
            </div>
        </body>
    </html>
    """

# ✅ نهاية الكود المضاف
# 📥 نقطة نهاية لاستيراد بيانات السفن من Excel
@app.route('/import-ships', methods=['GET', 'POST'])
def import_ships_route():
    """استيراد بيانات السفن من ملف Excel"""
    # مفتاح سري للتحقق
    SECRET_KEY = "123456"  # استخدم نفس المفتاح

    # التحقق من المفتاح
    key = request.args.get('key', '')
    if key != SECRET_KEY:
        return "❌ خطأ: مفتاح التهيئة غير صحيح", 401

    if request.method == 'POST':
        try:
            # التحقق من رفع ملف
            if 'file' not in request.files:
                return "❌ لم يتم رفع ملف", 400

            file = request.files['file']
            if file.filename == '':
                return "❌ لم يتم اختيار ملف", 400

            if not file.filename.endswith(('.xlsx', '.xls')):
                return "❌ الملف يجب أن يكون Excel (.xlsx أو .xls)", 400

            # حفظ الملف مؤقتاً
            import tempfile
            import os

            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, 'ships_data.xlsx')
            file.save(temp_path)

            # استيراد البيانات
            from import_ships import import_ships_from_excel

            with app.app_context():
                result = import_ships_from_excel(temp_path)

            # حذف الملف المؤقت
            os.remove(temp_path)

            if 'error' in result:
                return f"""
                <html>
                    <body>
                        <h1 style="color:red;">❌ خطأ في الاستيراد</h1>
                        <pre>{result['error']}</pre>
                    </body>
                </html>
                """, 500

            return f"""
            <html dir="rtl">
                <head>
                    <title>✅ نتيجة استيراد السفن</title>
                    <style>
                        body {{ font-family: 'Arial', sans-serif; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; margin: 0; display: flex; justify-content: center; align-items: center; }}
                        .container {{ background: white; padding: 40px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 600px; width: 90%; }}
                        .success {{ color: #28a745; font-size: 24px; margin: 20px 0; text-align: center; }}
                        .stats {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; direction: rtl; }}
                        .stat-item {{ display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #eee; }}
                        .stat-item:last-child {{ border-bottom: none; }}
                        .btn {{ display: inline-block; background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="success">✅ تم استيراد بيانات السفن بنجاح!</div>
                        <div class="stats">
                            <h3>📊 النتائج:</h3>
                            <div class="stat-item"><span>➕ سفن جديدة:</span> <strong>{result['imported']}</strong></div>
                            <div class="stat-item"><span>🔄 سفن محدثة:</span> <strong>{result['updated']}</strong></div>
                            <div class="stat-item"><span>⚠️ سفن متخطية:</span> <strong>{result['skipped']}</strong></div>
                            <div class="stat-item"><span>🚢 إجمالي السفن:</span> <strong>{result['imported'] + result['updated']}</strong></div>
                        </div>
                        <div style="text-align: center;">
                            <a href="/ships" class="btn">🚢 عرض السفن</a>
                            <a href="/" class="btn" style="background: #28a745;">🏠 الرئيسية</a>
                        </div>
                    </div>
                </body>
            </html>
            """, 200

        except Exception as e:
            import traceback
            return f"""
            <html>
                <body>
                    <h1 style="color:red;">❌ خطأ</h1>
                    <pre>{str(e)}</pre>
                    <pre>{traceback.format_exc()}</pre>
                </body>
            </html>
            """, 500

    # عرض نموذج رفع الملف
    return """
    <html dir="rtl">
        <head>
            <title>📥 استيراد السفن</title>
            <style>
                body { font-family: 'Arial', sans-serif; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; margin: 0; display: flex; justify-content: center; align-items: center; }
                .container { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 500px; width: 90%; }
                h1 { color: #333; text-align: center; margin-bottom: 30px; }
                .form-group { margin-bottom: 20px; }
                label { display: block; margin-bottom: 10px; font-weight: bold; }
                input[type=file] { width: 100%; padding: 10px; border: 2px dashed #667eea; border-radius: 5px; }
                button { background: #667eea; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; width: 100%; }
                button:hover { background: #764ba2; }
                .note { background: #fff3cd; color: #856404; padding: 15px; border-radius: 5px; margin-top: 20px; font-size: 14px; }
                .note h3 { margin-top: 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📥 استيراد بيانات السفن</h1>
                <form method="post" enctype="multipart/form-data">
                    <div class="form-group">
                        <label>اختر ملف Excel:</label>
                        <input type="file" name="file" accept=".xlsx,.xls" required>
                    </div>
                    <button type="submit">رفع واستيراد</button>
                </form>
                <div class="note">
                    <h3>📌 ملاحظات:</h3>
                    <ul>
                        <li>الملف يجب أن يحتوي على عمود "الرقم" (IMO)</li>
                        <li>سيتم تحديث السفن الموجودة بناءً على رقم IMO</li>
                        <li>القيم الصفرية في الأبعاد سيتم تجاهلها</li>
                    </ul>
                </div>
            </div>
        </body>
    </html>
    """


@app.route('/fingerprint/diagnose')
@login_required
@admin_required
def fingerprint_diagnose():
    """تشخيص نظام البصمة"""
    from sqlalchemy import func

    # إحصائيات عامة
    stats = {
        'total_devices': FingerprintDevice.query.count(),
        'active_devices': FingerprintDevice.query.filter_by(is_active=True).count(),
        'total_enrollments': FingerprintEnrollment.query.count(),
        'active_enrollments': FingerprintEnrollment.query.filter_by(is_active=True).count(),
        'total_attendance': AttendanceLog.query.count(),
        'today_attendance': AttendanceLog.query.filter(
            func.date(AttendanceLog.timestamp) == datetime.now().date()
        ).count(),
        'success_attendance': AttendanceLog.query.filter_by(status='success').count(),
        'denied_attendance': AttendanceLog.query.filter_by(status='denied').count(),
    }

    # آخر 20 سجل حضور
    recent_logs = AttendanceLog.query.order_by(AttendanceLog.timestamp.desc()).limit(20).all()

    # الموظفين المسجلين بصمة
    enrolled_employees = []
    for emp in Employee.query.filter_by(is_active=True).all():
        enrollments = [e for e in emp.fingerprint_enrollments if e.is_active]
        if enrollments:
            enrolled_employees.append({
                'employee': emp,
                'enrollments': enrollments,
                'count': len(enrollments),
                'devices': [e.device.device_name for e in enrollments]
            })

    return render_template('fingerprint/diagnose.html',
                           stats=stats,
                           recent_logs=recent_logs,
                           enrolled_employees=enrolled_employees)


@app.route('/fingerprint/logs')
@login_required
@admin_required
def fingerprint_request_logs():
    """عرض سجلات الطلبات من جهاز البصمة"""
    import os

    log_file = 'fingerprint_requests.log'
    logs = []

    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            logs = content.split('=' * 50)
            logs = [l.strip() for l in logs if l.strip()]
            logs.reverse()  # أحدثها أولاً

    return render_template('fingerprint/logs.html', logs=logs[:50])


@app.route('/fingerprint/clear-test-logs')
@login_required
@admin_required
def clear_test_logs():
    """حذف سجلات الاختبار القديمة"""
    try:
        # حذف سجلات الاختبار (التي تحتوي على سبب "تسجيل يدوي للاختبار" أو "اختبار")
        test_logs = AttendanceLog.query.filter(
            AttendanceLog.reason.like('%اختبار%')
        ).all()

        count = len(test_logs)

        for log in test_logs:
            db.session.delete(log)

        db.session.commit()

        return f"""
        <html dir="rtl">
            <head>
                <style>
                    body {{ font-family: Arial; padding: 40px; background: #f5f7fa; direction: rtl; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; }}
                    .success {{ color: green; }}
                    .btn {{ display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2 class="success">✅ تم حذف {count} سجل اختبار</h2>
                    <p>تم حذف جميع سجلات الحضور التي تحتوي على كلمة "اختبار".</p>
                    <a href="/fingerprint/attendance" class="btn">📋 عرض سجلات الحضور</a>
                    <a href="/fingerprint/diagnose" class="btn">🔍 تشخيص البصمة</a>
                </div>
            </body>
        </html>
        """
    except Exception as e:
        return f"<h1 style='color:red'>خطأ: {str(e)}</h1>"


@app.route('/fingerprint/clear-all-logs')
@login_required
@admin_required
def clear_all_logs():
    """حذف جميع سجلات الحضور (تحذير: لا يمكن التراجع)"""
    try:
        count = AttendanceLog.query.count()

        if count > 0:
            # حذف جميع السجلات
            AttendanceLog.query.delete()
            db.session.commit()

            return f"""
            <html dir="rtl">
                <head>
                    <style>
                        body {{ font-family: Arial; padding: 40px; background: #f5f7fa; direction: rtl; }}
                        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; }}
                        .success {{ color: green; }}
                        .warning {{ color: orange; }}
                        .btn {{ display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2 class="success">✅ تم حذف {count} سجل حضور</h2>
                        <p class="warning">⚠️ تم حذف جميع سجلات الحضور نهائياً.</p>
                        <a href="/fingerprint/attendance" class="btn">📋 عرض سجلات الحضور</a>
                        <a href="/fingerprint/diagnose" class="btn">🔍 تشخيص البصمة</a>
                    </div>
                </body>
            </html>
            """
        else:
            return f"""
            <html dir="rtl">
                <body>
                    <h2>ℹ️ لا توجد سجلات حضور لحذفها</h2>
                    <a href="/fingerprint/diagnose">🔙 العودة</a>
                </body>
            </html>
            """
    except Exception as e:
        return f"<h1 style='color:red'>خطأ: {str(e)}</h1>"


@app.route('/test-fingerprint-api', methods=['GET', 'POST'])
def test_fingerprint_api():
    """صفحة لاختبار API البصمة يدوياً"""
    import requests

    if request.method == 'POST':
        try:
            # محاكاة بيانات من جهاز البصمة
            device_id = int(request.form.get('device_id', 1))
            employee_code = request.form.get('employee_code', '3456')
            fingerprint_data = request.form.get('fingerprint_data', 'test_template_123')

            test_data = {
                'device_id': device_id,
                'employee_code': employee_code,
                'fingerprint_data': fingerprint_data,
                'timestamp': datetime.now().isoformat()
            }

            # استدعاء API التحقق العام باستخدام requests
            with app.test_client() as client:
                response = client.post('/api/fingerprint/verify-public',
                                       json=test_data,
                                       headers={'Content-Type': 'application/json'})
                response_data = response.get_json()
                status_code = response.status_code

            return f"""
            <html dir="rtl">
                <head>
                    <style>
                        body {{ font-family: Arial; padding: 20px; direction: rtl; background: #f5f7fa; }}
                        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; }}
                        .success {{ color: green; }}
                        .error {{ color: red; }}
                        pre {{ background: #f0f0f0; padding: 10px; border-radius: 5px; overflow-x: auto; }}
                        .btn {{ display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>🔬 نتيجة اختبار API البصمة</h2>

                        <h4>📤 البيانات المرسلة:</h4>
                        <pre>{json.dumps(test_data, indent=2, ensure_ascii=False)}</pre>

                        <h4>📥 الرد من الخادم:</h4>
                        <pre>حالة HTTP: {status_code}</pre>
                        <pre>{json.dumps(response_data, indent=2, ensure_ascii=False)}</pre>

                        <div class="alert alert-{'success' if response_data and response_data.get('success') else 'danger'}">
                            {'✅ تم تسجيل الحضور بنجاح!' if response_data and response_data.get('success') else '❌ فشل تسجيل الحضور: ' + (response_data.get('error', 'خطأ غير معروف') if response_data else 'لا توجد استجابة')}
                        </div>

                        <hr>
                        <a href="/test-fingerprint-api" class="btn">🔙 العودة للاختبار</a>
                        <a href="/fingerprint/attendance" class="btn">📋 عرض سجلات الحضور</a>
                        <a href="/fingerprint/logs" class="btn">📝 سجلات الطلبات</a>
                    </div>
                </body>
            </html>
            """
        except Exception as e:
            import traceback
            return f"""
            <html dir="rtl">
                <body>
                    <h1 style="color:red">❌ خطأ: {str(e)}</h1>
                    <pre>{traceback.format_exc()}</pre>
                    <a href="/test-fingerprint-api">🔙 العودة</a>
                </body>
            </html>
            """

    # عرض نموذج الاختبار (GET)
    devices = FingerprintDevice.query.all()
    employees = Employee.query.filter(Employee.employee_code.isnot(None)).all()

    device_options = ''.join([f'<option value="{d.id}">{d.device_name} (ID: {d.id})</option>' for d in devices])
    employee_options = ''.join(
        [f'<option value="{e.employee_code}">{e.name} - كود: {e.employee_code}</option>' for e in employees])

    return f"""
    <html dir="rtl">
        <head>
            <style>
                body {{ font-family: Arial; padding: 20px; direction: rtl; background: #f5f7fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                input, select {{ width: 100%; padding: 8px; margin: 5px 0 15px; border: 1px solid #ddd; border-radius: 5px; }}
                button {{ background: #667eea; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }}
                button:hover {{ background: #764ba2; }}
                .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .nav-links {{ margin-top: 20px; text-align: center; }}
                .nav-links a {{ margin: 0 10px; color: #667eea; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🔬 اختبار API البصمة</h2>
                <p>استخدم هذا النموذج لمحاكاة طلب من جهاز البصمة</p>

                <form method="POST">
                    <label>📟 معرف الجهاز (device_id):</label>
                    <select name="device_id">
                        {device_options}
                    </select>

                    <label>👤 كود الموظف (employee_code):</label>
                    <select name="employee_code">
                        {employee_options}
                    </select>

                    <label>🔐 بيانات البصمة (محاكاة):</label>
                    <input type="text" name="fingerprint_data" value="test_template_{datetime.now().strftime('%H%M%S')}" placeholder="أدخل بيانات البصمة">

                    <button type="submit">🚀 إرسال اختبار</button>
                </form>

                <div class="info">
                    <strong>📌 ملاحظات:</strong>
                    <ul>
                        <li>هذا الاختبار يحاكي الطلب الذي يرسله جهاز البصمة الفعلي</li>
                        <li>بعد الإرسال، سيتم استدعاء API التحقق الحقيقي</li>
                        <li>النتيجة ستظهر في الصفحة التالية</li>
                        <li>يمكنك بعدها رؤية السجل في <a href="/fingerprint/attendance">سجلات الحضور</a></li>
                    </ul>
                </div>

                <div class="nav-links">
                    <hr>
                    <a href="/fingerprint/diagnose">🔍 صفحة التشخيص</a>
                    <a href="/fingerprint/attendance">📋 سجلات الحضور</a>
                    <a href="/fingerprint/logs">📝 سجلات الطلبات</a>
                    <a href="/fix-employee-codes">🔧 إصلاح أكواد الموظفين</a>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/api/fingerprint/verify-public', methods=['POST'])
def fingerprint_verify_public():
    """API عام للتحقق من البصمة - لا يتطلب تسجيل دخول (يستخدم من جهاز البصمة)"""
    import json
    import logging

    # تسجيل كل الطلبات لملف للتشخيص
    with open('fingerprint_requests.log', 'a', encoding='utf-8') as f:
        f.write(f"\n{'=' * 50}\n")
        f.write(f"الوقت: {datetime.now()}\n")
        f.write(f"البيانات الخام: {request.get_data(as_text=True)}\n")

    try:
        # محاولة قراءة JSON
        if request.is_json:
            data = request.get_json()
        else:
            # محاولة قراءة البيانات كـ form data
            data = request.form.to_dict()

        with open('fingerprint_requests.log', 'a', encoding='utf-8') as f:
            f.write(f"البيانات المحولة: {json.dumps(data, ensure_ascii=False)}\n")

        # التحقق من البيانات
        if not data:
            return jsonify({'success': False, 'error': 'لا توجد بيانات'}), 400

        # استخراج البيانات (قد تختلف أسماء الحقول حسب جهاز البصمة)
        device_id = data.get('device_id') or data.get('deviceId') or data.get('DeviceID')
        fingerprint_data = data.get('fingerprint_data') or data.get('fingerprint') or data.get('template')
        employee_code = data.get('employee_code') or data.get('userId') or data.get('UserID') or data.get('code')

        with open('fingerprint_requests.log', 'a', encoding='utf-8') as f:
            f.write(f"المستخلص: device_id={device_id}, employee_code={employee_code}\n")

        # البحث عن الجهاز
        device = None
        if device_id:
            device = FingerprintDevice.query.filter_by(id=device_id).first()
            if not device:
                device = FingerprintDevice.query.filter_by(device_name=device_id).first()

        if not device:
            device = FingerprintDevice.query.first()  # افتراضي

        if not device:
            return jsonify({'success': False, 'error': 'جهاز غير معروف'}), 401

        # البحث عن الموظف
        employee = None
        if employee_code:
            employee = Employee.query.filter_by(employee_code=employee_code, is_active=True).first()

        with open('fingerprint_requests.log', 'a', encoding='utf-8') as f:
            f.write(f"الموظف: {'موجود' if employee else 'غير موجود'}\n")

        # تسجيل المحاولة
        log = AttendanceLog(
            employee_id=employee.id if employee else None,
            device_id=device.id,
            timestamp=datetime.now(),
            attendance_type='check_in',
            status='success' if employee else 'denied',
            reason='بصمة مقبولة' if employee else f'كود غير معروف: {employee_code}',
            fingerprint_data=str(fingerprint_data)[:500] if fingerprint_data else None
        )
        db.session.add(log)
        db.session.commit()

        with open('fingerprint_requests.log', 'a', encoding='utf-8') as f:
            f.write(f"✅ تم تسجيل المحاولة في قاعدة البيانات (ID: {log.id})\n")

        return jsonify({
            'success': employee is not None,
            'employee': {
                'id': employee.id,
                'code': employee.employee_code,
                'name': employee.name,
                'team': employee.team.name if employee.team else None
            } if employee else None,
            'message': 'تم التسجيل بنجاح' if employee else 'كود غير معروف',
            'log_id': log.id
        })

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        with open('fingerprint_requests.log', 'a', encoding='utf-8') as f:
            f.write(f"❌ خطأ: {error_msg}\n")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/test-attendance', methods=['GET', 'POST'])
@login_required
@admin_required
def test_attendance():
    """اختبار تسجيل حضور يدوي"""
    if request.method == 'POST':
        employee_code = request.form.get('employee_code')
        device_id = request.form.get('device_id')

        # البحث عن الموظف
        employee = Employee.query.filter_by(employee_code=employee_code).first()
        device = FingerprintDevice.query.get(device_id)

        if not employee:
            flash(f'❌ موظف بالكود {employee_code} غير موجود', 'danger')
        elif not device:
            flash(f'❌ جهاز بالرقم {device_id} غير موجود', 'danger')
        else:
            # تسجيل حضور
            log = AttendanceLog(
                employee_id=employee.id,
                device_id=device.id,
                timestamp=datetime.now(),
                attendance_type='check_in',
                status='success',
                reason='تسجيل يدوي للاختبار'
            )
            db.session.add(log)
            db.session.commit()
            flash(f'✅ تم تسجيل حضور {employee.name} بنجاح', 'success')

        return redirect(url_for('test_attendance'))

    # عرض النموذج
    employees = Employee.query.filter(Employee.employee_code.isnot(None)).all()
    devices = FingerprintDevice.query.filter_by(is_active=True).all()

    return render_template('fingerprint/test_attendance.html',
                           employees=employees,
                           devices=devices)


@app.route('/fix-employee-codes')
@login_required
@admin_required
def fix_employee_codes():
    """إضافة أكواد للموظفين الذين ليس لديهم أكواد"""
    try:
        employees = Employee.query.all()
        fixed_count = 0
        results = []

        for emp in employees:
            # التحقق من أن employee_code غير موجود أو None أو 'None'
            if not emp.employee_code or emp.employee_code == 'None' or emp.employee_code == '':
                # توليد كود جديد
                # البحث عن أكبر كود موجود
                last_employee = Employee.query.filter(
                    Employee.employee_code.isnot(None),
                    Employee.employee_code != 'None',
                    Employee.employee_code != ''
                ).order_by(Employee.id.desc()).first()

                if last_employee and last_employee.employee_code and last_employee.employee_code.isdigit():
                    new_num = int(last_employee.employee_code) + 1
                else:
                    new_num = 100001

                # التأكد من عدم التكرار
                while True:
                    new_code = str(new_num)
                    existing = Employee.query.filter_by(employee_code=new_code).first()
                    if not existing:
                        break
                    new_num += 1

                emp.employee_code = new_code
                fixed_count += 1
                results.append(f"✅ {emp.name} ← كود: {new_code}")

        if fixed_count > 0:
            db.session.commit()
            flash(f'✅ تم تحديث {fixed_count} موظف بأكواد جديدة', 'success')
        else:
            flash('✅ جميع الموظفين لديهم أكواد بالفعل', 'info')

        return f"""
        <html dir="rtl">
            <head>
                <style>
                    body {{ font-family: Arial; padding: 40px; background: #f5f7fa; direction: rtl; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; }}
                    .success {{ color: green; }}
                    .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .btn {{ display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2 class="success">✅ تم إصلاح أكواد الموظفين</h2>
                    <div class="info">
                        <strong>النتائج:</strong>
                        <ul>
                            {"".join([f"<li>{r}</li>" for r in results]) if results else "<li>لا توجد تغييرات</li>"}
                        </ul>
                    </div>
                    <a href="/employees" class="btn">👥 عرض الموظفين</a>
                    <a href="/fingerprint/diagnose" class="btn">🔍 تشخيص البصمة</a>
                </div>
            </body>
        </html>
        """
    except Exception as e:
        import traceback
        return f"""
        <html dir="rtl">
            <head>
                <style>
                    body {{ font-family: Arial; padding: 40px; }}
                    .error {{ color: red; }}
                </style>
            </head>
            <body>
                <h1 class="error">❌ خطأ: {str(e)}</h1>
                <pre>{traceback.format_exc()}</pre>
                <a href="/">العودة</a>
            </body>
        </html>
        """

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