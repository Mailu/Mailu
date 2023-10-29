var render = 'RenderLoaded';
//Store API token in variable.
var token = $("#api_token").val();

$(document).ready(function() {
	if ($("#webmail").val() == 'none') {
		$("#webmail_path").hide();
		$("#webmail_path").val("");
	} else {
		$("#webmail_path").show();
		$("#webmail_path").val("/webmail");
	}
	$("#webmail").click(function() {
		if (this.value == 'none') {
			$("#webmail_path").hide();
			$("#webmail_path").val("");
		} else {
			$("#webmail_path").show();
			$("#webmail_path").val("/webmail");
		}
	});
});

$(document).ready(function() {
	if ($('#admin').prop('checked')) {
		$("#admin_path").show();
		$("#admin_path").val("/admin");
	}
	$("#admin").change(function() {
		if ($(this).is(":checked")) {
			$("#admin_path").show();
			$("#admin_path").val("/admin");
		} else {
			$("#admin_path").hide();
			$("#admin_path").val("");
		}
	});
});

$(document).ready(function() {
	if ($('#api_enabled').prop('checked')) {
		$("#api_path").show();
		$("#api_path").val("/api")
		$("#api_token").show();
		$("#api_token").prop('required',true);
		$("#api_token").val(token);
		$("#api_token_label").show();
	} else {
		$("#api_path").hide();
		$("#api_path").val("")
		$("#api_token").hide();
		$("#api_token").prop('required',false);
		$("#api_token").val("");
		$("#api_token_label").hide();
	}
	$("#api_enabled").change(function() {
		if ($(this).is(":checked")) {
			$("#api_path").show();
			$("#api_path").val("/api");
			$("#api_token").show();
			$("#api_token").prop('required',true);
			$("#api_token").val(token)
			$("#api_token_label").show();
		} else {
			$("#api_path").hide();
			$("#api_path").val("")
			$("#api_token").hide();
			$("#api_token").prop('required',false);
			$("#api_token").val("");
			$("#api_token_label").hide();
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
	$("#resolver_enabled").change(function() {
		if ($(this).is(":checked")) {
			$("#unbound").hide();
		} else {
			$("#unbound").show();
		}
	});
});
