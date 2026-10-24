(function () {
  "use strict";

  var PREVIEW = window.MUNSHI_PREVIEW === true;
  var state = { data: null, view: "today", forgetArmed: null };

  function api(name) {
    var args = Array.prototype.slice.call(arguments, 1);
    if (PREVIEW) {
      return fetch("/api/" + name, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ args: args })
      }).then(function (r) {
        if (!r.ok) { throw new Error("request failed"); }
        return r.json();
      });
    }
    return window.pywebview.api[name].apply(null, args);
  }

  function $(id) { return document.getElementById(id); }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) { node.className = cls; }
    if (text !== undefined) { node.textContent = text; }
    return node;
  }

  function fill(list, items) {
    list.replaceChildren.apply(list, items);
  }

  function status(text) { $("status").textContent = text || ""; }

  function renderHours() {
    var hours = state.data.hours[state.view];
    document.querySelectorAll(".seg button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.view === state.view));
    });
    $("hours-total").textContent = hours.total ? "Active " + hours.total : "Nothing yet.";
    fill($("hours-list"), hours.rows.map(function (r) {
      var li = el("li");
      var label = el("div", "label");
      label.append(el("span", "", r.project), el("span", "", r.hours));
      var track = el("div", "track");
      var bar = el("div", "fill");
      bar.style.width = r.pct + "%";
      track.append(bar);
      li.append(label, track, el("div", "topics", r.topics));
      return li;
    }));
  }

  function render(data) {
    state.data = data;
    state.view = data.hours_view || state.view;
    $("where-text").textContent = data.where.text;
    $("where-facts").textContent = data.where.facts;
    $("where-updated").textContent = data.where.updated;

    var today = data.today.map(function (row) {
      if (row.kind === "away") { return el("li", "away", row.text); }
      var li = el("li");
      li.append(el("span", "time", row.time), el("span", "project", row.project), el("span", "topic", row.topic));
      return li;
    });
    fill($("today-list"), today.length ? today : [el("li", "muted", "Nothing today yet.")]);

    var y = data.yesterday;
    fill($("yesterday-list"), y.empty ? [el("li", "muted", y.empty)] : y.lines.map(function (t) { return el("li", "", t); }));
    $("yesterday-total").textContent = y.total;

    renderHours();

    var paused = data.paused.on;
    $("paused-badge").hidden = !paused;
    $("paused-badge").textContent = data.paused.text;
    $("pause").hidden = paused;
    $("resume").hidden = !paused;
    $("pause-options").hidden = true;
    $("refresh").disabled = !!data.busy;
    if (data.message) { status(data.message); }
    return data;
  }

  function load() { return api("card").then(render).catch(function () { status("Could not load the card."); }); }

  function act(button, name) {
    var args = Array.prototype.slice.call(arguments, 2);
    button.disabled = true;
    return api.apply(null, [name].concat(args)).then(render)
      .catch(function () { status("That did not work."); })
      .finally(function () { button.disabled = false; });
  }

  function copyInBrowser(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return legacyCopy(text); });
    }
    return Promise.resolve(legacyCopy(text));
  }

  function legacyCopy(text) {
    var area = el("textarea");
    area.value = text;
    document.body.append(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    area.remove();
    return ok;
  }

  $("refresh").addEventListener("click", function () {
    status("Writing…");
    act($("refresh"), "refresh");
  });
  $("pause").addEventListener("click", function () { $("pause-options").hidden = false; $("pause").hidden = true; });
  document.querySelectorAll("[data-pause]").forEach(function (b) {
    b.addEventListener("click", function () { act(b, "pause", b.dataset.pause).then(function () { status(""); }); });
  });
  $("resume").addEventListener("click", function () { act($("resume"), "resume").then(function () { status(""); }); });
  $("forget").addEventListener("click", function () {
    var b = $("forget");
    if (!state.forgetArmed) {
      b.textContent = "Forget the last hour?";
      b.classList.add("confirm");
      state.forgetArmed = setTimeout(function () {
        state.forgetArmed = null; b.textContent = "Forget last hour"; b.classList.remove("confirm");
      }, 4000);
      return;
    }
    clearTimeout(state.forgetArmed);
    state.forgetArmed = null;
    b.textContent = "Forget last hour";
    b.classList.remove("confirm");
    act(b, "forget").then(function () { status("Forgot the last hour."); });
  });
  $("journal").addEventListener("click", function () {
    api("open_journal").then(function (r) { status(r.note || "Opened the journal folder."); });
  });
  $("copy").addEventListener("click", function () {
    api("copy_timesheet", state.view).then(function (r) {
      if (r.empty) { return "Nothing to copy yet."; }
      if (r.text !== undefined) {
        return copyInBrowser(r.text).then(function (ok) { return ok ? "Copied" : "Copy failed"; });
      }
      return r.copied ? "Copied" : "Copy failed";
    }).then(function (text) {
      $("copy-note").textContent = text;
      setTimeout(function () { $("copy-note").textContent = ""; }, 3000);
    });
  });
  document.querySelectorAll(".seg button").forEach(function (b) {
    b.addEventListener("click", function () {
      state.view = b.dataset.view;
      renderHours();
      api("set_hours_view", state.view).then(render);
    });
  });
  function hide() {
    if (PREVIEW) { status("In the app this hides the card."); } else { api("hide_card"); }
  }
  $("close").addEventListener("click", hide);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { hide(); } });

  window.munshiCard = { reload: load };
  if (PREVIEW || (window.pywebview && window.pywebview.api)) {
    load();
  } else {
    window.addEventListener("pywebviewready", load);
  }
})();
