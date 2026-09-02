# -*- coding: utf-8 -*-
import base64
import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
EXCEL_EPOCH = date(1899, 12, 30)
DATE_NUM_FMT_IDS = {
    14, 15, 16, 17, 22, 27, 30, 31, 36, 45, 46, 47, 50, 54, 57, 58,
}

OUTPUT_FIELDS = [
    'sequence',
    'po_number',
    'execution_date',
    'work_order_number',
    'contractor_id',
    'entry_date',
    'employee_name',
    'office_id',
    'description',
    'tax_invoice',
    'invoice_number',
    'invoice_date',
    'uploaded_to_system',
    'disbursement',
    'value',
    'state',
]

# Exact header → field. Longer Arabic keys first when using "contains".
HEADER_EXACT = {
    'sequence': 'sequence',
    '#': 'sequence',
    'م': 'sequence',
    'po': 'po_number',
    'po_number': 'po_number',
    'execution_date': 'execution_date',
    'work_order_number': 'work_order_number',
    'contractor_id': 'contractor_id',
    'entry_date': 'entry_date',
    'employee_name': 'employee_name',
    'office_id': 'office_id',
    'description': 'description',
    'tax_invoice': 'tax_invoice',
    'invoice_number': 'invoice_number',
    'invoice_date': 'invoice_date',
    'uploaded_to_system': 'uploaded_to_system',
    'disbursement': 'disbursement',
    'value': 'value',
    'state': 'state',
    'تاريخ التنفيذ': 'execution_date',
    'رقم أمر العمل': 'work_order_number',
    'المقاول': 'contractor_id',
    'تاريخ الادخال': 'entry_date',
    'تاريخ الإدخال': 'entry_date',
    'الموظف': 'employee_name',
    'الجهة': 'office_id',
    'وصف العمل': 'description',
    'فاتورة ضريبية': 'tax_invoice',
    'رقم الفاتورة': 'invoice_number',
    'تاريخ الفوترة': 'invoice_date',
    'رفع على النظام': 'uploaded_to_system',
    'الصرف': 'disbursement',
    'القيمة': 'value',
}

HEADER_CONTAINS = [
    ('القيمة بالضريبة', None),
    ('value with tax', None),
    ('value_with_tax', None),
    ('رقم أمر العمل', 'work_order_number'),
    ('تاريخ التنفيذ', 'execution_date'),
    ('تاريخ الادخال', 'entry_date'),
    ('تاريخ الإدخال', 'entry_date'),
    ('تاريخ الفوترة', 'invoice_date'),
    ('فاتورة ضريبية', 'tax_invoice'),
    ('رقم الفاتورة', 'invoice_number'),
    ('رفع على النظام', 'uploaded_to_system'),
    ('وصف العمل', 'description'),
    ('المقاول', 'contractor_id'),
    ('الموظف', 'employee_name'),
    ('الجهة', 'office_id'),
    ('الصرف', 'disbursement'),
    ('القيمة', 'value'),
    ('work order', 'work_order_number'),
    ('contractor', 'contractor_id'),
]


def _norm_header(value):
    text = str(value or '').replace('\u00a0', ' ').strip()
    return ' '.join(text.split())


def map_header(value):
    header = _norm_header(value)
    if not header:
        return None
    if header in HEADER_EXACT:
        return HEADER_EXACT[header]
    lowered = header.lower()
    if lowered in HEADER_EXACT:
        return HEADER_EXACT[lowered]
    for needle, field in HEADER_CONTAINS:
        if needle in header or needle.lower() in lowered:
            return field
    return None


def as_text_id(val):
    if val is None or val == '':
        return ''
    if isinstance(val, bool):
        return ''
    if isinstance(val, float):
        if abs(val - round(val)) < 1e-6:
            return str(int(round(val)))
        return ('%.15g' % val)
    if isinstance(val, int):
        return str(val)
    text = str(val).strip()
    if re.match(r'^\d+(\.\d+)?[eE][+\-]?\d+$', text):
        try:
            return str(int(float(text)))
        except (TypeError, ValueError):
            return text
    if re.match(r'^\d+\.0$', text):
        return text[:-2]
    if text.endswith('.0') and text[:-2].isdigit():
        return text[:-2]
    return text


