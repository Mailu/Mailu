require('./app.css');

import 'select2';
jQuery("document").ready(function() {
    jQuery(".mailselect").select2({
        tags: true,
        tokenSeparators: [',', ' '],
    });

    // disable login if not possible
    var l = jQuery('#login_needs_https');
    if (l.length && window.location.protocol != 'https:') {
        l.removeClass("d-none");
        jQuery('form :input').prop('disabled', true);
    }
});

