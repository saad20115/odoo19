# models/employee_request_analysis.py

from odoo import models, fields, tools

class EmployeeRequestAnalysis(models.Model):
    _name = 'employee.request.analysis'
    _description = 'Employee Request Analysis'
    _auto = False
    _rec_name = 'serial_number'

    # Basic fields
    id = fields.Integer('ID', readonly=True)
    serial_number = fields.Char('رقم المعاملة', readonly=True)
    company_id = fields.Many2one('res.company', 'الشركة', readonly=True)
    partner_id = fields.Many2one('res.partner', 'العميل/الجهة', readonly=True)

    transaction_type = fields.Many2one('employee.request.type', 'نوع المعاملة', readonly=True)
    status = fields.Selection([
        ('new', 'جديد'),
        ('in_progress', 'قيد الإجراء'),
        ('overdue', 'متأخر'),
        ('done', 'منتهى'),
    ], string='الحالة', readonly=True)
    
    department = fields.Many2one('hr.department', 'القسم', readonly=True)
    created_by = fields.Many2one('res.users', 'المنشئ', readonly=True)
    start_date = fields.Date('تاريخ البداية', readonly=True)
    end_date = fields.Date('تاريخ النهاية', readonly=True)
    create_date = fields.Datetime('تاريخ الإنشاء', readonly=True)
    incoming_number = fields.Char('رقم الوارد', readonly=True)
    
    # Simple computed fields
    duration_days = fields.Integer('المدة بالأيام', readonly=True)
    days_overdue = fields.Integer('أيام التأخير', readonly=True)
    is_overdue = fields.Boolean('متأخر؟', readonly=True)
    is_completed = fields.Boolean('مكتمل؟', readonly=True)
    
    # Date grouping fields  
    create_year = fields.Char('سنة الإنشاء', readonly=True)
    create_month = fields.Char('شهر الإنشاء', readonly=True)
    
    # Related names
    company_name = fields.Char('اسم الشركة', readonly=True)
    department_name = fields.Char('اسم القسم', readonly=True)
    transaction_type_name = fields.Char('نوع المعاملة', readonly=True)
    partner_name = fields.Char('اسم العميل', readonly=True)
    created_by_name = fields.Char('اسم المنشئ', readonly=True)

    def init(self):
        """Create the database view - ULTRA SIMPLE VERSION"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        
        query = f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT 
                    er.id,
                    er.serial_number,
                    er.company_id,
                    er.partner_id,
                    er.transaction_type,
                    er.status,
                    er.department,
                    er.created_by,
                    er.start_date,
                    er.end_date,
                    er.create_date,
                    er.incoming_number,
                    
                    -- Simple duration calculation
                    CASE 
                        WHEN er.start_date IS NOT NULL AND er.end_date IS NOT NULL 
                        THEN (er.end_date - er.start_date)
                        ELSE 0 
                    END as duration_days,
                    
                    -- Simple overdue calculation
                    CASE 
                        WHEN er.end_date IS NOT NULL AND er.end_date < CURRENT_DATE AND er.status != 'done'
                        THEN (CURRENT_DATE - er.end_date)
                        ELSE 0
                    END as days_overdue,
                    
                    -- Simple boolean flags
                    CASE 
                        WHEN er.end_date IS NOT NULL AND er.end_date < CURRENT_DATE AND er.status != 'done' 
                        THEN true 
                        ELSE false 
                    END as is_overdue,
                    
                    CASE 
                        WHEN er.status = 'done' 
                        THEN true 
                        ELSE false 
                    END as is_completed,
                    
                    -- Simple date groupings
                    EXTRACT(year FROM er.create_date)::text as create_year,
                    TO_CHAR(er.create_date, 'YYYY-MM') as create_month,
                    
                    -- Related names with proper user name handling
                    c.name as company_name,
                    d.name as department_name,
                    tt.name as transaction_type_name,
                    p.name as partner_name,
                    up.name as created_by_name
                    
                FROM employee_request er
                LEFT JOIN res_company c ON er.company_id = c.id
                LEFT JOIN hr_department d ON er.department = d.id
                LEFT JOIN employee_request_type tt ON er.transaction_type = tt.id
                LEFT JOIN res_partner p ON er.partner_id = p.id
                LEFT JOIN res_users u ON er.created_by = u.id
                LEFT JOIN res_partner up ON u.partner_id = up.id
            )
        """
        
        self.env.cr.execute(query)