def parse_date(val):
    if val is None or val == '':
        return ''
    if isinstance(val, datetime):
        return val.date().isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, bool):
        return ''
    if isinstance(val, (int, float)):
        number = float(val)
        if 20000 <= number <= 60000:
            return (EXCEL_EPOCH + timedelta(days=int(number))).isoformat()
        packed = str(int(number))
        if len(packed) == 7:
            day, month, year = int(packed[:2]), int(packed[2:3]), int(packed[3:])
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                return ''
        if len(packed) == 8:
            day, month, year = int(packed[:2]), int(packed[2:4]), int(packed[4:])
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                return ''
        return ''
    text = str(val).strip()
    if not text:
        return ''
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%m/%d/%Y'):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    digits = re.sub(r'\D', '', text)
    if digits.isdigit() and len(digits) in (7, 8):
        return parse_date(int(digits))
    return ''


def yn(val):
    if val is None or val == '':
        return 'no'
    text = str(val).strip().lower()
    if text in ('تم', 'yes', 'true', '1', 'done', 'y'):
        return 'yes'
    return 'no'


def _col_to_idx(cell_ref):
    col = ''.join(char for char in (cell_ref or '') if char.isalpha())
    number = 0
    for char in col:
        number = number * 26 + (ord(char.upper()) - 64)
    return number - 1


def _xlsx_shared_strings(zip_file):
    shared = []
    if 'xl/sharedStrings.xml' not in zip_file.namelist():
        return shared
    root = ET.fromstring(zip_file.read('xl/sharedStrings.xml'))
    for si in root.findall('m:si', NS):
        texts = [
            node.text or ''
            for node in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
        ]
        shared.append(''.join(texts))
    return shared


def _xlsx_date_style_indexes(zip_file):
    date_styles = set()
    if 'xl/styles.xml' not in zip_file.namelist():
        return date_styles
    root = ET.fromstring(zip_file.read('xl/styles.xml'))
    custom_date = set()
    for num_fmt in root.findall('m:numFmts/m:numFmt', NS):
        fmt_id = int(num_fmt.get('numFmtId') or 0)
        code = (num_fmt.get('formatCode') or '').lower()
        if any(token in code for token in ('d', 'y', 'm')) and 'h' not in code.replace('hh', ''):
            custom_date.add(fmt_id)
        elif any(token in code for token in ('yy', 'dd', 'mm')):
            custom_date.add(fmt_id)
    for index, xf in enumerate(root.findall('m:cellXfs/m:xf', NS)):
        fmt_id = int(xf.get('numFmtId') or 0)
        if fmt_id in DATE_NUM_FMT_IDS or fmt_id in custom_date:
            date_styles.add(index)
    return date_styles


def _xlsx_cell_value(cell, shared, date_styles):
    cell_type = cell.get('t')
    style_index = cell.get('s')
    is_date = False
    if style_index is not None:
        try:
            is_date = int(style_index) in date_styles
        except ValueError:
            is_date = False
    if cell_type == 's':
        node = cell.find('m:v', NS)
        if node is None or node.text is None:
            return ''
        try:
            return shared[int(node.text)]
        except (ValueError, IndexError):
            return node.text
    if cell_type == 'inlineStr':
        texts = [
            node.text or ''
            for node in cell.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
        ]
        return ''.join(texts)
    if cell_type == 'str':
        node = cell.find('m:v', NS)
        return node.text if node is not None and node.text is not None else ''
    if cell_type == 'b':
        node = cell.find('m:v', NS)
        return node.text if node is not None else ''
    node = cell.find('m:v', NS)
    if node is None or node.text is None:
        return ''
    raw = node.text
    try:
        if '.' in raw or 'e' in raw.lower():
            number = float(raw)
        else:
            number = int(raw)
    except ValueError:
        return raw
    if is_date and isinstance(number, (int, float)) and 20000 <= float(number) <= 60000:
        return (EXCEL_EPOCH + timedelta(days=int(number))).isoformat()
    return number


