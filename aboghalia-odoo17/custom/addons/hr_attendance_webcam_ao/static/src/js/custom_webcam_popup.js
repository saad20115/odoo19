/** @odoo-module */

import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState } from "@odoo/owl";

export class CustomWebcamPopup extends Component {
  setup() {
    this.state = useState({
      message: "Please Put Your Face in the Camera",
    });
  }
}

CustomWebcamPopup.template = "hr_attendance_webcam_ao.CustomWebcamPopup";
CustomWebcamPopup.components = { Dialog };
