/* Display-only countdown. The server's expires_at is the authority. */
function startTimer(opts) {
  var el = document.getElementById("timer");
  var remaining = opts.seconds;
  var expired = false;

  function paint() {
    var m = Math.floor(Math.max(remaining, 0) / 60);
    var s = Math.max(remaining, 0) % 60;
    el.textContent = String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
    el.classList.toggle("warn", remaining <= 300 && remaining > 60);
    el.classList.toggle("danger", remaining <= 60);
  }

  paint();
  setInterval(function () {
    remaining -= 1;
    paint();
    if (remaining <= 0 && !expired) {
      expired = true;
      opts.onExpire();
    }
  }, 1000);

  /* Re-sync with the server every 30s so clock drift or a paused tab can't
     let the browser think there is more time than there is. */
  if (opts.stateUrl) {
    setInterval(function () {
      fetch(opts.stateUrl, { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (state) {
          remaining = state.seconds_left;
          if (state.status !== "active" && !expired) {
            expired = true;
            opts.onExpire();
          }
        })
        .catch(function () { /* keep the local countdown running */ });
    }, 30000);
  }
}
