/*
 * workflow-poller.js — drive the live workflow dashboard.
 *
 * Polls GET /api/workflow/{project_id} (app/routes/workflow_api.py) and writes
 * the response into the panel rendered by
 * app/components/workflow_dashboard.py.
 *
 * HOW A RUN STARTS
 *
 *   There is no start API. The run button posts to the existing
 *   POST /analyze/{slug}, which is what emits into the pipeline tracker, and
 *   the poller watches that run. Adding a second way to launch an analysis
 *   would mean two code paths that could disagree about what "running" means.
 *
 *   That endpoint is synchronous and returns only when the analysis is done,
 *   so the fetch is deliberately not awaited before polling begins — the whole
 *   point is to show progress while it is still in flight.
 *
 * WHY FETCH RATHER THAN hx-trigger="every 500ms"
 *
 *   The payload updates several fields across five engines from one JSON
 *   document, and polling must stop when the run ends. HTMX polling swaps
 *   server-rendered HTML on a fixed interval whether or not anything changed,
 *   and would need extra endpoints rendering fragments. A small fetch loop is
 *   simpler and quieter.
 *
 * WHY NOT 500ms
 *
 *   Each tick waits for the previous response before scheduling the next, so a
 *   slow server halves the rate instead of queueing requests behind itself.
 *   750ms keeps the bar smooth without hammering an endpoint whose underlying
 *   counters advance per element.
 */
