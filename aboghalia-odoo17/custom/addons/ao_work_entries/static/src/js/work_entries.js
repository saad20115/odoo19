/** @odoo-module */
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";


/**
 * Simplified Attendance Grid Component for Odoo 17
 * Most logic moved to Python backend to prevent infinite loading
 */
/**
 * Simplified Day Details Modal Component
 */
class DayDetailsModal extends Component {
  static template = "hr_attendance_grid.DayDetailsModal";
  static components = { Dialog };

  setup() {
    this.orm = useService("orm");
    this.notification = useService("notification");

    this.state = useState({
      dayDetails: {
        status: this.props.currentData?.status || "absent",
        checkInTime: this.formatTimeForInput(this.props.currentData?.check_in),
        checkOutTime: this.formatTimeForInput(
          this.props.currentData?.check_out
        ),
        totalHours: this.props.currentData?.hours || 0,
        breakTime: 0,
        notes: this.props.currentData?.notes || "",
      },
      newRecord: {
        checkInTime: "",
        checkOutTime: "",
        notes: "",
        departmentId: "",
      },
      attendanceRecords: [],
      departments: [],
      isLoading: false,
    });

    onWillStart(async () => {
      await this.loadDayDetails();
      await this.loadDepartments();
    });
  }
  async loadDepartments() {
    try {
      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "_get_departments",
        []
      );
      this.state.departments = result || [];
    } catch (error) {
      console.error("Error loading departments:", error);
      this.state.departments = [];
    }
  }
  /**
   * Load detailed attendance records from backend
   */
  async loadDayDetails() {
    try {
      this.state.isLoading = true;

      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "get_day_details",
        [],
        {
          employee_id: this.props.employeeId,
          date: this.props.date,
        }
      );

      if (result.success) {
        this.state.attendanceRecords = result.attendance_records || [];
        this.calculateTotalHours();
      }
    } catch (error) {
      console.error("Error loading day details:", error);
    } finally {
      this.state.isLoading = false;
    }
  }

  /**
   * Navigate to edit request form
   */
  navigateToEditRequest(requestId) {
    try {
      // Close the modal first
      this.props.close();

      // Navigate directly using window location
      const baseUrl = window.location.origin;
      const url = `${baseUrl}/web#id=${requestId}&model=hr.attendance.edit.request&view_type=form`;

      // Navigate to the URL
      window.location.href = url;
    } catch (error) {
      console.error("Error navigating to edit request:", error);
      // Fallback: show the ID to user
      alert(
        `Please navigate to HR > Attendance > Edit Requests and search for ID: ${requestId}`
      );
    }
  }

  /**
   * Format time for input field
   */
  formatTimeForInput(timeStr) {
    if (!timeStr) return "";
    try {
      const date = new Date(timeStr);
      // Convert to Riyadh timezone for input
      const riyadhTime = new Date(
        date.toLocaleString("en-US", { timeZone: "Asia/Riyadh" })
      );
      return riyadhTime.toTimeString().slice(0, 5); // HH:MM format
    } catch (e) {
      return "";
    }
  }

  /**
   * Format time for display
   */
  formatTime(timeStr) {
    if (!timeStr) return "N/A";
    try {
      const date = new Date(timeStr);
      // Times are already converted to Riyadh timezone by backend
      return date.toLocaleTimeString("en-SA", {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Riyadh",
      });
    } catch (e) {
      return timeStr;
    }
  }

  /**
   * Format date for display
   */
  formatDate(timeStr) {
    if (!timeStr) return "";
    try {
      const date = new Date(timeStr);
      return date.toLocaleDateString();
    } catch (e) {
      return "";
    }
  }

  /**
   * Get employee avatar URL
   */
  getEmployeeAvatar(employeeId) {
    return `/web/image/hr.employee/${employeeId}/avatar_128`;
  }

  /**
   * Change attendance status
   */
  changeStatus(newStatus) {
    this.state.dayDetails.status = newStatus;
    if (newStatus !== "present") {
      this.state.dayDetails.checkInTime = "";
      this.state.dayDetails.checkOutTime = "";
      this.state.dayDetails.totalHours = 0;
      this.state.dayDetails.breakTime = 0;
    }
  }

  /**
   * Calculate total hours based on check in/out times
   */
  calculateTotalHours() {
    if (
      this.state.dayDetails.checkInTime &&
      this.state.dayDetails.checkOutTime
    ) {
      const checkIn = new Date(
        `2000-01-01T${this.state.dayDetails.checkInTime}:00`
      );
      const checkOut = new Date(
        `2000-01-01T${this.state.dayDetails.checkOutTime}:00`
      );

      if (checkOut > checkIn) {
        const diffMs = checkOut - checkIn;
        const diffHours = diffMs / (1000 * 60 * 60);
        const breakTime = parseFloat(this.state.dayDetails.breakTime) || 0;
        this.state.dayDetails.totalHours =
          Math.round((diffHours - breakTime) * 2) / 2;
      }
    }
  }

  /**
   * Handle time change
   */
  onTimeChange() {
    this.calculateTotalHours();
  }

  /**
   * Get status badge class
   */
  getStatusBadgeClass() {
    const statusClasses = {
      present: "bg-success",
      absent: "bg-danger",
      holiday: "bg-warning",
      leave: "bg-info",
    };
    return `badge ${
      statusClasses[this.state.dayDetails.status] || "bg-secondary"
    }`;
  }

  /**
   * Get status label
   */
  getStatusLabel() {
    const statusLabels = {
      present: "Present",
      absent: "Absent",
      holiday: "Holiday",
      leave: "Leave",
    };
    return statusLabels[this.state.dayDetails.status] || "Unknown";
  }

  /**
   * Get record status class
   */
  getRecordStatusClass(record) {
    if (record.check_out) {
      return "bg-success";
    } else if (record.check_in) {
      return "bg-warning";
    }
    return "bg-secondary";
  }

  /**
   * Get record status label
   */
  getRecordStatusLabel(record) {
    if (record.check_out) {
      return "Complete";
    } else if (record.check_in) {
      return "In Progress";
    }
    return "Unknown";
  }

  /**
   * Edit attendance record
   */
  editRecord(record) {
    // Fill form with record data
    this.state.dayDetails.checkInTime = this.formatTimeForInput(
      record.check_in
    );
    this.state.dayDetails.checkOutTime = this.formatTimeForInput(
      record.check_out
    );
    this.state.dayDetails.totalHours = record.worked_hours || 0;
    this.state.dayDetails.status = "present";
  }

  /**
   * Delete attendance record
   */
  async deleteRecord(recordId) {
    if (confirm("Are you sure you want to delete this attendance record?")) {
      try {
        await this.orm.unlink("hr.attendance", [recordId]);

        // Reload day details
        await this.loadDayDetails();

        this.notification.add("Attendance record deleted", {
          type: "success",
        });
      } catch (error) {
        console.error("Error deleting record:", error);
        this.notification.add("Error deleting record", { type: "danger" });
      }
    }
  }

  /**
   * Get current location using browser geolocation API
   */
  async getCurrentLocation() {
    return new Promise((resolve) => {
      if (!navigator.geolocation) {
        console.warn("Geolocation is not supported by this browser");
        resolve({
          latitude: null,
          longitude: null,
          error: "Geolocation not supported",
        });
        return;
      }

      const options = {
        enableHighAccuracy: true,
        timeout: 10000, // 10 seconds timeout
        maximumAge: 300000, // 5 minutes cache
      };

      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: new Date().toISOString(),
          });
        },
        (error) => {
          console.warn("Geolocation error:", error.message);
          let errorMessage = "Location access denied";

          switch (error.code) {
            case error.PERMISSION_DENIED:
              errorMessage = "Location access denied by user";
              break;
            case error.POSITION_UNAVAILABLE:
              errorMessage = "Location information unavailable";
              break;
            case error.TIMEOUT:
              errorMessage = "Location request timed out";
              break;
          }

          resolve({
            latitude: null,
            longitude: null,
            error: errorMessage,
          });
        },
        options
      );
    });
  }
  /**
   * Create new attendance record
   */

  async createNewRecord() {
    try {
      // Prevent duplicate submissions
      if (this.state.isCreating) {
        return;
      }

      if (!this.state.newRecord.checkInTime) {
        this.notification.add("Check-in time is required to create a record", {
          type: "warning",
        });
        return;
      }

      // Set creating flag to prevent duplicate calls
      this.state.isCreating = true;

      // Get current location for check-in
      const location = await this.getCurrentLocation();

      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "create_attendance_record",
        [
          "",
          parseInt(this.props.employeeId),
          this.props.date,
          this.state.newRecord.checkInTime,
          this.state.newRecord.checkOutTime || "",
          this.state.newRecord.notes || "",
          location.latitude || null, // in_latitude
          location.longitude || null, // in_longitude
          location.latitude || null, // out_latitude (same as in if both times provided)
          location.longitude || null, // out_longitude (same as in if both times provided)
          this.state.newRecord.departmentId || null,
        ]
      );

      if (result.success) {
        // Reload day details to show the new record
        await this.loadDayDetails();

        // Clear the new record form
        this.state.newRecord.checkInTime = "";
        this.state.newRecord.checkOutTime = "";
        this.state.newRecord.notes = "";
        this.state.newRecord.departmentId = "";

        this.notification.add(
          "New attendance record created successfully with location",
          {
            type: "success",
          }
        );
      } else {
        throw new Error(result.message || "Creation failed");
      }
    } catch (error) {
      console.error("Error creating attendance record:", error);
      this.notification.add("Error creating record: " + error.message, {
        type: "danger",
      });
    } finally {
      // Reset creating flag to allow future creations
      this.state.isCreating = false;
    }
  }

  /**
   * Save changes
   */
  onSave() {
    const updatedData = {
      status: this.state.dayDetails.status,
      checkInTime: this.state.dayDetails.checkInTime,
      checkOutTime: this.state.dayDetails.checkOutTime,
      totalHours: this.state.dayDetails.totalHours,
      breakTime: this.state.dayDetails.breakTime,
      notes: this.state.dayDetails.notes,
    };

    this.props.onSave(this.props.employeeId, this.props.day, updatedData);
    this.props.close();
  }

  /**
   * Close modal
   */
  onClose() {
    this.props.close();
  }
}

