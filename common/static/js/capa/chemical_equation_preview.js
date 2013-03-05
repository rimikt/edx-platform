(function () {
    update = function() {
        function create_handler(saved_div) {
            return (function(response) {
                if (response.error) {
                    saved_div.html("<span class='error'>" + response.error + "</span>");
                } else {
                    saved_div.html(response.preview);
                }
            });
        }

        prev_id = "#" + this.id + "_preview";
        preview_div = $(prev_id);

        url = $(this).parents('.problems-wrapper').data('url');
        input_id = $(this).data('input-id')

        Problem.inputAjax(url, input_id, 'preview_chemcalc', {"formula" : this.value}, create_handler(preview_div));
    }

    inputs = $('.chemicalequationinput input');
    // update on load
    inputs.each(update); 
    // and on every change
    inputs.bind("input", update);
}).call(this);
