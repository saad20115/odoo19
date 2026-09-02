{   
'name': 'saudi',
'version':'1.0.0',
'category':'',
'author':' saleh',
'sequence':'-100' ,
'summary':'',
'description':"""saudi""",
'depends':['project',
           'base',
           'hr_expense',
           'mail',
           ],
"data": [
    'security/ir.model.access.csv',
    'security/hr_security_groups.xml',
    'views/hr_expense_views.xml',
    'views/saudi.xml',
    'views/menu_item.xml',
],
'application':'True',
'auto install':'false',

 }