/**
 * Employee Details Dialog Component
 */
class EmployeeDetailsDialog extends Component {
  static template = "hr_attendance_grid.EmployeeDetailsDialog";
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

  /**
   * Format time for display
   */
  formatTime(timeStr) {
    if (!timeStr) return "N/A";
    try {
      const date = new Date(timeStr);
      // Times are already converted to Riyadh timezone by backend
      return date.toLocaleTimeString("en-SA", {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Riyadh",
      });
    } catch (e) {
      return timeStr;
    }
  }
}

/**
 * Edit Hours Dialog Component
 */
class EditHoursDialog extends Component {
  static template = "hr_attendance_grid.QuickEditHours";
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
 * Summary Field Edit Dialog Component
 */
class SummaryFieldEditDialog extends Component {
  static template = "hr_attendance_grid.SummaryFieldEditDialog";
  static components = { Dialog };

  setup() {
    this.state = useState({
      value: this.props.currentValue || 0,
      isValid: true,
      errorMessage: "",
    });
  }

  validateValue() {
    const value = parseFloat(this.state.value);

    if (isNaN(value) || value < 0) {
      this.state.isValid = false;
      this.state.errorMessage = "Value must be a positive number";
      return false;
    }

    this.state.isValid = true;
    this.state.errorMessage = "";
    return true;
  }

