/** @odoo-module **/

import {
  Component,
  useState,
  onWillStart,
  onMounted,
  onWillUnmount,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class AttendancePage extends Component {
  static template = "ao_employee_attendance_page.AttendancePage";

  setup() {
    this.orm = useService("orm");
    this.notification = useService("notification");

    this.state = useState({
      employee: null,
      attendances: [],
      todayHours: 0,
      loading: true,
      processing: false,
      currentTime: this.getCurrentTime(),
      error: null,
      locationPermission: null,
      gettingLocation: false,
    });

    onWillStart(async () => {
      await this.loadAttendanceData();
      this.checkLocationPermission();
    });

    onMounted(() => {
      // Update current time every second
      this.timeInterval = setInterval(() => {
        this.state.currentTime = this.getCurrentTime();
      }, 1000);
    });

    onWillUnmount(() => {
      if (this.timeInterval) {
        clearInterval(this.timeInterval);
      }
    });
  }

  checkLocationPermission() {
    if (navigator.geolocation) {
      navigator.permissions
        .query({ name: "geolocation" })
        .then((result) => {
          this.state.locationPermission = result.state;
          console.log("Location permission:", result.state);
        })
        .catch(() => {
          this.state.locationPermission = "unknown";
        });
    } else {
      this.state.locationPermission = "unsupported";
    }
  }

  async getCurrentLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Geolocation is not supported"));
        return;
      }

      const options = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000, // 1 minute
      };

      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
          });
        },
        (error) => {
          console.error("Location error:", error);
          reject(error);
        },
        options
      );
    });
  }

  async reverseGeocode(latitude, longitude) {
    try {
      // Using a free reverse geocoding service
      const response = await fetch(
        `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=en`
      );

      if (!response.ok) {
        throw new Error("Geocoding service unavailable");
      }

      const data = await response.json();

      // Build a readable location string
      const parts = [];
      if (data.locality) parts.push(data.locality);
      if (data.city && data.city !== data.locality) parts.push(data.city);
      if (data.principalSubdivision) parts.push(data.principalSubdivision);
      if (data.countryName) parts.push(data.countryName);

      return parts.length > 0
        ? parts.join(", ")
        : `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
    } catch (error) {
      console.error("Reverse geocoding failed:", error);
      // Fallback to coordinates
      return `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
    }
  }

  async getLocationData() {
    try {
      this.state.gettingLocation = true;
      const location = await this.getCurrentLocation();

      // Get readable location name (with fallback)
      let locationName;
      try {
        locationName = await this.reverseGeocode(
          location.latitude,
          location.longitude
        );
      } catch (geocodeError) {
        console.warn("Geocoding failed, using coordinates:", geocodeError);
        locationName = `${location.latitude.toFixed(
          4
        )}, ${location.longitude.toFixed(4)}`;
      }

      return {
        latitude: location.latitude,
        longitude: location.longitude,
        accuracy: location.accuracy,
        location_name: locationName,
      };
    } catch (error) {
      console.error("Failed to get location:", error);

      // Show user-friendly message based on error type
      if (error.code === 1) {
        // PERMISSION_DENIED
        this.notification.add(
          _t("Location access denied. Check-in will proceed without location."),
          { type: "warning" }
        );
      } else if (error.code === 2) {
        // POSITION_UNAVAILABLE
        this.notification.add(
          _t("Location unavailable. Check-in will proceed without location."),
          { type: "warning" }
        );
      } else if (error.code === 3) {
        // TIMEOUT
        this.notification.add(
          _t("Location timeout. Check-in will proceed without location."),
          { type: "warning" }
        );
      }

      // Return null to allow check-in without location
      return null;
    } finally {
      this.state.gettingLocation = false;
    }
  }

  getCurrentTime() {
    return new Date().toLocaleString();
  }

  async loadAttendanceData() {
    try {
      this.state.loading = true;
      this.state.error = null;

      const data = await this.orm.call(
        "hr.attendance",
        "get_user_attendance_data",
        []
      );

      if (data.error) {
        this.state.error = data.message;
        return;
      }

      console.log("Employee data:", data.employee); // Debug log
      console.log("Location data:", data.employee?.current_location); // Debug location
      this.state.employee = data.employee;
      this.state.attendances = data.recent_attendances;
      this.state.todayHours = data.today_hours;
    } catch (error) {
      console.error("Error loading attendance data:", error);
      this.state.error = _t("Failed to load attendance data");
    } finally {
      this.state.loading = false;
    }
  }

  async handleCheckIn() {
    try {
      this.state.processing = true;

      // Get location data
      let locationData = null;
      if (
        this.state.locationPermission === "granted" ||
        this.state.locationPermission === "prompt"
      ) {
        this.notification.add(_t("Getting location..."), { type: "info" });
        locationData = await this.getLocationData();

        if (locationData) {
          console.log("Check-in location:", locationData);
        } else {
          this.notification.add(
            _t("Location unavailable, checking in without location"),
            { type: "warning" }
          );
        }
      }

      const result = await this.orm.call(
        "hr.attendance",
        "user_check_in",
        [locationData] // Pass as positional argument
      );

      if (result.success) {
        let message = result.message;
        if (result.location && result.location.location_name) {
          message += ` at ${result.location.location_name}`;
        }
        this.notification.add(message, { type: "success" });
        await this.loadAttendanceData();
      }
    } catch (error) {
      this.notification.add(error.message || _t("Check in failed"), {
        type: "danger",
      });
    } finally {
      this.state.processing = false;
    }
  }

  async handleCheckOut() {
    try {
      this.state.processing = true;

      // Get location data for check-out as well
      let locationData = null;
      if (
        this.state.locationPermission === "granted" ||
        this.state.locationPermission === "prompt"
      ) {
        this.notification.add(_t("Getting location..."), { type: "info" });
        locationData = await this.getLocationData();

        if (locationData) {
          console.log("Check-out location:", locationData);
        } else {
          this.notification.add(
            _t("Location unavailable, checking out without location"),
            { type: "warning" }
          );
        }
      }

      const result = await this.orm.call(
        "hr.attendance",
        "user_check_out",
        [locationData] // Pass as positional argument
      );

      if (result.success) {
        let message = result.message;
        if (result.location && result.location.location_name) {
          message += ` at ${result.location.location_name}`;
        }
        this.notification.add(message, { type: "success" });
        await this.loadAttendanceData();
      }
    } catch (error) {
      this.notification.add(error.message || _t("Check out failed"), {
        type: "danger",
      });
    } finally {
      this.state.processing = false;
    }
  }

  formatDateTime(dateTime) {
    if (!dateTime) return "";
    return new Date(dateTime).toLocaleString();
  }

  formatTime(dateTime) {
    if (!dateTime) return "";
    return new Date(dateTime).toLocaleTimeString();
  }

  formatWorkedHours(hours) {
    if (!hours) return "0h 0m";
    const h = Math.floor(hours);
    const m = Math.floor((hours - h) * 60);
    return `${h}h ${m}m`;
  }

  getEmployeeImageUrl() {
    if (this.state.employee) {
      return `/web/image?model=hr.employee&field=avatar_128&id=${this.state.employee.id}`;
    }
    return null;
  }

  get isCheckedIn() {
    return this.state.employee?.is_checked_in || false;
  }

  get statusText() {
    return this.isCheckedIn ? _t("Checked In") : _t("Checked Out");
  }

  get statusClass() {
    return this.isCheckedIn ? "o_status_checked_in" : "o_status_checked_out";
  }

  get actionButtonText() {
    return this.isCheckedIn ? _t("Check Out") : _t("Check In");
  }

  get actionButtonClass() {
    return this.isCheckedIn ? "btn-danger" : "btn-success";
  }
}

registry.category("actions").add("attendance_page", AttendancePage);
