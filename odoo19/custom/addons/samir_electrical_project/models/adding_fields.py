from odoo import fields, models, api
from datetime import datetime

class projectproject(models.Model):
    _inherit = 'project.project'
    project_type = fields.Many2one(
        comodel_name='arcgis.project.type',
        string='Project Type',
 
    )
    task_stages = fields.Many2many(
        comodel_name='project.task.type',
        string='Task Stages',
    )
    
class projecttype(models.Model):

    _name = "arcgis.project.type"
    name = fields.Char('Name')


class RegionModel(models.Model):

    _name = "arcgis.region"
    _description = "Region Field Model"


    name = fields.Char('Name')

class ContractorModel(models.Model):

    _name = "arcgis.contractor"
    _description = "Contractor Field Model"

    name = fields.Char('Name')


class WorkTypeModel(models.Model):

    _name = "arcgis.work.type"
    _description = "Work Type Field Model"


    name = fields.Char('Name')
class ConsultantCodeModel(models.Model):

    _name = "arcgis.consultant"
    _description = "Consultant Code Model"


    name = fields.Char('Name')
class JobDescriptionModel(models.Model):

    _name = "arcgis.job.description"
    _description = "Job Description"

    name = fields.Char('Name')
class SectionModel(models.Model):

    _name = "arcgis.section"
    _description = "Section"

    name = fields.Char('Name')

class WorkOrderType(models.Model):

    _name = "arcgis.work.order.type"
    _description = "Work Order Type"

    name = fields.Char('Name')
    n_days = fields.Integer('Days From Assignment Date (When Field One Not Done)', default=0)
class WorkDurationType(models.Model):

    _name = "arcgis.work.duration.type"
    _description = "Work Duration Type"

    x_work_type = fields.Many2one('arcgis.work.type',string='نوع العمل')
    x_consultant_code = fields.Many2one('arcgis.consultant',string='كود الاستشاري')
    x_job_description = fields.Many2one('arcgis.job.description',string='وصف العمل')
    x_section = fields.Many2one('arcgis.section',string='القسم')
    x_job_duration = fields.Integer(string='مدة العمل')

class Xsector(models.Model):

    _name = "arcgis.x.sector"
    _description = "Sector"

    name = fields.Char('Name')
    
class Xarea(models.Model):

    _name = "arcgis.x.area"
    _description = "Area"

    name = fields.Char('Name')

class ClassificationOfWorkModel(models.Model):

    _name = "arcgis.classification.of.work.model"
    _description = "Classification Of Work Model"

    name = fields.Char('Name')

class Xwebsite(models.Model):

    _name = "arcgis.x.website"
    _description = "Website"

    name = fields.Char('Name')
    
class AttachmentNames(models.Model):

    _name = "arcgis.attachment.names"
    _description = "Attachment Names"

    name = fields.Char('Name')


class Attachments(models.Model):

    _name = "arcgis.attachments"
    _description = "Attachments"

    task_id = fields.Many2one('project.task')
    task_id_2 = fields.Many2one('project.task')
    task_id_3 = fields.Many2one('project.task')
    task_id_4 = fields.Many2one('project.task')
    task_id_5 = fields.Many2one('project.task')
    task_id_6 = fields.Many2one('project.task')
    task_id_7 = fields.Many2one('project.task')
    task_id_8 = fields.Many2one('project.task')
    task_id_9 = fields.Many2one('project.task')
    task_id_10 = fields.Many2one('project.task')
    name = fields.Many2one('arcgis.attachment.names',string='اسم المرفق ')
    file = fields.Binary('المرفق')
    upload_date = fields.Date(' تاريخ الرفع', default=datetime.today())
    comment = fields.Char('التعليق')
    status =  fields.Selection(
        selection=[
            ('pending', 'قيد الانتظار'),
            ('accepted', 'مقبول '),
            ('rejected', 'مرفوض'),
            ('modifications', 'تعديل'),
        ],
        string='الحالة ',
        default='pending',
    )
    x_duration_of_the_permit = fields.Integer(string='مدة التصريح',compute="_compute_x_duration_of_the_permit")



    @api.depends("x_start_date","x_end_date")
    def _compute_x_duration_of_the_permit(self):
                for record in self:
                    if record.x_end_date and record.x_start_date:
                        # Convert date_field to a datetime object
                        x_date_obj = fields.Date.from_string(record.x_end_date)
                        y_date_obj = fields.Date.from_string(record.x_start_date)     
                                    
                        # Calculate the difference in days
                        delta = x_date_obj - y_date_obj 
                        
                        # Store the difference in the computed field
                        record.x_duration_of_the_permit = delta.days + 1
                    else:
                        record.x_duration_of_the_permit = 0



    x_permit_number = fields.Integer(
        string='رقم التصريح ',
    )
    x_start_date = fields.Date(
        string='تاريخ البدايه',
    )
    x_end_date = fields.Date(
        string='تاريخ الانتهاء',
    )