  onInputChange(event) {
    this.state.value = event.target.value;
    this.validateValue();
  }

  onSave() {
    if (this.validateValue()) {
      const isIntegerField = this.props.fieldName === "total_absence_days";
      const finalValue = isIntegerField
          ? Math.round(parseFloat(this.state.value))
          : parseFloat(this.state.value);

      this.props.onSave(finalValue);
      this.props.close();
    }
  }

  onCancel() {
    this.props.onCancel();
    this.props.close();
  }

  getInputType() {
    return "number";
  }

  getInputStep() {
    return this.props.fieldName === "total_absence_days" ? "1" : "0.1";
  }
}



class AttendanceGridComponent extends Component {
  static template = "hr_attendance_grid_template";
  static components = { Dialog };

  get attendanceReportLabel() {
    return _t("Attendance Report (Excel)");
  }

  get editAbsenceDaysLabel() {
    return _t("Edit Employees' Absence Days");
  }

  get editAbsenceDaysTitle() {
    return _t("Bulk edit absence days for employees");
  }

  get editLateHoursLabel() {
    return _t("Edit Employees' Late Hours");
  }

  get editLateHoursTitle() {
    return _t("Bulk edit late hours for employees");
  }

  get archiveEmployeeTitle() {
    return _t("Archive employee");
  }

  get remainingLeaveDaysLabel() {
    return _t("Remaining Leave Days");
  }

  setup() {
    // Odoo services
    this.orm = useService("orm");
    this.notification = useService("notification");
    this.dialog = useService("dialog");
    this.action = useService("action");

    // Simplified state management
    this.state = useState({
      // Data
      employees: [],
      attendanceData: {},
      monthlySummaries: {},
      departmentSummaries: {},
      departments: [],
      daysInMonth: [],

      // Current view
      currentYear: new Date().getFullYear(),
      currentMonth: new Date().getMonth() + 1,
      currentMonthName: "",

      // UI state
      isLoading: false,
      activeTab: "grid",

      // Filters - using separate reactive objects
      selectedDepartmentId: "",
      searchEmployeeName: "",
      selectedStatusFilter: "",

      // Pagination (handled by backend)
      pagination: {
        currentPage: 1,
        pageSize: "50",
        totalPages: 1,
        totalCount: 0,
        startIndex: 1,
        endIndex: 0,
      },

      // Statistics
      stats: {},

      // Error handling
      error: null,
    });

    // Reactive filters object for backend
    this.filters = {
      get departmentId() {
        return this.state.selectedDepartmentId;
      },
      get employeeName() {
        return this.state.searchEmployeeName;
      },
      get statusFilter() {
        return this.state.selectedStatusFilter;
      },
    };

    // Load data on component start
    onWillStart(async () => {
      await this.loadData();
    });

    onMounted(() => {
      this.setupEventListeners();
    });
  }

  /**
   * Main data loading method - calls Python backend
   */
  async loadData() {
    if (this.state.isLoading) return;

    try {
      this.state.isLoading = true;
      this.state.error = null;

      // Update month name
      const monthNames = [
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
      this.state.currentMonthName = monthNames[this.state.currentMonth - 1];

      // Prepare filters object
      const filters = {
        departmentId: this.state.selectedDepartmentId,
        employeeName: this.state.searchEmployeeName,
        statusFilter: this.state.selectedStatusFilter,
      };

      // Single call to Python backend with all parameters
      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "get_attendance_data",
        [],
        {
          year: this.state.currentYear,
          month: this.state.currentMonth,
          filters: filters,
          pagination: {
            page: this.state.pagination.currentPage,
            page_size: this.state.pagination.pageSize,
          },
        }
      );

      if (result.success) {
        // Update state with all data from backend
        this.state.employees = result.employees || [];
        this.state.attendanceData = result.attendance_data || {};
        this.state.daysInMonth = result.days_in_month || [];
        this.state.stats = result.statistics || {};
        this.state.departments = result.departments || [];
        this.state.monthlySummaries = result.monthly_summaries || {};
        this.state.departmentSummaries = result.department_summaries || {};
        // Update pagination with backend data
        if (result.pagination) {
          this.state.pagination = {
            currentPage: result.pagination.current_page || 1,
            pageSize: result.pagination.page_size || "50",
            totalPages: result.pagination.total_pages || 1,
            totalCount: result.pagination.total_count || 0,
            startIndex: result.pagination.start_index || 0,
            endIndex: result.pagination.end_index || 0,
          };
        }

        console.log("Monthly summaries loaded:", this.state.monthlySummaries);
      } else {
        throw new Error(result.error || "Failed to load attendance data");
      }
    } catch (error) {
      console.error("Error loading attendance data:", error);
      this.state.error = error.message || "Error loading attendance data";
      this.notification.add(
        _t("Error loading attendance data: ") + this.state.error,
        { type: "danger" }
      );

      // Set fallback empty data
      this.state.employees = [];
      this.state.attendanceData = {};
      this.state.daysInMonth = [];
      this.state.stats = {};
      this.state.monthlySummaries = {};
      this.state.departmentSummaries = {};
    } finally {
      this.state.isLoading = false;
    }
  }

  /**
   * Get additional CSS classes for special attendance flags
   */
  getAttendanceSpecialClasses(employeeId, day) {
    const data = this.state.attendanceData[employeeId]?.[day];
    if (!data) return "";

    let classes = [];
    if (data.auto_checkedout) {
      classes.push("o_auto_checkedout");
    }
    if (data.holiday_warning) {
      classes.push("o_holiday_warning");
    }

    return classes.join(" ");
  }

