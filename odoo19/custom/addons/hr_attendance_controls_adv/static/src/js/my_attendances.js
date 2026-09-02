odoo.define('hr_attendance_controls_adv.my_attendances', function (require) {
    "use strict";

    var MyAttendances = require('hr_attendance.my_attendances');
    var KioskMode = require('hr_attendance.kiosk_mode');

    var GeofenceCommon = require('hr_attendance_controls_adv.GeofenceCommon');
    var session = require("web.session");
    var Widget = require("web.Widget");

    var core = require('web.core');
    var _t = core._t;

    var MyAttendances = MyAttendances.include({
        cssLibs: [
            '/hr_attendance_controls_adv/static/src/js/lib/ol-6.12.0/ol.css',
            '/hr_attendance_controls_adv/static/src/js/lib/ol-ext/ol-ext.css',
        ],
        jsLibs: [
            '/hr_attendance_controls_adv/static/src/js/lib/ol-6.12.0/ol.js',
            '/hr_attendance_controls_adv/static/src/js/lib/ol-ext/ol-ext.js',
        ],
        events: _.extend({}, MyAttendances.prototype.events, {
            'click .gmap_kisok_toggle': '_toggle_gmap',
            'click .gip_kisok_toggle': '_toggle_gip',
            'click .glocation_kisok_toggle': '_toggle_glocation',
            'change .oe_attendance_reasons': '_on_change_reason',
        }),
        willStart: function () {
            var self = this;
            var superDef = this._super.apply(this, arguments);
            var def = this._rpc({
                model: 'hr.attendance.reasons',
                method: 'search_read',
                args: [[], ['id', 'name', 'attendance_state']],
            }).then(function (reasons) {
                self.reasons = reasons;
            });
            return Promise.all([superDef, def]);
        },
        start: function () {
            var self = this;
            this.olmap = null;
            this.ip = null;
            return this._super.apply(this, arguments).then(function () {
                self.$('.o_hr_attendance_kiosk_mode').addClass('o_hr_attendance_kiosk_mode_top');
                if (window.location.protocol == 'https:') {

                    self.$('.o_hr_attendance_sign_in_out_icon').css('pointer-events','none');

                    self.def_geofence = $.Deferred();
                    if (session.hr_attendance_geofence) {
                        self._initMap();
                    } else {
                        self.$('.gmap_kisok_container').css('display', 'none');
                        self.def_geofence.resolve();
                    }

                    self.def_geolocation = $.Deferred();
                    if (session.hr_attendance_geolocation) {
                        self._getGeolocation();
                    } else {
                        self.$('.glocation_kisok_container').css('display', 'none');
                        self.def_geolocation.resolve();
                    }

                    self.def_face_recognition = $.Deferred();
                    if (session.hr_attendance_face_recognition) {
                        self.$('a.o_hr_attendance_sign_in_out_icon').addClass('icon_disabled');
                        if (!("faceapi" in window)) {
                            self._loadfaceapi();
                        } else {
                            self._loadModels();
                            self.def_face_recognition.resolve();
                        }
                    } else {
                        self.def_face_recognition.resolve();
                    }

                    self.def_ipaddress = $.Deferred();
                    if (session.hr_attendance_ip) {
                        self._getUserIP();
                    } else {
                        self.$('.gip_kisok_container').css('display', 'none');
                        self.def_ipaddress.resolve();
                    }

                    $.when(self.def_geofence, self.def_geolocation, self.def_face_recognition, self.def_ipaddress ).then(function(){
                        self.$('.o_hr_attendance_sign_in_out_icon').css('pointer-events','');
                    })
                }

                self.def_reason = $.Deferred();
                if (session.hr_attendance_reason) {
                    self._showReasons();
                } else {
                    self.$('.attendance_reason').css('display', 'none');
                    self.def_reason.resolve();
                }
            });
        },
        _loadfaceapi: function () {
            var self = this;
            if (!("faceapi" in window)) {
                (function (w, d, s, g, js, fjs) {
                    g = w.faceapi || (w.faceapi = {});
                    g.faceapi = { q: [], ready: function (cb) { this.q.push(cb); } };
                    js = d.createElement(s); fjs = d.getElementsByTagName(s)[0];
                    js.src = window.origin + '/hr_attendance_controls_adv/static/src/js/lib/faceapi/source/face-api.js';
                    fjs.parentNode.insertBefore(js, fjs); js.onload = function () {
                        console.log("apis loaded");
                        self._loadModels();
                        self.def_face_recognition.resolve();
                    };
                }(window, document, 'script'));
            }
        },
        _loadModels: function () {
            var self = this;
            return Promise.all([
                faceapi.nets.tinyFaceDetector.loadFromUri('/hr_attendance_controls_adv/static/src/js/lib/faceapi/weights'),
                faceapi.nets.faceLandmark68Net.loadFromUri('/hr_attendance_controls_adv/static/src/js/lib/faceapi/weights'),
                faceapi.nets.faceLandmark68TinyNet.loadFromUri('/hr_attendance_controls_adv/static/src/js/lib/faceapi/weights'),
                faceapi.nets.faceRecognitionNet.loadFromUri('/hr_attendance_controls_adv/static/src/js/lib/faceapi/weights'),
                faceapi.nets.faceExpressionNet.loadFromUri('/hr_attendance_controls_adv/static/src/js/lib/faceapi/weights'),
            ]).then(function () {
                self.$('a.o_hr_attendance_sign_in_out_icon').removeClass('icon_disabled');
                self.loadLabeledImages();
            });
        },
        loadLabeledImages: function () {
            var self = this;
            self.load_label = $.Deferred();
            return this._rpc({
                route: '/hr_attendance_controls_adv/loadLabeledImages/'
            }).then(async function (data) {
                self.labeledFaceDescriptors = await Promise.all(
                    data.map((data, i) => {
                        const descriptors = [];
                        for (var i = 0; i < data.descriptors.length; i++) {
                            if (data.descriptors[i]) {
                                descriptors.push(new Float32Array(new Uint8Array([...window.atob(data.descriptors[i])].map(d => d.charCodeAt(0))).buffer));
                            }
                        }
                        return new faceapi.LabeledFaceDescriptors(data.label.toString(), descriptors);
                    }));
                self.load_label.resolve();
            });
        },
        getCurrentFaceDetectionNet: function () {
            return faceapi.nets.tinyFaceDetector;
        },

        isFaceDetectionModelLoaded: function () {
            return !!this.getCurrentFaceDetectionNet().params
        },

        getCurrentFaceRecognitionNet: function () {
            return faceapi.nets.faceRecognitionNet;
        },

        isFaceRecognitionModelLoaded: function () {
            return !!this.getCurrentFaceRecognitionNet().params
        },

        getCurrentFaceLandmarkNet: function () {
            return faceapi.nets.faceLandmark68Net;
        },

        isFaceLandmarkModelLoaded: function () {
            return !!this.getCurrentFaceLandmarkNet().params
        },
        on_attach_callback: function () {
            this._super.apply(this, arguments);
            if (this.olmap) {
                this.olmap.updateSize();
            }
        },
        _toggle_gmap: function () {
            var self = this;
            if (self.$(".gmap_kisok_toggle").hasClass('fa-angle-double-down')) {
                self.$('.gmap_kisok_view').toggle('show');
                self.$("i.gmap_kisok_toggle", self).toggleClass("fa-angle-double-down fa-angle-double-up");
                self.$(".o_hr_attendance_kiosk_backdrop")[0].setAttribute('style', 'height: calc(100vh + 197px);');
                setTimeout(function () {
                    self.olmap.updateSize()
                }, 400);
            } else {
                self.$('.gmap_kisok_view').toggle('hide');
                self.$("i.gmap_kisok_toggle", self).toggleClass("fa-angle-double-up fa-angle-double-down");
                self.$(".o_hr_attendance_kiosk_backdrop")[0].setAttribute('style', 'height: calc(100vh);');
                setTimeout(function () {
                    self.olmap.updateSize()
                }, 400);
            }
        },
        _toggle_gip: function () {
            var self = this;
            if (self.$(".gip_kisok_toggle").hasClass('fa-angle-double-down')) {
                self.$('.gip_kisok_view').toggle('show');
                self.$("i.gip_kisok_toggle", self).toggleClass("fa-angle-double-down fa-angle-double-up");
                if (self.ip) {
                    self.$('.gip_kisok_view span')[0].innerText = "IP: " + self.ip;
                }
            } else {
                self.$('.gip_kisok_view').toggle('hide');
                self.$("i.gip_kisok_toggle", self).toggleClass("fa-angle-double-up fa-angle-double-down");
            }
        },
        _toggle_glocation: function () {
            var self = this;
            if (self.$(".glocation_kisok_toggle").hasClass('fa-angle-double-down')) {
                self.$('.glocation_kisok_view').toggle('show');
                self.$("i.glocation_kisok_toggle", self).toggleClass("fa-angle-double-down fa-angle-double-up");
                if (self.latitude && self.longitude) {
                    self.$('.glocation_kisok_view span')[0].innerText = "Lattitude:" + self.latitude + ", Longitude:" + self.longitude;
                }
            } else {
                self.$('.glocation_kisok_view').toggle('hide');
                self.$("i.glocation_kisok_toggle", self).toggleClass("fa-angle-double-up fa-angle-double-down");
            }
        },
        _showReasons: function () {
            var self = this;
            self.$('.attendance_reason').css('display', '');
            self.def_reason.resolve();
        },
        _on_change_reason: function () {
            var self = this;
            var inputReason = this.$('.oe_attendance_reasons')[0];
            if (inputReason.value !== '') {
                self.attendance_reason = inputReason.value;
            }
        },
        _initMap: function () {
            var self = this;
            if (window.location.protocol == 'https:') {
                var options = {
                    enableHighAccuracy: true,
                    maximumAge: 30000,
                    timeout: 27000
                };
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(successCallback, errorCallback, options);
                } else {
                    self.geolocation = false;
                }

                function successCallback(position) {
                    self.latitude = position.coords.latitude;
                    self.longitude = position.coords.longitude;
                    if (!self.olmap) {
                        var olmap_div = self.$('.gmap_kisok_view').get(0);
                        $(olmap_div).css({
                            width: '425px !important',
                            height: '200px !important'
                        });
                        var vectorSource = new ol.source.Vector({});
                        self.olmap = new ol.Map({
                            layers: [
                                new ol.layer.Tile({
                                    source: new ol.source.OSM(),
                                }),
                                new ol.layer.Vector({
                                    source: vectorSource
                                })
                            ],

                            loadTilesWhileInteracting: true,
                            target: olmap_div,
                            view: new ol.View({
                                center: [self.latitude, self.longitude],
                                zoom: 2,
                            }),
                        });
                        const coords = [position.coords.longitude, position.coords.latitude];
                        const accuracy = ol.geom.Polygon.circular(coords, position.coords.accuracy);
                        vectorSource.clear(true);
                        vectorSource.addFeatures([
                            new ol.Feature(accuracy.transform('EPSG:4326', self.olmap.getView().getProjection())),
                            new ol.Feature(new ol.geom.Point(ol.proj.fromLonLat(coords)))
                        ]);
                        self.olmap.getView().fit(vectorSource.getExtent(), { duration: 100, maxZoom: 6 });
                        self.olmap.updateSize();
                    }
                    self.$('.gmap_kisok_container').css('display', '');
                    self.def_geofence.resolve();
                }

                function errorCallback(err) {
                    switch (err.code) {
                        case err.PERMISSION_DENIED:
                            console.log("The request for geolocation was refused by the user.");
                            break;
                        case err.POSITION_UNAVAILABLE:
                            console.log("There is no information about the location available.");
                            break;
                        case err.TIMEOUT:
                            console.log("The request for the user's location was unsuccessful.");
                            break;
                        case err.UNKNOWN_ERROR:
                            console.log("An unidentified error has occurred.");
                            break;
                    }
                    self.def_geofence.resolve();
                }
            }
            else {
                self.$('.gmap_kisok_container').addClass('d-none');
                self.do_notify(false, _t("GEOLOCATION API MAY ONLY WORKS WITH HTTPS CONNECTIONS."));
            }
        },
        _getUserIP: function (onNewIP) {
            var self = this;
            $.getJSON("https://api.ipify.org?format=json", function (data) {
                if (data.ip) {
                    self.ip = data.ip;
                    self.$('.gip_kisok_container').css('display', '');
                    self.def_ipaddress.resolve();
                }
            });
        },
        _getGeolocation: function () {
            var self = this;
            var options = {
                enableHighAccuracy: true,
                maximumAge: 30000,
                timeout: 27000
            };
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(successCallback, errorCallback, options);
            } else {
                self.geolocation = false;
                self.def_geolocation.resolve();
            }

            function successCallback(position) {
                self.latitude = position.coords.latitude;
                self.longitude = position.coords.longitude;
                self.$('.glocation_kisok_container').css('display', '');
                self.def_geolocation.resolve();
            }

            function errorCallback(err) {
                switch (err.code) {
                    case err.PERMISSION_DENIED:
                        console.log("The request for geolocation was refused by the user.");
                        break;
                    case err.POSITION_UNAVAILABLE:
                        console.log("There is no information about the location available.");
                        break;
                    case err.TIMEOUT:
                        console.log("The request for the user's location was unsuccessful.");
                        break;
                    case err.UNKNOWN_ERROR:
                        console.log("An unidentified error has occurred.");
                        break;
                }
                self.def_geolocation.reject();
            }
        },
        update_attendance: function () {
            var self = this;
            if (window.location.protocol == 'https:') {
                self._validate_attendances();
            } else {
                this._rpc({
                    model: 'hr.employee',
                    method: 'attendance_manual',
                    args: [[self.employee.id], 'hr_attendance.hr_attendance_action_my_attendances'],
                })
                    .then(function (result) {
                        if (result.action) {
                            var action = result.action;
                            self.do_action(action);
                            var employee_id = action.attendance.employee_id[0];
                            var attendance_id = action.attendance['id'];
                            self._rpc({
                                model: 'hr.attendance',
                                method: 'update_reason',
                                args: [[attendance_id], employee_id, self.attendance_reason],
                            });
                        } else if (result.warning) {
                            self.do_warn(result.warning);
                        }
                    });
            }
        },
        _validate_attendances: function () {
            var self = this;

            self.data_ip_address = null;
            self.data_latitude = null;
            self.data_longitude = null;
            self.data_is_inside = false;
            self.data_geofence_ids = null;
            self.data_photo = false;
            self.data_employee_id = null;

            self.def_geolocation_data = new $.Deferred();
            if (session.hr_attendance_geolocation) {
                if (window.location.protocol == 'https:') {
                    self._validate_Geolocation();
                } else {
                    self.def_geolocation_data.resolve();
                }
            } else {
                self.def_geolocation_data.resolve();
            }

            self.def_geofence_data = new $.Deferred();
            if (session.hr_attendance_geofence) {
                if (window.location.protocol == 'https:') {
                    self._validate_Geofence();
                } else {
                    self.def_geofence_data.resolve();
                }
            } else {
                self.def_geofence_data.resolve();
            }

            self.def_ip_data = new $.Deferred();
            if (session.hr_attendance_ip) {
                if (window.location.protocol == 'https:') {
                    self._validate_IP();
                } else {
                    self.def_ip_data.resolve();
                }
            } else {
                self.def_ip_data.resolve();
            }

            self.def_face_recognition = new $.Deferred();
            if (session.hr_attendance_face_recognition) {
                if (window.location.protocol == 'https:') {
                    self._open_recognition_dialog();
                } else {
                    self.def_face_recognition.resolve();
                }
            } else {
                self.def_face_recognition.resolve();
            }

            $.when(self.def_geolocation_data, self.def_geofence_data, self.def_face_recognition, self.def_ip_data).then(function () {                
                self._manual_attendance();
            })
        },
        _open_recognition_dialog: function () {
            var self = this;
            if (self.labeledFaceDescriptors && self.labeledFaceDescriptors.length != 0) {
                var matchedEmployee = new FaceRecognitionDialog(this, self.labeledFaceDescriptors)._onOpen();
            } else {
                self.displayNotification({ message: _t('Detection Failed: Resource not found, Please add it to your employee profile.'), type: 'danger' });
            }
        },
        _validate_face_recognition(employee_id, img) {
            var self = this;
            if (employee_id && img) {
                self.data_photo = img;
                self.data_employee_id = employee_id;
                if (parseInt(self.employee.id) === parseInt(self.data_employee_id)) {
                    self.def_face_recognition.resolve();
                } else {
                    self.displayNotification({ message: _t('Detection Failed: Detected employee is not matched with login employee profile.'), type: 'danger' });
                }
            } else {
                self.def_face_recognition.reject();
            }
        },
        _validate_Geolocation: function () {
            var self = this;
            if (self.latitude && self.longitude) {
                self.data_latitude = self.latitude || null;
                self.data_longitude = self.longitude || null;
                self.def_geolocation_data.resolve();
            } else {
                self.def_geolocation_data.reject();
            }
        },
        _validate_IP: function () {
            var self = this;
            if (self.ip) {
                self.data_ip_address = self.ip || null;
                self.def_ip_data.resolve();
            } else {
                self.def_ip_data.reject();
            }
        },
        _validate_Geofence: async function () {
            var self = this;
            var insidePolygon = false;
            var insideGeofences = []

            await self._rpc({
                model: 'hr.attendance.geofence',
                method: 'search_read',
                args: [[['company_id', '=', self.getSession().company_id], ['employee_ids', 'in', self.employee.id]], ['id', 'name', 'overlay_paths']],
            }).then(function (res) {
                self.geofence_data = res.length && res;
                if (!res.length) {
                    self.def_geofence_data.reject();
                }

                var options = {
                    enableHighAccuracy: true,
                    maximumAge: 30000,
                    timeout: 27000
                };
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(successCallback, errorCallback, options);
                }

                function successCallback(position) {
                    self.latitude = position.coords.latitude;
                    self.longitude = position.coords.longitude;
                    if (self.olmap) {
                        for (let i = 0; i < self.geofence_data.length; i++) {
                            var path = self.geofence_data[i].overlay_paths;
                            var value = JSON.parse(path);
                            if (Object.keys(value).length > 0) {
                                let coords = ol.proj.fromLonLat([self.longitude, self.latitude]);
                                var features = new ol.format.GeoJSON().readFeatures(value);
                                var geometry = features[0].getGeometry();
                                insidePolygon = geometry.intersectsCoordinate(coords);
                                if (insidePolygon === true) {
                                    insideGeofences.push(self.geofence_data[i].id);
                                }
                            }
                        }

                        if (insideGeofences.length > 0) {
                            self.data_is_inside = true;
                            self.data_geofence_ids = insideGeofences;
                            self.def_geofence_data.resolve();
                        } else {
                            Swal.fire({
                                title: 'Access Denied',
                                text: "You haven't entered any of the geofence zones.",
                                icon: 'error',
                                confirmButtonColor: '#3085d6',
                                confirmButtonText: 'Ok'
                            }).then(function () {
                                if (self.dialogPhoto && self.dialogPhoto != undefined) {
                                    var $closeBtn = self.dialogPhoto.$footer.find('.captureClose');
                                    $closeBtn.click();
                                }
                            });
                            self.def_geofence_data.reject();
                        }
                    }
                }
                function errorCallback(err) {
                    console.log(err);
                }
            })
        },

        _manual_attendance: function () {
            var self = this;
            var data_ip_address = self.data_ip_address || null;
            var data_latitude = self.data_latitude || null;
            var data_longitude = self.data_longitude || null;
            var data_geofence_ids = self.data_geofence_ids || null;
            var data_photo = self.data_photo || null;

            this._rpc({
                model: 'hr.employee',
                method: 'attendance_manual',
                args: [[self.employee.id], 'hr_attendance.hr_attendance_action_my_attendances', null, [data_latitude, data_longitude], data_ip_address, data_geofence_ids, [data_photo]],
            }).then(function (result) {
                if (result.action) {
                    var action = result.action;
                    self.do_action(action);
                    var employee_id = action.attendance.employee_id[0];
                    var attendance_id = action.attendance['id'];
                    self._rpc({
                        model: 'hr.attendance',
                        method: 'update_reason',
                        args: [[attendance_id], employee_id, self.attendance_reason],
                    });
                } else if (result.warning) {
                    self.do_warn(result.warning);
                }
            });
        },
    });

    var KioskMode = KioskMode.include({
        cssLibs: [
            '/hr_attendance_controls_adv/static/src/js/lib/ol-6.12.0/ol.css',
            '/hr_attendance_controls_adv/static/src/js/lib/ol-ext/ol-ext.css',
        ],
        jsLibs: [
            '/hr_attendance_controls_adv/static/src/js/lib/ol-6.12.0/ol.js',
            '/hr_attendance_controls_adv/static/src/js/lib/ol-ext/ol-ext.js',
        ],
        events: _.extend(KioskMode.prototype.events, {
            "click .o_hr_kiosk_face_recognition": _.debounce(function () {
                this.update_kiosk_attendance();
            }, 200, true),
            'click .gmap_kisok_toggle': '_toggle_gmap',
            'click .glocation_kisok_toggle': '_toggle_glocation',
            'click .gip_kisok_toggle': '_toggle_gip',
        }),
        init: function (parent, action) {
            this._super.apply(this, arguments);
        },
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                if (window.location.protocol == 'https:') {
                    self.def_geofence = $.Deferred();
                    if (session.hr_attendance_geofence_k) {
                        self._initMap();
                    } else {
                        self.$('.gmap_kisok_container').css('display', 'none');
                        self.def_geofence.resolve();
                    }

                    self.def_geolocation = $.Deferred();
                    if (session.hr_attendance_geolocation_k) {
                        self._getGeolocation();
                    } else {
                        self.$('.glocation_kisok_container').css('display', 'none');
                        self.def_geolocation.resolve();
                    }

                    self.def_face_recognition = $.Deferred();
                    if (session.hr_attendance_face_recognition_k) {
                        if (!("faceapi" in window)) {
                            self._loadfaceapi();
                        } else {
                            self._loadModels();
                            self.def_face_recognition.resolve();
                        }
                    } else {
                        self.$('.face_recognition_kisok_container').css('display', 'none');
                        self.def_face_recognition.resolve();
                    }

                    self.def_ipaddress = $.Deferred();
                    if (session.hr_attendance_ip_k) {
                        self._getUserIP();
                    } else {
                        self.$('.gip_kisok_container').css('display', 'none');
                        self.def_ipaddress.resolve();
                    }
                }
            });
        },
        _toggle_gmap: function () {
            var self = this;
            if (self.$(".gmap_kisok_toggle").hasClass('fa-angle-double-down')) {
                self.$('.gmap_kisok_view').toggle('show');
                self.$("i.gmap_kisok_toggle", self).toggleClass("fa-angle-double-down fa-angle-double-up");
                self.$(".o_hr_attendance_kiosk_backdrop")[0].setAttribute('style', 'height: calc(100vh + 197px);');
                setTimeout(function () {
                    self.olmap.updateSize()
                }, 400);
            } else {
                self.$('.gmap_kisok_view').toggle('hide');
                self.$("i.gmap_kisok_toggle", self).toggleClass("fa-angle-double-up fa-angle-double-down");
                self.$(".o_hr_attendance_kiosk_backdrop")[0].setAttribute('style', 'height: calc(100vh);');
                setTimeout(function () {
                    self.olmap.updateSize()
                }, 400);
            }
        },
        _toggle_glocation: function () {
            var self = this;
            if (self.$(".glocation_kisok_toggle").hasClass('fa-angle-double-down')) {
                self.$('.glocation_kisok_view').toggle('show');
                self.$("i.glocation_kisok_toggle", self).toggleClass("fa-angle-double-down fa-angle-double-up");
                if (self.latitude && self.longitude) {
                    self.$('.glocation_kisok_view span')[0].innerText = "Lattitude:" + self.latitude + ", Longitude:" + self.longitude;
                }
            } else {
                self.$('.glocation_kisok_view').toggle('hide');
                self.$("i.glocation_kisok_toggle", self).toggleClass("fa-angle-double-up fa-angle-double-down");
            }
        },
        _toggle_gip: function () {
            var self = this;
            if (self.$(".gip_kisok_toggle").hasClass('fa-angle-double-down')) {
                self.$('.gip_kisok_view').toggle('show');
                self.$("i.gip_kisok_toggle", self).toggleClass("fa-angle-double-down fa-angle-double-up");
                if (self.ip) {
                    self.$('.gip_kisok_view span')[0].innerText = "IP: " + self.ip;
                }
            } else {
                self.$('.gip_kisok_view').toggle('hide');
                self.$("i.gip_kisok_toggle", self).toggleClass("fa-angle-double-up fa-angle-double-down");
            }
        },
        _getUserIP: function (onNewIP) {
            var self = this;
            $.getJSON("https://api.ipify.org?format=json", function (data) {
                if (data.ip) {
                    self.ip = data.ip;
                    self.$('.gip_kisok_container').css('display', '');
                    self.def_ipaddress.resolve();
                }
            });
        },
        _initMap: function () {
            var self = this;
            if (window.location.protocol == 'https:') {
                var options = {
                    enableHighAccuracy: true,
                    maximumAge: 30000,
                    timeout: 27000
                };
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(successCallback, errorCallback, options);
                } else {
                    self.geolocation = false;
                }

                function successCallback(position) {
                    self.latitude = position.coords.latitude;
                    self.longitude = position.coords.longitude;
                    if (!self.olmap) {
                        var olmap_div = self.$('.gmap_kisok_view').get(0);
                        $(olmap_div).css({
                            width: '425px !important',
                            height: '200px !important'
                        });
                        var vectorSource = new ol.source.Vector({});
                        self.olmap = new ol.Map({
                            layers: [
                                new ol.layer.Tile({
                                    source: new ol.source.OSM(),
                                }),
                                new ol.layer.Vector({
                                    source: vectorSource
                                })
                            ],

                            loadTilesWhileInteracting: true,
                            target: olmap_div,
                            view: new ol.View({
                                center: [self.latitude, self.longitude],
                                zoom: 2,
                            }),
                        });
                        const coords = [position.coords.longitude, position.coords.latitude];
                        const accuracy = ol.geom.Polygon.circular(coords, position.coords.accuracy);
                        vectorSource.clear(true);
                        vectorSource.addFeatures([
                            new ol.Feature(accuracy.transform('EPSG:4326', self.olmap.getView().getProjection())),
                            new ol.Feature(new ol.geom.Point(ol.proj.fromLonLat(coords)))
                        ]);
                        self.olmap.getView().fit(vectorSource.getExtent(), { duration: 100, maxZoom: 6 });
                        self.olmap.updateSize();
                    }
                    self.$('.gmap_kisok_container').css('display', '');
                    self.def_geofence.resolve();
                }

                function errorCallback(err) {
                    switch (err.code) {
                        case err.PERMISSION_DENIED:
                            console.log("The request for geolocation was refused by the user.");
                            break;
                        case err.POSITION_UNAVAILABLE:
                            console.log("There is no information about the location available.");
                            break;
                        case err.TIMEOUT:
                            console.log("The request for the user's location was unsuccessful.");
                            break;
                        case err.UNKNOWN_ERROR:
                            console.log("An unidentified error has occurred.");
                            break;
                    }
                    self.def_geofence.resolve();
                }
            }
            else {
                self.$('.gmap_kisok_container').addClass('d-none');
                self.do_notify(false, _t("GEOLOCATION API MAY ONLY WORKS WITH HTTPS CONNECTIONS."));
            }
        },
        _getGeolocation: function () {
            var self = this;
            var options = {
                enableHighAccuracy: true,
                maximumAge: 30000,
                timeout: 27000
            };
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(successCallback, errorCallback, options);
            } else {
                self.geolocation = false;
                self.def_geolocation.resolve();
            }

            function successCallback(position) {
                self.latitude = position.coords.latitude;
                self.longitude = position.coords.longitude;
                self.$('.glocation_kisok_container').css('display', '');
                self.def_geolocation.resolve();
            }

            function errorCallback(err) {
                switch (err.code) {
                    case err.PERMISSION_DENIED:
                        console.log("The request for geolocation was refused by the user.");
                        break;
                    case err.POSITION_UNAVAILABLE:
                        console.log("There is no information about the location available.");
                        break;
                    case err.TIMEOUT:
                        console.log("The request for the user's location was unsuccessful.");
                        break;
                    case err.UNKNOWN_ERROR:
                        console.log("An unidentified error has occurred.");
                        break;
                }
                self.def_geolocation.reject();
            }
        },
        _loadfaceapi: function () {
            var self = this;
            if (!("faceapi" in window)) {
                (function (w, d, s, g, js, fjs) {
                    g = w.faceapi || (w.faceapi = {});
                    g.faceapi = { q: [], ready: function (cb) { this.q.push(cb); } };
                    js = d.createElement(s); fjs = d.getElementsByTagName(s)[0];
                    js.src = window.origin + '/hr_attendance_controls_adv/static/src/js/lib/faceapi/source/face-api.js';
                    fjs.parentNode.insertBefore(js, fjs); js.onload = function () {
                        console.log("apis loaded");
                        self._loadModels();
                        self.def_face_recognition.resolve();
                    };
                }(window, document, 'script'));
            }
        },
        _loadModels: function () {
            var self = this;
            return Promise.all([
                faceapi.nets.tinyFaceDetector.loadFromUri('/hr_attendance_controls_adv/static/src/js/lib/faceapi/weights'),
                faceapi.nets.faceLandmark68Net.loadFromUri('/hr_attendance_controls_adv/static/src/js/lib/faceapi/weights'),
                faceapi.nets.faceLandmark68TinyNet.loadFromUri('/hr_attendance_controls_adv/static/src/js/lib/faceapi/weights'),
                faceapi.nets.faceRecognitionNet.loadFromUri('/hr_attendance_controls_adv/static/src/js/lib/faceapi/weights'),
                faceapi.nets.faceExpressionNet.loadFromUri('/hr_attendance_controls_adv/static/src/js/lib/faceapi/weights'),
            ]).then(function () {
                if (session.hr_attendance_face_recognition_k) {
                    self.$('.face_recognition_kisok_container').css('display', '');
                }
                self.loadLabeledImages();
            });
        },
        loadLabeledImages: function () {
            var self = this;
            self.load_label = $.Deferred();
            return this._rpc({
                route: '/hr_attendance_controls_adv/loadLabeledImages/'
            }).then(async function (data) {
                self.labeledFaceDescriptors = await Promise.all(
                    data.map((data, i) => {
                        const descriptors = [];
                        for (var i = 0; i < data.descriptors.length; i++) {
                            if (data.descriptors[i]) {
                                descriptors.push(new Float32Array(new Uint8Array([...window.atob(data.descriptors[i])].map(d => d.charCodeAt(0))).buffer));
                            }
                        }
                        return new faceapi.LabeledFaceDescriptors(data.label.toString(), descriptors);
                    }));
                self.load_label.resolve();
            });
        },
        update_kiosk_attendance: function () {
            var self = this;
            if (window.location.protocol == 'https:') {
                self._validate_attendances();
            } else {
                self.do_notify(false, _t("GEOLOCATION API MAY ONLY WORKS WITH HTTPS CONNECTIONS."));
            }
        },
        _validate_attendances: function () {
            var self = this;

            self.data_ip_address = null;
            self.data_photo = false;
            self.data_employee_id = null;
            self.data_is_inside = false;
            self.data_geofence_ids = null;

            self.def_geolocation_data = new $.Deferred();
            if (session.hr_attendance_geolocation_k) {
                if (window.location.protocol == 'https:') {
                    self._validate_Geolocation();
                } else {
                    self.def_geolocation_data.resolve();
                }
            } else {
                self.def_geolocation_data.resolve();
            }

            self.def_ip_data = new $.Deferred();
            if (session.hr_attendance_ip_k) {
                if (window.location.protocol == 'https:') {
                    self._validate_IP();
                } else {
                    self.def_ip_data.resolve();
                }
            } else {
                self.def_ip_data.resolve();
            }

            self.def_face_recognition = new $.Deferred();
            if (session.hr_attendance_face_recognition_k) {
                if (window.location.protocol == 'https:') {
                    self._open_recognition_dialog();
                } else {
                    self.def_face_recognition.resolve();
                }
            } else {
                self.def_face_recognition.resolve();
            }

            $.when(self.def_geolocation_data, self.def_geofence_data, self.def_face_recognition, self.def_ip_data).then(function () {
                self._update_attendance();
            });
        },
        _validate_Geolocation: function () {
            var self = this;
            if (self.latitude && self.longitude) {
                self.data_latitude = self.latitude || null;
                self.data_longitude = self.longitude || null;
                self.def_geolocation_data.resolve();
            } else {
                self.def_geolocation_data.reject();
            }
        },
        _validate_IP: function () {
            var self = this;
            if (self.ip) {
                self.data_ip_address = self.ip || null;
                self.def_ip_data.resolve();
            } else {
                self.def_ip_data.reject();
            }
        },
        _open_recognition_dialog: function () {
            var self = this;
            if (self.labeledFaceDescriptors && self.labeledFaceDescriptors.length != 0) {
                var matchedEmployee = new FaceRecognitionDialog(this, self.labeledFaceDescriptors)._onOpen();
            } else {
                self.displayNotification({ message: _t('Detection Failed: Resource not found, Please add it to your employee profile.'), type: 'danger' });
            }
        },
        _update_attendance: function () {
            var self = this;

            var data_ip_address = self.data_ip_address || null;
            var data_photo = self.data_photo || null;
            var data_employee_id = self.data_employee_id || null;
            var data_latitude = self.data_latitude || null;
            var data_longitude = self.data_longitude || null;
            var data_geofence_ids = self.data_geofence_ids || null;

            this._rpc({
                model: 'hr.employee',
                method: 'attendance_kiosk_recognition',
                args: [[parseInt(data_employee_id)], [data_latitude, data_longitude], data_ip_address, data_geofence_ids, [data_photo]],
            })
                .then(function (result) {
                    if (result.action) {
                        self.do_action(result.action);

                    } else if (result.warning) {
                        self.displayNotification({ message: result.warning, type: 'danger' });
                    }
                });
        },
        _validate_face_recognition(employee_id, img) {
            var self = this;
            if (employee_id && img) {
                self.data_photo = img;
                self.data_employee_id = employee_id;
                self.def_face_recognition.resolve();
            } else {
                self.def_face_recognition.reject();
            }

            if (self.data_employee_id && self.data_employee_id != undefined) {
                self.def_geofence_data = new $.Deferred();
                if (session.hr_attendance_geofence_k) {
                    if (window.location.protocol == 'https:') {
                        self._validate_Geofence();
                    } else {
                        self.def_geofence_data.resolve();
                    }
                } else {
                    self.def_geofence_data.resolve();
                }
            }
        },
        _validate_Geofence: async function () {
            var self = this;
            var insidePolygon = false;
            var insideGeofences = []

            await self._rpc({
                model: 'hr.attendance.geofence',
                method: 'search_read',
                args: [[['company_id', '=', self.getSession().company_id], ['employee_ids', 'in', parseInt(self.data_employee_id)]], ['id', 'name', 'overlay_paths']],
            }).then(function (res) {
                self.geofence_data = res.length && res;
                if (!res.length) {
                    self.def_geofence_data.reject();
                }

                var options = {
                    enableHighAccuracy: true,
                    maximumAge: 30000,
                    timeout: 27000
                };
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(successCallback, errorCallback, options);
                }

                function successCallback(position) {
                    self.latitude = position.coords.latitude;
                    self.longitude = position.coords.longitude;
                    if (self.olmap) {
                        for (let i = 0; i < self.geofence_data.length; i++) {
                            var path = self.geofence_data[i].overlay_paths;
                            var value = JSON.parse(path);
                            if (Object.keys(value).length > 0) {
                                let coords = ol.proj.fromLonLat([self.longitude, self.latitude]);
                                var features = new ol.format.GeoJSON().readFeatures(value);
                                var geometry = features[0].getGeometry();
                                insidePolygon = geometry.intersectsCoordinate(coords);
                                if (insidePolygon === true) {
                                    insideGeofences.push(self.geofence_data[i].id);
                                }
                            }
                        }

                        if (insideGeofences.length > 0) {
                            self.data_is_inside = true;
                            self.data_geofence_ids = insideGeofences;
                            self.def_geofence_data.resolve();
                        } else {
                            Swal.fire({
                                title: 'Access Denied',
                                text: "You haven't entered any of the geofence zones.",
                                icon: 'error',
                                confirmButtonColor: '#3085d6',
                                confirmButtonText: 'Ok'
                            }).then(function () {
                                if (self.dialogPhoto && self.dialogPhoto != undefined) {
                                    var $closeBtn = self.dialogPhoto.$footer.find('.captureClose');
                                    $closeBtn.click();
                                }
                            });
                            self.def_geofence_data.reject();
                        }
                    }
                }
                function errorCallback(err) {
                    console.log(err);
                }
            })
        },
    });

    var FaceRecognitionDialog = Widget.extend({  
        template: "FaceRecognitionDialog",
        events: {
            'click .close':  '_onDestroy',
            'change select#videoSource' : 'getStream',
        },
        init: function(parent, descriptors) {
            this._super.apply(this, arguments);
            this.title = _t("Face Recognition");
            this.match_label = '';
            this.match_employee_id = false;
            this.is_update_attendance = false;
            this.parent = parent;  
            this.descriptors =  descriptors; 
        },
        start: async function () {
            var self = this;             
            return this._super.apply(this, arguments);
        },
        renderElement: async function() {
            var self = this;
            this._super();
            var def = new $.Deferred();
            navigator.getUserMedia = navigator.getUserMedia 
                || navigator.webkitGetUserMedia 
                || navigator.mozGetUserMedia;
            
            if (navigator.getUserMedia) {                
                var openRecognition = self.getStream().then(self.getDevices.bind(self)).then(self.gotDevices.bind(self));
                def.resolve(openRecognition);
            }else {
                console.log("getUserMedia not supported");
            }
            return $.when(def);
        },
        _onOpen: function(){
            this.open();
        },
        open: async function() {
            var self = this;
            self.renderElement().then(function(){
                self.$el.modal("show");
            })            
            return self;
        },
        _onDestroy: function () {      
            this.destroy();
        },
        destroy: function () {
            if (this.isDestroyed()) {
                return;
            }
            if (this.intervalID){
                clearInterval(this.intervalID);
            }            
            this.$el.modal('hide');
            this.$el.remove();
            this._super.apply(this, arguments);            
        },

        getStream: function () {
            var self = this;
            if (window.stream) {
                window.stream.getTracks().forEach(track => {
                    track.stop();
                });
            }
            var videoSelect = self.$el.find('select#videoSource').get(0);
            const videoSource = videoSelect.value;
            const constraints = {
                video: { deviceId: videoSource ? { exact: videoSource } : undefined }
            };
            return navigator.mediaDevices.getUserMedia(constraints)
                .then(self.gotStream.bind(self))
                .catch(self.handleError.bind(self));;
        },

        getDevices: function () {
            var self = this;
            return navigator.mediaDevices.enumerateDevices();
        },

        gotDevices: function (deviceInfos) {
            var self = this;
            var videoSelect = self.$el.find('select#videoSource').get(0);
            window.deviceInfos = deviceInfos;
            for (const deviceInfo of deviceInfos) {
                const option = document.createElement('option');
                option.selected = deviceInfo.label;
                option.value = deviceInfo.deviceId;
                if (deviceInfo.kind === 'videoinput') {
                    option.text = deviceInfo.label || "Camera" + (videoSelect.length + 1) + "";
                    videoSelect.appendChild(option);
                }
            }
        },

        gotStream: function (stream) {
            var self = this;
            var videoElement = self.$el.find('#video').get(0);
            var videoSelect = self.$el.find('select#videoSource').get(0);
            window.stream = stream;
            videoSelect.selectedIndex = [...videoSelect.options].findIndex(option => option.text === stream.getVideoTracks()[0].label);
            videoElement.srcObject = stream;
            videoElement.play().then(self.onLoadStream.bind(self))     
        },
        handleError: function (error) {
            var self = this;
            console.log('Error: ', error);
        },
        _onDestroy: function () {            
            this.destroy();
        },
        destroy: function () {
            if (this.isDestroyed()) {
                return;
            }
            if (this.intervalID) {
                clearInterval(this.intervalID);
            }
            if (window.stream) {
                window.stream.getTracks().forEach(track => {
                    track.stop();
                });
            }
            this._super.apply(this, arguments);
        },
        onLoadStream: async function () {
            var self = this;
            if (this.intervalID) {
                clearInterval(this.intervalID);
            }            
            var video = self.$el.find("#video").get(0);
            var canvas = self.$el.find("#canvas").get(0);
            self.FaceDetector(video, canvas);        
        },

        FaceDetector: async function() {
            var self = this;

            var video = self.$el.find("#video").get(0);
            if(video.paused || video.ended || !this.isFaceDetectionModelLoaded() || faceapi.LabeledFaceDescriptors.length === 0){
                return setTimeout(() => this.FaceDetector())
            }
            
            var options = this.getFaceDetectorOptions();
            var useTinyModel = true;
            var match_count = 0;
            
            if (!self.intervalId) {
                self.intervalID = setInterval(async () => {
                    var displaySize = { width: video.offsetWidth, height: video.offsetHeight };

                    const detections = await faceapi.detectSingleFace(video, options)
                    .withFaceLandmarks()
                    .withFaceDescriptor();

                    if (detections){                        
                        var canvas = self.$el.find("#canvas").get(0);
                        faceapi.matchDimensions(canvas, displaySize);

                        const resizedDetections = faceapi.resizeResults(detections, displaySize)
                        faceapi.draw.drawDetections(canvas, resizedDetections)
                        faceapi.draw.drawFaceLandmarks(canvas, resizedDetections)
                                               
                        if (resizedDetections && Object.keys(resizedDetections).length > 0) {
                            var faceMatcher = new faceapi.FaceMatcher(self.descriptors, 0.5);
                            const result = faceMatcher.findBestMatch(resizedDetections.descriptor);  

                            if (result && result._label != 'unknown'){
                                match_count += 1;
                                self.match_employee_id = result._label;
                                var label = self.getName(self.match_employee_id);                                
                                
                                if (label){
                                    const box = resizedDetections.detection.box;
                                    const drawBox = new faceapi.draw.DrawBox(box, { label: label.toString()});
                                    drawBox.draw(canvas);
                                }

                                if (self.match_label && self.match_employee_id && match_count > 2){
                                    clearInterval(self.intervalID);
                                    if (!self.intervalId) {
                                        var image = self.$el.find("#image").get(0);
                                        image.width = $(video).width();
                                        image.height = $(video).height();
                                        image.getContext('2d').drawImage(video, 0, 0);
                                        var img64 = image.toDataURL("image/jpeg");
                                        img64 = img64.replace(/^data:image\/(png|jpg|jpeg);base64,/, "");
                                        self.update_attendance(self.match_employee_id, img64);
                                    }
                                }
                            }
                        }
                    }
                    else{
                        var canvas = self.$el.find("#canvas").get(0);
                        faceapi.matchDimensions(canvas, displaySize);
                    }               
                },200);
            }         
        },

        update_attendance: function(employee_id, img){
            var self = this;
            if (!self.intervalId && !self.is_update_attendance){
                self.parent._validate_face_recognition(employee_id, img);
                self.is_update_attendance = true;
                self.match_label = '';
                self.match_count = [];
                self.match_employee_id = false;
                self._onDestroy();
            }
        },

        getName: function(employee_id){
            var self = this;            
            var prom = Promise.resolve();
            prom.then(function () {
                if (employee_id !== 'unknown'){
                    self._rpc({
                        route: `/hr_attendance_controls_adv/getName/${employee_id}/`
                    })
                    .then(function(result){
                        if (result){
                            self.match_label = result;
                        }
                    })
                }                
            })
            return self.match_label; 
        },

        getFaceDetectorOptions: function() {
            let inputSize = 384; // by 32, common sizes are 128, 160, 224, 320, 416, 512, 608,
            let scoreThreshold = 0.5;
            return new faceapi.TinyFaceDetectorOptions(); // {inputSize, scoreThreshold }
        },

        getCurrentFaceDetectionNet: function() {
            return faceapi.nets.tinyFaceDetector;
        },

        isFaceDetectionModelLoaded: function() {
            return !!this.getCurrentFaceDetectionNet().params
        },
    });
    return FaceRecognitionDialog;
});
