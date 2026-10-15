//Store API token in variable.
var token = $("#api_token").val();

$(document).ready(function() {
	function updateLetsEncryptWarning() {
		var bind4 = $.trim($('[name="bind4"]').val() || '');
		var bind6 = $.trim($('[name="bind6"]').val() || '');
		var loopback4 = /^127(?:\.\d{1,3}){3}$/.test(bind4);
		var loopback6 = false;
		if ($('#enable_ipv6').prop('checked')) {
			try {
				loopback6 = new URL('http://[' + bind6 + ']/').hostname === '[::1]';
			} catch (error) {
				// Invalid addresses are handled by the setup form validation.
			}
		}
		$('#letsencrypt-loopback-warning').toggle(
			$('[name="tls_flavor"]').val() === 'letsencrypt' && (loopback4 || loopback6)
		);
	}
	$('[name="bind4"], [name="bind6"]').on('input change', updateLetsEncryptWarning);
	$('[name="tls_flavor"], #enable_ipv6').on('change', updateLetsEncryptWarning);
	updateLetsEncryptWarning();
});

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
