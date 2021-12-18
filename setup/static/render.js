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

$(document).ready(function() {
	if ($("#database").val() == 'sqlite') {
		$("#external_db").hide();
	} else {
		$("#external_db").show();
	}

	$("#webmail").click(function() {
		if (this.value == 'roundcube') {
			$("#db_flavor_rc_sel").show();
		} else {
			$("#db_flavor_rc_sel").hide();
			$("#roundcube_db_user,#roundcube_db_pw,#roundcube_db_url,#roundcube_db_name").prop('required',false);
		}
	});

	$("#database").click(function() {
		if (this.value == 'sqlite') {
			$("#external_db").hide();
			$("#db_user,#db_pw,#db_url,#db_name").prop('required',false);
			$("#roundcube_db_user,#roundcube_db_pw,#roundcube_db_url,#roundcube_db_name").prop('required',false);
		} else {
			$("#external_db").show();
			$("#db_user,#db_pw,#db_url,#db_name").prop('required',true);
		}
	});

	$("#database_rc").click(function() {
		if (this.value == 'sqlite'){
			$("#roundcube_external_db").hide();
			$("#roundcube_db_user,#roundcube_db_pw,#roundcube_db_url,#roundcube_db_name").prop('required',false);
		}
		else if ($("#webmail").val() == 'roundcube') {
			$("#roundcube_external_db").show();
			$("#roundcube_db_user,#roundcube_db_pw,#roundcube_db_url,#roundcube_db_name").prop('required',true);
		}
	});
});

$(document).ready(function() {
	if ($('#enable_ipv6').prop('checked')) {
		$("#ipv6").show();
	}
	$("#enable_ipv6").change(function() {
		if ($(this).is(":checked")) {
			$("#ipv6").show();
		} else {
			$("#ipv6").hide();
		}
	});
});
