/** @odoo-module */

import { onWillRender, useState } from "@odoo/owl";
import { useDateTimePicker } from "@web/core/datetime/datetime_hook";
import { areDatesEqual } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { DateTimeField, dateField } from "@web/views/fields/datetime/datetime_field";
import { listDateField } from "@web/views/fields/datetime/list_datetime_field";

/** Always D/M/YYYY with Western digits, never Arabic locale / numbering. */
const EN_US_DATE_FORMAT = "d/M/yyyy";

function toEnUsDate(value) {
    if (!value) {
        return value;
    }
    return value.reconfigure({ locale: "en-US", numberingSystem: "latn" });
}

function formatEnUsDate(value) {
    if (!value) {
        return "";
    }
    return toEnUsDate(value).toFormat(EN_US_DATE_FORMAT);
}

export class EnUsDateField extends DateTimeField {
    setup() {
        const getPickerProps = () => {
            const value = this.getRecordValue();
            const pickerProps = {
                value: Array.isArray(value) ? value.map((v) => toEnUsDate(v)) : toEnUsDate(value),
                type: this.field.type,
                range: this.isRange(value),
            };
            if (this.props.maxDate) {
                pickerProps.maxDate = this.parseLimitDate(this.props.maxDate);
            }
            if (this.props.minDate) {
                pickerProps.minDate = this.parseLimitDate(this.props.minDate);
            }
            if (!isNaN(this.props.rounding)) {
                pickerProps.rounding = this.props.rounding;
            }
            return pickerProps;
        };

        const dateTimePicker = useDateTimePicker({
            target: "root",
            format: EN_US_DATE_FORMAT,
            get pickerProps() {
                return getPickerProps();
            },
            onChange: () => {
                this.state.range = this.isRange(this.state.value);
            },
            onApply: () => {
                const toUpdate = {};
                if (Array.isArray(this.state.value)) {
                    [toUpdate[this.startDateField], toUpdate[this.endDateField]] = this.state.value;
                } else {
                    toUpdate[this.props.name] = this.state.value;
                }
                if (!this.startDateField || !this.endDateField) {
                    for (const fieldName in toUpdate) {
                        if (areDatesEqual(toUpdate[fieldName], this.props.record.data[fieldName])) {
                            delete toUpdate[fieldName];
                        }
                    }
                } else if (
                    areDatesEqual(
                        toUpdate[this.startDateField],
                        this.props.record.data[this.startDateField]
                    ) &&
                    areDatesEqual(
                        toUpdate[this.endDateField],
                        this.props.record.data[this.endDateField]
                    )
                ) {
                    delete toUpdate[this.startDateField];
                    delete toUpdate[this.endDateField];
                }
                if (Object.keys(toUpdate).length) {
                    this.props.record.update(toUpdate);
                }
            },
        });
        this.state = useState(dateTimePicker.state);
        this.openPicker = dateTimePicker.open;
        onWillRender(() => this.triggerIsDirty());
    }

    getFormattedValue(valueIndex) {
        return formatEnUsDate(this.values[valueIndex]);
    }
}

export const enUsDateField = {
    ...dateField,
    component: EnUsDateField,
};

export const listEnUsDateField = {
    ...listDateField,
    component: EnUsDateField,
};

registry.category("fields").add("makka_en_us_date", enUsDateField);
registry.category("fields").add("list.makka_en_us_date", listEnUsDateField);
