/* Reports soft integrity signals. These are review indicators, not accusations,
   and they never block the student from answering. */
function trackIntegrity(url, csrfToken) {
  function send(eventType, value) {
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ event_type: eventType, value: value || "" }),
      keepalive: true,
    }).catch(function () { /* never interrupt the exam over telemetry */ });
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) send("tab_hidden", new Date().toISOString());
  });
  window.addEventListener("blur", function () { send("window_blurred", ""); });
  document.addEventListener("copy", function () { send("copy_event", ""); });
  document.addEventListener("paste", function () { send("paste_event", ""); });

  var start = Date.now();
  var form = document.getElementById("answer-form");
  if (form) {
    form.addEventListener("submit", function () {
      var field = document.getElementById("client_response_time");
      if (field) field.value = ((Date.now() - start) / 1000).toFixed(2);
    });
  }
}
