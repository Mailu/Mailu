import Quill from 'quill';
import 'quill/dist/quill.snow.css';
document.querySelectorAll('textarea[data-mail-editor], #announcement_body').forEach(textarea => {
  const htmlField = document.getElementById(textarea.dataset.htmlField || '');
  const container = document.createElement('div');
  container.id = `${textarea.id}-editor`;
  textarea.after(container);
  const editor = new Quill(container, {
    theme: 'snow',
    formats: ['header', 'bold', 'italic', 'underline', 'list', 'link'],
    modules: {toolbar: [[{header: [2, 3, false]}], ['bold', 'italic', 'underline'], [{list: 'ordered'}, {list: 'bullet'}], ['link', 'clean']]}
  });
  if (htmlField && !htmlField.value) editor.setText(textarea.value);
  else editor.clipboard.dangerouslyPasteHTML(htmlField ? htmlField.value : textarea.value);
  textarea.hidden = true;
  textarea.required = false;
  const editable = container.querySelector('.ql-editor');
  editable.setAttribute('aria-label', textarea.labels[0]?.textContent || 'Message');
  editable.setAttribute('aria-multiline', 'true');
  textarea.labels[0]?.setAttribute('for', container.id);
  const synchronize = () => {
    textarea.value = htmlField ? editor.getText() : editor.getSemanticHTML();
    if (htmlField) {
      htmlField.value = editor.getSemanticHTML();
      const marker = textarea.form.querySelector('[name=reply_formatted]');
      if (marker) marker.value = '1';
    }
  };
  const previewButton = textarea.form.querySelector('[data-reply-preview]');
  if (previewButton) {
    const form = textarea.form;
    const editing = form.querySelector('[data-reply-editing]');
    const preview = form.querySelector('[data-reply-preview-content]');
    const error = form.querySelector('[data-reply-preview-error]');
    previewButton.addEventListener('click', async () => {
      synchronize();
      error.classList.add('d-none');
      previewButton.disabled = true;
      previewButton.setAttribute('aria-busy', 'true');
      try {
        const response = await fetch(form.dataset.previewUrl, {method: 'POST', body: new FormData(form)});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || error.dataset.failed);
        form.querySelector('[data-reply-preview-body]').innerHTML = result.html;
        const subject = form.querySelector('[data-reply-preview-subject]');
        subject.textContent = form.querySelector('#reply_subject').value || subject.dataset.default;
        editing.hidden = true; preview.hidden = false; preview.focus();
      } catch (failure) {
        error.textContent = failure.message || error.dataset.failed;
        error.classList.remove('d-none');
      } finally {
        previewButton.disabled = false; previewButton.removeAttribute('aria-busy');
      }
    });
    form.querySelector('[data-reply-preview-close]').addEventListener('click', () => {
      preview.hidden = true; editing.hidden = false; editor.focus();
    });
  }
  editor.on('text-change', synchronize);
  textarea.form.addEventListener('submit', synchronize);
});