  /**
   * Create payslips for employees in current page view
   */
  async createPayslips() {
    try {
      const paginationInfo = this.getPaginationInfo();

      // Show confirmation dialog with current page info
      const confirmed = confirm(
        `Create payslips for ${this.state.currentMonthName} ${this.state.currentYear}?\n\n` +
          `This will create payslips for ${this.state.employees.length} employees currently displayed on page ${this.state.pagination.currentPage}.\n` +
          `(Showing ${paginationInfo.start}-${paginationInfo.end} of ${paginationInfo.total} total employees)\n\n` +
          `Current filters will be applied.`
      );

      if (!confirmed) return;

      this.state.isLoading = true;

      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "create_payslips_from_attendance",
        [],
        {
          year: this.state.currentYear,
          month: this.state.currentMonth,
          filters: {
            departmentId: this.state.selectedDepartmentId,
            employeeName: this.state.searchEmployeeName,
            statusFilter: this.state.selectedStatusFilter,
          },
          pagination: {
            page: this.state.pagination.currentPage,
            page_size: this.state.pagination.pageSize,
          },
        }
      );

      if (result.success) {
        // Show success message with current page details
        let message = `${result.message}\n\n`;
        message += `Processed: ${result.processed_employees} employees on page ${result.current_page}\n`;
        message += `Total employees (all pages): ${result.total_employees}\n\n`;

        if (result.created_payslips && result.created_payslips.length > 0) {
          message += "Created payslips:\n";
          result.created_payslips.forEach((payslip, index) => {
            if (index < 8) {
              // Show first 8 only
              message += `• ${payslip.employee_name} - ${payslip.department_name} (${payslip.absence_days} abs, ${payslip.late_hours}h late)\n`;
            }
          });

          if (result.created_payslips.length > 8) {
            message += `... and ${
              result.created_payslips.length - 8
            } more payslips\n`;
          }
        }

        if (result.errors && result.errors.length > 0) {
          message += `\nErrors: ${result.errors.length}\n`;
          result.errors.slice(0, 2).forEach((error) => {
            message += `• ${error}\n`;
          });
        }

        alert(message);

        this.notification.add(
          _t(
            `Created ${result.created_count} payslips for page ${result.current_page} (${result.processed_employees} employees)`
          ),
          { type: "success" }
        );
      } else {
        throw new Error(result.message || "Failed to create payslips");
      }
    } catch (error) {
      console.error("Error creating payslips:", error);
      this.notification.add(_t("Error creating payslips: ") + error.message, {
        type: "danger",
      });
    } finally {
      this.state.isLoading = false;
    }
  }

  /**
   * Get special indicator icons for attendance flags
   */
  getSpecialIndicators(employeeId, day) {
    const data = this.state.attendanceData[employeeId]?.[day];
    if (!data) return [];

    let indicators = [];
    if (data.auto_checkedout) {
      indicators.push({
        icon: "fa fa-robot",
        title: "Auto",
        class: "o_indicator_auto",
      });
    }
    if (data.holiday_warning) {
      indicators.push({
        icon: "fa fa-exclamation-triangle",
        title: "Holiday",
        class: "o_indicator_warning",
      });
    }
    if (data.has_edit_request) {
      indicators.push({
        icon: "fa fa-edit",
        title: "Edit Request",
        class: "o_indicator_edit_request",
      });
    }

    return indicators;
  }
  async loadDepartmentSummaries() {
    try {
      const departmentSummaries = {};

      // Load department summary for each employee
      for (const employee of this.state.employees) {
        const result = await this.orm.call(
          "hr.employee.attendance.grid",
          "get_employee_department_summary",
          [],
          {
            employee_id: employee.id,
            year: this.state.currentYear,
            month: this.state.currentMonth,
          }
        );

        if (result.success) {
          departmentSummaries[employee.id] = result.department_summary;
        }
      }

      this.state.departmentSummaries = departmentSummaries;
    } catch (error) {
      console.error("Error loading department summaries:", error);
      this.state.departmentSummaries = {};
    }
  }
  /**
   * Setup event listeners
   */
  setupEventListeners() {
    // Keyboard shortcuts
    document.addEventListener("keydown", this.handleKeydown.bind(this));
  }

  // === TAB MANAGEMENT ===

  setActiveTab(tabName) {
    this.state.activeTab = tabName;
  }

  // === NAVIGATION ===

  async onPreviousMonth() {
    if (this.state.isLoading) return;

    if (this.state.currentMonth === 1) {
      this.state.currentMonth = 12;
      this.state.currentYear--;
    } else {
      this.state.currentMonth--;
    }
    this.state.pagination.currentPage = 1; // Reset pagination
    await this.loadData();
  }

  async onNextMonth() {
    if (this.state.isLoading) return;

    if (this.state.currentMonth === 12) {
      this.state.currentMonth = 1;
      this.state.currentYear++;
    } else {
      this.state.currentMonth++;
    }
    this.state.pagination.currentPage = 1; // Reset pagination
    await this.loadData();
  }

  async onToday() {
    if (this.state.isLoading) return;

    const now = new Date();
    this.state.currentYear = now.getFullYear();
    this.state.currentMonth = now.getMonth() + 1;
    this.state.pagination.currentPage = 1; // Reset pagination
    await this.loadData();
  }

  // === FILTERING ===

  onDepartmentFilterChange(event) {
    if (this.state.isLoading) return;

    const selectedValue = event.target.value;
    console.log("Department filter changed to:", selectedValue);

    // Update the state
    this.state.selectedDepartmentId = selectedValue;
    this.state.pagination.currentPage = 1; // Reset to first page

    // Reload data after a short delay to ensure state is updated
    setTimeout(() => this.loadData(), 10);
  }

  onEmployeeSearchChange(event) {
    if (this.state.isLoading) return;

    const searchValue = event.target.value;
    console.log("Employee search changed to:", searchValue);

    // Update state immediately
    this.state.searchEmployeeName = searchValue;

    // Add debounce to avoid too many API calls while typing
    clearTimeout(this.searchTimeout);
    this.searchTimeout = setTimeout(() => {
      this.state.pagination.currentPage = 1; // Reset to first page
      this.loadData();
    }, 500); // 500ms delay
  }

