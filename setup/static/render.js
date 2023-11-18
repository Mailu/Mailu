//Store API token in variable.
var token = $("#api_token").val();

$(document).ready(function() {
	$("#no_java_script").hide();
	$("#container").show();
});

$(document).ready(function() {
	if ($('#api_enabled').prop('checked')) {
		$("#api_token").show();
		$("#api_token").prop('required',true);
		$("#api_token").val(token);
		$("#api_token_label").show();
	} else {
		$("#api_token").hide();
		$("#api_token").prop('required',false);
		$("#api_token").val("");
		$("#api_token_label").hide();
	}
	$("#api_enabled").change(function() {
		if ($(this).is(":checked")) {
			$("#api_token").show();
			$("#api_token").prop('required',true);
			$("#api_token").val(token)
			$("#api_token_label").show();
		} else {
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
