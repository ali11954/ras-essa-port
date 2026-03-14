# -*- coding: utf-8 -*-
import pandas as pd
import re
from app import app
from models import db, Employee, Team
from datetime import datetime


#def clean_national_id(national_id):
    """تنظيف الرقم الوطني من الصيغ المختلفة"""
    if pd.isna(national_id) or str(national_id).strip() == '':
        return None
    cleaned = str(national_id).strip()
    # إزالة أي أحرف غير رقمية
    cleaned = re.sub(r'\D', '', cleaned)
    return cleaned if cleaned else None


#def extract_year_from_date(year_value):
    """استخراج السنة من البيانات"""
    if pd.isna(year_value) or str(year_value).strip() == '':
        return None
    try:
        # إذا كان رقماً
        if isinstance(year_value, (int, float)):
            return int(year_value)
        # إذا كان نصاً
        year_str = str(year_value).strip()
        # البحث عن 4 أرقام متتالية
        match = re.search(r'(\d{4})', year_str)
        if match:
            return int(match.group(1))
    except:
        pass
    return None


#def get_profession(profession_text, is_leader=False):
    """تحديد المهنة"""
    if pd.isna(profession_text) or str(profession_text).strip() == '':
        return 'عامل'
    prof = str(profession_text).strip()
    if 'رئيس' in prof or is_leader:
        return 'رئيس فرقة'
    return prof


#def import_data(file_path=None):
    """استيراد البيانات من ملف Excel"""

    if file_path is None:
        file_path = r'D:\ghith\ras_essa_port\port.xlsx'

    print("=" * 60)
    print("📥 بدء استيراد بيانات الموظفين")
    print("=" * 60)

    try:
        # قراءة الشيت الثاني (الكشف الكلي)
        df = pd.read_excel(file_path, sheet_name='الكشف الكلي (9)', header=None)
        print(f"📊 تم قراءة {len(df)} صف من ملف Excel")

        with app.app_context():
            # إنشاء الفرق من 1 إلى 31
            print("\n🏢 جاري إنشاء الفرق...")
            teams = {}
            for i in range(1, 32):
                team_name = f'الفرقة {i}'
                team = Team.query.filter_by(name=team_name).first()
                if not team:
                    team = Team(
                        name=team_name,
                        team_type='عمل',
                        is_active=True
                    )
                    db.session.add(team)
                    print(f"   ✅ إنشاء {team_name}")
                else:
                    print(f"   ⏩ {team_name} موجود مسبقاً")
                db.session.commit()
                teams[i] = team.id

            print("✅ تم تجهيز الفرق")

            # إحصائيات
            stats = {
                'imported': 0,
                'updated': 0,
                'skipped': 0,
                'no_national_id': 0,
                'errors': []
            }

            print("\n👥 جاري استيراد الموظفين...")
            print("-" * 50)

            # تخطي الصفوف الأولى (العناوين)
            for idx, row in df.iterrows():
                try:
                    if idx < 2:  # تخطي العناوين
                        continue

                    # التحقق من وجود بيانات
                    if pd.isna(row[2]):  # إذا كان الاسم فارغاً
                        continue

                    # استخراج البيانات
                    national_id = clean_national_id(row[1])  # العمود B
                    name = str(row[2]).strip() if not pd.isna(row[2]) else None  # العمود C
                    birth_year = extract_year_from_date(row[3])  # العمود D
                    birth_place = str(row[4]).strip() if not pd.isna(row[4]) else 'الصليف'  # العمود E
                    current_address = str(row[5]).strip() if not pd.isna(row[5]) else 'راس عيسى'  # العمود F
                    profession_text = row[6]  # العمود G
                    team_num = row[7]  # العمود H

                    if not name:
                        continue

                    # التحقق من وجود رقم وطني
                    if not national_id:
                        print(f"⚠️ تحذير: {name} - لا يوجد رقم وطني (استخدام معرف مؤقت)")
                        national_id = f"TEMP{idx:04d}"
                        stats['no_national_id'] += 1

                    # تحديد ما إذا كان قائد فرقة
                    is_leader = False
                    if not pd.isna(profession_text) and 'رئيس' in str(profession_text):
                        is_leader = True

                    profession = get_profession(profession_text, is_leader)

                    # تحديد رقم الفرقة
                    team_id = None
                    if not pd.isna(team_num):
                        try:
                            team_num_int = int(float(team_num))
                            if 1 <= team_num_int <= 31:
                                team_id = teams[team_num_int]
                        except:
                            pass

                    # إنشاء تاريخ الميلاد
                    birth_date = None
                    if birth_year and 1900 <= birth_year <= 2010:
                        birth_date = datetime(birth_year, 1, 1)
                    else:
                        birth_date = datetime(1990, 1, 1)

                    # التحقق من وجود الموظف
                    existing = Employee.query.filter_by(national_id=national_id).first()

                    if existing:
                        # تحديث البيانات
                        existing.name = name
                        existing.birth_place = birth_place
                        existing.current_address = current_address
                        existing.birth_date = birth_date
                        existing.profession = profession
                        existing.team_id = team_id
                        stats['updated'] += 1
                    else:
                        # إضافة موظف جديد
                        employee = Employee(
                            name=name,
                            national_id=national_id,
                            birth_place=birth_place,
                            current_address=current_address,
                            birth_date=birth_date,
                            profession=profession,
                            team_id=team_id,
                            phone='',
                            is_active=True
                        )
                        db.session.add(employee)
                        stats['imported'] += 1

                    # حفظ كل 50 موظف
                    if (stats['imported'] + stats['updated']) % 50 == 0:
                        db.session.commit()
                        print(f"📊 تم استيراد {stats['imported'] + stats['updated']} موظف...")

                except Exception as e:
                    print(f"❌ خطأ في الصف {idx + 1}: {str(e)}")
                    stats['errors'].append(f"الصف {idx + 1}: {str(e)}")
                    stats['skipped'] += 1

            # الحفظ النهائي (هذا السطر كان داخل الحلقة خطأ)
            db.session.commit()

            # عرض الإحصائيات
            total = Employee.query.count()

            print("\n" + "=" * 50)
            print("✅ تم الانتهاء من الاستيراد!")
            print("=" * 50)
            print(f"📊 إحصائيات:")
            print(f"   ➕ موظفين جدد: {stats['imported']}")
            print(f"   🔄 موظفين محدثين: {stats['updated']}")
            print(f"   ⚠️ موظفين متخطين: {stats['skipped']}")
            print(f"   🆔 بدون رقم وطني: {stats['no_national_id']}")
            print(f"   👥 إجمالي الموظفين: {total}")

            if stats['errors']:
                print("\n⚠️ الأخطاء:")
                for error in stats['errors'][:10]:
                    print(f"   - {error}")
                if len(stats['errors']) > 10:
                    print(f"   ... و {len(stats['errors']) - 10} خطأ آخر")

            print("\n" + "=" * 50)

            # إضافة إجمالي الموظفين إلى النتائج
            stats['total'] = total
            return stats

    except Exception as e:
        print(f"❌ خطأ عام: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


#def import_from_excel(file_path):
    """دالة للاستيراد من مسار ملف محدد"""
    result = import_data(file_path)
    # التأكد من وجود total في النتائج
    if isinstance(result, dict) and 'total' not in result:
        with app.app_context():
            from models import Employee
            result['total'] = Employee.query.count()
    return result


#if __name__ == '__main__':
    import_data()