  onStatusFilterChange(status) {
    if (this.state.isLoading) return;

    console.log("Status filter changed to:", status);
    this.state.selectedStatusFilter = status;
    this.state.pagination.currentPage = 1; // Reset to first page

    // Reload data after a short delay
    setTimeout(() => this.loadData(), 10);
  }

  // Legacy method for compatibility
  async setStatusFilter(status) {
    this.onStatusFilterChange(status);
  }

  /**
   * Clear all filters and reload data
   */
  async clearFilters() {
    if (this.state.isLoading) return;

    console.log("Clearing all filters");
    this.state.selectedDepartmentId = "";
    this.state.searchEmployeeName = "";
    this.state.selectedStatusFilter = "";
    this.state.pagination.currentPage = 1;

    // Reload data after clearing
    setTimeout(() => this.loadData(), 10);
  }

  /**
   * Debug method to check current filter state
   */
  debugFilters() {
    const paginationInfo = this.getPaginationInfo();
    console.log("=== DEBUG INFO ===");
    console.log("Current filter state:", {
      selectedDepartmentId: this.state.selectedDepartmentId,
      searchEmployeeName: this.state.searchEmployeeName,
      selectedStatusFilter: this.state.selectedStatusFilter,
    });
    console.log("Pagination state:", this.state.pagination);
    console.log("Pagination info:", paginationInfo);
    console.log("Employees:", {
      displayed: this.state.employees.length,
      total: this.state.pagination.totalCount,
    });
    console.log("Departments:", this.state.departments.length);
    console.log("==================");

    // Test a simple filter call
    this.testFilterCall();
  }