class ProjectTask(models.Model):

    _inherit = "project.task"
    

    x_axis = fields.Float('الإحداثي X', digits=(16, 10))
    y_axis = fields.Float('الإحداثي Y', digits=(16, 10))
    
    seq = fields.Char(string='sequence number', copy=False, readonly=True, index=True)


    is_late_f1 = fields.Boolean('تأخير')
    
    @api.model
    def create(self, vals):
          if not vals.get('seq'):
              vals['seq'] = self.env['ir.sequence'].next_by_code('work.order')
          return super(ProjectTask, self).create(vals)
    

            
    

    def _compute_is_late(self):
        for record in self:
                if record.procedure155_date:
                    # Convert date_field to a datetime object
                    x_date_obj = fields.Date.from_string(record.procedure155_date)
                    y_date_obj = fields.Date.today() 
                                
                    # Calculate the difference in days
                    delta = x_date_obj - y_date_obj 
                    
                    # Store the difference in the computed field
                    record.is_late_f1 = delta.days < 0
                else:
                    record.is_late_f1 = False    
                
    maps_code = fields.Html('الخريطة',sanitize=False)
    maps_link = fields.Html(' ',sanitize=False,compute='compute_maps_link')
    def compute_maps_link(self):
         self.maps_link = self.maps_code
    x_region = fields.Many2one('arcgis.region')
    x_contractor = fields.Many2one('arcgis.contractor')
    x_work_type = fields.Many2one('arcgis.work.type',string='نوع العمل' )
    x_consultant_code = fields.Many2one('arcgis.consultant')
    x_job_description = fields.Many2one('arcgis.job.description')
    x_section = fields.Many2one('arcgis.section')



    x_area = fields.Many2one('arcgis.x.area', string='المنطقة')


    work_order_number = fields.Char(
        string='المسلسل'
         
    )
    
    # type_of_data = fields.Selection(
    #     selection=[
    #         ('option1', 'امر عمل جديد'),
    #     ],
    #     string='اختار نوع البيانات المطلوب',
    #      , default='option1'
    # )
    
    
    station_number = fields.Integer(
        string='رقم المحطة',
          
    )
    work_order_assignment_date = fields.Datetime(
        string='تاريخ إسناد أمر العمل',
        
    )

    work_order_duration_date = fields.Integer(
        string='مدة امر العمل/يوم',
        
    )
    x_sectors = fields.Many2one('arcgis.section', string='قطاعات')   
    
    supervising_engineer = fields.Char(
        string='المهندس المشرف',
        
    )
    scouting_the_site = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', ' لم يتم'),
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),
        ],
        string='كشفية الموقع',
        
    )
    presence_of_barriers = fields.Selection(
        selection=[
            ('option1', 'لايوجد'),
            ('option2', 'يوجد'),
        ],
        string='وجود عوائق',
        
    )
    declaration = fields.One2many('arcgis.attachments',inverse_name='task_id_9',
    string='التصريح',                   
    )

    x_declaration = fields.Selection(
        selection=[
            ('option1', ' لا يتطلب' ),
            ('option2', ' تم الاصدار'),
            ('option3', ' قيد التنسيق'),
            ('option4', ' باقي السداد'),
            ('option5', ' لم يتم الادخال'),
            ('option6', 'تصريح نقل'),
            ('option7', ' رفض التصريح'),
            ('option8', 'إعادة الادخال'),
            ('option9', 'مسودة'),
            ('option10', 'ملغي'),

        ],
        string=' حالة التصريح',
        
    )
    excution_start_date = fields.Date(
        string='تاريخ بداية التنفيذ',
        
    )
    excution_end_date = fields.Date(
        string='تاريخ نهاية التنفيذ',
        
    )
    implementation_status = fields.Selection(
        selection=[
            ('option1', '   تم الانتهاء'),
            ('option2', ' جاري '),
            ('option3', '  لم يتم البدء'),
            ('option4', '  تمت الفوترة'),
        ],
        string='حالة التنفيذ',
        
    )
    repositioning = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', ' لم يتم '),
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),
        ],
        string='إعادة الوضع',
        
    )
    rent_rate = fields.Float(
        string='نسبة الإنجاز', default=0.0,
        
    )
    procedure203 = fields.Selection(
        selection=[
            ('option1', 'جاهز'),
            ('option2', '  غير جاهز'), 
            ('option3', '  لا يتطلب'),
        ],
        string=' إجراء 203',
        
    )
    final_planning_approval = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', ' لم يتم'),
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),
            
        ],
        string=' اعتماد التخطيط النهائي',
        
    )
    approval_of_final_quantities = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', ' لم يتم'),
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),

        ],
        string='اعتماد الكميات النهائية',
        
    )
    procedure155 = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'), 
            ('option3', ' لا يتطلب'),
            ('option4', 'جاري'),
            
        ],
        string=' إجراء 155',
        
    )
    procedure155_date = fields.Date(
        string='تاريخ الاجراء 155',
        
    )
    x_procedure155_date = fields.Date(
        string='تاريخ اجراء 155 علي النظام',
        
    )
    final_closure = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'), 
            ('option3', ' لا يتطلب'),
            ('option4', 'جاري'),
        ],
        string='عمل محضر اثبات حالة',
    )
    x_entering_a_note_into_the_system = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', ' لم يتم '),
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),  
        ],
        string='ادخال ملاحظة على النظام',
    )
    issuing_a_certificate_of_completion = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', ' لم يتم '),
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),  
        ],
        string='اصدار شهادة الانجاز',
    )
    extract = fields.Integer(
        string=' المستخلص ',
         
    )
    site_photos = fields.Binary(
        string='صور الموقع',
    )
    download_files = fields.Binary(
        string='تحميل الملفات و التقارير',
         
    )
    notes = fields.Text(
        string='ملاحظات ',
    )
    job_type = fields.Char(
        string='نوع العمل ',
    )
    job_description = fields.Text(
        string='وصف العمل',
    )
    y_start_date = fields.Date(
        string='تاريخ البدايه',
    )
    x_attachments = fields.One2many('arcgis.attachments',inverse_name='task_id',
        string='مرفقات',
    )
    x_attachments_2 = fields.One2many('arcgis.attachments',inverse_name='task_id_2',
        string='مرفقات',
    )
    x_attachments_3 = fields.One2many('arcgis.attachments',inverse_name='task_id_3',
        string='مرفقات',
    )
    x_attachments_4 = fields.One2many('arcgis.attachments',inverse_name='task_id_4',
        string='مرفقات',
    )
    x_attachments_5 = fields.One2many('arcgis.attachments',inverse_name='task_id_5',
        string='مرفقات',
    )
    x_attachments_6 = fields.One2many('arcgis.attachments',inverse_name='task_id_6',
        string='مرفقات',
    )
    x_attachments_7 = fields.One2many('arcgis.attachments',inverse_name='task_id_7',
        string='مرفقات',
    )
    x_attachments_8 = fields.One2many('arcgis.attachments',inverse_name='task_id_8',
        string='مرفقات',
    )


    x_scout_date = fields.Date(
        string='تاريخ الكشفيه',
    )
    x_comments = fields.Text(
        string='ملاحظات',
    )
    x_completion_rate = fields.Float(
        string='نسبة الإنجاز',
    )
    x_declaration_attachments = fields.One2many('arcgis.attachments',inverse_name='task_id_10',
        string='مرفقات التصريح',
    )
    x_actual_start_date = fields.Date(
        string='تاريخ البدء الفعلي',
    )
    x_actual_end_date = fields.Date(
        string='تاريخ الانتهاء الفعلي',
    )
    x_approval_of_the_final_layout = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'), 
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),
        ],
        string='اعتماد التخطيط النهائي ',
    )
    s_procedure = fields.Text(
        string='الاجراء',
    )
    x_date_of_approval = fields.Date(
        string='تاريخ الاعتماد',
        default = datetime.today(),

    )

    x_final_planning_approval = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'), 
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),
        ],
        string='اعتماد التخطيط النهائي',
    )
    x_approval_of_final_quantities = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'), 
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),
        ],
        string='اعتماد الكميات النهائية',
    )
    procedure155_on_the_system = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'), 
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),
            
        ],
        string='اجراء 155 علي النظام',
        
    )
    x_proof_of_status = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'), 
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),             
        ],
        string='محضر اثبات حاله',
        
    )
    x_abstract_number = fields.Integer(
        string='رقم المستخلص ',
    )
    x_tax_invoice = fields.Char(
        string='الفاتوره الضريبيه',
    )
    x_abstract_value = fields.Char(
        string='قيمة المستخلص',
    )
    x_abstract_status = fields.Selection(
        selection=[
            ('option1', 'مفوتر'),
            ('option2', 'مرسل'), 
            ('option3', 'ملاحظات'), 
            ('option4', 'قيد الجراء'), 
            ('option5', 'تم الصرف'), 
            
        ],
        string='حالة المستخلص',
        
    )
    x_work_order_type = fields.Many2one('arcgis.work.order.type',
        string='القسم',
    )
    x_station_name = fields.Many2one('arcgis.attachments',
        string='اسم المحطة',
    )
    x_cell_number = fields.Integer(
        string='رقم الخليه',
    )
    x_section_number = fields.Integer(
        string='رقم السيكشن',
    )
    x_RMU = fields.Selection(
        selection=[
            ('option1', 'يوجد'),
            ('option2', 'لا يوجد'),             
        ],
        string='هل يوجد RMU ',
        
    )
    x_issuing_security = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),       
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),      
        ],
        string='اصدار التصاريح الأمنية لدخول المحطة',
        
    )
    x_scout_work = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),        
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),     
        ],
        string='عمل كشفية بالمحطة و تحديد مكان دخول الكابلات',
        
    )
    x_contractor_drilling_permits = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),   
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),          
        ],
        string='تصاريح الحفر الخاصة بالمقاول',
        
    )
    x_request_to_specify = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),            
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'), 
        ],
        string='طلب تحديد مسار بدون عزل',
        
    )
    x_request_a_calibration = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),         
        ],
        string='طلب معايرة للخلية',
        
    )
    x_cables_entering_station = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),         
        ],
        string='دخول الكابلات للمحطة',
        
    )
    x_painting_and_arranging_cables = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),         
        ],
        string='دهان و ترتيب الكابلات',
        
    )
    x_submit_as_built_program = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),   
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),          
        ],
        string='تقديم AS BUILT لطلب برنامج',
        
    )
    x_test_cables = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),        
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),     
        ],
        string='اختبار الكابلات قبل طلب برنامج',
        
    )
    x_transport_delivery = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),         
        ],
        string='تسليم النقل',
        
    )
    x_Request_an_isolation_program = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),         
        ],
        string='طلب برنامج عزل',
        
    )
    x_station_location = fields.Many2one('arcgis.work.order.type',
        string='موقع المحطه',
    )
    x_nature_of_the_site = fields.Selection(
        selection=[
            ('option1', 'فندق / شقق فندقية'),
            ('option2', 'مستشفى/ مستوصف'),             
            ('option3', 'سكني'),             
            ('option4', 'مدرسة'),             
            ('option5', 'أخرى'),             
        ],
        string='طبيعة الموقع',
        
    )
    x_number_of_low_voltage_cables = fields.Integer(
        string='عدد كوابل الجهد المنخفض',
    )
    x_painting_category = fields.Selection(
        selection=[
            ('option1', 'عامة'),
            ('option2', 'خاصة'),             
        ],
        string='فئة اللوحة',
        
    )
    x_transformer_capacity = fields.Char(
        string='سعة المحول',
    )
    x_exchange_status = fields.Selection(
        selection=[
            ('option1', 'نعم'),
            ('option2', 'لا'),             
        ],
        string='حالة الصرف',
        
    )
    x_number_of_loop_unit = fields.Char(
        string='عدد مخارج الوحدة الحلقية',
    )
    x_contractors_notes = fields.Text(
        string='ملاحظات المقاول',
    )   
    x_consultant_notes = fields.Text(
        string='ملاحظات الاستشاري',
    )   
    x_programming_date = fields.Date(
        string='موعد البرمجه',
        
    )
    x_task_number = fields.Char(
        string='رقم المهمة',
    )
    x_subscription_number = fields.Char(
        string='رقم الاشتراك',
    )
    x_almashear = fields.Many2one('arcgis.attachments',
        string='المشعر',
    )
    x_implementation_date = fields.Date(
        string='تاريخ التنفيذ',
        
    )
    x_working_condition = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),   
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),          
        ],
        string='حالة العمل',
        
    )
    x_restore_the_situation = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),
            ('option3', 'لا يتطلب'),             
        ],
        string='اعاده الوضع',
        
    )
    x_quantities = fields.Char(
        string='الكميات',
    )
    x_end_notes = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),     
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),        
        ],
        string='انهاء الملاحظات',
        
    )
    x_receiving = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'), 
            ('option3', 'جاري'), 
            ('option4', 'لا يتطلب'), 
                        
        ],
        string='استلام الاصول',
        
    )
    x_documents = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'), 
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),            
        ],
        string='المستندات',
        
    )
    x_extracts = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),         
        ],
        string='المستخلصات',
        
    )
    x_contractors_extract_number = fields.Integer(
        string='رقم المستخلص للمقاول',
    )
    x_submit_documents_to_electricity = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),         
        ],
        string='تسليم المستندات للكهرباء',
        
    )
    x_po_version = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),         
        ],
        string='اصدار po',
        
    )
    x_certificate_billing = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),   
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),          
        ],
        string='فوترة الشهادة',
        
    )
    x_implementation_photos = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),   
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),             
        ],
        string='صور التنفيذ',
        
    )
    x_execution_quantities = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),             
        ],
        string='كميات التنفيذ',
        
    )
    x_execution_quantities = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),     
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),        
        ],
        string='كميات التنفيذ',
        
    )
    x_site = fields.Many2one('arcgis.attachments',
        string='الموقع',
    )
    x_type = fields.Char(
        string='النوع',
        
    )
    x_overlapping_front = fields.Many2one('arcgis.attachments',
        string='الجبهة المتداخلة',
    )
    x_interference_type = fields.Char(
        string='نوع التداخل',
        
    )
    x_action_taken = fields.Char(
        string='الأجراء المتخذ',
        
    )
    x_follow_up = fields.Char(
        string='المتابعة',
        
    )
    x_former_contractor = fields.Many2one('arcgis.attachments',
        string='المقاول السابق',
    )
    x_current_contractor = fields.Many2one('arcgis.attachments',
        string='المقاول الحالي',
    )
    x_receiving_materials_in_report = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),      
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),       
        ],
        string='استلام المواد بمحضر',
        
    )
    x_transfer_report = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),     
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),        
        ],
        string='محضر التحويل',
        
    )
    x_send_email_electricity = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),      
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),       
        ],
        string='ارسال اميل للكهرباء',
        
    )
    x_transfer_to_system = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),   
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),          
        ],
        string='التحويل علي النظام',
        
    )
    x_program_date = fields.Date(
        string='تاريخ البرنامج',
        
    )
    x_sector = fields.Many2one('arcgis.x.sector',
        string='القطاع',
    )
    x_program_time = fields.Datetime(
        string='وقت البرنامج',
        
    )
    x_request_for_isolation = fields.Datetime(
        string='طلب العزل',
        
    )
    x_isolation_time = fields.Datetime(
        string='وقت العزل',
        
    )
    x_run_request = fields.Datetime(
        string='طلب التشغيل',
        
    )
    x_duration_of_implementation = fields.Integer(
        string='مدة التنفيذ',
        
    )
    x_operating_time = fields.Datetime(
        string='وقت التشغيل',
        
    )
    x_admin = fields.Many2one('arcgis.attachments',
        string='المشرف',
    )
    
    x_admin_new = fields.Many2many('res.users',
        string='المشرف',)

    x_attribution_date = fields.Date(
        string='تاريخ الاسناد',
        
    )
    y_end_date = fields.Date(
        string='تاريخ نهاية',
        
    )
    x_project_stages = fields.Char(
        string='مراحل المشروع',
        
    )
    x_description_of_stage = fields.Text(
        string='وصف المرحله',
        
    )
    x_permits = fields.Many2many('arcgis.attachments',
        string='التصاريح',
        
    )
    x_quality = fields.Selection(
        selection=[
            ('option1', 'هوائي'),
            ('option2', 'ارضي'),             
        ],
        string='النوعيه',
        
    )
    x_exchange = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),  
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),           
        ],
        string='الصرف',
        
    )
    x_scheme = fields.Integer(
        string='المخطط',
        
    )
    x_port = fields.Integer(
        string='المنفذ',
        
    )
    x_completion_rate = fields.Float(
        string='نسبة الإنجاز',
        
    )
    x_done = fields.Float(
        string='تم =1',
        
    )
    x_not_done = fields.Float(
        string='لم يتم =0',
        
    )
    x_stage_completion_rate = fields.Float(
        string='نسبة انجاز المرحلة',
        
    )
    x_overall_completion_rate = fields.Float(
        string='نسبة الانجاز الكلية',
        
    )
    x_warning_to_make_case_report = fields.Date(
        string='انذار لعمل محضر اثبات حالة',
        
    )
    x_attribution_order_history = fields.Date(
        string='تاريخ اسناد أمر العمل',
        
    )
    x_disbursement_of_materials = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', ' لم يتم'),
            ('option3', 'لا يتطلب'),
            ('option4', 'جاري'),
        ],
        string='صرف المواد',
        
    )
    x_program = fields.Char(
        string='البرنامج',
    )
    x_program_date = fields.Date(
        string='تاريخ البرنامج',
    )
    x_program_implementation = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),             
            ('option3', 'يتطلب'),
            ('option4', 'لا يتطلب'),             
        ],
        string='تنفيذ البرنامج',   
    )
    x_send_email = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),             
            ('option3', 'يتطلب'),
            ('option4', 'لا يتطلب'),             
        ],
        string='ارسال اميل',
        
    )
    x_sap_number = fields.Integer(
        string='رقم الساب',
    )
    x_po_number = fields.Integer(
        string='رقم PO',
    )
    x_source_with_feeder = fields.Char(
        string='المصدر مع الفيدر',
    )
    x_area_of_square = fields.Char(
      string='مساحة المربع',
    )
    x_cable_length = fields.Integer(
        string='طول الكابل',
    )
    x_coordinates = fields.Char(
        string='الاحداثيات',
    )
    x_scheduling_date = fields.Date(
        string='تاريخ الجدولة',
    )
    x_submit_documents = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),   
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),          
        ],
        string='تقديم المستندات',
        
    )
    x_consultant_extract_number = fields.Integer(
        string='رقم مستخلص الاستشاري',
    )
    x_removing_and_transporting = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),     
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),        
        ],
        string='إزالة وترحيل مواد الدفان القديمة',
        
    )
    x_supply_and_spread = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),     
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),        
        ],
        string='توريد وفرد حصباء جديدة',
        
    )
    x_requires = fields.Selection(
        selection=[
            ('option1', 'يتطلب'),
            ('option2', 'لا يتطلب'),             
        ],
        string='يتطلب / لا يتطلب',
    )
    x_contractor_value = fields.Float(
        string='قيمة المقاول',
    )
    x_approximate_value = fields.Float(
        string='قيمة تقريبية',
    )
    x_left_wall = fields.Float(
        string='الجدار الأيسر',
    )
    x_back_wall = fields.Float(
        string='الجدار الخلفي',
    )
    x_right_wall = fields.Float(
        string='الجدار الأيمن',
    )
    x_hieght = fields.Float(
        string='الارتفاع',
    )
    x_supply_and_spread_new_sand = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),           
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),  
        ],
        string='توريد وفرد رمال جديدة',
        
    )
    x_room = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),      
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),       
        ],
        string='غرفة',
        
    )
    x_RMU = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),       
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),      
        ],
        string='RMU',
        
    )
    x_TRA = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),         
        ],
        string='TRA',
    )
    x_manual_drilling = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),         
        ],
        string='حفر يدوي',
    )
    x_locking_slots = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),     
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),        
        ],
        string='تقفيل فتحات',
    )
    x_equipment_paint = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),   
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),          
        ],
        string='دهان المعدة',
    )
    x_painting_station  = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),         
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),    
        ],
        string='دهان باب غرفة محطة (مصمت)',
    )
    x_website = fields.Many2one('arcgis.x.website',string='الموقع')

    x_classification_of_work = fields.Many2one('arcgis.classification.of.work.model',string='تصنيف العمل')
     

    x_disbursement_of_materials  = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),             
            ('option3', 'جزئي'),      
            ('option4', 'لا يتطلب'),
            ('option5', 'جاري'),       
        ],
        string='صرف المواد',
    )
    x_permit_number = fields.Integer(
        string='رقم التصريح ',
    )
    x_start_date = fields.Date(
        string='تاريخ البدايه',
    )
    x_end_date = fields.Date(
        string='تاريخ الانتهاء',
    )
    x_modify_implementation_data = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),         
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),    
        ],
        string='تعديل بيانات التنفيذ',   
    )
    x_approval_initial_planning = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),       
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),      
        ],
        string='اعتماد التخطيط الاولي',   
    )
    x_attach_technical_report = fields.Selection(
        selection=[
            ('option1', 'تم'),
            ('option2', 'لم يتم'),    
            ('option3', 'جاري'),
            ('option4', 'لا يتطلب'),         
        ],
        string='ارفاق التقرير الفني',   
    )

    x_duration_of_the_permit = fields.Integer(string='مدة التصريح',compute="_compute_x_duration_of_the_permit")

    # def create(self, vals):
    #         vals['work_order_number'] = self.env['ir.sequence'].next_by_code('work_order_connections') 
    #         return super(ProjectTask, self).create(vals)

    @api.depends("x_start_date","x_end_date")
    def _compute_x_duration_of_the_permit(self):
                for record in self:
                    if record.x_end_date and record.x_start_date:
                        # Convert date_field to a datetime object
                        x_date_obj = fields.Date.from_string(record.x_end_date)
                        y_date_obj = fields.Date.from_string(record.x_start_date)     
                                    
                        # Calculate the difference in days
                        delta = x_date_obj - y_date_obj 
                        
                        # Store the difference in the computed field
                        record.x_duration_of_the_permit = delta.days + 1
                    else:
                        record.x_duration_of_the_permit = 0



    execution_duration_cell = fields.Integer(string="مدة التنفيذ", compute="_compute_execution_duration_cell")


    @api.depends("excution_end_date","excution_start_date")
    def _compute_execution_duration_cell(self):
            for record in self:
                if record.excution_end_date and record.excution_start_date:
                    # Convert date_field to a datetime object
                    x_date_obj = fields.Date.from_string(record.excution_end_date)
                    y_date_obj = fields.Date.from_string(record.excution_start_date)     
                                 
                    # Calculate the difference in days
                    delta = x_date_obj - y_date_obj
                    
                    # Store the difference in the computed field
                    record.execution_duration_cell = delta.days
                else:
                    record.execution_duration_cell = 0




    the_elapsed_period = fields.Integer(string="المدة المنقضية ", compute="_compute_the_elapsed_period")
    
    the_remaining_period = fields.Integer(string="المدة المتبقيه", compute="_compute_the_remaining_period")

   

    @api.depends("x_attribution_date")
    def _compute_the_elapsed_period(self):
            for record in self:
                if record.x_attribution_date:
                    # Convert date_field to a datetime object
                    date_obj = fields.Date.from_string(record.x_attribution_date)
                    
                    # Calculate the difference in days
                    delta = datetime.today().date() - date_obj
                    
                    # Store the difference in the computed field
                    record.the_elapsed_period = delta.days
                else:
                    record.the_elapsed_period = 0
        

    @api.depends("date_deadline")
    def _compute_the_remaining_period(self):
            for record in self:
                if record.date_deadline:
                    # Convert date_field to a datetime object
                    x_date_obj = fields.Date.from_string(record.date_deadline)
                    
                    # Calculate the difference in days
                    x_delta = x_date_obj - datetime.today().date()
                    
                    # Store the difference in the computed field
                    record.the_remaining_period = x_delta.days
                else:
                    record.the_remaining_period = 0
        


    
    x_actual_duration = fields.Integer(string="المده الفعليه", compute="_compute_x_actual_duration")

    x_duration_of_delay = fields.Integer(string="مدة التأخير", compute="_compute_x_duration_of_delay")



    @api.depends("x_attribution_date","x_duration_of_implementation")
    def _compute_x_duration_of_delay(self):
            for record in self:
                if record.x_attribution_date and record.x_duration_of_implementation:
                    # Convert date_field to a datetime object
                    x_date_obj = fields.Date.from_string(record.x_attribution_date)
                    y_date_obj = record.x_duration_of_implementation

                    # Calculate the difference in days
                    delta = (x_date_obj - datetime.today().date()).days + y_date_obj
                    
                    # Store the difference in the computed field
                    record.x_duration_of_delay = delta
                else:
                    record.x_duration_of_delay = 0

    @api.depends("x_actual_end_date","x_actual_start_date")
    def _compute_x_actual_duration(self):
            for record in self:
                if record.x_actual_start_date and record.x_actual_end_date:
                    # Convert date_field to a datetime object
                    x_date_obj = fields.Date.from_string(record.x_actual_end_date)
                    y_date_obj = fields.Date.from_string(record.x_actual_start_date)
                    
                    # Calculate the difference in days
                    delta = x_date_obj - y_date_obj
                    
                    # Store the difference in the computed field
                    record.x_actual_duration = delta.days
                else:
                    record.x_actual_duration = 0
                    
    @api.onchange("x_work_type","x_consultant_code","x_job_description","x_section","x_job_duration")
    def _compute_work_duration_type(self):
        wdt =  self.env['arcgis.work.duration.type'].search([('x_work_type','=',self.x_work_type.id)] ,limit=1)
        self.x_consultant_code = wdt.x_consultant_code.id
        self.x_job_description = wdt.x_job_description.id
        self.x_section = wdt.x_section.id
        self.work_order_duration_date = wdt.x_job_duration


    @api.onchange('rent_rate')
    def _onchange_rent_rate(self):
        for record in self:
            if record.rent_rate < 0.0:
                record.rent_rate = 0.0
            elif record.rent_rate > 100.0:
                record.rent_rate = 100.0
                
                
     #============
    x_project_type = fields.Selection(string='نوع أمر العمل', 
    selection=[
        ('التوصيلات', 'التوصيلات'),
        ('المشاريع', 'المشاريع'),
        ('توصيلات المشاعر', 'توصيلات المشاعر'),
        ('مشاريع المشاعر','مشاريع المشاعر'),
        ('صيانة المشاعر','صيانة المشاعر'),
        ('أستبدلات المنطقة المركزية','أستبدلات المنطقة المركزية'),
        ('تأهيل غرفة المحولات','تأهيل غرفة المحولات'),
        ('تأهيل غرفة العدادات','تأهيل غرفة العدادات'),
        ('توصيلات خليص','توصيلات خليص'),
        ('مشاريع خليص','مشاريع خليص'),
        ('صيانة خليص','صيانة خليص'),
        ('الصيانة و الطوارئ','الصيانة و الطوارئ'),
     ])
    #============
    # -----------------------------------------------------------------------------------------------------------------
    x_region_name = fields.Char()
    x_contractor_name = fields.Char()
    x_work_type_name = fields.Char()
    x_consultant_code_name = fields.Char()
    x_job_description_name = fields.Char()
    x_section_name = fields.Char()
    x_area_name = fields.Char()
    x_sectors_name =  fields.Char()
    x_work_order_type_name = fields.Char()
    x_station_name_name = fields.Char()
    x_station_location_name = fields.Char()
    # ---
    x_almashear_name = fields.Char()
    x_site_name = fields.Char()
    x_overlapping_front_name = fields.Char()
    x_former_contractor_name = fields.Char()
    x_current_contractor_name = fields.Char()
    x_sector_name = fields.Char()
    x_admin_name = fields.Char()
    x_website_name = fields.Char()
    x_classification_of_work_name = fields.Char()
    x_url = fields.Char()
    x_image_url = fields.Text()
    # ---
    @api.model
    def create(self,vals):
         
        res = super(ProjectTask,self).create(vals)
        # set URL
        x_server_name = "https://portal.aboghaliaoffice.com/"
        x_menu_id = 388
        x_action=567
        res.x_url = f"{x_server_name}web#id={res.id}&cids=1&{x_menu_id}&{x_action}&model=project.task&view_type=form"

        # storing name of many2one fields
        related_fields=[ 'x_region','x_contractor','x_work_type','x_consultant_code','x_job_description',
            'x_section','x_area','x_sectors','x_work_order_type','x_station_name','x_station_location',
            'x_almashear','x_site','x_overlapping_front','x_former_contractor','x_current_contractor',
            'x_sector','x_admin','x_website','x_classification_of_work']
        
        for field in related_fields:
             if getattr(res,field):
                  setattr(res,f"{field}_name",getattr(res,field).name)
        # get image id
        x_attachmentsID = self.env['ir.attachment'].search([
            ('res_model', '=', 'project.task'),
            ('res_id', '=', res.id)])
        if x_attachmentsID:
            res.x_image_url = f"{self.env['ir.config_parameter'].get_param('web.base.url')}/web/content/{x_attachmentsID.id}"

        return res
    
    def write(self,vals):
        model_attach = self.env['arcgis.attachments']
        model_section = self.env['arcgis.section']
        model_workOrder = self.env['arcgis.work.order.type']

        if 'x_website' in vals:
            site = self.env['arcgis.x.website'].search([('id','=',vals['x_website'])])
            vals['x_website_name'] = site.name

        if 'x_region' in vals:
            region = self.env['arcgis.region'].search([('id','=',vals['x_region'])])
            vals['x_region_nme'] = region.name

        if 'x_contractor' in vals:
            contracor = self.env['arcgis.contractor'].search([('id','=',vals['x_contractor'])])
            vals['x_contractor_name'] = contracor.name

        if 'x_work_type' in vals:
            workType = self.env['arcgis.work.type'].search([('id','=',vals['x_work_type'])])
            vals['x_work_type_name'] = workType.name

        if 'x_consultant_code' in vals:
            consultantCode = self.env['arcgis.consultant'].search([('id','=',vals['x_consultant_code'])])
            vals['x_consultant_code_name'] = consultantCode.name
        
        if 'x_job_description' in vals:
            jobDescribtion = self.env['arcgis.job.description'].search([('id','=',vals['x_job_description '])])
            vals['x_job_description_name'] = jobDescribtion.name
        
        if 'x_section' in vals:
            section = model_section.search([('id','=',vals['x_section'])])
            vals['x_section_name'] = section.name

        if 'x_sectors' in vals:
            sector = model_section.search([('id','=',vals['x_sectors'])])
            vals['x_sectors_name'] = sector.name

        if 'x_area' in vals:
            area = self.env['arcgis.x.area'].search([('id','=',vals['x_area'])])
            vals['x_area_name'] = area.name
        
        if 'x_work_order_type' in vals:
            workType = model_workOrder.search([('id','=',vals['x_work_order_type'])])
            vals['x_work_order_type_name'] = workType.name
        
        if 'x_station_name' in vals:
            station = model_attach.search([('id','=',vals['x_station_name'])])
            vals['x_station_name_name'] = station.name

        if 'x_station_location' in vals:
            stationLocation = model_workOrder.search([('id','=',vals['x_station_location'])])
            vals['x_station_location_name'] = stationLocation.name

        if 'x_almashear' in vals:
            almashear = model_attach.search([('id','=',vals['x_almashear'])])
            vals['x_almashear_name'] = almashear.name
        
        if 'x_site' in vals:
            site = model_attach.search([('id','=',vals['x_site'])])
            vals['x_site_name'] = site.name
        
        if 'x_overlapping_front' in vals:
            overlapping = model_attach.search([('id','=',vals['x_overlapping_front'])])
            vals['x_overlapping_front_name'] = overlapping.name

        if 'x_former_contractor' in vals:
            former_contractor  = model_attach.search([('id','=',vals['x_former_contractor'])])
            vals['x_former_contractor_name'] = former_contractor.name
        
        if 'x_current_contractor' in vals:
            current_contractor   = model_attach.search([('id','=',vals['x_current_contractor'])])
            vals['x_current_contractor_name'] = current_contractor.name
        
        if 'x_sector' in vals:
            sector = self.env['arcgis.x.sector'].search([('id','=',vals['x_sector'])])
            vals['x_sector_name'] = sector.name
        
        if 'x_admin' in vals:
            admin = model_attach.search([('id','=',vals['x_admin'])])
            vals['x_admin_name'] = admin.name
        
        if 'x_classification_of_work' in vals:
            classification_of_work  = self.env['arcgis.classification.of.work.model'].search([('id','=',vals['x_classification_of_work'])])
            vals['x_classification_of_work_name'] = classification_of_work.name
        
        res = super(ProjectTask,self).write(vals)
        return res
         
    # -----------------------------------------------------------------------------------------------------------------