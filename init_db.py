# -*- coding: utf-8 -*-
from app import app
from models import db, User, Employee, Team, Ship, Berth
from datetime import datetime, timedelta
import random


def init_db():
    with app.app_context():
        print("=" * 60)
        print("🚀 بدء تهيئة قاعدة البيانات")
        print("=" * 60)

        # Create tables
        print("📊 جاري حذف الجداول القديمة...")
        db.drop_all()
        print("✅ تم حذف الجداول القديمة")

        print("📊 جاري إنشاء الجداول الجديدة...")
        db.create_all()
        print("✅ تم إنشاء الجداول الجديدة")

        # Create admin user
        print("\n👤 جاري إنشاء مستخدم admin...")
        admin = User(
            username='admin',
            email='admin@rasessa.gov',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        print("✅ تم إنشاء مستخدم admin (admin/admin123)")

        # Create sample teams
        print("\n🏢 جاري إنشاء فرق العمل...")
        teams = [
            Team(name='فرقة التحميل 1', team_type='loading'),
            Team(name='فرقة التحميل 2', team_type='loading'),
            Team(name='فرقة التفريغ 1', team_type='unloading'),
            Team(name='فرقة الصيانة', team_type='maintenance'),
            Team(name='فرقة الأمن', team_type='security')
        ]

        for team in teams:
            db.session.add(team)
            print(f"   ✅ تم إنشاء {team.name}")

        db.session.commit()
        print(f"✅ تم إنشاء {len(teams)} فرقة عمل")

        # Create sample employees (بدون email)
        print("\n👥 جاري إنشاء موظفين تجريبيين...")
        employees = []
        professions = ['مهندس', 'فني', 'مشرف', 'عامل', 'سائق']
        places = ['الصليف', 'راس عيسى', 'الحديدة', 'الزحيفي', 'الولي', 'الضبره']

        for i in range(1, 21):
            # اختيار تاريخ ميلاد عشوائي
            birth_year = 1980 + random.randint(0, 20)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            birth_date = datetime(birth_year, birth_month, birth_day)

            # اختيار فرقة عشوائية
            team_id = random.choice([1, 2, 3, 4, 5])

            # اختيار مهنة عشوائية
            profession = random.choice(professions)

            # جعل بعض الموظفين رؤساء فرق
            if i % 5 == 0:  # كل 5 موظفين
                profession = 'رئيس فرقة'

            employee = Employee(
                name=f'موظف {i}',
                national_id=f'1234567890{i:02d}',
                birth_place=random.choice(places),
                current_address=f'راس عيسى - {random.choice(["الزحيفي", "الولي", "الضبره"])}',
                birth_date=birth_date,
                profession=profession,
                team_id=team_id,
                phone=f'0770{i:08d}',
                is_active=True
            )
            employees.append(employee)
            db.session.add(employee)

            # عرض التقدم
            if i % 5 == 0:
                print(f"   ✅ تم إنشاء {i} موظف...")

        db.session.commit()
        print(f"✅ تم إنشاء {len(employees)} موظف تجريبي")

        # تعيين قادة الفرق
        print("\n👑 جاري تعيين قادة الفرق...")
        for team in teams:
            # البحث عن أول موظف في هذه الفرقة
            team_employees = [e for e in employees if e.team_id == team.id]
            if team_employees:
                team.leader_id = team_employees[0].id
                team_employees[0].profession = 'رئيس فرقة'
                print(f"   ✅ تم تعيين {team_employees[0].name} قائداً لـ {team.name}")

        db.session.commit()

        # Create sample ships
        print("\n🚢 جاري إنشاء سفن تجريبية...")
        ships = []
        ship_names = ['البحر الأحمر', 'الخليج العربي', 'المحيط الهندي', 'البحر المتوسط', 'بحر العرب']
        flags = ['ليبيريا', 'بنما', 'العراق', 'الإمارات']

        for i, name in enumerate(ship_names, 1):
            arrival_date = datetime.now() - timedelta(days=random.randint(1, 30))

            ship = Ship(
                name=name,
                imo_number=f'IMO{i:07d}',
                flag=random.choice(flags),
                ship_type=random.choice(['cargo', 'tanker', 'container']),
                length=random.uniform(100, 300),
                width=random.uniform(20, 50),
                draft=random.uniform(5, 15),
                cargo_capacity=random.uniform(5000, 50000),
                arrival_date=arrival_date,
                berth_number=f'B{random.randint(1, 5)}',
                status='arrived'
            )
            ships.append(ship)
            db.session.add(ship)

        db.session.commit()
        print(f"✅ تم إنشاء {len(ships)} سفينة تجريبية")

        # Create berths
        print("\n⚓ جاري إنشاء الأرصفة...")
        for i in range(1, 6):
            berth = Berth(
                number=f'B{i}',
                length=random.uniform(150, 250),
                depth=random.uniform(10, 20),
                is_available=random.choice([True, False])
            )
            db.session.add(berth)

        db.session.commit()
        print(f"✅ تم إنشاء 5 أرصفة")

        print("\n" + "=" * 60)
        print("✅ تم تهيئة قاعدة البيانات بنجاح!")
        print("=" * 60)
        print("📊 ملخص البيانات:")
        print(f"   👤 المستخدمين: 1 (admin/admin123)")
        print(f"   🏢 فرق العمل: {len(teams)}")
        print(f"   👥 الموظفين: {len(employees)}")
        print(f"   🚢 السفن: {len(ships)}")
        print(f"   ⚓ الأرصفة: 5")
        print("=" * 60)


if __name__ == '__main__':
    init_db()