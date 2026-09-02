# Odoo 17 ERP System & SEC Unified Contract Management

مستودع نظام Odoo 17 المتكامل، ويشمل سورس كود أودو، والموديولات المخصصة، وموديول إدارة مشاريع العقود الموحدة للكهرباء.

---

## 📁 هيكلية المستودع (Repository Structure)

- **`odoo17-v2-server/`**: سورس كود Odoo 17 الرسمي ومكتبات النواة والـ Addons القياسية.
- **`custom/addons/`**: كافة الموديولات المخصصة (Custom Addons) وتشمل:
  - `sec_unified_contract_management`: موديول إدارة مشاريع وعقود وأوامر العمل الموحدة للكهرباء (السلاسل المتتابعة الـ 7 والتنبيهات الآلية).
  - موديولات الحضور والانصراف، الموارد البشرية، الأصول، الباركود، والمستخلصات.
- **`scripts/`**: سكربتات التشغيل والربط.

---

## 🚀 متطلبات التشغيل على الجهاز الجديد من الصفر

### 1️⃣ المتطلبات الأساسية (Prerequisites)
- **Python**: الإصدار 3.10 أو 3.11.
- **PostgreSQL**: الإصدار 14+ أو 16+.
- **Node.js & RTL CSS**:
  ```bash
  npm install -g rtlcss
  ```

### 2️⃣ تثبيت مكتبات بايثون (Python Dependencies)
```bash
pip install -r odoo17-v2-server/requirements.txt
pip install libsass firebase-admin phonenumbers pandas openpyxl python-dotenv geopy pyjwt qrcode pypdf pyOpenSSL>=24.0.0 urllib3>=2.0.0
```

### 3️⃣ أمر تشغيل النظام (Running Odoo)
```bash
python odoo17-v2-server/odoo-bin \
  --addons-path="odoo17-v2-server/odoo/addons,odoo17-v2-server/addons,custom/addons" \
  --db_host=localhost \
  --db_port=5432 \
  --db_user=openpg \
  --db_password=openpgpwd \
  -d MainDB1_test \
  --http-port=8069
```

---

## ⚡ الموديول الجديد: `sec_unified_contract_management`

### المراحل الـ 7 المترابطة والتنبيهات الآلية:
1. **1️⃣ الإسناد (Draft):** إدخال بيانات أمر العمل، رقم الإشعار، المحطة، المقاول، والتكلفة التقديرية.
2. **2️⃣ الكشفية والتصاريح (Survey & Permits):** بيانات وتواريخ ورقم التصريح، واشتراطات السلامة.
3. **3️⃣ التنفيذ الميداني (Execution):** مراحل الإنجاز (استلام 15% ➔ إنجاز كلي)، مع نسب مئوية وإثباتات.
4. **4️⃣ الإغلاق والتسليم (Closing):** رفع المخططات التنفيذية (As-Built)، شهادات إتمام التمديد، واختبارات العزل.
5. **5️⃣ الفوترة والمستخلصات (Invoicing):** إعداد المستخلص ورفعه لشركة الكهرباء، والاعتماد.
6. **6️⃣ التحصيل المالي (Collection):** قيد الدفع، رقم الحوالة، وتحصيل القيمة.
7. **7️⃣ الإغلاق النهائي والأرشفة (Done):** اكتمال الدورة وأرشفة أمر العمل.
- **✖️ الإلغاء والأرشفة:** حماية ضد الحذف النهائي (Soft-delete / Cancellation Reason).
