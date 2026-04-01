from wtforms import (
    StringField, IntegerField, SelectField, BooleanField, DateField,
    TextAreaField, PasswordField, FloatField, HiddenField, DateTimeField, FileField
)
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, DateField, DateTimeField, SelectField, SelectMultipleField, TextAreaField, FloatField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError

# دوال التحقق المخصصة
def validate_national_id(form, field):
    """التحقق من الرقم الوطني (11 رقم)"""
    if field.data:
        # إزالة المسافات
        national_id = field.data.replace(' ', '').replace('-', '')

        # التحقق من أن الرقم يحتوي على أرقام فقط
        if not national_id.isdigit():
            raise ValidationError('❌ الرقم الوطني يجب أن يحتوي على أرقام فقط')

        # التحقق من الطول (11 رقم)
        if len(national_id) != 11:
            raise ValidationError(f'❌ الرقم الوطني يجب أن يتكون من 11 رقمًا (المدخل: {len(national_id)} أرقام)')


class LoginForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired()])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])

    # forms.py - إضافة حقل employee_code


# forms.py - إضافة حقل employee_code في EmployeeForm

class EmployeeForm(FlaskForm):
    """نموذج إضافة/تعديل موظف"""
    employee_code = StringField('كود الموظف للبصمة', validators=[Optional(), Length(min=1, max=20)])
    name = StringField('الاسم', validators=[DataRequired(), Length(min=3, max=100)])
    national_id = StringField('الرقم الوطني', validators=[DataRequired(), Length(min=9, max=20)])
    birth_place = StringField('مكان الميلاد', validators=[Length(max=100)])
    current_address = StringField('السكن الحالي', validators=[Length(max=200)])
    birth_date = DateField('تاريخ الميلاد', validators=[DataRequired()], format='%Y-%m-%d')
    profession = StringField('المهنة', validators=[DataRequired(), Length(max=100)])
    team_id = SelectField('الفرقة', coerce=int, choices=[], validators=[Optional()])
    phone = StringField('رقم الهاتف', validators=[Length(max=20), Optional()])
    is_active = BooleanField('نشط', default=True)

    def validate_employee_code(self, field):
        """التحقق من أن الكود يحتوي على أرقام فقط"""
        if field.data:
            if not field.data.isdigit():
                raise ValidationError('الكود يجب أن يحتوي على أرقام فقط')




class ShipForm(FlaskForm):
    name = StringField('اسم السفينة', validators=[DataRequired(), Length(max=100)])
    imo_number = StringField('رقم IMO', validators=[DataRequired(), Length(max=20)])
    flag = StringField('العلم', validators=[DataRequired(), Length(max=50)])
    ship_type = SelectField('نوع السفينة', choices=[
        ('cargo', 'بضائع'),
        ('tanker', 'ناقلة نفط'),
        ('container', 'حاويات'),
        ('passenger', 'ركاب'),
        ('other', 'أخرى')
    ])
    length = FloatField('الطول (متر)', validators=[Optional()])
    width = FloatField('العرض (متر)', validators=[Optional()])
    draft = FloatField('الغاطس (متر)', validators=[Optional()])
    cargo_capacity = FloatField('سعة الحمولة (طن)', validators=[Optional()])
    arrival_date = DateField('تاريخ الوصول', validators=[DataRequired()])
    berth_number = StringField('رقم الرصيف', validators=[Optional(), Length(max=10)])
    notes = TextAreaField('ملاحظات', validators=[Optional()])


class TeamForm(FlaskForm):
    name = StringField('اسم الفرقة', validators=[DataRequired(), Length(max=100)])
    team_type = SelectField('نوع الفرقة', choices=[
        ('loading', 'تحميل'),
        ('unloading', 'تفريغ'),
        ('maintenance', 'صيانة'),
        ('security', 'أمن'),
        ('administration', 'إدارة')
    ])
    leader_id = SelectField('قائد الفرقة', coerce=int, validators=[Optional()])


class ReportForm(FlaskForm):
    report_type = SelectField('نوع التقرير', choices=[
        ('ships', '🚢 تقارير السفن'),
        ('employees', '👥 تقارير الموظفين'),
        ('teams', '👥 فرق العمل'),
        ('teams-operations', '⚙️ تقارير فرق العمل مع العمليات'),
        ('operations', '⚙️ تقارير العمليات'),
        ('berths', '⚓ تقارير الأرصفة')
    ])
    date_from = DateField('من تاريخ', validators=[DataRequired()])
    date_to = DateField('إلى تاريخ', validators=[DataRequired()])
    format = SelectField('صيغة التقرير', choices=[
        ('html', '🌐 HTML (عرض)'),
        ('pdf', '📑 PDF (للطباعة)'),
        ('excel', '📊 Excel (للتحليل)')
    ])


class UserForm(FlaskForm):
    """نموذج إضافة مستخدم جديد"""
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('كلمة المرور', validators=[DataRequired(), Length(min=6, max=100)])
    role = SelectField('الصلاحية', choices=[
        ('admin', 'مدير'),
        ('employee', 'موظف')
    ], validators=[DataRequired()])

    def validate_username(self, field):
        if ' ' in field.data:
            raise ValidationError('اسم المستخدم لا يجب أن يحتوي على مسافات')


