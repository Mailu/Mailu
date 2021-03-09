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
		$("#postgres_db").hide();
	} else if ($("#database").val() == 'postgresql') {
		$("#postgres_db").show();
	} else if ($("#database").val() == 'mysql') {
		$("#external_db").show();
	}
	if ($('#external_psql').prop('checked')) {
		$("#external_db").show();
	}
	$("#database").click(function() {
		if (this.value == 'sqlite') {
			$("#postgres_db").hide();
			$("#external_db").hide();
		} else if (this.value == 'postgresql') {
			$("#postgres_db").show();
			$("#external_db").hide();
			$("#external_psql").prop('checked', true);
			$("#external_db").show();
			$("#db_user").prop('required',true);
			$("#db_pw").prop('required',true);
			$("#db_url").prop('required',true);
			$("#db_name").prop('required',true);
		} else if (this.value == 'mysql') {
			$("#postgres_db").hide();
			$("#external_db").show();
			$("#db_user").prop('required',true);
			$("#db_pw").prop('required',true);
			$("#db_url").prop('required',true);
			$("#db_name").prop('required',true);
		}
	});
	$("#external_psql").change(function() {
		if ($(this).is(":checked")) {
			$("#external_db").show();
			$("#db_user").prop('required',true);
			$("#db_pw").prop('required',true);
			$("#db_url").prop('required',true);
			$("#db_name").prop('required',true);
		} else {
			$("#external_db").hide();
		}
	});
	$("#internal_psql").change(function() {
		if ($(this).is(":checked")) {
			$("#external_db").hide();
			$("#db_user").val("");
			$("#db_pw").val("");
			$("#db_url").val("");
			$("#db_name").val("");
			$("#db_user").prop('required',false);
			$("#db_pw").prop('required',false);
			$("#db_url").prop('required',false);
			$("#db_name").prop('required',false);
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
