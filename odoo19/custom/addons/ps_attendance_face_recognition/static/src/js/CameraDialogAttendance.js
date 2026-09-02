/** @odoo-module */

import { Dialog } from "@web/core/dialog/dialog";
import { useRef, onMounted, useState, Component, onWillUnmount, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Camera Dialog with Effects for Face Recognition
 */
export class CameraDialog extends Component {
    setup() {
        super.setup();
        this.rpc = useService("rpc");
        this.video = useRef('video');
        this.image = useRef('image');
        this.flashOverlay = useRef('flashOverlay');  // Flash effect
        this.state = useState({ img: false, isProcessing: false });
        this.intervalId = null;

        onMounted(async () => {
            this.video.el.srcObject = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });

            // Start automatic face detection
            this.intervalId = setInterval(() => {
                this._autoCaptureAndVerify();
            }, 5000);
        });

        onWillUnmount(() => {
            this.stopCamera();
        });

        this.state = useState({
                isFaceRecognitionEnabled: false,
            });

    }

    async _fetchCustomCheckInStatus() {
        try {
            const result = await this.rpc('/web/dataset/call_kw', {
                model: "ir.config_parameter",
                method: "get_param",
                args: ["ps_attendance_face_recognition.custom_checkin_enabled"],
                kwargs: {},  // ✅ Added missing kwargs parameter
            });

            this.showCustomCheckIn = result === "True";
        } catch (error) {
            console.error("Error fetching custom check-in status:", error);
        }
    }

    // Automatically capture image and verify with effects
    async _autoCaptureAndVerify() {
        if (this.state.isProcessing) return;
        this.state.isProcessing = true;

        let video = this.video.el;
        let image = this.image.el;
        let flash = this.flashOverlay.el; // Get flash overlay
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const canvasContext = canvas.getContext("2d");

        // 🎇 Add Flash Effect
        flash.classList.add("flash-effect");
        setTimeout(() => flash.classList.remove("flash-effect"), 200);

        // Capture Image
        canvasContext.drawImage(video, 0, 0);
        const imageData = canvas.toDataURL("image/jpeg");
        this.img_binary = imageData.split(",")[1];

        // Show captured image with fade effect
        image.src = imageData;
        image.classList.remove("d-none");
        image.classList.add("fade-in");
        video.classList.add("d-none");

        // Send image for verification
        try {
            const response = await this.rpc("/hr_attendance/verify_employee_face", {
                employee_id: this.props.parent.employee.id,
                image_data: this.img_binary,
                checkout: this.props.checkout,
            });

            if (response.matched) {
                alert(this.props.checkout ? "✅ Face Matched! Marking Checkout..." : "✅ Face Matched! Marking Attendance...");
                await this.rpc("/hr_attendance/systray_check_in_out", { checkout: this.props.checkout });
                this.props.parent.searchReadEmployee();
                this.stopCamera();
                const rec_id = await this.rpc("/get_checkin_image", {
                employee_id: this.props.parent.employee.id,
                image_data: this.img_binary,
                checkout: this.props.checkout
                 });
            } else {
                alert("Face not matched, trying again...");
                // Show video again if not matched
                this._reset();
            }
        } catch (error) {
            console.error("Error in face recognition:", error);
        }

        this.state.isProcessing = false;
    }

    // Reset the image
    _reset() {
        this.img_binary = false;
        this.state.img = false;
        this.video.el.classList.remove("d-none");
        this.image.el.classList.add("d-none");
    }

    _cancel() {
        (this.env.dialogData).close()
        this.stopCamera();
    }

    // Stop camera
    stopCamera() {
        if (this.intervalId) clearInterval(this.intervalId);
        this.video.el.srcObject.getVideoTracks().forEach((track) => track.stop());
        (this.env.dialogData).close();
    }
}

CameraDialog.template = "ps_attendance_face_recognition.camera_dialog_attendance";
CameraDialog.components = { Dialog };
