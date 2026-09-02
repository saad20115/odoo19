/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
const actionRegistry = registry.category("actions");
/**
 * Main Attendance Grid Component for Odoo 17
 */
export class AttendanceGridComponent extends owl.Component {
  static template = "attendance.AttendanceGrid";
  static components = { Dialog };

  setup() {
    // Odoo services
    this.orm = useService("orm");
    this.action = useService("action");
    this.notification = useService("notification");
    this.dialog = useService("dialog");

    // Component state
    this.state = useState({
      employees: [],
      attendanceData: {},
      currentYear: new Date().getFullYear(),
      currentMonth: new Date().getMonth() + 1,
      currentMonthName: "",
      daysInMonth: [],
      isLoading: true,
      stats: {
        totalEmployees: 0,
        workingDays: 0,
        avgAttendance: 0,
        totalAbsences: 0,
      },
    });

    // Component refs
    this.containerRef = useRef("container");

    // Context menu state
    this.contextMenu = {
      visible: false,
      x: 0,
      y: 0,
      employeeId: null,
      day: null,
    };

    // Month names for display
    this.monthNames = [
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
    ];

    // Status configurations
    this.statusConfig = {
      present: {
        class: "o_status_present",
        icon: "fa-check-circle",
        color: "#28a745",
        label: _t("Present"),
      },
      absent: {
        class: "o_status_absent",
        icon: "fa-times-circle",
        color: "#dc3545",
        label: _t("Absent"),
      },
      holiday: {
        class: "o_status_holiday",
        icon: "fa-calendar",
        color: "#ffc107",
        label: _t("Holiday"),
      },
      leave: {
        class: "o_status_leave",
        icon: "fa-plane",
        color: "#17a2b8",
        label: _t("Leave"),
      },
      weekend: {
        class: "o_status_weekend",
        icon: "fa-bed",
        color: "#6c757d",
        label: _t("Weekend"),
      },
    };

    onWillStart(async () => {
      await this.loadData();
    });

    onMounted(() => {
      this.setupEventListeners();
    });
  }

  /**
   * Setup global event listeners
   */
  setupEventListeners() {
    // Hide context menu on outside click
    document.addEventListener("click", this.hideContextMenu.bind(this));

    // Keyboard shortcuts
    document.addEventListener("keydown", this.handleKeydown.bind(this));
  }

  /**
   * Load attendance data for current month using Python backend
   */
  async loadData() {
    try {
      this.state.isLoading = true;

      // Update current month name
      this.state.currentMonthName =
        this.monthNames[this.state.currentMonth - 1];

      // Call Python method to get all attendance data for the month
      const attendanceData = await this.orm.call(
        "hr.employee.attendance.grid",
        "get_attendance_data",
        [],
        {
          year: this.state.currentYear,
          month: this.state.currentMonth,
        }
      );

      // Update state with data from Python
      this.state.employees = attendanceData.employees;
      this.state.daysInMonth = attendanceData.days_in_month;
      this.state.attendanceData = attendanceData.attendance_data;
      this.state.stats = attendanceData.statistics;
    } catch (error) {
      console.error("Error loading attendance data:", error);
      this.notification.add(_t("Error loading attendance data"), {
        type: "danger",
      });

      // Fallback to basic data if Python call fails
      await this.loadFallbackData();
    } finally {
      this.state.isLoading = false;
    }
  }

  /**
   * Fallback method to load basic data if Python backend fails
   */
  async loadFallbackData() {
    try {
      // Generate days in month
      const daysInMonth = new Date(
        this.state.currentYear,
        this.state.currentMonth,
        0
      ).getDate();
      this.state.daysInMonth = Array.from(
        { length: daysInMonth },
        (_, i) => i + 1
      );

      // Load employees directly
      const employees = await this.orm.searchRead(
        "hr.employee",
        [["active", "=", true]],
        ["name", "department_id", "user_id", "work_email"],
        { order: "name asc" }
      );
      this.state.employees = employees;

      // Initialize empty attendance data
      this.state.attendanceData = {};
      employees.forEach((employee) => {
        this.state.attendanceData[employee.id] = {};
        this.state.daysInMonth.forEach((day) => {
          this.state.attendanceData[employee.id][day] = {
            status: "absent",
            hours: 0,
            checkIn: null,
            checkOut: null,
          };
        });
      });

      this.calculateBasicStats();
    } catch (error) {
      console.error("Error loading fallback data:", error);
      this.notification.add(_t("Error loading employee data"), {
        type: "danger",
      });
    }
  }

