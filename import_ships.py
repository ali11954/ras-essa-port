# -*- coding: utf-8 -*-
"""
استيراد بيانات السفن من ملف Excel
الملف: SHIP.xlsx
"""

import pandas as pd
import re
from app import app
from models import db, Ship
from datetime import datetime


def clean_imo_number(imo):
    """تنظيف رقم IMO من المسافات"""
    if pd.isna(imo) or str(imo).strip() == '':
        return None
    return str(imo).strip()


def clean_value(value, default=None):
    """تنظيف القيم الرقمية"""
    if pd.isna(value) or str(value).strip() == '':
        return default
    try:
        return float(value)
    except:
        return default


def clean_date(date_value):
    """تنظيف التاريخ"""
    if pd.isna(date_value) or str(date_value).strip() == '':
        return None
    try:
        if isinstance(date_value, datetime):
            return date_value
        elif isinstance(date_value, str):
            return datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
        else:
            return None
    except:
        return None


def import_ships(file_path=None):
    """استيراد بيانات السفن من ملف Excel"""

    if file_path is None:
        file_path = r'D:\ghith\ras_essa_port\SHIP.xlsx'

    print("=" * 70)
    print("🚢 بدء استيراد بيانات السفن")
    print("=" * 70)

    try:
        # قراءة ملف Excel
        df = pd.read_excel(file_path, sheet_name='ورقة4 (2)', header=0)
        print(f"📊 تم قراءة {len(df)} صف من ملف Excel")

        with app.app_context():
            # إحصائيات
            stats = {
                'imported': 0,
                'updated': 0,
                'skipped': 0,
                'errors': []
            }

            print("\n📋 بيانات السفن المستوردة:")
            print("-" * 70)

            for idx, row in df.iterrows():
                try:
                    # استخراج البيانات حسب الأعمدة
                    imo_number = clean_imo_number(row.get('الرقم', row.get('C')))
                    name = str(row.get('اسم الباخرة', row.get('B', ''))).strip()

                    if not imo_number or imo_number == '':
                        print(f"⚠️ الصف {idx + 2}: تخطي - لا يوجد رقم IMO")
                        stats['skipped'] += 1
                        continue

                    if not name or name == '':
                        print(f"⚠️ الصف {idx + 2}: تخطي - لا يوجد اسم سفينة")
                        stats['skipped'] += 1
                        continue

                    # استخراج باقي البيانات
                    flag = str(row.get('الشركة الملاحية', row.get('D', ''))).strip()
                    ship_type = str(row.get('نوع السفينة', row.get('E', 'cargo'))).strip()

                    # تحويل نوع السفينة إلى القيم المتوقعة
                    ship_type_map = {
                        'بضائع': 'cargo',
                        'cargo': 'cargo',
                        'ناقلة': 'tanker',
                        'tanker': 'tanker',
                        'حاويات': 'container',
                        'container': 'container',
                        'ركاب': 'passenger',
                        'passenger': 'passenger'
                    }
                    ship_type = ship_type_map.get(ship_type, 'cargo')

                    # الأبعاد (تحويل القيم الصفرية إلى None)
                    length = clean_value(row.get('الطول', row.get('F')))
                    width = clean_value(row.get('العرض', row.get('G')))
                    draft = clean_value(row.get('الغاطس', row.get('H')))
                    cargo_capacity = clean_value(row.get('سعة الحمولة', row.get('I')))

                    # التاريخ
                    arrival_date = clean_date(row.get('تاريخ الوصول', row.get('J')))

                    # رقم الرصيف
                    berth_number = str(row.get('رقم الرصيف', row.get('K', ''))).strip()
                    if berth_number == '' or pd.isna(berth_number):
                        berth_number = None

                    # ملاحظات
                    notes = str(row.get('ملاحظة', row.get('L', ''))).strip()
                    if notes == '' or pd.isna(notes):
                        notes = None

                    # التحقق من وجود السفينة
                    existing_ship = Ship.query.filter_by(imo_number=imo_number).first()

                    if existing_ship:
                        # تحديث البيانات
                        print(f"🔄 تحديث: {imo_number} - {name}")
                        existing_ship.name = name
                        existing_ship.flag = flag if flag else existing_ship.flag
                        existing_ship.ship_type = ship_type

                        # تحديث الأبعاد فقط إذا كانت القيم الجديدة غير صفرية
                        if length and length > 0:
                            existing_ship.length = length
                        if width and width > 0:
                            existing_ship.width = width
                        if draft and draft > 0:
                            existing_ship.draft = draft
                        if cargo_capacity and cargo_capacity > 0:
                            existing_ship.cargo_capacity = cargo_capacity

                        if arrival_date:
                            existing_ship.arrival_date = arrival_date
                        if berth_number:
                            existing_ship.berth_number = berth_number
                        if notes:
                            existing_ship.notes = notes

                        stats['updated'] += 1
                    else:
                        # إضافة سفينة جديدة
                        print(f"➕ إضافة: {imo_number} - {name}")
                        ship = Ship(
                            name=name,
                            imo_number=imo_number,
                            flag=flag if flag else 'غير معروف',
                            ship_type=ship_type,
                            length=length if length and length > 0 else None,
                            width=width if width and width > 0 else None,
                            draft=draft if draft and draft > 0 else None,
                            cargo_capacity=cargo_capacity if cargo_capacity and cargo_capacity > 0 else None,
                            arrival_date=arrival_date,
                            berth_number=berth_number,
                            status='arrived',
                            notes=notes
                        )
                        db.session.add(ship)
                        stats['imported'] += 1

                    # حفظ كل 10 سفن
                    if (stats['imported'] + stats['updated']) % 10 == 0:
                        db.session.commit()
                        print(f"📊 تم حفظ {stats['imported'] + stats['updated']} سفينة...")

                except Exception as e:
                    print(f"❌ خطأ في الصف {idx + 2}: {str(e)}")
                    stats['errors'].append(f"الصف {idx + 2}: {str(e)}")
                    stats['skipped'] += 1

            # الحفظ النهائي
            db.session.commit()

            # عرض الإحصائيات
            total = Ship.query.count()

            print("\n" + "=" * 70)
            print("✅ تم الانتهاء من استيراد السفن!")
            print("=" * 70)
            print(f"📊 إحصائيات:")
            print(f"   ➕ سفن جديدة: {stats['imported']}")
            print(f"   🔄 سفن محدثة: {stats['updated']}")
            print(f"   ⚠️ سفن متخطية: {stats['skipped']}")
            print(f"   👥 إجمالي السفن: {total}")

            if stats['errors']:
                print("\n⚠️ الأخطاء:")
                for error in stats['errors'][:10]:
                    print(f"   - {error}")
                if len(stats['errors']) > 10:
                    print(f"   ... و {len(stats['errors']) - 10} خطأ آخر")

            print("\n" + "=" * 70)

            return stats

    except Exception as e:
        print(f"❌ خطأ عام: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


def import_ships_from_excel(file_path):
    """دالة للاستيراد من مسار ملف محدد"""
    return import_ships(file_path)


if __name__ == '__main__':
    import_ships()