def read_xlsx_grid(raw_bytes):
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zip_file:
        sheet_name = next(
            (
                name for name in zip_file.namelist()
                if name.startswith('xl/worksheets/sheet') and name.endswith('.xml')
            ),
            None,
        )
        if not sheet_name:
            raise ValueError('No worksheet found in the Excel file.')
        shared = _xlsx_shared_strings(zip_file)
        date_styles = _xlsx_date_style_indexes(zip_file)
        sheet = ET.fromstring(zip_file.read(sheet_name))
        grid = {}
        max_row = 0
        max_col = 0
        for row in sheet.findall('m:sheetData/m:row', NS):
            row_idx = int(row.get('r') or 0)
            max_row = max(max_row, row_idx)
            for cell in row.findall('m:c', NS):
                col_idx = _col_to_idx(cell.get('r'))
                max_col = max(max_col, col_idx)
                grid[(row_idx, col_idx)] = _xlsx_cell_value(cell, shared, date_styles)
    return grid, max_row, max_col


def find_header_row(rows):
    """rows: list of lists. Return (index, mapped_headers)."""
    for index, row in enumerate(rows[:40]):
        mapped = [map_header(cell) for cell in row]
        fields = {field for field in mapped if field}
        if 'po_number' in fields and (
            'work_order_number' in fields or 'contractor_id' in fields or 'value' in fields
        ):
            return index, mapped
    return None, []


def _row_to_record(raw, colmap):
    def get(field):
        idx = colmap.get(field)
        if idx is None or idx >= len(raw):
            return ''
        return raw[idx]

    po_number = as_text_id(get('po_number'))
    work_order = as_text_id(get('work_order_number'))
    seq_raw = get('sequence')
    try:
        sequence = int(float(seq_raw)) if seq_raw not in ('', None) else ''
    except (TypeError, ValueError):
        sequence = ''
    val_raw = get('value')
    try:
        value = float(val_raw) if val_raw not in ('', None) else 0.0
    except (TypeError, ValueError):
        value = 0.0
    contractor = get('contractor_id')
    office = get('office_id')
    employee = get('employee_name')
    description = get('description')
    return {
        'sequence': sequence,
        'po_number': po_number,
        'execution_date': parse_date(get('execution_date')),
        'work_order_number': work_order,
        'contractor_id': '' if contractor in ('', None) else str(contractor).strip(),
        'entry_date': parse_date(get('entry_date')),
        'employee_name': '' if employee in ('', None) else str(employee).strip(),
        'office_id': '' if office in ('', None) else str(office).strip(),
        'description': '' if description in ('', None) else str(description).strip(),
        'tax_invoice': yn(get('tax_invoice')),
        'invoice_number': as_text_id(get('invoice_number')),
        'invoice_date': parse_date(get('invoice_date')),
        'uploaded_to_system': yn(get('uploaded_to_system')),
        'disbursement': yn(get('disbursement')),
        'value': value,
        'state': 'draft',
    }


def _decode_text(raw_bytes):
    for encoding in ('utf-8-sig', 'utf-8', 'cp1256', 'latin-1'):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode('utf-8', errors='replace')


def read_csv_rows(raw_bytes):
    text = _decode_text(raw_bytes)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    return [list(row) for row in reader]


def parse_tabular_rows(table_rows):
    header_index, mapped = find_header_row(table_rows)
    if header_index is None:
        raise UserError(_(
            'Could not find the header row. The file must contain columns like '
            'po / رقم أمر العمل / المقاول (or already-fixed field names).'
        ))
    colmap = {}
    for idx, field in enumerate(mapped):
        if field and field not in colmap:
            colmap[field] = idx
    if 'po_number' not in colmap:
        raise UserError(_('The file has no PO column.'))

    records = []
    skipped_empty = 0
    for raw in table_rows[header_index + 1:]:
        if not raw or all(cell in ('', None) for cell in raw):
            skipped_empty += 1
            continue
        record = _row_to_record(raw, colmap)
        if not record['po_number'] and not record['work_order_number']:
            skipped_empty += 1
            continue
        records.append(record)
    return records, skipped_empty


def parse_xlsx_bytes(raw_bytes):
    grid, max_row, max_col = read_xlsx_grid(raw_bytes)
    table_rows = []
    for row_idx in range(1, max_row + 1):
        table_rows.append([grid.get((row_idx, col), '') for col in range(0, max_col + 1)])
    return parse_tabular_rows(table_rows)