  /**
   * Calculate basic statistics (fallback method)
   */
  calculateBasicStats() {
    const stats = {
      totalEmployees: this.state.employees.length,
      workingDays: 0,
      totalPresent: 0,
      totalAbsences: 0,
      avgAttendance: 0,
    };

    this.state.daysInMonth.forEach((day) => {
      const date = new Date(
        this.state.currentYear,
        this.state.currentMonth - 1,
        day
      );
      if (date.getDay() !== 0 && date.getDay() !== 6) {
        stats.workingDays++;
      }
    });

    this.state.employees.forEach((employee) => {
      this.state.daysInMonth.forEach((day) => {
        const dayData = this.state.attendanceData[employee.id]?.[day];
        if (dayData) {
          if (dayData.status === "present") {
            stats.totalPresent++;
          } else if (dayData.status === "absent") {
            stats.totalAbsences++;
          }
        }
      });
    });

    const totalWorkingSlots = stats.workingDays * stats.totalEmployees;
    stats.avgAttendance =
      totalWorkingSlots > 0
        ? Math.round((stats.totalPresent / totalWorkingSlots) * 100)
        : 0;

    this.state.stats = stats;
  }

  // Event Handlers

  /**
   * Handle attendance cell click
   */
  async onAttendanceCellClick(event, employeeId, day) {
    event.preventDefault();
    event.stopPropagation();

    const currentData = this.state.attendanceData[employeeId]?.[day];
    if (!currentData || currentData.status === "weekend") {
      return;
    }

    // Cycle through statuses: present -> absent -> holiday -> leave -> present
    const statusCycle = {
      present: "absent",
      absent: "holiday",
      holiday: "leave",
      leave: "present",
    };

    const newStatus = statusCycle[currentData.status] || "present";
    await this.updateAttendanceStatus(employeeId, day, newStatus);
  }

  /**
   * Handle right-click context menu
   */
  onAttendanceCellRightClick(event, employeeId, day) {
    event.preventDefault();
    event.stopPropagation();

    const employee = this.state.employees.find((emp) => emp.id === employeeId);
    const currentData = this.state.attendanceData[employeeId]?.[day];

    if (!employee || !currentData || currentData.status === "weekend") {
      return;
    }

    this.showContextMenu(
      event.clientX,
      event.clientY,
      employee,
      day,
      currentData
    );
  }