(function () {
  "use strict";

  var POLL_MS = 750;

  /* Exactly the values app.services.pipeline_tracker.Status emits. */
  var STATUS_LABEL = {
    pending: "PENDING",
    running: "RUNNING",
    complete: "COMPLETE",
    failed: "FAILED",
    not_implemented: "NOT IMPLEMENTED",
  };
  var STATUS_CLASS = {
    pending: "wf-pending",
    running: "wf-running",
    complete: "wf-complete",
    failed: "wf-failed",
    not_implemented: "wf-not-implemented",
  };
  var ALL_STATUS_CLASSES = Object.keys(STATUS_CLASS).map(function (k) {
    return STATUS_CLASS[k];
  });

  /* Statuses that mean this engine will not report progress. */
  var INERT = { pending: true, not_implemented: true };

  function el(root, role) {
    return root.querySelector('[data-role="' + role + '"]');
  }

  function seconds(value) {
    return (typeof value === "number" ? value : 0).toFixed(2) + "s";
  }

  /*
   * Build the metrics line from whatever the tracker actually reported.
   *
   * Keys vary by engine and stage, so this renders what is present rather than
   * asking for a fixed set and printing zeros for the rest — a zero the run
   * never measured reads exactly like one it did.
   */
  function metricsText(metrics) {
    if (!metrics) return "";
    var parts = [];

    if (typeof metrics.elements_analyzed === "number" && metrics.elements_total) {
      parts.push("Elements: " + metrics.elements_analyzed + "/" + metrics.elements_total);
    } else if (typeof metrics.elements_total === "number") {
      parts.push("Elements: " + metrics.elements_total);
    }
    if (typeof metrics.findings === "number") parts.push("Findings: " + metrics.findings);
    if (typeof metrics.data_quality === "number" && metrics.data_quality > 0) {
      parts.push("Data quality: " + metrics.data_quality);
    }
    if (typeof metrics.model_bytes === "number") {
      parts.push("Model: " + Math.round(metrics.model_bytes / 1024) + " KB");
    }
    if (typeof metrics.duration_seconds === "number") {
      parts.push("Duration: " + seconds(metrics.duration_seconds));
    }
    return parts.join(" | ");
  }

  function paintEngine(row, engine) {
    var status = engine.status || "pending";
    var bar = el(row, "bar");
    var percent = el(row, "percent");
    var badge = el(row, "badge");
    var detail = el(row, "detail");

    if (badge) {
      badge.textContent = STATUS_LABEL[status] || status.toUpperCase();
      ALL_STATUS_CLASSES.forEach(function (c) {
        badge.classList.remove(c);
      });
      badge.classList.add(STATUS_CLASS[status] || "wf-pending");
    }

    row.classList.toggle("is-running", status === "running");
    row.classList.toggle("is-inert", !!INERT[status]);

    /* An untracked engine's payload is {status} alone. Leave the bar at zero
       and say why, rather than inventing a stage for it. */
    if (INERT[status]) {
      if (bar) bar.style.width = "0%";
      if (percent) percent.textContent = "—";
      if (detail) {
        detail.textContent =
          status === "not_implemented"
            ? "No engine behind this code in this build"
            : "Queued";
      }
      return;
    }

    var pct = typeof engine.progress_percent === "number" ? engine.progress_percent : 0;
    if (bar) bar.style.width = pct + "%";
    if (percent) percent.textContent = pct + "%";

    if (!detail) return;
    var bits = [];
    if (engine.current_stage && engine.total_stages) {
      bits.push(
        "Stage " + engine.current_stage + "/" + engine.total_stages + ": " + engine.stage_name
      );
    }
    var metrics = metricsText(engine.metrics);
    if (metrics) bits.push(metrics);
    if (engine.error) bits.push(engine.error);
    detail.textContent = bits.join(" | ");
  }

  function paint(panel, data) {
    var engines = data.engines || {};
    var codes = Object.keys(engines);
    var running = 0;
    var finished = 0;
    var tracked = 0;

    codes.forEach(function (code) {
      var row = panel.querySelector('[data-engine="' + code + '"]');
      if (row) paintEngine(row, engines[code]);

      var status = engines[code].status;
      if (status === "running") running += 1;
      if (status === "complete" || status === "failed") finished += 1;
      if (!INERT[status]) tracked += 1;
    });

    var stage = el(panel, "stage");
    if (stage) {
      if (running > 0) {
        /* Report the furthest-along running engine, so the header tracks the
           run rather than whichever engine happens to be first in the payload. */
        var lead = null;
        codes.forEach(function (code) {
          var e = engines[code];
          if (e.status !== "running") return;
          if (!lead || (e.current_stage || 0) > (lead.current_stage || 0)) lead = e;
        });
        stage.textContent = lead
          ? "Stage " + lead.current_stage + "/" + lead.total_stages + ": " + lead.stage_name
          : "Running";
      } else if (tracked > 0 && finished === tracked) {
        stage.textContent = "Complete";
      } else {
        stage.textContent = "Idle";
      }
    }

    return { running: running, tracked: tracked, finished: finished };
  }

  function setBusy(panel, busy) {
    var button = el(panel, "run");
    if (!button) return;
    button.disabled = busy;
    button.textContent = busy ? "Running…" : "Run analysis";
  }

  function poll(panel, idleTicks) {
    fetch(panel.dataset.statusEndpoint, { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(function (data) {
        var state = paint(panel, data);

        if (state.running > 0) {
          window.setTimeout(function () {
            poll(panel, 0);
          }, POLL_MS);
          return;
        }

        /* Nothing is running. The POST may not have reached the tracker yet, so
           keep looking briefly before concluding the run is over — but bound it,
           so a run that never starts does not poll forever. */
        if (panel.dataset.wfBusy === "1" && idleTicks < 8) {
          window.setTimeout(function () {
            poll(panel, idleTicks + 1);
          }, POLL_MS);
          return;
        }

        panel.dataset.wfBusy = "0";
        setBusy(panel, false);
      })
      .catch(function (error) {
        var stage = el(panel, "stage");
        if (stage) stage.textContent = "Lost contact with the server: " + error.message;
        panel.dataset.wfBusy = "0";
        setBusy(panel, false);
      });
  }

  function start(panel) {
    var body = new FormData();
    body.append("project_id", panel.dataset.projectId);

    panel.dataset.wfBusy = "1";
    setBusy(panel, true);

    /* Deliberately not awaited: this endpoint returns only when the analysis is
       finished, and the point is to show progress while it runs. Polling starts
       immediately below. */
    fetch(panel.dataset.runEndpoint, {
      method: "POST",
      body: body,
      headers: { "HX-Request": "true" },
    })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.text();
      })
      .then(function () {
        var summary = el(panel, "summary");
        if (summary) summary.textContent = "Results ready";
        panel.dispatchEvent(new CustomEvent("workflow:finished", { bubbles: true }));
      })
      .catch(function (error) {
        var stage = el(panel, "stage");
        if (stage) stage.textContent = "Run failed: " + error.message;
      })
      .finally(function () {
        panel.dataset.wfBusy = "0";
        setBusy(panel, false);
      });

    poll(panel, 0);
  }

  function attach(panel) {
    if (panel.dataset.wfAttached === "1") return;
    panel.dataset.wfAttached = "1";
    panel.dataset.wfBusy = "0";

    var button = el(panel, "run");
    if (button) {
      button.addEventListener("click", function () {
        start(panel);
      });
    }

    if (panel.dataset.autostart === "1") {
      start(panel);
    } else {
      /* One read on load, so a run already in flight — started from the analyse
         page, or before a reload — shows up instead of the panel looking idle. */
      poll(panel, 8);
    }
  }

  function init() {
    document.querySelectorAll(".wf-dashboard").forEach(attach);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  /* Panels swapped in by HTMX after load need attaching too. */
  document.body.addEventListener("htmx:afterSwap", init);
})();
