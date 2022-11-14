// Inspired from https://github.com/mehdibo/hibp-js/blob/master/hibp.js
function sha1(string) {
    var buffer = new TextEncoder("utf-8").encode(string);
    return crypto.subtle.digest("SHA-1", buffer).then(function (buffer) {
        // Get the hex code
        var hexCodes = [];
        var view = new DataView(buffer);
        for (var i = 0; i < view.byteLength; i += 4) {
            // Using getUint32 reduces the number of iterations needed (we process 4 bytes each time)
            var value = view.getUint32(i);
            // toString(16) will give the hex representation of the number without padding
            var stringValue = value.toString(16);
            // We use concatenation and slice for padding
            var padding = '00000000';
            var paddedValue = (padding + stringValue).slice(-padding.length);
            hexCodes.push(paddedValue);
        }
        // Join all the hex strings into one
        return hexCodes.join("");
    });
}

function hibpCheck(pwd) {
    // We hash the pwd first
    sha1(pwd).then(function(hash){
        // We send the first 5 chars of the hash to hibp's API
        const req = new XMLHttpRequest();
        req.open('GET', 'https://api.pwnedpasswords.com/range/'+hash.substr(0, 5));
        req.setRequestHeader('Add-Padding', 'true');
        req.addEventListener("load", function(){
            // When we get back a response from the server
            // We create an array of lines and loop through them
            const lines = this.responseText.split("\n");
            const hashSub = hash.slice(5).toUpperCase();
            for (var i in lines){
                // Check if the line matches the rest of the hash
                if (lines[i].substring(0, 35) == hashSub){
                    const val = parseInt(lines[i].trimEnd("\r").split(":")[1]);
                    if (val > 0) {
                        $("#pwned").val(val);
                    }
                    return; // If found no need to continue the loop
                }
            }
            $("#pwned").val(0);
        });
        req.send();
    });
}

// TODO: conditionally (or lazy) load select2 and dataTable
$('document').ready(function() {

    // intercept anchors with data-clicked attribute and open alternate location instead
    $('[data-clicked]').click(function(e) {
        e.preventDefault();
        window.location.href = $(this).data('clicked');
    });

    // use post for language selection
    $('#mailu-languages > a').click(function(e) {
        e.preventDefault();
        $.post({
            url: $(this).attr('href'),
            success: function() {
                window.location = window.location.href;
            },
        });
    });

    // allow en-/disabling of inputs in fieldset with checkbox in legend
    $('fieldset legend input[type=checkbox]').change(function() {
        var fieldset = $(this).parents('fieldset');
        if (this.checked) {
            fieldset.removeAttr('disabled');
            fieldset.find('input,textarea').not(this).removeAttr('disabled');
        } else {
            fieldset.attr('disabled', '');
            fieldset.find('input,textarea').not(this).attr('disabled', '');
        }
    });

    // display of range input value
    $('input[type=range]').each(function() {
        var value_element = $('#'+this.id+'_value');
        if (value_element.length) {
            value_element = $(value_element[0]);
            var infinity = $(this).data('infinity');
            var step = $(this).attr('step');
            $(this).on('input', function() {
                var num = (infinity && this.value == 0) ? '∞' : (this.value/step).toFixed(2);
                if (num.endsWith('.00')) num = num.substr(0, num.length - 3);
                value_element.text(num);
            }).trigger('input');
        }
    });

    // init select2
    $('.mailselect').select2({
        tags: true,
        tokenSeparators: [',', ' '],
    });

    // init dataTable
    var d = $(document.documentElement);
    $('.dataTable').DataTable({
        'responsive': true,
        language: {
            url: d.data('static') + d.attr('lang') + '.json',
        },
    });

    // init clipboard.js
    new ClipboardJS('.btn-clip');

    // disable login if not possible
    var l = $('#login_needs_https');
    if (l.length && window.location.protocol != 'https:') {
        l.removeClass("d-none");
        $('form :input').prop('disabled', true);
    }

    if (window.isSecureContext) {
        $("#pw").on("change paste", function(){
            hibpCheck($(this).val());
            return true;
        });
        $("#pw").closest("form").submit(function(event){
            if (parseInt($("#pwned").val()) < 0) {
                hibpCheck($("#pw").val());
            }
        });
    }

});

