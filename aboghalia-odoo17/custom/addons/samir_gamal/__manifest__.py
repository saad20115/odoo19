{   
'name': 'samir',
'version':'1.0.0',
'category':'',
'author':' saleh',
'sequence':'-100' ,
'summary':'',
'license': 'LGPL-3',

'description':"""saudi""",
'depends':['project', 'base','hr_expense','mail', 'website' ,
           
           ],
"data": [
    

    'data/employee_request_sequence.xml',
'security/ir.model.access.csv',
    'data/cron.xml',
    'views/reports.xml',
    'views/res_company.xml',
    'report/employee_request_report.xml',


],
'application':'True',
'auto install':'false',

 }

