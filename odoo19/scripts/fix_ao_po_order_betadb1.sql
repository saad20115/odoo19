-- BetaDB1 cleanup for ao_po_order upgrade FK errors.
-- Safe for po.order data used by ao_po_followup.

BEGIN;

-- Collect old stub group ids (by xmlid and by category/name)
CREATE TEMP TABLE tmp_po_groups (id integer PRIMARY KEY);

INSERT INTO tmp_po_groups (id)
SELECT res_id FROM ir_model_data
 WHERE module = 'ao_po_order' AND model = 'res.groups' AND res_id IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO tmp_po_groups (id)
SELECT g.id
  FROM res_groups g
  JOIN ir_module_category c ON c.id = g.category_id
 WHERE c.name::text ILIKE '%PO Order%'
ON CONFLICT DO NOTHING;

INSERT INTO tmp_po_groups (id)
SELECT g.id
  FROM res_groups g
 WHERE g.name::text ILIKE '%(ignore)%'
    OR g.name::text ILIKE '%User (ignore)%'
    OR g.name::text ILIKE '%Administrator (ignore)%'
ON CONFLICT DO NOTHING;

-- Show what we found
SELECT id FROM tmp_po_groups;

-- 1) Access rights on those groups
DELETE FROM ir_model_access
 WHERE group_id IN (SELECT id FROM tmp_po_groups);

-- Access owned by ao_po_order xmlids
DELETE FROM ir_model_access
 WHERE id IN (
    SELECT res_id FROM ir_model_data
     WHERE module = 'ao_po_order' AND model = 'ir.model.access' AND res_id IS NOT NULL
 );

-- 2) Users on those groups
DELETE FROM res_groups_users_rel
 WHERE gid IN (SELECT id FROM tmp_po_groups);

-- 3) Optional relation tables (ignore if missing)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rule_group_rel') THEN
        DELETE FROM rule_group_rel WHERE group_id IN (SELECT id FROM tmp_po_groups);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ir_rule_group_rel') THEN
        DELETE FROM ir_rule_group_rel WHERE group_id IN (SELECT id FROM tmp_po_groups);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'res_groups_implied_rel') THEN
        DELETE FROM res_groups_implied_rel
         WHERE gid IN (SELECT id FROM tmp_po_groups)
            OR hid IN (SELECT id FROM tmp_po_groups);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ir_ui_view_group_rel') THEN
        DELETE FROM ir_ui_view_group_rel WHERE gid IN (SELECT id FROM tmp_po_groups);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ir_act_window_group_rel') THEN
        DELETE FROM ir_act_window_group_rel WHERE gid IN (SELECT id FROM tmp_po_groups);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ir_ui_menu_group_rel') THEN
        DELETE FROM ir_ui_menu_group_rel WHERE gid IN (SELECT id FROM tmp_po_groups);
    END IF;
END $$;

-- 4) Delete groups
DELETE FROM res_groups
 WHERE id IN (SELECT id FROM tmp_po_groups);

-- 5) Move model ownership to followup if still on ao_po_order
UPDATE ir_model_data AS src
   SET module = 'ao_po_followup'
 WHERE src.module = 'ao_po_order'
   AND src.model IN ('ir.model', 'ir.model.fields', 'ir.model.constraint', 'ir.model.relation')
   AND NOT EXISTS (
        SELECT 1 FROM ir_model_data dst
         WHERE dst.module = 'ao_po_followup' AND dst.name = src.name
   );

-- 6) Drop stub xmlids (not the po.order table)
DELETE FROM ir_model_data
 WHERE module = 'ao_po_order'
   AND model IN (
        'res.groups',
        'ir.model.access',
        'ir.ui.menu',
        'ir.ui.view',
        'ir.actions.act_window',
        'ir.actions.server',
        'ir.module.category',
        'ir.rule'
   );

-- 7) Keep module installed empty
UPDATE ir_module_module
   SET state = 'installed',
       latest_version = '17.0.1.0.8'
 WHERE name = 'ao_po_order';

DROP TABLE tmp_po_groups;

COMMIT;
