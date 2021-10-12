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
                location.reload();
            },
        });
    });

    // allow en-/disabling of inputs in fieldset with checkbox in legend
    $('fieldset legend input[type=checkbox]').change(function() {
        var fieldset = $(this).parents('fieldset');
        if (this.checked) {
            fieldset.removeAttr('disabled');
            fieldset.find('input').not(this).removeAttr('disabled');
        } else {
            fieldset.attr('disabled', '');
            fieldset.find('input').not(this).attr('disabled', '');
        }
    });

    // display of range input value
    $('input[type=range]').each(function() {
        var value_element = $('#'+this.id+'_value');
        if (value_element.length) {
            value_element = $(value_element[0]);
            var infinity = $(this).data('infinity');
            var step = $(this).attr('step');
            $(this).on('input', function() {
                value_element.text((infinity && this.value == 0) ? '∞' : this.value/step);
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