  /**
   * Update attendance status
   */
  async updateAttendanceStatus(employeeId, day, newStatus) {
    try {
      const dateStr = `${this.state.currentYear}-${String(
        this.state.currentMonth
      ).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

      // Call Python method to update attendance
      await this.orm.call(
        "hr.employee.attendance.grid",
        "update_attendance_status",
        [],
        {
          employee_id: employeeId,
          date: dateStr,
          status: newStatus,
        }
      );

      // Update local state
      if (!this.state.attendanceData[employeeId]) {
        this.state.attendanceData[employeeId] = {};
      }

      this.state.attendanceData[employeeId][day] = {
        ...this.state.attendanceData[employeeId][day],
        status: newStatus,
      };

      // Recalculate stats
      this.calculateStats();

      // Show notification
      const employee = this.state.employees.find(
        (emp) => emp.id === employeeId
      );
      const statusLabel = this.statusConfig[newStatus]?.label || newStatus;

      this.notification.add(
        _t(`${employee.name} marked as ${statusLabel} for day ${day}`),
        { type: "success" }
      );

      // Trigger custom event
      this.env.bus.trigger("attendance-updated", {
        employeeId,
        day,
        newStatus,
        employee: employee.name,
      });
    } catch (error) {
      console.error("Error updating attendance:", error);
      this.notification.add(_t("Error updating attendance"), {
        type: "danger",
      });
    }
  }

  /**
   * Navigate to previous month
   */
  async onPreviousMonth() {
    if (this.state.currentMonth === 1) {
      this.state.currentMonth = 12;
      this.state.currentYear--;
    } else {
      this.state.currentMonth--;
    }
    await this.loadData();
  }

  /**
   * Navigate to next month
   */
  async onNextMonth() {
    if (this.state.currentMonth === 12) {
      this.state.currentMonth = 1;
      this.state.currentYear++;
    } else {
      this.state.currentMonth++;
    }
    await this.loadData();
  }

  /**
   * Navigate to current month
   */
  async onToday() {
    const now = new Date();
    this.state.currentYear = now.getFullYear();
    this.state.currentMonth = now.getMonth() + 1;
    await this.loadData();
  }

  // Helper Methods

  /**
   * Get CSS class for attendance cell
   */
  getAttendanceCellClass(employeeId, day) {
    const data = this.state.attendanceData[employeeId]?.[day];
    if (!data) return "o_attendance_cell";

    const config = this.statusConfig[data.status];
    return `o_attendance_cell ${config?.class || ""}`;
  }

  /**
   * Get tooltip for attendance cell
   */
  getAttendanceCellTooltip(employeeId, day) {
    const employee = this.state.employees.find((emp) => emp.id === employeeId);
    const data = this.state.attendanceData[employeeId]?.[day];

    if (!employee || !data) return "";

    const config = this.statusConfig[data.status];
    const statusLabel = config?.label || data.status;

    let tooltip = `${employee.name} - Day ${day}: ${statusLabel}`;

    if (data.hours > 0) {
      tooltip += `\nHours: ${data.hours}`;
    }

    if (data.checkIn) {
      const checkIn = new Date(data.checkIn).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      tooltip += `\nCheck In: ${checkIn}`;
    }

    if (data.checkOut) {
      const checkOut = new Date(data.checkOut).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      tooltip += `\nCheck Out: ${checkOut}`;
    }

    return tooltip;
  }

  /**
   * Get status icon class
   */
  getStatusIcon(employeeId, day) {
    const data = this.state.attendanceData[employeeId]?.[day];
    if (!data) return "";

    const config = this.statusConfig[data.status];
    return `fa ${config?.icon || "fa-question"}`;
  }

  /**
   * Get worked hours display
   */
  getWorkedHours(employeeId, day) {
    const data = this.state.attendanceData[employeeId]?.[day];
    if (!data || data.hours <= 0) return "";

    return `${data.hours}h`;
  }

  /**
   * Get employee avatar URL
   */
  getEmployeeAvatar(employeeId) {
    return `/web/image/hr.employee/${employeeId}/avatar_128`;
  }

  /**
   * Get CSS class for day header
   */
  getDayHeaderClass(day) {
    const date = new Date(
      this.state.currentYear,
      this.state.currentMonth - 1,
      day
    );
    let classes = "o_day_header_cell";

    // Check if weekend
    if (date.getDay() === 0 || date.getDay() === 6) {
      classes += " weekend";
    }

    // Check if today
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
      classes += " today";
    }

    return classes;
  }

  /**
   * Get tooltip for day header
   */
  getDayTooltip(day) {
    const date = new Date(
      this.state.currentYear,
      this.state.currentMonth - 1,
      day
    );
    const dayName = date.toLocaleDateString("en", { weekday: "long" });
    const fullDate = date.toLocaleDateString("en", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    return `${dayName}, ${fullDate}`;
  }

  /**
   * Get weekday name for day
   */
  getWeekdayName(day) {
    const date = new Date(
      this.state.currentYear,
      this.state.currentMonth - 1,
      day
    );
    return date.toLocaleDateString("en", { weekday: "short" });
  }

  /**
   * Show context menu
   */
  showContextMenu(x, y, employee, day, currentData) {
    this.hideContextMenu(); // Hide any existing menu

    const date = new Date(
      this.state.currentYear,
      this.state.currentMonth - 1,
      day
    );
    const dayName = date.toLocaleDateString("en", { weekday: "long" });
    const dateStr = date.toLocaleDateString("en", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });

    // Create context menu component
    const contextMenuProps = {
      x: x,
      y: y,
      employeeId: employee.id,
      employeeName: employee.name,
      day: day,
      dayName: dayName,
      date: dateStr,
      currentStatus: currentData.status,
      onStatusChange: this.onContextMenuStatusChange.bind(this),
      onViewDetails: this.onViewEmployeeDetails.bind(this),
      onEditHours: this.onEditHours.bind(this),
      onClose: this.hideContextMenu.bind(this),
    };

    this.contextMenu = {
      visible: true,
      props: contextMenuProps,
    };

    // Force re-render to show context menu
    this.render();
  }

  /**
   * Hide context menu
   */
  hideContextMenu() {
    if (this.contextMenu.visible) {
      this.contextMenu.visible = false;
      this.render();
    }
  }

  /**
   * Handle context menu status change
   */
  async onContextMenuStatusChange(employeeId, day, newStatus) {
    this.hideContextMenu();
    await this.updateAttendanceStatus(employeeId, day, newStatus);
  }

  /**
   * View employee details
   */
  async onViewEmployeeDetails(employeeId, day) {
    this.hideContextMenu();

    try {
      const dateStr = `${this.state.currentYear}-${String(
        this.state.currentMonth
      ).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

      const details = await this.orm.call(
        "hr.employee.attendance.grid",
        "get_employee_details",
        [],
        {
          employee_id: employeeId,
          date: dateStr,
        }
      );

      // Show details in dialog
      this.dialog.add(EmployeeDetailsDialog, {
        title: _t("Employee Details"),
        employee: details.employee,
        date: details.date,
        attendanceRecords: details.attendance_records,
      });
    } catch (error) {
      console.error("Error loading employee details:", error);
      this.notification.add(_t("Error loading employee details"), {
        type: "danger",
      });
    }
  }

  /**
   * Edit working hours
   */
  async onEditHours(employeeId, day) {
    this.hideContextMenu();

    const employee = this.state.employees.find((emp) => emp.id === employeeId);
    const currentData = this.state.attendanceData[employeeId]?.[day];
    const dateStr = `${this.state.currentYear}-${String(
      this.state.currentMonth
    ).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

    // Show edit hours dialog
    this.dialog.add(EditHoursDialog, {
      title: _t("Edit Working Hours"),
      employeeName: employee.name,
      date: dateStr,
      currentData: currentData,
      onSave: this.onSaveHours.bind(this),
    });
  }

  /**
   * Save edited hours
   */
  async onSaveHours(employeeId, day, hoursData) {
    try {
      const dateStr = `${this.state.currentYear}-${String(
        this.state.currentMonth
      ).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

      await this.orm.call(
        "hr.employee.attendance.grid",
        "update_working_hours",
        [],
        {
          employee_id: employeeId,
          date: dateStr,
          check_in: hoursData.checkIn,
          check_out: hoursData.checkOut,
          total_hours: hoursData.totalHours,
        }
      );

      // Update local state
      if (!this.state.attendanceData[employeeId]) {
        this.state.attendanceData[employeeId] = {};
      }

      this.state.attendanceData[employeeId][day] = {
        ...this.state.attendanceData[employeeId][day],
        hours: hoursData.totalHours,
        checkIn: hoursData.checkIn,
        checkOut: hoursData.checkOut,
      };

      this.notification.add(_t("Working hours updated successfully"), {
        type: "success",
      });
    } catch (error) {
      console.error("Error updating hours:", error);
      this.notification.add(_t("Error updating working hours"), {
        type: "danger",
      });
    }
  }

  /**
   * Handle keyboard shortcuts
   */
  handleKeydown(event) {
    switch (event.key) {
      case "Escape":
        this.hideContextMenu();
        break;
      case "ArrowLeft":
        if (event.ctrlKey) {
          event.preventDefault();
          this.onPreviousMonth();
        }
        break;
      case "ArrowRight":
        if (event.ctrlKey) {
          event.preventDefault();
          this.onNextMonth();
        }
        break;
      case "Home":
        if (event.ctrlKey) {
          event.preventDefault();
          this.onToday();
        }
        break;
    }
  }

  /**
   * Export attendance data
   */
  async exportData(format = "xlsx") {
    try {
      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "export_attendance_data",
        [],
        {
          year: this.state.currentYear,
          month: this.state.currentMonth,
          format: format,
        }
      );

      if (result.success) {
        // Create download link
        const link = document.createElement("a");
        link.href = `data:${result.mimetype};base64,${result.file_content}`;
        link.download = result.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        this.notification.add(_t("Data exported successfully"), {
          type: "success",
        });
      } else {
        throw new Error(result.message || "Export failed");
      }
    } catch (error) {
      console.error("Error exporting data:", error);
      this.notification.add(_t("Error exporting data"), { type: "danger" });
    }
  }

