//Store API token in variable.
var token = $("#api_token").val();

$(document).ready(function() {
	$("#no_java_script").hide();
	$("#container").show();
});

$(document).ready(function() {
	if ($("#webmail").val() == 'none') {
		$("#webmail_path").hide();
		$("#webmail_path").val("");
		$("#webmail_path").prop('required',false);
	} else {
		$("#webmail_path").show();
		$("#webmail_path").val("/webmail");
		$("#webmail_path").prop('required',true);
	}
	$("#webmail").click(function() {
		if (this.value == 'none') {
			$("#webmail_path").hide();
			$("#webmail_path").val("");
			$("#webmail_path").prop('required',false);
		} else {
			$("#webmail_path").show();
			$("#webmail_path").val("/webmail");
			$("#webmail_path").prop('required',true);
		}
	});
});

$(document).ready(function() {
	if ($('#admin').prop('checked')) {
		$("#admin_path").show();
		$("#admin_path").val("/admin");
		$("#admin_path").prop('required',true);
	}
	$("#admin").change(function() {
		if ($(this).is(":checked")) {
			$("#admin_path").show();
			$("#admin_path").val("/admin");
			$("#admin_path").prop('required',true);
		} else {
			$("#admin_path").hide();
			$("#admin_path").val("");
			$("#admin_path").prop('required',false);
		}
	});
});

$(document).ready(function() {
	if ($('#api_enabled').prop('checked')) {
		$("#api_path").show();
		$("#api_path").prop('required',true);
		$("#api_path").val("/api")
		$("#api_token").show();
		$("#api_token").prop('required',true);
		$("#api_token").val(token);
		$("#api_token_label").show();
	} else {
		$("#api_path").hide();
		$("#api_path").prop('required',false);
		$("#api_path").val("")
		$("#api_token").hide();
		$("#api_token").prop('required',false);
		$("#api_token").val("");
		$("#api_token_label").hide();
	}
	$("#api_enabled").change(function() {
		if ($(this).is(":checked")) {
			$("#api_path").show();
			$("#api_path").prop('required',true);
			$("#api_path").val("/api");
			$("#api_token").show();
			$("#api_token").prop('required',true);
			$("#api_token").val(token)
			$("#api_token_label").show();
		} else {
			$("#api_path").hide();
			$("#api_path").prop('required',false);
			$("#api_path").val("")
			$("#api_token").hide();
			$("#api_token").prop('required',false);
			$("#api_token").val("");
			$("#api_token_label").hide();
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
