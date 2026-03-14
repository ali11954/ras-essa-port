from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'


class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    national_id = db.Column(db.String(20), unique=True, nullable=False)
    birth_place = db.Column(db.String(100), nullable=False)
    current_address = db.Column(db.String(200), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    profession = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    phone = db.Column(db.String(20))
    hire_date = db.Column(db.Date, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationship - يتم تعريف العلاقة من جهة Employee فقط
    team = db.relationship('Team', foreign_keys=[team_id], back_populates='members')


class Team(db.Model):
    __tablename__ = 'teams'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_type = db.Column(db.String(50), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    members = db.relationship('Employee', foreign_keys='Employee.team_id', back_populates='team')
    leader = db.relationship('Employee', foreign_keys=[leader_id])
    operation_teams = db.relationship('OperationTeam', back_populates='team', cascade='all, delete-orphan')

    @property
    def operations(self):
        """الحصول على جميع العمليات التي شاركت فيها الفرقة"""
        return [ot.operation for ot in self.operation_teams]

    @property
    def total_operations(self):
        """إجمالي عدد العمليات للفرقة"""
        return len(self.operation_teams)

    @property
    def total_hours(self):
        """إجمالي ساعات العمل للفرقة"""
        total = 0
        for ot in self.operation_teams:
            if ot.operation.duration:
                total += ot.operation.duration
        return round(total, 2)


    @property
    def current_operations(self):
        """الحصول على العمليات الجارية لهذه الفرقة"""
        current_ops = []
        for ot in self.operation_teams:
            if not ot.operation.end_time:
                current_ops.append(ot.operation)
        return current_ops

class Ship(db.Model):
    __tablename__ = 'ships'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    imo_number = db.Column(db.String(20), unique=True, nullable=False)
    flag = db.Column(db.String(50), nullable=False)
    ship_type = db.Column(db.String(50), nullable=False)
    length = db.Column(db.Float)
    width = db.Column(db.Float)
    draft = db.Column(db.Float)
    cargo_capacity = db.Column(db.Float)
    arrival_date = db.Column(db.DateTime, nullable=False)
    departure_date = db.Column(db.DateTime)
    berth_number = db.Column(db.String(10))
    status = db.Column(db.String(20), default='arrived')
    notes = db.Column(db.Text)

    @property
    def ongoing_operations(self):
        """الحصول على العمليات الجارية لهذه السفينة"""
        return ShipOperation.query.filter(
            ShipOperation.ship_id == self.id,
            ShipOperation.end_time == None
        ).all()

class Berth(db.Model):
    __tablename__ = 'berths'

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(10), unique=True, nullable=False)
    length = db.Column(db.Float)
    depth = db.Column(db.Float)
    is_available = db.Column(db.Boolean, default=True)
    current_ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'))
    notes = db.Column(db.Text)

    current_ship = db.relationship('Ship')

    @property
    def ships_in_berth(self):
        """الحصول على جميع السفن التي رست على هذا الرصيف"""
        return Ship.query.filter_by(berth_number=self.number).all()

    @property
    def ships_count(self):
        """عدد السفن التي رست على هذا الرصيف"""
        return Ship.query.filter_by(berth_number=self.number).count()

    @property
    def is_occupied(self):
        """التحقق مما إذا كان الرصيف مشغولاً حالياً"""
        return self.current_ship_id is not None

class ShipOperation(db.Model):
    __tablename__ = 'ship_operations'

    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=False)
    operation_type = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    cargo_type = db.Column(db.String(100))
    cargo_quantity = db.Column(db.Float)
    notes = db.Column(db.Text)

    # العلاقات
    ship = db.relationship('Ship')
    operation_teams = db.relationship('OperationTeam', back_populates='operation', cascade='all, delete-orphan')

    @property
    def teams(self):
        """الحصول على جميع الفرق المشاركة في العملية"""
        return [ot.team for ot in self.operation_teams]

    @property
    def duration(self):
        """حساب مدة العملية بالساعات"""
        if self.end_time and self.start_time:
            delta = self.end_time - self.start_time
            return round(delta.total_seconds() / 3600, 2)  # بالساعات
        return None

    @property
    def duration_text(self):
        """نص مدة العملية"""
        if self.duration:
            hours = int(self.duration)
            minutes = int((self.duration - hours) * 60)
            if hours > 0 and minutes > 0:
                return f"{hours} ساعة {minutes} دقيقة"
            elif hours > 0:
                return f"{hours} ساعة"
            elif minutes > 0:
                return f"{minutes} دقيقة"
        return '—'

class Report(db.Model):
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    report_type = db.Column(db.String(50), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    data = db.Column(db.JSON)
    file_path = db.Column(db.String(500))

    creator = db.relationship('User')


class OperationTeam(db.Model):
    """نموذج ربط العمليات بالفرق (علاقة كثير إلى كثير)"""
    __tablename__ = 'operation_teams'

    id = db.Column(db.Integer, primary_key=True)
    operation_id = db.Column(db.Integer, db.ForeignKey('ship_operations.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # العلاقات
    operation = db.relationship('ShipOperation', back_populates='operation_teams')
    team = db.relationship('Team', back_populates='operation_teams')

