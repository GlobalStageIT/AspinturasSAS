odoo.define('odc_template_list.controller', function (require) {
    "use strict";
    const ListController = require('web.ListController');

    return ListController.include({

        /**
         * @override
         */
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (!this.isExportEnable) {
                this.$buttons.find('button.o_button_odc_template').hide();
            }
            this.$buttons.on('click', '.o_button_odc_template', this._onCreateODCTemplate.bind(this));
        },

        // -------------------------------------------------------------------------
        // Handlers
        // -------------------------------------------------------------------------

        _onCreateODCTemplate: function () {
            let state = this.model.get(this.handle);
            let template_fields = [];
            const self = this;
            self.renderer.columns.forEach(function (column) {
                let field = state.fields[column.attrs.name];
                if (column.tag === 'field' && field.exportable !== false) {
                    template_fields.push([0, false, {
                        model: self.modelName,
                        field_name: column.attrs.name,
                        name: field.string,
                        export_type: self.get_export_type(field),
                    }]);
                }
            });

            self.do_action({
                name: 'ODC Template',
                type: 'ir.actions.act_window',
                res_model: 'odc.template',
                target: 'new',
                views: [[false, 'form']],
                context: {
                    is_modal: true,
                    default_name: self._title,
                    default_model: state.model,
                    default_domain: JSON.stringify(state.getDomain()),
                    default_field_ids: template_fields,
                }
            });
        },

        get_export_type: function (column) {
            if (['integer', 'float', 'monetary'].includes(column.type)) {
                return 'number';
            }
            if (column.type === 'date') {
                return 'date';
            }
            if (column.type === 'datetime') {
                return 'datetime';
            }
            return 'text';
        }
    });
});