  /**
   * Bulk update attendance
   */
  async bulkUpdateAttendance(updates) {
    try {
      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "bulk_update_attendance",
        [updates]
      );

      if (result.success_count > 0) {
        this.notification.add(
          _t(`${result.success_count} records updated successfully`),
          { type: "success" }
        );

        // Reload data to reflect changes
        await this.loadData();
      }

      if (result.error_count > 0) {
        this.notification.add(
          _t(`${result.error_count} records failed to update`),
          { type: "warning" }
        );
      }
    } catch (error) {
      console.error("Error in bulk update:", error);
      this.notification.add(_t("Error in bulk update"), { type: "danger" });
    }
  }

  /**
   * Get attendance summary for employee
   */
  async getEmployeeSummary(employeeId) {
    try {
      const summary = await this.orm.call(
        "hr.employee.attendance.grid",
        "get_attendance_summary",
        [],
        {
          employee_id: employeeId,
          year: this.state.currentYear,
          month: this.state.currentMonth,
        }
      );

      return summary;
    } catch (error) {
      console.error("Error getting employee summary:", error);
      return null;
    }
  }

  /**
   * Clean up event listeners when component is destroyed
   */
  willUnmount() {
    document.removeEventListener("click", this.hideContextMenu.bind(this));
    document.removeEventListener("keydown", this.handleKeydown.bind(this));
  }
}

