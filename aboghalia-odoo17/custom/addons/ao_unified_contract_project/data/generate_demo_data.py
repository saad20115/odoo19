import sys
sys.path.insert(0, '/home/saad/abighalia/aboghalia-odoo17/odoo17-v2-server')
import random
from datetime import date, timedelta
import odoo

def generate_data(env):
    print("=== Generating Settings and Lookup Data ===")
    admin_user = env['res.users'].search([('login', '=', 'admin')], limit=1)

    # 1. Regions
    regions_data = [
        "منطقة مكة المكرمة", "منطقة المدينة المنورة", "منطقة الرياض",
        "المنطقة الشرقية", "منطقة عسير", "منطقة تبوك", "منطقة القصيم"
    ]
    regions = []
    for name in regions_data:
        r = env['unified.contract.region'].search([('name', '=', name)], limit=1)
        if not r:
            r = env['unified.contract.region'].create({'name': name})
        regions.append(r)

    # 2. Districts
    districts_data = [
        ("حي العزيزية", regions[0]), ("حي الشوقية", regions[0]), ("حي النزهة", regions[0]), ("حي العوالي", regions[0]),
        ("حي سلطانة", regions[1]), ("حي الخالدية", regions[1]), ("حي العريض", regions[1]),
        ("حي العليا", regions[2]), ("حي الملك فهد", regions[2]), ("حي الملز", regions[2]),
        ("حي الشاطئ", regions[3]), ("حي الفيصلية", regions[3])
    ]
    districts = []
    for d_name, r_rec in districts_data:
        d = env['unified.contract.district'].search([('name', '=', d_name)], limit=1)
        if not d:
            d = env['unified.contract.district'].create({'name': d_name, 'region_id': r_rec.id})
        districts.append(d)

    # 3. Stations (require district_id)
    stations_data = [
        ("محطة العزيزية الرئيسية (ST-101)", districts[0]),
        ("محطة الشوقية التحويلية (ST-102)", districts[1]),
        ("محطة المطار القديم (ST-103)", districts[4]),
        ("محطة شمال المدينة (ST-104)", districts[5]),
        ("محطة النزهة الفرعية (ST-105)", districts[2]),
        ("محطة العليا الهيدروليكية (ST-106)", districts[7]),
        ("محطة المركز الغربي (ST-107)", districts[3]),
        ("محطة التغذية الشرقية (ST-108)", districts[10])
    ]
    stations = []
    for s_name, dist_rec in stations_data:
        st = env['unified.contract.station'].search([('name', '=', s_name)], limit=1)
        if not st:
            st = env['unified.contract.station'].create({'name': s_name, 'district_id': dist_rec.id})
        stations.append(st)

    # 4. Departments
    departments_data = [
        "إدارة شبكات المياه والخدمات", "إدارة التوزيع والشبكات الكهربائية",
        "إدارة التخطيط والدراسات الفنية", "إدارة الصيانة والتشغيل طوارئ",
        "إدارة السلامة والجودة والبيئة", "إدارة المشاريع والتنفيذ",
        "إدارة الاتصالات والألياف البصرية"
    ]
    departments = []
    for dept_name in departments_data:
        dept = env['unified.contract.department'].search([('name', '=', dept_name)], limit=1)
        if not dept:
            dept = env['unified.contract.department'].create({'name': dept_name})
        departments.append(dept)

    # 5. Work Order Types
    types_data = [
        "أمر عمل طارئ", "أمر عمل اعتيادي", "أمر عمل صيانة وقائية",
        "أمر عمل ربط وتوصيل للمشتركين", "أمر عمل استبدال وتحديث شبكات", "أمر عمل حفر وتمديد رئيسي"
    ]
    wo_types = []
    for t_name in types_data:
        wt = env['unified.contract.work.order.type'].search([('name', '=', t_name)], limit=1)
        if not wt:
            wt = env['unified.contract.work.order.type'].create({'name': t_name})
        wo_types.append(wt)

    # 6. Work Order Categories
    categories_data = [
        "شبكات المياه والصرف الصحي", "شبكات التوزيع الكهربائي الجهد المتوسط",
        "شبكات التوزيع الكهربائي الجهد المنخفض", "شبكات الألياف البصرية والاتصالات",
        "أعمال الإنارة والطرق", "الأعمال المدنية والخرسانية"
    ]
    wo_categories = []
    for c_name in categories_data:
        wc = env['unified.contract.work.order.category'].search([('name', '=', c_name)], limit=1)
        if not wc:
            wc = env['unified.contract.work.order.category'].create({'name': c_name})
        wo_categories.append(wc)

    # 7. Permit Statuses
    permit_statuses_data = [
        "ساري ومكفول", "معتمد ومكتمل", "قيد المراجعة في الأمانة",
        "منتهي ويلزم التمديد", "مرفوض - يلزم تعديل المسار"
    ]
    permit_statuses = []
    for ps_name in permit_statuses_data:
        ps = env['unified.contract.permit.status'].search([('name', '=', ps_name)], limit=1)
        if not ps:
            ps = env['unified.contract.permit.status'].create({'name': ps_name})
        permit_statuses.append(ps)

    # 8. Contractors (res.partner)
    contractors_data = [
        "شركة المباني الكبرى للمقاولات المحدودة", "شركة شبه الجزيرة للمقاولات",
        "شركة الراشد للتجارة والمقاولات", "شركة الفنار للإنشاءات والمشاريع",
        "شركة مجموعة السيف مهندسون ومقاولون", "شركة الناصر للحلول الكهربائية والهندسية",
        "شركة أراسكو للمشاريع البنائية", "شركة البلاغة للمقاولات العامة",
        "شركة البنيان السعودية للمقاولات", "شركة اليمامة للمقاولات والتجارة"
    ]
    contractors = []
    for c_name in contractors_data:
        p = env['res.partner'].search([('name', '=', c_name)], limit=1)
        if not p:
            p = env['res.partner'].create({'name': c_name, 'is_company': True})
        contractors.append(p)

    # 9. Projects
    projects_data = [
        ("UC-2026-MAK-01", "مشروع تطوير وتوسعة شبكات المياه بالعاصمة المقدسة", contractors[0]),
        ("UC-2026-MAD-02", "مشروع التغذية الكهربائية لمركز المدينة المنورة", contractors[1]),
        ("UC-2026-RIY-03", "مشروع إنشاء وتمديد شبكات الألياف البصرية بالرياض", contractors[2]),
        ("UC-2026-JED-04", "مشروع الصيانة الشاملة لشبكات الصرف الصحي بجدة", contractors[3]),
        ("UC-2026-EAS-05", "مشروع ربط المحطات الرئيسية بالمنطقة الشرقية", contractors[4]),
        ("UC-2026-ASR-06", "مشروع تأهيل شبكات التوزيع والمحولات بمنطقة عسير", contractors[5]),
        ("UC-2026-TBK-07", "مشروع إنارة وتطوير الطرق الرئيسية بتبوك", contractors[6]),
        ("UC-2026-QSM-08", "مشروع تحسين كفاءة إمدادات المياه بالقصيم", contractors[7]),
    ]
    projects = []
    for code, p_name, ctr in projects_data:
        p = env['unified.contract.project'].search([('code', '=', code)], limit=1)
        if not p:
            p = env['unified.contract.project'].create({
                'code': code,
                'name': p_name,
                'partner_id': ctr.id,
                'contract_date': date.today() - timedelta(days=180),
                'contract_end_date': date.today() + timedelta(days=500),
                'contract_entity': 'شركة المياه الوطنية / شركة الكهرباء السعودية',
            })
        projects.append(p)

    # 10. Teams (require project_id and leader_id)
    teams_data = [
        ("فريق الطوارئ والصيانة السريعة - مكة المكرمة", projects[0]),
        ("فريق الحفريات والتمديد الرئيسي - جدة", projects[3]),
        ("فريق التوصيلات الكهربائية والربط - الرياض", projects[2]),
        ("فريق التوثيق والإغلاق الفني", projects[1]),
        ("فريق الفحص الفني والجودة", projects[4]),
        ("فريق شبكات المياه والضغط العالي", projects[0]),
        ("فريق الألياف البصرية - العاصمة المقدسة", projects[2]),
        ("فريق المسح الميداني والكشوفات", projects[5]),
        ("فريق الصيانة الوقائية - المدينة المنورة", projects[1]),
        ("فريق المتابعة والتدقيق المالي", projects[6])
    ]
    teams = []
    for tm_name, prj_rec in teams_data:
        tm = env['unified.contract.team'].search([('name', '=', tm_name)], limit=1)
        if not tm:
            tm = env['unified.contract.team'].create({
                'name': tm_name,
                'project_id': prj_rec.id,
                'leader_id': admin_user.id
            })
        teams.append(tm)

    # 11. Stages
    stages = env['unified.contract.work.order.stage'].search([], order='sequence asc')
    stage_by_seq = {s.sequence: s for s in stages}

    print("=== Creating 210 Work Orders ===")

    geo_locations = [
        (21.3891, 39.8579, "مكة المكرمة"),
        (24.5247, 39.5692, "المدينة المنورة"),
        (24.7136, 46.6753, "الرياض"),
        (21.5433, 39.1728, "جدة"),
        (26.4207, 50.0888, "الدمام"),
        (18.2164, 42.5053, "أبها"),
    ]

    total_wos = env['unified.contract.work.order'].search_count([])
    target_count = 210

    if total_wos >= target_count:
        print(f"Already have {total_wos} work orders in database. Done!")
        return

    needed = target_count - total_wos
    print(f"Current WOs: {total_wos}. Generating {needed} new work orders...")

    today = date.today()
    base_number = 1236254870

    wos_to_create = []
    for i in range(needed):
        current_num = str(base_number + total_wos + i)

        stage_seq = random.choices([1, 2, 3, 4, 5], weights=[20, 25, 30, 15, 10])[0]
        stg = stage_by_seq.get(stage_seq, stages[0])

        prj = projects[0]
        ctr = prj.partner_id if prj.partner_id else random.choice(contractors)
        reg = random.choice(regions)
        dist = random.choice(districts)
        stat = random.choice(stations)
        dept = random.choice(departments)
        wtype = random.choice(wo_types)
        wcat = random.choice(wo_categories)
        pstatus = random.choice(permit_statuses)
        tm = random.choice(teams)

        if stage_seq == 5:
            st = random.choices(['in_progress', 'done'], weights=[40, 60])[0]
        elif stage_seq == 1:
            st = random.choices(['draft', 'in_progress', 'on_hold'], weights=[60, 30, 10])[0]
        else:
            st = random.choices(['in_progress', 'on_hold', 'late', 'cancel'], weights=[70, 10, 15, 5])[0]

        assign_date = today - timedelta(days=random.randint(10, 150))
        permit_start = assign_date + timedelta(days=random.randint(2, 10))
        permit_end = permit_start + timedelta(days=random.randint(30, 90))
        
        if stage_seq == 1:
            exec_prog = 0.0
        elif stage_seq == 2:
            exec_prog = float(random.randint(0, 30))
        elif stage_seq == 3:
            exec_prog = float(random.randint(20, 99))
        else:
            exec_prog = 100.0

        lat_base, lng_base, city_name = random.choice(geo_locations)
        lat = round(lat_base + random.uniform(-0.05, 0.05), 6)
        lng = round(lng_base + random.uniform(-0.05, 0.05), 6)
        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"

        est_amount = float(random.randint(15, 450) * 1000)

        if stage_seq >= 4:
            r155 = 'yes' if (stage_seq == 5 or random.random() > 0.3) else 'no'
            cert_status = 'yes' if (stage_seq == 5 or (r155 == 'yes' and random.random() > 0.4)) else 'no'
        else:
            r155 = 'no'
            cert_status = 'no'

        inv_num = f"INV2026{i:05d}" if stage_seq == 5 else False
        inv_amt = round(est_amount * 1.15, 2) if stage_seq == 5 else 0.0
        pay_st = random.choice(['unpaid', 'partially_paid', 'paid']) if stage_seq == 5 else 'unpaid'

        vals = {
            'work_order_number': current_num,
            'name': current_num,
            'project_id': prj.id,
            'contractor_id': ctr.id,
            'region_id': reg.id,
            'district_id': dist.id,
            'station_id': stat.id,
            'department_id': dept.id,
            'work_order_type_id': wtype.id,
            'work_order_category_id': wcat.id,
            'permit_status_id': pstatus.id,
            'team_id': tm.id,
            'stage_id': stg.id,
            'state': st,
            'assignment_date': assign_date,
            'estimated_amount': est_amount,
            'coordinate_x': str(lng),
            'coordinate_y': str(lat),
            'google_maps_url': maps_url,
            'permit_number': str(random.randint(5445000000, 5445999999)),
            'permit_start_date': permit_start,
            'permit_end_date': permit_end,
            'execution_start_date': permit_start if stage_seq >= 3 else False,
            'execution_end_date': permit_start + timedelta(days=30) if exec_prog == 100.0 else False,
            'excavation_quantity': float(random.randint(50, 1500)),
            'extension_quantity': float(random.randint(100, 3000)),
            'equipment_count': random.randint(2, 15),
            'execution_progress': exec_prog,
            'receipt_155_status': r155,
            'receipt_155_number': str(random.randint(1550000000, 1559999999)) if r155 == 'yes' else False,
            'receipt_155_date': assign_date + timedelta(days=20) if r155 == 'yes' else False,
            'completion_certificate_status': cert_status,
            'completion_certificate_no': str(random.randint(9000000000, 9000999999)) if cert_status == 'yes' else False,
            'invoice_number': inv_num,
            'invoice_amount': inv_amt,
            'payment_status': pay_st,
            'description': f"أمر عمل منفذ في مدينة {city_name} - {wtype.name} ضمن {prj.name}.",
        }
        wos_to_create.append(vals)

    chunk_size = 50
    for chunk_start in range(0, len(wos_to_create), chunk_size):
        chunk = wos_to_create[chunk_start:chunk_start + chunk_size]
        env['unified.contract.work.order'].create(chunk)
        print(f"Created batch {chunk_start + 1} to {chunk_start + len(chunk)} work orders.")

    final_wos = env['unified.contract.work.order'].search_count([])
    print(f"=== SUCCESS! Total Work Orders in Database: {final_wos} ===")

if __name__ == '__main__':
    odoo.tools.config.parse_config(['-d', 'MainDB1', '-r', 'odoo', '--db_host', '127.0.0.1', '--addons-path', 'addons,../custom,../custom/addons'])
    registry = odoo.registry('MainDB1')
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        generate_data(env)
        cr.commit()
