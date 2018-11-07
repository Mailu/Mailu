$(document).ready(function() {
	if ($("#webmail").val() == 'none') {
		$("#webmail_path").hide();
		$("#webmail_path").attr("value", "");
	} else {
		$("#webmail_path").show();
		$("#webmail_path").attr("value", "/webmail");
	}
	$("#webmail").click(function() {
		if (this.value == 'none') {
			$("#webmail_path").hide();
			$("#webmail_path").attr("value", "");
		} else {
			$("#webmail_path").show();
			$("#webmail_path").attr("value", "/webmail");
		}
	});
});

$(document).ready(function() {
	if ($('#admin').prop('checked')) {
		$("#admin_path").show();
		$("#admin_path").attr("value", "/admin");
	}
	$("#admin").change(function() {
		if ($(this).is(":checked")) {
			$("#admin_path").show();
			$("#admin_path").attr("value", "/admin");
		} else {
			$("#admin_path").hide();
			$("#admin_path").attr("value", "");
		}
	});
});