def uniquify_work_orders(records, existing_numbers=None):
    existing_numbers = set(existing_numbers or [])
    seen = set(existing_numbers)
    skipped_existing = 0
    renamed = 0
    kept = []
    for record in records:
        work_order = (record.get('work_order_number') or '').strip()
        if not work_order:
            kept.append(record)
            continue
        if work_order in existing_numbers:
            skipped_existing += 1
            continue
        if work_order in seen:
            renamed += 1
            base = work_order
            suffix = 2
            candidate = '%s-DUP%s' % (base, suffix)
            while candidate in seen:
                suffix += 1
                candidate = '%s-DUP%s' % (base, suffix)
            record = dict(record, work_order_number=candidate)
            work_order = candidate
        seen.add(work_order)
        kept.append(record)
    return kept, renamed, skipped_existing


def records_to_csv_bytes(records):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=OUTPUT_FIELDS, extrasaction='ignore')
    writer.writeheader()
    for record in records:
        row = dict(record)
        row['value'] = '' if row.get('value') in (None, '') else row['value']
        writer.writerow(row)
    return ('\ufeff' + buffer.getvalue()).encode('utf-8')


class MakkaPoImportFixWizard(models.TransientModel):
    _name = 'makka.po.import.fix.wizard'
    _description = 'Fix Makka PO Import File'

    data_file = fields.Binary(string='Excel / CSV File', required=True)
    data_filename = fields.Char(string='File Name')
    output_file = fields.Binary(string='Fixed CSV', readonly=True)
    output_filename = fields.Char(string='Fixed File Name', readonly=True)
    summary = fields.Text(string='Summary', readonly=True)
    state = fields.Selection(
        [('upload', 'Upload'), ('done', 'Done')],
        default='upload',
        required=True,
    )

    def action_fix_file(self):
        self.ensure_one()
        if not self.data_file:
            raise UserError(_('Please upload an Excel (.xlsx) or CSV file.'))

        filename = (self.data_filename or '').strip().lower()
        raw = base64.b64decode(self.data_file)
        if not raw:
            raise UserError(_('The uploaded file is empty.'))

        is_xlsx = filename.endswith('.xlsx') or raw[:2] == b'PK'
        if filename.endswith('.xls') and not is_xlsx:
            raise UserError(_('Please save the file as .xlsx or .csv, then upload it again.'))

        try:
            if is_xlsx:
                records, skipped_empty = parse_xlsx_bytes(raw)
            else:
                records, skipped_empty = parse_tabular_rows(read_csv_rows(raw))
        except UserError:
            raise
        except zipfile.BadZipFile:
            raise UserError(_('This is not a valid Excel .xlsx file. Save it as .xlsx or .csv.'))
        except Exception as exc:
            raise UserError(_('Could not read the file: %s') % exc) from exc

        if not records:
            raise UserError(_('No PO rows were found in the file.'))

        existing = {
            number.strip()
            for number in self.env['makka.po.followup'].with_context(active_test=False).search([
                ('work_order_number', '!=', False),
            ]).mapped('work_order_number')
            if number and number.strip()
        }
        records, renamed, skipped_existing = uniquify_work_orders(records, existing)

        contractors_created = self._ensure_master_data(
            'makka.po.contractor',
            {row['contractor_id'] for row in records if row.get('contractor_id')},
        )
        offices_created = self._ensure_master_data(
            'makka.po.office',
            {row['office_id'] for row in records if row.get('office_id')},
        )

        csv_bytes = records_to_csv_bytes(records)
        summary = _(
            'Rows ready to import: %(rows)s\n'
            'Empty rows skipped: %(empty)s\n'
            'Duplicate work orders renamed (-DUP): %(renamed)s\n'
            'Rows skipped (work order already in Makka): %(existing)s\n'
            'Contractors created: %(contractors)s\n'
            'Offices created: %(offices)s\n\n'
            'Download the CSV, then use Favorites → Import records and upload it.'
        ) % {
            'rows': len(records),
            'empty': skipped_empty,
            'renamed': renamed,
            'existing': skipped_existing,
            'contractors': contractors_created,
            'offices': offices_created,
        }
        self.write({
            'output_file': base64.b64encode(csv_bytes),
            'output_filename': 'makka_po_followup_import.csv',
            'summary': summary,
            'state': 'done',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fix Import File'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _ensure_master_data(self, model_name, names):
        created = 0
        Model = self.env[model_name].sudo()
        for name in sorted(names):
            name = (name or '').strip()
            if not name:
                continue
            if not Model.search([('name', '=', name)], limit=1):
                Model.create({'name': name})
                created += 1
        return created
