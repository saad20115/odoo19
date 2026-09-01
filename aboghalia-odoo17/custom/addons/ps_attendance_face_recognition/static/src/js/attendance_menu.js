/** @odoo-module */

import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
import { CameraDialog } from "./CameraDialogAttendance.js";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(ActivityMenu.prototype, {
  setup() {
    super.setup(...arguments);
    this.rpc = useService("rpc");
    this.dialogService = useService("dialog");
    this.fetchFaceRecognitionSetting(); // Fetch config setting
  },
  async fetchFaceRecognitionSetting() {
    try {
      const result = await this.rpc("/attendance/face_recognition_setting", {
        params: {},
      });
      this.state.isFaceRecognitionEnabled = result.is_face_recognition;
      console.log(
        "Face Recognition Setting:",
        this.state.isFaceRecognitionEnabled
      );
    } catch (error) {
      console.error("Error fetching face recognition setting:", error);
    }
  },

  onCheckIn(ev) {
    ev.stopPropagation();
    this.dialogService.add(CameraDialog, { parent: this });
  },

  async onCheckOut(ev) {
    ev.stopPropagation();
    this.dialogService.add(CameraDialog, { parent: this, checkout: true });
  },
});
