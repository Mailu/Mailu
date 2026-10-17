import { Calendar } from 'fullcalendar';
import dayGridPlugin from 'fullcalendar/daygrid';
import interactionPlugin from 'fullcalendar/interaction';
import themePlugin from 'fullcalendar/themes/monarch';
import 'fullcalendar/skeleton.css';
import 'fullcalendar/themes/monarch/theme.css';
import 'fullcalendar/themes/monarch/palettes/blue.css';

const element = document.getElementById('reply-calendar');
if (element) {
  const enabled = document.getElementById('reply_enabled');
  const configuration = document.getElementById('reply-configuration');
  const updateEnabled = () => {
    configuration.hidden = !enabled.checked;
    enabled.setAttribute('aria-expanded', String(enabled.checked));
    if (enabled.checked) requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  };
  enabled.addEventListener('change', updateEnabled);
  updateEnabled();
  const start = document.getElementById('reply_startdate');
  const end = document.getElementById('reply_enddate');
  const dates = document.getElementById('reply-dates');
  const summary = document.getElementById('reply-date-summary');
  const scheduled = document.querySelector('input[name="reply_schedule"][value="dates"]');
  const unlimited = document.querySelector('input[name="reply_schedule"][value="always"]');
  const offset = (iso, days) => {
    const date = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
    date.setUTCDate(date.getUTCDate() + days);
    return date.toISOString().slice(0, 10);
  };
  const markChanged = () => start.dispatchEvent(new Event('input', {bubbles: true}));
  const selectRange = (first, exclusiveEnd) => {
    start.value = first.slice(0, 10);
    end.value = offset(exclusiveEnd, -1);
    scheduled.checked = true;
    synchronize(); markChanged();
  };
  const calendar = new Calendar(element, {
    plugins: [themePlugin, dayGridPlugin, interactionPlugin],
    locale: document.documentElement.lang.replaceAll('_', '-'),
    initialView: 'dayGridMonth', initialDate: start.value || undefined,
    headerToolbar: {left: 'prev,next', center: 'title', right: 'today'},
    buttonText: {today: element.dataset.today},
    height: 'auto', fixedWeekCount: false,
    selectable: true, selectMirror: true, unselectAuto: false,
    select: info => { selectRange(info.startStr, info.endStr); calendar.unselect(); },
    editable: true, eventDurationEditable: true, eventResizableFromStart: true,
    eventDrop: info => selectRange(info.event.startStr, info.event.endStr),
    eventResize: info => selectRange(info.event.startStr, info.event.endStr),
    selectLongPressDelay: 350,
  });
  function synchronize() {
    dates.hidden = unlimited.checked;
    calendar.removeAllEvents();
    if (scheduled.checked && start.value && end.value && start.value <= end.value) {
      calendar.addEvent({id: 'vacation', title: element.dataset.away, start: start.value, end: offset(end.value, 1), allDay: true});
      summary.textContent = `${start.value} – ${end.value}. ${summary.dataset.summary}`;
    } else summary.textContent = '';
    if (!dates.hidden) requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  }
  [start, end].forEach(input => input.addEventListener('change', () => {
    scheduled.checked = true;
    if (start.value) calendar.gotoDate(start.value);
    synchronize(); markChanged();
  }));
  [scheduled, unlimited].forEach(input => input.addEventListener('change', synchronize));
  calendar.render(); synchronize();
}
