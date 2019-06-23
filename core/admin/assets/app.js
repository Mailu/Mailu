import 'select2';

jQuery("document").ready(function() {
    jQuery(".mailselect").select2({
        tags: true,
        tokenSeparators: [',', ' ']
    })
});
