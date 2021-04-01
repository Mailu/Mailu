require('./app.css');

import 'select2';
import 'admin-lte/plugins/datatables/jquery.dataTables.js';
import 'admin-lte/plugins/datatables-bs4/js/dataTables.bootstrap4.js';
import 'admin-lte/plugins/datatables-responsive/js/dataTables.responsive.js';
import 'admin-lte/plugins/datatables-responsive/js/responsive.bootstrap4.js';

jQuery("document").ready(function() {
    jQuery(".mailselect").select2({
        tags: true,
        tokenSeparators: [',', ' ']
    });
    jQuery(".dataTable").DataTable({
        "responsive": true,
    });
});