  /**
   * Test method to verify backend filtering works
   */
  async testFilterCall() {
    try {
      console.log("Testing direct backend call...");
      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "get_attendance_data",
        [],
        {
          year: this.state.currentYear,
          month: this.state.currentMonth,
          filters: {
            departmentId: "", // Test with no filters
            employeeName: "",
            statusFilter: "",
          },
          pagination: { page: 1, page_size: 5 }, // Test with small page size
        }
      );
      console.log("Test result:", {
        success: result.success,
        employees_count: result.employees?.length,
        pagination: result.pagination,
        total_departments: result.departments?.length,
      });
    } catch (error) {
      console.error("Test failed:", error);
    }
  }

  // === PAGINATION ===

  async goToPage(pageNumber) {
    if (this.state.isLoading) return;

    if (
      typeof pageNumber === "number" &&
      pageNumber >= 1 &&
      pageNumber <= this.state.pagination.totalPages
    ) {
      console.log(`Going to page ${pageNumber}`);
      this.state.pagination.currentPage = pageNumber;
      await this.loadData();
    }
  }

  async onPreviousPage() {
    if (this.canGoPrevious()) {
      await this.goToPage(this.state.pagination.currentPage - 1);
    }
  }

  async onNextPage() {
    if (this.canGoNext()) {
      await this.goToPage(this.state.pagination.currentPage + 1);
    }
  }

  async onPageSizeChange(event) {
    if (this.state.isLoading) return;

    const newPageSize = event.target ? event.target.value : event;
    console.log(`Page size changed to: ${newPageSize}`);

    this.state.pagination.pageSize = newPageSize;
    this.state.pagination.currentPage = 1; // Reset to first page
    await this.loadData();
  }

  // === ATTENDANCE MANAGEMENT ===

  /**
   * Handle attendance cell click - simplified to just open details modal
   */
  async onAttendanceCellClick(event, employeeId, day) {
    event.preventDefault();
    event.stopPropagation();

    const employee = this.state.employees.find((emp) => emp.id === employeeId);
    const currentData = this.state.attendanceData[employeeId]?.[day];

    if (!employee) return;

    // Create date string
    const dateStr = `${this.state.currentYear}-${String(
      this.state.currentMonth
    ).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
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

    // Show day details modal
    this.dialog.add(DayDetailsModal, {
      title: _t("Day Details"),
      employeeId: employeeId,
      employeeName: employee.name,
      employeeDepartment: employee.department_name || "No Department",
      day: day,
      dayName: dayName,
      fullDate: fullDate,
      date: dateStr,
      currentData: currentData || {},
      onSave: this.onDayDetailsUpdate.bind(this),
      navigateToEditRequest: this.handleEditRequestNavigation.bind(this),
    });
  }

  /**
   * Handle day details update - calls Python backend
   */
  async onDayDetailsUpdate(employeeId, day, updatedData) {
    try {
      const dateStr = `${this.state.currentYear}-${String(
        this.state.currentMonth
      ).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "update_day_details",
        [],
        {
          employee_id: employeeId,
          date: dateStr,
          status: updatedData.status,
          check_in: updatedData.checkInTime,
          check_out: updatedData.checkOutTime,
          break_time: updatedData.breakTime,
          notes: updatedData.notes,
        }
      );

      if (result.success) {
        // Update local state with new data
        if (!this.state.attendanceData[employeeId]) {
          this.state.attendanceData[employeeId] = {};
        }

        this.state.attendanceData[employeeId][day] = {
          status: updatedData.status,
          hours: result.total_hours || 0,
          check_in: updatedData.checkInTime,
          check_out: updatedData.checkOutTime,
          notes: updatedData.notes,
        };

        const employee = this.state.employees.find(
          (emp) => emp.id === employeeId
        );
        this.notification.add(
          _t(`Updated attendance for ${employee.name} on day ${day}`),
          { type: "success" }
        );

        // Reload data to get updated statistics
        await this.loadData();
      } else {
        throw new Error(result.message || "Update failed");
      }
    } catch (error) {
      console.error("Error updating day details:", error);
      this.notification.add(
        _t("Error updating day details: ") + error.message,
        {
          type: "danger",
        }
      );
    }
  }

  // === EXPORT FUNCTIONALITY ===

  openAttendanceReportWizard() {
    const year = this.state.currentYear;
    const month = this.state.currentMonth;
    const lastDay = new Date(year, month, 0).getDate();
    const monthStr = String(month).padStart(2, "0");
    this.action.doAction("ao_work_entries.action_attendance_report_wizard", {
      additionalContext: {
        default_date_from: `${year}-${monthStr}-01`,
        default_date_to: `${year}-${monthStr}-${String(lastDay).padStart(2, "0")}`,
      },
    });
  }

  openEditAbsenceDaysWizard() {
    this.action.doAction("ao_work_entries.action_edit_absence_days_wizard", {
      additionalContext: {
        default_year: this.state.currentYear,
        default_month: this.state.currentMonth,
      },
      onClose: async () => {
        await this.loadData();
      },
    });
  }

  openEditLateHoursWizard() {
    this.action.doAction("ao_work_entries.action_edit_late_hours_wizard", {
      additionalContext: {
        default_year: this.state.currentYear,
        default_month: this.state.currentMonth,
      },
      onClose: async () => {
        await this.loadData();
      },
    });
  }

  async archiveEmployee(employeeId, employeeName, ev) {
    if (ev) {
      ev.preventDefault();
      ev.stopPropagation();
    }

    const confirmed = confirm(
      _t("Archive employee %(name)s?\n\nThey will be removed from this dashboard and excluded from Calculate Metrics and Create Payslips.", { name: employeeName })
    );
    if (!confirmed) {
      return;
    }

    try {
      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "archive_employee_from_grid",
        [],
        { employee_id: employeeId }
      );

      if (result.success) {
        delete this.state.monthlySummaries[employeeId];
        delete this.state.departmentSummaries[employeeId];
        delete this.state.attendanceData[employeeId];
        this.state.employees = this.state.employees.filter(
          (employee) => employee.id !== employeeId
        );

        this.notification.add(result.message, { type: "success" });
      } else {
        throw new Error(result.message || _t("Failed to archive employee"));
      }
    } catch (error) {
      console.error("Error archiving employee:", error);
      this.notification.add(
        _t("Error archiving employee: ") + error.message,
        { type: "danger" }
      );
    }
  }

  async exportData(format = "xlsx") {
    try {
      this.state.isLoading = true;

      const result = await this.orm.call(
        "hr.employee.attendance.grid",
        "export_attendance_data",
        [],
        {
          year: this.state.currentYear,
          month: this.state.currentMonth,
          format: format,
          filters: this.state.filters,
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
      this.notification.add(_t("Error exporting data: ") + error.message, {
        type: "danger",
      });
    } finally {
      this.state.isLoading = false;
    }
  }

  // === UTILITY METHODS ===

  /**
   * Check if day is weekend
   */
  isWeekend(day) {
    const date = new Date(
      this.state.currentYear,
      this.state.currentMonth - 1,
      day
    );
    // Saudi Arabia weekend: Friday (5) and Saturday (6)
    return date.getDay() === 5;
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

    if (this.isWeekend(day)) {
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
   * Check if present-day check-in/out times trigger late/early warning styling.
   */
  hasAttendanceTimeWarning(data) {
    if (!data || data.status !== "present") return false;

    const toMinutes = (timeStr) => {
      if (!timeStr) return null;
      const date = new Date(timeStr);
      const h = Number(
        date.toLocaleString("en-GB", {
          hour: "2-digit",
          hour12: false,
          timeZone: "Asia/Riyadh",
        })
      );
      const m = Number(
        date.toLocaleString("en-GB", {
          minute: "2-digit",
          timeZone: "Asia/Riyadh",
        })
      );
      return h * 60 + m;
    };

    const checkIn = toMinutes(data.check_in);
    const checkOut = toMinutes(data.check_out);
    const lateIn = checkIn !== null && checkIn > 8 * 60 + 30;
    const earlyOut = checkOut !== null && checkOut < 16 * 60 + 30;
    return lateIn || earlyOut;
  }

  /**
   * Get CSS class for attendance cell
   */
  getAttendanceCellClass(employeeId, day) {
    const data = this.state.attendanceData[employeeId]?.[day];
    if (!data) return "o_attendance_cell";

    const statusClasses = {
      present: "o_status_present",
      absent: "o_status_absent",
      holiday: "o_status_holiday",
      leave: "o_status_leave",
      weekend: "o_status_weekend",
    };

    const statusClass = statusClasses[data.status] || "";

    // Add special indicator if employee checked in during leave/holiday
    const leaveIndicator = data.checked_in_during_leave ? "o_checked_in_during_leave" : "";
    const timeWarning = this.hasAttendanceTimeWarning(data)
      ? "o_attendance_time_warning"
      : "";

    return `o_attendance_cell ${statusClass} ${leaveIndicator} ${timeWarning}`.trim();
  }

  /**
   * Get tooltip for attendance cell
   */
  getAttendanceCellTooltip(employeeId, day) {
    const employee = this.state.employees.find((emp) => emp.id === employeeId);
    const data = this.state.attendanceData[employeeId]?.[day];

    if (!employee || !data) return "";

    const statusLabels = {
      present: "Present",
      absent: "Absent",
      holiday: "Holiday",
      leave: "Leave",
      weekend: "Weekend",
    };

    const statusLabel = statusLabels[data.status] || data.status;
    let tooltip = `${employee.name} - Day ${day}: ${statusLabel}`;

    if (data.hours > 0) {
      tooltip += `\nHours: ${data.hours}`;
    }

    if (data.check_in) {
      tooltip += `\nCheck In: ${this.formatTime(data.check_in)}`;
    }

    if (data.check_out) {
      tooltip += `\nCheck Out: ${this.formatTime(data.check_out)}`;
    }
    if (data.auto_checkedout) {
      tooltip += `\nAuto Checked Out: Yes`;
    }

    if (data.holiday_warning) {
      tooltip += `\nHoliday Warning: Yes`;
    }

    if (data.has_edit_request) {
      tooltip += `\nPending Edit Request: Yes`;
    }

    return tooltip;
  }

  /**
   * Get status icon class
   */
  getStatusIcon(employeeId, day) {
    const data = this.state.attendanceData[employeeId]?.[day];
    if (!data) return "fa fa-question";

    const statusIcons = {
      present: "fa fa-check-circle",
      absent: "fa fa-times-circle",
      holiday: "fa fa-calendar",
      leave: "fa fa-plane",
      weekend: "fa fa-bed",
    };

    return statusIcons[data.status] || "fa fa-question";
  }

  /**
   * Get worked hours display
   */
  getWorkedHours(employeeId, day) {
    const data = this.state.attendanceData[employeeId]?.[day];
    if (!data || data.hours <= 0) return "";

    const totalHours = data.hours;
    const hours = Math.floor(totalHours);
    const minutes = Math.round((totalHours - hours) * 60);

    // Handle case where minutes round to 60
    if (minutes === 60) {
      return `${hours + 1}:00`;
    }

    return `${hours}:${minutes.toString().padStart(2, "0")}`;
  }

  /**
   * Format time for display
   */
  formatTime(timeStr) {
    if (!timeStr) return "N/A";
    try {
      const date = new Date(timeStr);
      // Times are already converted to Riyadh timezone by backend
      return date.toLocaleTimeString("en-SA", {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Riyadh",
      });
    } catch (e) {
      return timeStr;
    }
  }

  /**
   * Get employee avatar URL
   */
  getEmployeeAvatar(employeeId) {
    return `/web/image/hr.employee/${employeeId}/avatar_128`;
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
   * Get pagination information for display
   */
  getPaginationInfo() {
    const pagination = this.state.pagination;
    const info = {
      start: pagination.startIndex || 0,
      end: pagination.endIndex || 0,
      total: pagination.totalCount || 0,
    };

    // Debug log
    console.log("Pagination info:", info, "from state:", pagination);

    return info;
  }

  /**
   * Get pagination page numbers for display
   */
  getPageNumbers() {
    const totalPages = this.state.pagination.totalPages;
    const currentPage = this.state.pagination.currentPage;
    const pages = [];

    if (totalPages <= 1) {
      return [1];
    }

    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Smart pagination
      if (currentPage <= 4) {
        for (let i = 1; i <= 5; i++) pages.push(i);
        pages.push("...");
        pages.push(totalPages);
      } else if (currentPage >= totalPages - 3) {
        pages.push(1);
        pages.push("...");
        for (let i = totalPages - 4; i <= totalPages; i++) pages.push(i);
      } else {
        pages.push(1);
        pages.push("...");
        for (let i = currentPage - 1; i <= currentPage + 1; i++) pages.push(i);
        pages.push("...");
        pages.push(totalPages);
      }
    }

    return pages;
  }

  /**
   * Check pagination navigation availability
   */
  canGoPrevious() {
    return this.state.pagination.currentPage > 1;
  }

  canGoNext() {
    return this.state.pagination.currentPage < this.state.pagination.totalPages;
  }

  /**
   * Handle keyboard shortcuts
   */
  handleKeydown(event) {
    switch (event.key) {
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
   * Get attendance rate for statistics display
   */
  getAttendanceRate(status) {
    const totalWorkingSlots =
      this.state.stats.working_days * this.state.stats.total_employees;
    if (totalWorkingSlots === 0) return 0;

    let statusCount = 0;
    switch (status) {
      case "present":
        statusCount = this.state.stats.total_present;
        break;
      case "absent":
        statusCount = this.state.stats.total_absent;
        break;
      case "leave":
        statusCount = this.state.stats.total_leaves;
        break;
      case "holiday":
        statusCount = this.state.stats.total_holidays;
        break;
    }

    return Math.round((statusCount / totalWorkingSlots) * 100);
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
   * Get top performing employees - calculated from current attendance data
   */
  getTopPerformers() {
    if (!this.state.employees || this.state.employees.length === 0) {
      return [];
    }

    const performers = this.state.employees.map((employee) => {
      const employeeStats = this.calculateEmployeeStats(employee.id);
      return {
        id: employee.id,
        name: employee.name,
        attendance_rate: employeeStats.attendance_rate,
      };
    });

    return performers
      .sort((a, b) => b.attendance_rate - a.attendance_rate)
      .slice(0, 5); // Top 5
  }

  /**
   * Get low performing employees who need attention
   */
  getLowPerformers() {
    if (!this.state.employees || this.state.employees.length === 0) {
      return [];
    }

    const performers = this.state.employees.map((employee) => {
      const employeeStats = this.calculateEmployeeStats(employee.id);
      return {
        id: employee.id,
        name: employee.name,
        attendance_rate: employeeStats.attendance_rate,
      };
    });

    return performers
      .filter((p) => p.attendance_rate < 80) // Below 80%
      .sort((a, b) => a.attendance_rate - b.attendance_rate)
      .slice(0, 5); // Bottom 5
  }

  /**
   * Calculate individual employee statistics from local data
   */
  calculateEmployeeStats(employeeId) {
    const employeeData = this.state.attendanceData[employeeId] || {};
    let presentDays = 0;
    let workingDays = 0;

    this.state.daysInMonth.forEach((day) => {
      const dayData = employeeData[day];
      if (
        dayData &&
        dayData.status !== "weekend" &&
        dayData.status !== "holiday"
      ) {
        workingDays++;
        if (dayData.status === "present") {
          presentDays++;
        }
      }
    });

    const attendanceRate =
      workingDays > 0 ? Math.round((presentDays / workingDays) * 100) : 0;

    return {
      present_days: presentDays,
      working_days: workingDays,
      attendance_rate: attendanceRate,
    };
  }
  async onEditSummaryField(employeeId, fieldName, currentValue) {
    try {
      const employee = this.state.employees.find(
        (emp) => emp.id === employeeId
      );
      if (!employee) return;

      // Show input dialog
      const newValue = await this.showSummaryFieldDialog(
        employee.name,
        fieldName,
        currentValue
      );

      if (newValue !== null && newValue !== currentValue) {
        // Update the field
        const result = await this.orm.call(
          "hr.employee.attendance.grid",
          "update_employee_monthly_summary",
          [],
          {
            employee_id: employeeId,
            year: this.state.currentYear,
            month: this.state.currentMonth,
            field_name: fieldName,
            value: newValue,
            mark_absence_manual: fieldName === "total_absence_days",
            mark_late_manual: fieldName === "total_late_hours",
          }
        );

        if (result.success) {
          // Update local state
          if (!this.state.monthlySummaries[employeeId]) {
            this.state.monthlySummaries[employeeId] = {};
          }
          this.state.monthlySummaries[employeeId][fieldName] = newValue;

          this.notification.add(
            _t(`Updated ${this.getFieldLabel(fieldName)} for ${employee.name}`),
            { type: "success" }
          );
        } else {
          throw new Error(result.message || "Update failed");
        }
      }
    } catch (error) {
      console.error("Error updating summary field:", error);
      this.notification.add(_t("Error updating field: ") + error.message, {
        type: "danger",
      });
    }
  }

  // ADD this new method for showing dialog
  async showSummaryFieldDialog(employeeName, fieldName, currentValue) {
    return new Promise((resolve) => {
      this.dialog.add(SummaryFieldEditDialog, {
        title: _t("Edit Field"),
        employeeName: employeeName,
        fieldName: fieldName,
        fieldLabel: this.getFieldLabel(fieldName),
        currentValue: currentValue,
        currentMonthName: this.state.currentMonthName,
        currentYear: this.state.currentYear,
        onSave: (newValue) => resolve(newValue),
        onCancel: () => resolve(null),
      });
    });
  }

  // ADD this new method for field labels
  getFieldLabel(fieldName) {
    const labels = {
      total_absence_days: "Total Absence Days",
      total_late_hours: "Total Late Hours",
      total_overtime_hours: "Total Overtime Hours",
      remaining_leave_days: _t("Remaining Leave Days"),
    };
    return labels[fieldName] || fieldName;
  }
  async handleEditRequestNavigation(requestId) {
    try {
      await this.env.services.action.doAction({
        type: "ir.actions.act_window",
        res_model: "hr.attendance.edit.request",
        res_id: parseInt(requestId),
        view_mode: "form",
        target: "current",
      });
    } catch (error) {
      console.error("Error navigating to edit request:", error);
      this.notification.add(
        "Error opening edit request form: " + error.message,
        {
          type: "danger",
        }
      );
    }
  }
  // === METRICS ===

  /**
   * Calculate metrics for all employees
   */
  async calculateAllMetrics() {
    try {
      this.state.isLoading = true;

      const results = await Promise.all(
        this.state.employees.map((employee) =>
          this.orm.call(
            "hr.employee.attendance.grid",
            "calculate_attendance_metrics",
            [],
            {
              employee_id: employee.id,
              year: this.state.currentYear,
              month: this.state.currentMonth,
            }
          )
        )
      );

      // Update local state with calculated metrics
      results.forEach((result, index) => {
        if (result.success) {
          const employeeId = this.state.employees[index].id;
          this.state.monthlySummaries[employeeId] = result.metrics;
        }
      });

      this.notification.add(_t("Calculated metrics for all employees"), {
        type: "success",
      });
    } catch (error) {
      console.error("Error calculating metrics:", error);
      this.notification.add(_t("Error calculating metrics: ") + error.message, {
        type: "danger",
      });
    } finally {
      this.state.isLoading = false;
    }
  }

  /**
   * Get summary value for employee
   */
  getSummaryValue(employeeId, fieldName) {
    const isIntegerField = fieldName === "total_absence_days";
    if (!this.state || !this.state.monthlySummaries) {
      return isIntegerField ? 0 : 0.0;
    }
    const summary = this.state.monthlySummaries[employeeId];
    if (!summary) return isIntegerField ? 0 : 0.0;
    return summary[fieldName] || (isIntegerField ? 0 : 0.0);
  }

  /**
   * Format summary value for display
   */
  formatSummaryValue(value, fieldName) {
    if (value === null || value === undefined) {
      return fieldName === "total_absence_days" ? "0" : "0.0";
    }

    if (fieldName === "total_absence_days") {
      return Math.round(Number(value)).toString();
    }
    return Number(value).toFixed(1);
  }

  /**
   * Get CSS class for summary cell
   */
  getSummaryCellClass(value, fieldName) {
    let baseClass = "o_summary_cell";

    if (fieldName === "total_absence_days" && value > 5) {
      baseClass += " o_summary_high_absence";
    } else if (fieldName === "total_late_hours" && value > 10) {
      baseClass += " o_summary_high_late";
    } else if (fieldName === "total_overtime_hours" && value > 40) {
      baseClass += " o_summary_high_overtime";
    }

    return baseClass;
  }

  /**
   * Clean up event listeners
   */
  willUnmount() {
    document.removeEventListener("keydown", this.handleKeydown.bind(this));
  }
}

AttendanceGridComponent.template = "hr_attendance_grid_template";

// Register the main component
registry.category("actions").add("attendance_grid_component", AttendanceGridComponent);

// Export all components for use in other modules if needed
export {
  AttendanceGridComponent,
  DayDetailsModal,
  EmployeeDetailsDialog,
  EditHoursDialog,
  SummaryFieldEditDialog,
};
