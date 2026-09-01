/** @odoo-module */

import { ImageField } from '@web/views/fields/image/image_field';
import { patch } from "@web/core/utils/patch";
import Dialog from 'web.Dialog';
import { useService } from "@web/core/utils/hooks";
import { qweb , _t} from "web.core";

patch(ImageField.prototype, 'image_webcam', {
    setup() {
        this._super(...arguments);
        this.notification = useService("notification");
    },

    onWebcam(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        
        var self = this;

        navigator.getUserMedia = navigator.getUserMedia 
            || navigator.webkitGetUserMedia 
            || navigator.mozGetUserMedia;
        
        if (navigator.getUserMedia) {
            this.dialogWebam = new Dialog(this, {
                size: 'medium',
                title: this.env._t('Capture Snapshot'),
                $content: $(qweb.render('WebCamDialog')),
                buttons: [
                    {
                        classes: 'btn-primary captureSnapshot fa fa-camera',                       
                    },
                    {
                        classes:'btn-secondary captureClose fa fa-close', close: true,
                    }
                ]
            }).open();

            this.dialogWebam.opened().then(function () {  
                var video = self.dialogWebam.$('#video').get(0);
                if (navigator.getUserMedia) {
                    var media = navigator.getUserMedia(
                        { video: {} },
                        function(stream) {                                             
                            video.srcObject = stream; 
                            video.play(); 
                            video.muted = true;                            
                        },
                        function(err) {
                            console.log("on loaded metadata");
                        }
                    );
                }
                var $footer = self.dialogWebam.$footer;
                $footer.addClass('footer_center')
                var $captureSnapshot = self.dialogWebam.$footer.find('.captureSnapshot');
                var $closeBtn = self.dialogWebam.$footer.find('.captureClose');

                $captureSnapshot.on('click', function (event){
                    var image = self.dialogWebam.$('#image').get(0);
                    image.width = $(video).width();
                    image.height = $(video).height();
                    image.getContext('2d').drawImage(video, 0, 0, image.width, image.height);
                    var data = image.toDataURL("image/jpeg");
                    if (data){
                        data = data.split(',')[1];
                        self.props.update(data || false);
                        $closeBtn.click();
                    }
                });
            });                
        }
        else{
            this.notification.add(
                this.env._t(
                    "Warning! WEBCAM MAY ONLY WORKS WITH HTTPS CONNECTIONS. So your Odoo instance must be configured in https mode."
                ),
                { 
                    type: "danger",
                    title: this.env._t("https Failed.") 
                }
            );
        } 
    },

});