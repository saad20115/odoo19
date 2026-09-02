{   
'name': 'samir',
'version': '17.0.1.0.2',
'category':'',
'author':' saleh',
'sequence':'-100' ,
'summary':'',
'license': 'LGPL-3',

'description':"""saudi""",
'depends':['project', 'base','hr_expense','mail', 'website' ,
           
           ],
"data": [
    'security/security.xml',
    'security/ir.model.access.csv',
    'data/employee_request_sequence.xml',
    'data/cron.xml',
    'data/cts_cron.xml',
    'views/reports.xml',
    'views/res_company.xml',
    'report/employee_request_report.xml',


],
'application':'True',
'auto install':'false',
'post_init_hook': 'post_init_hook',

 }
