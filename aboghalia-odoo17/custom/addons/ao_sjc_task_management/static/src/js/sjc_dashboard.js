/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const PAGE_SIZE_DEFAULT = 80;

export class SjcDashboard extends Component {
    static template = "ao_sjc_task_management.SjcDashboard";
    static props = { "*": true };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            filter: "all",
            peopleSearch: "",
            selectedTask: null,
            visibleCount: PAGE_SIZE_DEFAULT,
            data: {
                page: "dashboard",
                role: "employee",
                user_name: "",
                user_avatar: "",
                title: "",
                labels: {},
                kpis: { total: 0, new: 0, in_progress: 0, completed: 0, overdue: 0, mail: 0 },
                branches: {},
                tasks: [],
                overdue: [],
                team_members: [],
                accounting_senders: [],
                companies: [],
                creators: [],
                responsibles: [],
                departments: [],
                managers: [],
                senders: [],
                mailboxes: [],
                inbox_staff: [],
                assignees: [],
                recent: [],
                total_mails: 0,
                grace_days: 10,
                page_size: PAGE_SIZE_DEFAULT,
                lang_ar: true,
            },
        });
        onWillStart(() => this.loadData());
    }

    get page() {
        const ctx = this.props.action?.context || {};
        return ctx.sjc_page || this.state.data.page || "dashboard";
    }

    get role() {
        return this.state.data.role;
    }

    get isManagerView() {
        return this.role === "management" || this.role === "project_manager";
    }

    get showPeopleSidebar() {
        return !!this.state.data.show_people_sidebar;
    }

    get showOverviewPanels() {
        return !!this.state.data.show_overview_panels;
    }

    get isAr() {
        return !!this.state.data.lang_ar;
    }

    get roleLabel() {
        if (this.isAr) {
            return { management: "الإدارة", project_manager: "مدير المشروع", employee: "موظف" }[this.role] || "";
        }
        return { management: "Management", project_manager: "Project Manager", employee: "Employee" }[this.role] || "";
    }

    get pageSize() {
        return this.state.data.page_size || PAGE_SIZE_DEFAULT;
    }

    async loadData() {
        this.state.loading = true;
        this.state.filter = "all";
        this.state.peopleSearch = "";
        this.state.selectedTask = null;
        this.state.visibleCount = this.pageSize;
        this.state.data = await this.orm.call("sjc.dashboard", "get_page_data", [this.page]);
        this.state.visibleCount = this.state.data.page_size || PAGE_SIZE_DEFAULT;
        this.state.loading = false;
    }

    onPeopleSearch(ev) {
        this.state.peopleSearch = ev.target.value || "";
    }

    filterPeople(list) {
        const rows = list || [];
        const q = (this.state.peopleSearch || "").trim().toLowerCase();
        if (!q) {
            return rows;
        }
        return rows.filter((p) => (p.name || "").toLowerCase().includes(q));
    }

    setFilter(filter) {
        this.state.filter = filter;
        this.state.visibleCount = this.pageSize;
    }

    filteredPoTasksAll() {
        const tasks = this.state.data.tasks || [];
        if (this.state.filter === "all") {
            return tasks;
        }
        return tasks.filter((t) => t.status === this.state.filter);
    }

    filteredPoTasks() {
        return this.filteredPoTasksAll().slice(0, this.state.visibleCount);
    }

    hasMoreTasks() {
        return this.filteredPoTasksAll().length > this.state.visibleCount;
    }

    loadMoreTasks() {
        this.state.visibleCount += this.pageSize;
    }

    cardSubtitle(task) {
        if (!task) {
            return "";
        }
        if (task.po_number) {
            return task.po_number;
        }
        if (task.company) {
            return task.company;
        }
        if (task.department) {
            return task.department;
        }
        if (task.mailbox) {
            return task.mailbox;
        }
        if (task.email_from) {
            return task.email_from;
        }
        return "";
    }

    detailRows(task) {
        if (!task) {
            return [];
        }
        const rows = [];
        const push = (key, value) => {
            if (value !== undefined && value !== null && value !== "") {
                rows.push({ key, label: this.label(key), value: String(value) });
            }
        };
        push("po", task.po_number);
        push("wo", task.work_order);
        push("company", task.company);
        push("department", task.department);
        push("transaction_type", task.transaction_type);
        if (task.source === "admin_comms") {
            push("end_date", task.due_date);
        } else {
            push("due_date", task.due_date);
        }
        push("expense_amount", task.amount);
        push("expense_state", task.x_state);
        if (task.source === "admin_comms") {
            push("responsible", task.assignee);
        } else {
            push("assignee", task.assignee || task.employee);
        }
        push("created_by_users", task.created_by);
        push("managers", task.manager);
        push("assigned_by", task.assigned_by);
        push("mailboxes", task.mailbox);
        if (task.email_from) {
            rows.push({ key: "email_from", label: this.label("email_count"), value: task.email_from });
        }
        push("assignees", task.assignees);
        if (task.location_label) {
            rows.push({ key: "location", label: this.label("accounting"), value: task.location_label });
        }
        if (task.partner) {
            rows.push({ key: "partner", label: this.label("company"), value: task.partner });
        }
        if (task.topic) {
            rows.push({ key: "topic", label: this.label("details"), value: task.topic });
        }
        if (task.description) {
            rows.push({ key: "description", label: this.label("details"), value: task.description });
        }
        if (task.archived) {
            push("archived", this.label("archived"));
        }
        const seen = new Set();
        return rows.filter((r) => {
            if (seen.has(r.key)) {
                return false;
            }
            seen.add(r.key);
            return true;
        });
    }

    canSendInstructions(task) {
        if (!task || !this.isManagerView) {
            return false;
        }
        return ["po_makka", "po_madina", "admin_comms", "expenses"].includes(task.source);
    }

    taskStatus(task) {
        if (!task) {
            return "in_progress";
        }
        if (task.status) {
            return task.status;
        }
        if (task.state === "done" || task.state === "archived") {
            return "completed";
        }
        if (task.state === "new") {
            return "new";
        }
        return "in_progress";
    }

    openTaskDetail(task) {
        this.state.selectedTask = task;
    }

    closeTaskDetail() {
        this.state.selectedTask = null;
    }

    onDetailBackdrop(ev) {
        if (ev.target === ev.currentTarget) {
            this.closeTaskDetail();
        }
    }

    openRecord(resModel, resId, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name || _t("Record"),
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTask(task) {
        this.openTaskDetail(task);
    }

    goToRecord(task, ev) {
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }
        const item = task || this.state.selectedTask;
        if (!item) {
            return;
        }
        this.closeTaskDetail();
        this.openRecord(item.res_model, item.res_id, item.name);
    }

    openInstructionWizard(task) {
        const item = task || this.state.selectedTask;
        if (!item) {
            return;
        }
        this.closeTaskDetail();
        this.action.doAction({
            type: "ir.actions.act_window",
            name: this.label("send_instructions"),
            res_model: "sjc.po.instruction.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_followup_model: item.res_model,
                default_followup_id: item.res_id,
                default_po_number: item.po_number || item.name,
            },
        });
    }

    openIncomingMail() {
        this.action.doAction("incoming_mail_store.action_incoming_mail");
    }

    label(key) {
        const ar = {
            total: "الإجمالي",
            in_progress: "قيد المعالجة",
            completed: "مكتمل",
            overdue: "متأخر",
            loading: "جاري التحميل...",
            all: "الكل",
            tasks: "المهام",
            overdue_alert: "مهام متأخرة تحتاج متابعة",
            grace: "مهلة الأيام بعد تاريخ الاستحقاق",
            makka: "مكة",
            madina: "المدينة",
            mailboxes: "صناديق البريد",
            inbox_staff: "مسؤولو البريد الوارد",
            assigned_out: "تم إسنادها للموظفين",
            assignees: "الموظفون المعيَّن لهم بريد",
            email_count: "الرسائل",
            assigned_by: "أُسند بواسطة",
            recent: "أحدث الرسائل",
            open_inbox: "فتح صندوق الوارد",
            empty: "لا توجد بيانات",
            portal: "فنيين البورتال",
            accounting: "فريق المحاسبة",
            overview: "نظرة عامة",
            team_members: "أعضاء الفريق",
            accounting_senders: "من أرسل للمحاسبة",
            po_sent_count: "أوامر مرسلة",
            po_assigned_count: "أوامر مسندة",
            send_instructions: "أرسل تعليماتك",
            companies: "الشركات",
            created_by_users: "أنشئ بواسطة",
            responsible_employees: "الموظف المسؤول",
            record_count: "عدد السجلات",
            transaction_type: "نوع المعاملة",
            company: "الشركة",
            new: "جديد",
            department: "القسم",
            end_date: "تاريخ النهاية",
            po: "أمر شراء",
            wo: "أمر عمل",
            due_date: "تاريخ الاستحقاق",
            assignee: "المسند إليه",
            responsible: "المسؤول",
            load_more: "عرض المزيد",
            showing: "المعروض",
            go_to_record: "الذهاب للسجل",
            details: "التفاصيل",
            close: "إغلاق",
            click_for_details: "اضغط لعرض التفاصيل",
            menu_summary: "ملخص القوائم",
            conclusion: "الخلاصة",
            employees_sidebar: "الموظفون",
            search_people: "بحث عن موظف...",
            departments: "الأقسام",
            managers: "مسند للمدير",
            sent_to_manager: "من أرسل للمدير",
            expense_amount: "المبلغ",
            expense_state: "الحالة",
            archived: "مؤرشف",
            menu_po_makka: "مهام PO مكة",
            menu_po_madina: "مهام PO المدينة",
            menu_admin_comms: "الاتصالات الإدارية",
            menu_expenses: "المصروفات",
            menu_emails: "مهام البريد",
        };
        const en = {
            total: "Total",
            in_progress: "Under processing",
            completed: "Done",
            overdue: "Late",
            loading: "Loading...",
            all: "All",
            tasks: "Tasks",
            overdue_alert: "late tasks need attention",
            grace: "Grace days after due date",
            makka: "Makka",
            madina: "Madina",
            mailboxes: "Mailboxes",
            inbox_staff: "Incoming mail staff",
            assigned_out: "Assigned to employees",
            assignees: "Employees with assigned emails",
            email_count: "Emails",
            assigned_by: "Assigned by",
            recent: "Recent emails",
            open_inbox: "Open inbox",
            empty: "No data",
            portal: "Portal technicians",
            accounting: "Accounting team",
            overview: "Overview",
            team_members: "Team members",
            accounting_senders: "Employees who sent to Accounting",
            po_sent_count: "POs sent",
            po_assigned_count: "Assigned POs",
            send_instructions: "Send your instructions",
            companies: "Companies",
            created_by_users: "Created by",
            responsible_employees: "Responsible employees",
            record_count: "Records",
            transaction_type: "Transaction type",
            company: "Company",
            new: "New",
            department: "Department",
            end_date: "End date",
            po: "PO",
            wo: "WO",
            due_date: "Due date",
            assignee: "Assignee",
            responsible: "Responsible",
            load_more: "Load more",
            showing: "Showing",
            go_to_record: "Go to record",
            details: "Details",
            close: "Close",
            click_for_details: "Click for details",
            menu_summary: "Menus summary",
            conclusion: "Conclusion",
            employees_sidebar: "Employees",
            search_people: "Search employees...",
            departments: "Departments",
            managers: "Assigned to managers",
            sent_to_manager: "Sent to manager by",
            expense_amount: "Amount",
            expense_state: "Status",
            archived: "Archived",
            menu_po_makka: "PO - Makka Tasks",
            menu_po_madina: "PO - Madina Tasks",
            menu_admin_comms: "Administrative Communications",
            menu_expenses: "Expenses",
            menu_emails: "Emails Tasks",
        };
        // Prefer local map when Arabic so UI stays translated even if server .po is missing.
        if (this.isAr) {
            return ar[key] || (this.state.data.labels && this.state.data.labels[key]) || key;
        }
        return (this.state.data.labels && this.state.data.labels[key]) || en[key] || key;
    }
}
registry.category("actions").add("sjc_dashboard", SjcDashboard);
