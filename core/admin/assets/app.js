require('./app.css');

import 'select2';
jQuery("document").ready(function() {
    jQuery(".mailselect").select2({
        tags: true,
<<<<<<< HEAD
        tokenSeparators: [',', ' ']
    })
=======
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

>>>>>>> aaf3ddd0 (moved javascript to app.js)
});

