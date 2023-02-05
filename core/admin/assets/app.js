require('./app.css');

import logo from './mailu.png';
import modules from "./*.json";

// TODO: conditionally (or lazy) load select2 and dataTable
$('document').ready(function() {

    // intercept anchors with data-clicked attribute and open alternate location instead
    $('[data-clicked]').click(function(e) {
        e.preventDefault();
        window.location.href = $(this).data('clicked');
    });

    // use post for language selection
    $('#mailu-languages > a').click(function(e) {
        e.preventDefault();
        $.post({
            url: $(this).attr('href'),
            success: function() {
                window.location = window.location.href;
            },
        });
    });

    // allow en-/disabling of inputs in fieldset with checkbox in legend
    $('fieldset legend input[type=checkbox]').change(function() {
        var fieldset = $(this).parents('fieldset');
        if (this.checked) {
            fieldset.removeAttr('disabled');
            fieldset.find('input,textarea').not(this).removeAttr('disabled');
        } else {
            fieldset.attr('disabled', '');
            fieldset.find('input,textarea').not(this).attr('disabled', '');
        }
    });

    // display of range input value
    $('input[type=range]').each(function() {
        var value_element = $('#'+this.id+'_value');
        if (value_element.length) {
            value_element = $(value_element[0]);
            var infinity = $(this).data('infinity');
            var unit = $(this).attr('unit');
            if (typeof unit === 'undefined' || unit === false) {
                unit=1;
            }
            $(this).on('input', function() {
                var num = (infinity && this.value == 0) ? '∞' : (this.value/unit).toFixed(2);
                if (num.endsWith('.00')) num = num.substr(0, num.length - 3);
                value_element.text(num);
            }).trigger('input');
        }
    });

    // init select2
    $('.mailselect').select2({
        tags: true,
        tokenSeparators: [',', ' '],
    });

    // init dataTable
    var d = $(document.documentElement);
    $('.dataTable').DataTable({
        'responsive': true,
        language: {
            url: d.data('static') + d.attr('lang') + '.json',
        },
    });

    // init clipboard.js
    new ClipboardJS('.btn-clip');

    // disable login if not possible
    var l = $('#login_needs_https');
    if (l.length && window.location.protocol != 'https:') {
        l.removeClass("d-none");
        $('form :input').prop('disabled', true);
    }

});

