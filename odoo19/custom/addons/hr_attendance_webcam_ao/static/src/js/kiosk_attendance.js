/** @odoo-module **/
import {
  kioskAttendanceApp,
  createPublicKioskAttendance,
} from "@hr_attendance/public_kiosk/public_kiosk_app";

// import { App, whenReady, Component, useState } from "@odoo/owl";
// import { CardLayout } from "@hr_attendance/components/card_layout/card_layout";
// import { KioskManualSelection } from "@hr_attendance/components/manual_selection/manual_selection";
// import { makeEnv, startServices } from "@web/env";
// import { templates } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
// import { MainComponentsContainer } from "@web/core/main_components_container";
// import { useService, useBus } from "@web/core/utils/hooks";
// import { url } from "@web/core/utils/urls";
// import { KioskGreetings } from "@hr_attendance/components/greetings/greetings";
// import { KioskPinCode } from "@hr_attendance/components/pin_code/pin_code";
// import { KioskBarcodeScanner } from "@hr_attendance/components/kiosk_barcode/kiosk_barcode";
// patch(kioskAttendanceApp.prototype, {
//   // Override onBarcodeScanned
//   async onBarcodeScanned(barcode) {
//     console.log("Custom onBarcodeScanned executed with barcode:", barcode);

//     if (this.lockScanner || this.state.active_display !== "main") {
//       return;
//     }
//     this.lockScanner = true;

//     const result = await this.rpc("attendance_barcode_scanned", {
//       barcode: barcode,
//       token: this.props.token,
//     });

//     if (result && result.employee_name) {
//       this.employeeData = result;
//       this.switchDisplay("greet");
//     } else {
//       this.displayNotification(
//         `Custom Error: No employee found for Badge ID '${barcode}'.`
//       );
//     }
//     this.lockScanner = false;
//   },

//   // Override onManualSelection
//   async onManualSelection(employeeId, enteredPin) {
//     console.log("Custom onManualSelection executed for employee:", employeeId);

//     const result = await this.rpc("manual_selection", {
//       token: this.props.token,
//       employee_id: employeeId,
//       pin_code: enteredPin,
//     });

//     if (result && result.attendance) {
//       this.employeeData = result;
//       this.switchDisplay("greet");
//       console.log("Custom onManualSelection result:", result);
//     } else {
//       if (enteredPin) {
//         this.displayNotification("Custom Message: Wrong Pin");
//       }
//     }
//   },
// });
