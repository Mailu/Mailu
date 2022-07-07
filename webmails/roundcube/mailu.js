if ({{ ADMIN }}) {
      rcmail.addEventListener('init', function(evt) {
            var btn = document.createElement('a');
            btn.setAttribute("href", "{{ WEB_ADMIN }}");
            btn.setAttribute("role", "button");
            btn.setAttribute("class", "showurl");
            btn.innerHTML = '<span class="inner">To {{ SITENAME }}</span>';

            document.getElementById("taskmenu").appendChild(btn);
      });
}