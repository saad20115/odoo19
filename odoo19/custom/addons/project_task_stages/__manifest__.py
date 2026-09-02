{
    'name': 'Project Task - Stages',
    'version': '1.0',
    'category': 'Project',
    'author': 'Ziad Bakry',
    'depends': ['project'],
    'summary': 'Enhanced project task management with department, stages, and attachments.',
    'description': """
        Project Department Management
        Project Task Enhancement
            - Department linkage and parent department tracking
            - Task types: main tasks and sub-tasks
            - Task status tracking (not started, started, finished)
            - Exploratory stage management with forms, obstacles, and attachments
            - Execution stage management with quantities, inspections, and procedures
            - Closure stage management with certificates, approvals, and attachments
            - Automatic finished date update when task is marked as finished
    """,
    'data': [
        'security/ir.model.access.csv',

        'views/project_department_view.xml',
        'views/project_task_form_view.xml',
        'views/project_project_view.xml',
        'views/project_task_view.xml',

        'views/groups.xml',
    ],

    "images": [],
    'auto_install': False,
}
