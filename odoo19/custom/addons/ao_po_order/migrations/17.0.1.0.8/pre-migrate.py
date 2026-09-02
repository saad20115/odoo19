def migrate(cr, version):
    # Delete stub access rows first so upgrade never hits group FK errors
    cr.execute(
        """
        DELETE FROM ir_model_access
         WHERE id IN (
            SELECT res_id FROM ir_model_data
             WHERE module = 'ao_po_order'
               AND model = 'ir.model.access'
               AND res_id IS NOT NULL
         )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'ao_po_order'
           AND model = 'ir.model.access'
        """
    )
