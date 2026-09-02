view = env.ref('ao_employee_self_service.portal_my_home_employee_self_service', raise_if_not_found=False)
if view:
    view.write({'groups_id': [(5, 0, 0)]})
    env.cr.commit()
    print("Fixed via ORM!")
else:
    print("View not found, maybe looking in wrong module?")