/**
 * Employee Details Dialog Component
 */
class EmployeeDetailsDialog extends Component {
  static template = "attendance.EmployeeDetailsDialog";
  static components = { Dialog };

  setup() {
    this.state = useState({
      employee: this.props.employee,
      date: this.props.date,
      attendanceRecords: this.props.attendanceRecords,
    });
  }

  onClose() {
    this.props.close();
  }
}

/**
 * Edit Hours Dialog Component
 */
class EditHoursDialog extends Component {
  static template = "attendance.QuickEditHours";
  static components = { Dialog };

  setup() {
    const currentData = this.props.currentData || {};

    this.state = useState({
      checkIn: currentData.checkIn
        ? new Date(currentData.checkIn).toTimeString().slice(0, 5)
        : "09:00",
      checkOut: currentData.checkOut
        ? new Date(currentData.checkOut).toTimeString().slice(0, 5)
        : "17:00",
      totalHours: currentData.hours || 8.0,
    });
  }

  onClose() {
    this.props.close();
  }

  onSave() {
    const hoursData = {
      checkIn: this.state.checkIn,
      checkOut: this.state.checkOut,
      totalHours: this.state.totalHours,
    };

    this.props.onSave(this.props.employeeId, this.props.day, hoursData);
    this.props.close();
  }

  // Calculate total hours when check in/out times change
  onTimeChange() {
    if (this.state.checkIn && this.state.checkOut) {
      const checkIn = new Date(`2000-01-01T${this.state.checkIn}:00`);
      const checkOut = new Date(`2000-01-01T${this.state.checkOut}:00`);

      if (checkOut > checkIn) {
        const diffMs = checkOut - checkIn;
        const diffHours = diffMs / (1000 * 60 * 60);
        this.state.totalHours = Math.round(diffHours * 2) / 2; // Round to nearest 0.5
      }
    }
  }
}

/**
 * Context Menu Component
 */
class AttendanceContextMenu extends Component {
  static template = "attendance.ContextMenu";

  setup() {
    this.state = useState({
      visible: this.props.visible || false,
      x: this.props.x || 0,
      y: this.props.y || 0,
    });
  }

  getContextMenuStyle() {
    return `left: ${this.state.x}px; top: ${this.state.y}px;`;
  }

  onStatusChange(status) {
    this.props.onStatusChange(this.props.employeeId, this.props.day, status);
  }

  onViewDetails() {
    this.props.onViewDetails(this.props.employeeId, this.props.day);
  }

  onEditHours() {
    this.props.onEditHours(this.props.employeeId, this.props.day);
  }
}

AttendanceGridComponent.template = "hr_attendance_grid_template";
actionRegistry.add("attendance_grid_component", AttendanceGridComponent);
