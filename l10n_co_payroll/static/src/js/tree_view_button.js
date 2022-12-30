odoo.define('book_vacations.tree_view_button', function (require){
    "use strict";

    var ajax = require('web.ajax');
    var ListController = require('web.ListController');

    var rpc = require('web.rpc')

    ListController.include({
        renderButtons: function($node) {
            this._super.apply(this, arguments);
            var self = this;
            if (this.$buttons) {
                $(this.$buttons).find('.o_list_button_generate_book').on('click', function(){
                    var self = this
                    rpc.query({
                        model: 'book.vacations',
                        method: 'generate_book',
                        args: [],
                    })
                //Recargar pagina
                location.reload();
                });
            }
        },
    });
});