class UserEditForm(FlaskForm):
    """نموذج تعديل مستخدم"""
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('كلمة المرور (اتركه فارغاً إذا لم ترد التغيير)',
                             validators=[Optional(), Length(min=6, max=100)])
    role = SelectField('الصلاحية', choices=[
        ('admin', 'مدير'),
        ('employee', 'موظف')
    ], validators=[DataRequired()])

    def validate_username(self, field):
        if ' ' in field.data:
            raise ValidationError('اسم المستخدم لا يجب أن يحتوي على مسافات')


class OperationForm(FlaskForm):
    """نموذج إضافة وتعديل العمليات مع اختيار متعدد للفرق"""
    ship_id = SelectField('السفينة', coerce=int, validators=[DataRequired()])
    operation_type = SelectField('نوع العملية', choices=[
        ('', '-- اختر نوع العملية --'),
        ('تحميل', 'تحميل'),
        ('تفريغ', 'تفريغ'),
        ('صيانة', 'صيانة'),
        ('تزويد وقود', 'تزويد وقود'),
        ('تدقيق', 'تدقيق'),
        ('أخرى', 'أخرى')
    ], validators=[DataRequired()])
    start_time = DateTimeField('تاريخ البدء', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    end_time = DateTimeField('تاريخ الانتهاء', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    team_ids = SelectMultipleField('الفرق المنفذة', coerce=int, validators=[Optional()])
    cargo_type = StringField('نوع البضاعة', validators=[Optional(), Length(max=100)])
    cargo_quantity = FloatField('الكمية (طن)', validators=[Optional()])
    notes = TextAreaField('ملاحظات', validators=[Optional(), Length(max=500)])


class TeamsOperationsReportForm(FlaskForm):
    """نموذج تقرير فرق العمل مع العمليات"""
    date_from = DateField('من تاريخ', validators=[DataRequired()])
    date_to = DateField('إلى تاريخ', validators=[DataRequired()])
    team_ids = SelectMultipleField('الفرق', coerce=int, validators=[Optional()])
    include_completed = SelectField('العمليات المكتملة فقط', choices=[
        ('all', 'جميع العمليات'),
        ('completed', 'المكتملة فقط'),
        ('ongoing', 'الجارية فقط')
    ], validators=[DataRequired()])
    format = SelectField('صيغة التقرير', choices=[
        ('html', '🌐 HTML (عرض)'),
        ('pdf', '📑 PDF (للطباعة)'),
        ('excel', '📊 Excel (للتحليل)')
    ], validators=[DataRequired()])


class BerthForm(FlaskForm):
    """نموذج إضافة وتعديل الأرصفة"""
    number = StringField('رقم الرصيف', validators=[DataRequired(), Length(max=10)])
    length = FloatField('الطول (متر)', validators=[Optional()])
    depth = FloatField('العمق (متر)', validators=[Optional()])
    is_active = BooleanField('نشط', default=True)
    notes = TextAreaField('ملاحظات', validators=[Optional(), Length(max=500)])

    def validate_number(self, field):
        """التحقق من عدم تكرار رقم الرصيف"""
        from models import Berth
        berth = Berth.query.filter_by(number=field.data).first()
        if berth:
            if hasattr(self, '_obj') and self._obj and self._obj.id == berth.id:
                return
            raise ValidationError(f'رقم الرصيف "{field.data}" موجود مسبقاً')


# أضف هذه النماذج في ملف forms.py

class FingerprintDeviceForm(FlaskForm):
    """نموذج إضافة/تعديل جهاز بصمة"""
    device_name = StringField('اسم الجهاز', validators=[DataRequired(), Length(max=100)])
    device_ip = StringField('عنوان IP', validators=[Length(max=50)])
    device_port = IntegerField('المنفذ', default=80)
    device_type = SelectField('نوع الجهاز', choices=[
        ('', 'اختر نوع الجهاز'),
        ('zkteco', 'ZKTeco'),
        ('suprema', 'Suprema'),
        ('other', 'أخرى')
    ])
    berth_id = SelectField('الرصيف المرتبط', coerce=int, choices=[(0, 'غير مرتبط برصيف')])
    is_active = BooleanField('نشط', default=True)


class EnrollFingerprintForm(FlaskForm):
    """نموذج تسجيل بصمة"""
    employee_id = SelectField('الموظف', coerce=int, validators=[DataRequired()])
    device_id = SelectField('الجهاز', coerce=int, validators=[DataRequired()])
    finger_index = SelectField('رقم الإصبع', choices=[
        (1, 'الإبهام'),
        (2, 'السبابة'),
        (3, 'الوسطى'),
        (4, 'البنصر'),
        (5, 'الخنصر')
    ], coerce=int, default=1)


class AttendanceFilterForm(FlaskForm):
    """نموذج تصفية سجلات الحضور"""
    date_from = DateField('من تاريخ', format='%Y-%m-%d')
    date_to = DateField('إلى تاريخ', format='%Y-%m-%d')
    employee_id = SelectField('الموظف', coerce=int, choices=[(0, 'الكل')])
    operation_id = SelectField('العملية', coerce=int, choices=[(0, 'الكل')])
    status = SelectField('الحالة', choices=[
        ('', 'الكل'),
        ('success', 'ناجح'),
        ('denied', 'مرفوض'),
        ('error', 'خطأ')
    ])