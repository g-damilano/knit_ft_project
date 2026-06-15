/* App shell — state, selection, run simulation, toasts, theme, tweaks */
(function () {
  const { useState, useEffect, useRef, useCallback } = React;
  const { SEED, makeSample } = window.KGModel;

  const ACCENTS = [
    { hex: "#1f6f5c", h: 175 }, // teal
    { hex: "#2f5fbf", h: 256 }, // indigo
    { hex: "#b4532a", h: 45 },  // terracotta
    { hex: "#6b4ea0", h: 300 }, // violet
    { hex: "#3f7d3a", h: 150 }, // green
  ];
  const hueFromHex = (hex) => (ACCENTS.find((a) => a.hex === hex) || ACCENTS[0]).h;

  const MOCK_YARNS = [
    { yarn_ref: "Superwash 2/30", fibre_composition: "100% merino wool", structure_ref: "plain / stockinette" },
    { yarn_ref: "Mohair Loop", fibre_composition: "78% mohair / 22% silk", structure_ref: "fuzzy / brushed" },
    { yarn_ref: "Cotton Slub 4/8", fibre_composition: "100% organic cotton", structure_ref: "rib 1x1" },
    { yarn_ref: "Tweed 1/12", fibre_composition: "100% wool", structure_ref: "cable" },
  ];

  function recomputeStatus(s) {
    if (["queued", "running", "done", "failed"].includes(s.status)) return s.status;
    const missing = window.missingFields(s);
    return missing.length ? "needs" : "ready";
  }

  function hashId(s) {
    s = String(s); let h = 2166136261;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }

  // Simulated swatch-lattice detection -> stitch gauge + lattice geometry.
  function detectGauge(s) {
    const seed = hashId(s.id + "|" + (s.source_image_name || ""));
    const fuzzy = /fuzzy|brush|alpaca|cashmere|mohair/i.test((s.structure_ref || "") + (s.fibre_composition || ""));
    const needles = String(s.needles_per_10cm).trim() ? Math.max(8, Math.round(Number(s.needles_per_10cm))) : (24 + (seed % 12));
    const rows = String(s.rows_per_10cm).trim() ? Math.max(8, Math.round(Number(s.rows_per_10cm))) : (32 + ((seed >> 4) % 14));
    const failed = fuzzy && (seed % 3 === 0);
    // confidence is a numeric score produced by the script (0–1)
    const score = failed ? (0.50 + (seed % 12) / 100) : ((fuzzy ? 0.78 : 0.90) + (seed % 10) / 100);
    return {
      needles_per_10cm: String(needles),
      rows_per_10cm: String(rows),
      axis_order: "needle / row",
      gauge_source: "image analysis", measurement_state: "measured",
      confidence: Math.min(0.99, score).toFixed(2), manual_override: "off",
      detect_state: failed ? "failed" : "detected",
    };
  }

  function nowTs() {
    const d = new Date();
    return d.toTimeString().slice(0, 8);
  }

  // tweak defaults
  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/ {
    "accent": "#1f6f5c",
    "dark": false,
    "density": "regular",
    "uiScale": 14,
    "showTexture": true,
  } /*EDITMODE-END*/;

  function App() {
    const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
    const [samples, setSamples] = useState(() => SEED.map((s) => ({ ...s, status: recomputeStatus(s) })));
    const [selectedIds, setSelectedIds] = useState(() => (SEED[0] ? [SEED[0].id] : []));
    const [lastSel, setLastSel] = useState(SEED[0] ? SEED[0].id : null);
    const [output, setOutput] = useState("C:\\Users\\giaco\\Documents\\KnitGridCatalogRuns");
    const [running, setRunning] = useState(false);
    const [statusText, setStatusText] = useState("Ready");
    const [runTotal, setRunTotal] = useState(0);
    const [runDone, setRunDone] = useState(0);
    const [logLines, setLogLines] = useState([]);
    const [logOpen, setLogOpen] = useState(false);
    const [canOpen, setCanOpen] = useState(false);
    const [toasts, setToasts] = useState([]);
    const addCounter = useRef(7);
    const timers = useRef([]);

    // ---- theme / tweaks effects ----
    useEffect(() => {
      const root = document.documentElement;
      root.classList.add("kg-no-transition");
      root.setAttribute("data-theme", t.dark ? "dark" : "light");
      root.setAttribute("data-density", t.density === "compact" ? "compact" : "regular");
      root.style.setProperty("--accent-h", String(hueFromHex(t.accent)));
      document.body.style.fontSize = (t.uiScale || 14) + "px";
      window.setChevron && window.setChevron();
      const r = requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("kg-no-transition")));
      return () => cancelAnimationFrame(r);
    }, [t.dark, t.density, t.accent, t.uiScale]);

    useEffect(() => () => timers.current.forEach(clearTimeout), []);

    // ---- toasts ----
    const toast = useCallback((type, title, msg) => {
      const id = Math.random().toString(36).slice(2);
      setToasts((ts) => [...ts, { id, type, title, msg }]);
      const tm = setTimeout(() => setToasts((ts) => ts.filter((x) => x.id !== id)), 4600);
      timers.current.push(tm);
    }, []);

    const pushLog = useCallback((text, kind) => {
      setLogLines((ls) => [...ls, { ts: nowTs(), text, kind }]);
    }, []);

    // ---- selection ----
    const order = samples.map((s) => s.id);
    const onRowClick = (id, e) => {
      if (e.shiftKey && lastSel) {
        const a = order.indexOf(lastSel), b = order.indexOf(id);
        const [lo, hi] = [Math.min(a, b), Math.max(a, b)];
        setSelectedIds(order.slice(lo, hi + 1));
      } else if (e.metaKey || e.ctrlKey) {
        setSelectedIds((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
      } else {
        setSelectedIds([id]);
      }
      setLastSel(id);
    };
    const onToggle = (id) => {
      setSelectedIds((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
      setLastSel(id);
    };
    const onSelectAll = () => setSelectedIds(samples.map((s) => s.id));
    const onClearSel = () => setSelectedIds([]);

    const targets = samples.filter((s) => selectedIds.includes(s.id));
    const batch = targets.length > 1;

    // ---- metadata edit (single or batch) ----
    const onChange = (key, value) => {
      const ids = new Set(selectedIds);
      setSamples((arr) => arr.map((s) => {
        if (!ids.has(s.id)) return s;
        const next = { ...s, [key]: value };
        // Editing a detected gauge value by hand flags a manual override + manual source.
        if (key === "needles_per_10cm" || key === "rows_per_10cm") {
          next.manual_override = "on";
          next.detect_state = "manual";
          next.gauge_source = "manual entry";
          next.measurement_state = "measured";
        }
        next.status = recomputeStatus(next);
        return next;
      }));
    };

    // ---- lattice detection (auto-spawned at import; re-runnable for fixes) ----
    const runDetection = (ids) => {
      if (!ids || ids.length === 0) return;
      setSamples((arr) => arr.map((s) => ids.includes(s.id) ? { ...s, detect_state: "detecting" } : s));
      setStatusText("Detecting lattice\u2026");
      pushLog("$ python -m knit_grid_catalog_delivery.launcher --detect-lattice (" + ids.length + ")", "cmd");
      const tm = setTimeout(() => {
        let fails = 0;
        setSamples((arr) => arr.map((s) => {
          if (!ids.includes(s.id)) return s;
          const r = detectGauge(s);
          if (r.detect_state === "failed") fails += 1;
          pushLog((s.sample_id || "sample") + ": lattice " + r.needles_per_10cm + "\u00d7" + r.rows_per_10cm + " /10cm \u00b7 confidence " + r.confidence + (r.detect_state === "failed" ? " \u2014 verify manually" : ""), r.detect_state === "failed" ? "err" : "ok");
          const next = { ...s, ...r };
          next.status = recomputeStatus(next);
          return next;
        }));
        setStatusText("Idle");
        if (fails > 0) toast("error", "Detection needs review", fails + " sample" + (fails > 1 ? "s" : "") + " came back low-confidence \u2014 correct the gauge by hand.");
        else toast("success", "Lattice detected", "Gauge measured for " + ids.length + " sample" + (ids.length > 1 ? "s" : "") + ".");
      }, 1400);
      timers.current.push(tm);
    };
    const onDetect = (ids) => {
      ids = (ids && ids.length ? ids : selectedIds).filter((id) => samples.some((s) => s.id === id));
      if (ids.length === 0) { toast("info", "No sample", "Select a sample to detect its lattice."); return; }
      runDetection(ids);
    };

    // ---- add / remove ----
    const onAdd = (kind, dropped) => {
      const n = dropped ? 3 : 2;
      const created = [];
      for (let i = 0; i < n; i++) {
        const c = addCounter.current++;
        const m = MOCK_YARNS[(c) % MOCK_YARNS.length];
        const stem = window.KGModel.nextNames(c);
        created.push(makeSample({
          source_image_name: stem + ".png", sample_id: stem,
          structure_ref: m.structure_ref, yarn_ref: m.yarn_ref, fibre_composition: m.fibre_composition,
          tension_ref: (5 + (c % 5) + 0.3).toFixed(1),
          yarn_tension: (2 + (c % 3) + 0.4).toFixed(1),
          operator: "G. Rossi", machine_ref: "Benchmark scan",
          detect_state: "detecting",
          status: "needs",
        }));
      }
      const cooked = created.map((s) => ({ ...s, status: recomputeStatus(s) }));
      setSamples((arr) => [...arr, ...cooked]);
      setSelectedIds(cooked.map((s) => s.id));
      setLastSel(cooked[cooked.length - 1].id);
      cooked.forEach((s) => pushLog("Imported " + s.source_image_name + " \u2014 queued for lattice detection.", ""));
      toast("info", (dropped ? "Dropped " : "Imported ") + cooked.length + " scans", "Lattice detection started automatically.");
      runDetection(cooked.map((s) => s.id));
    };

    const onRemove = () => {
      if (selectedIds.length === 0) return;
      const ids = new Set(selectedIds);
      setSamples((arr) => arr.filter((s) => !ids.has(s.id)));
      setSelectedIds([]);
      setLastSel(null);
    };

    // ---- yaml helpers ----
    const onSaveYaml = () => {
      const ids = new Set(selectedIds);
      setSamples((arr) => arr.map((s) => ids.has(s.id) ? { ...s, hasYaml: true, yamlName: (s.sample_id || "sample") + ".yaml" } : s));
      targets.forEach((s) => pushLog("Saved metadata YAML: " + output + "\\" + (s.sample_id || "sample") + ".yaml", "ok"));
      toast("success", "Saved " + targets.length + " YAML sidecar" + (targets.length > 1 ? "s" : ""), "Metadata written next to each scan.");
    };
    const onReload = () => toast("info", "Reloaded from YAML", "Metadata refreshed from sidecar files.");
    const onAttach = () => {
      const ids = new Set(selectedIds);
      setSamples((arr) => arr.map((s) => ids.has(s.id) ? { ...s, hasYaml: true, yamlName: (s.sample_id || "sample") + ".yaml" } : s));
      toast("info", "YAML attached", "Sidecar linked to " + targets.length + " sample" + (targets.length > 1 ? "s" : "") + ".");
    };
    const onReset = () => {
      const ids = new Set(selectedIds);
      setSamples((arr) => arr.map((s) => {
        if (!ids.has(s.id)) return s;
        const d = makeSample({ fileName: s.fileName, sample_id: s.sample_id, id: s.id });
        return { ...d, status: recomputeStatus(d) };
      }));
      toast("info", "Reset to defaults", "Editable fields restored.");
    };

    // ---- save / catalog delivery (detection already ran at import) ----
    const startSave = (ids) => {
      if (running) return;
      ids = ids.filter((id) => samples.some((s) => s.id === id));
      if (ids.length === 0) { toast("info", "No samples", "Add at least one swatch scan first."); return; }
      setLogOpen(true);
      setLogLines([]);
      setRunning(true);
      setCanOpen(false);
      setRunTotal(ids.length);
      setRunDone(0);
      setStatusText("Saving " + ids.length + " sample" + (ids.length > 1 ? "s" : "") + "\u2026");
      setSamples((arr) => arr.map((s) => ids.includes(s.id) ? { ...s, status: "queued", progress: 0, elapsed: null } : s));
      pushLog("Output root: " + output, "");
      pushLog("Saving " + ids.length + " sample(s) \u2014 writing catalog covers, layered TIFF + metadata.", "");
      let idx = 0; let okCount = 0;
      const sampleById = (id) => samples.find((s) => s.id === id) || {};

      const processNext = () => {
        if (idx >= ids.length) {
          setRunning(false);
          setStatusText("Saved \u2014 " + okCount + " of " + ids.length);
          setCanOpen(true);
          pushLog("Catalog saved: " + okCount + " of " + ids.length + " written to output.", "ok");
          toast("success", "Catalog saved", okCount + " of " + ids.length + " samples written to output.");
          return;
        }
        const id = ids[idx];
        const sm = sampleById(id);
        const name = sm.sample_id || "sample";
        setSamples((arr) => arr.map((s) => s.id === id ? { ...s, status: "running", progress: 0 } : s));
        setStatusText("Saving " + name + "\u2026");
        pushLog("$ python -m knit_grid_catalog_delivery.launcher --deliver --input " + name + "=" + name + ".png", "cmd");
        let p = 0;
        const tick = () => {
          p += 10 + Math.random() * 18;
          if (p >= 100) {
            setSamples((arr) => arr.map((s) => s.id === id ? { ...s, progress: 100 } : s));
            const elapsed = 1.4 + Math.random() * 3.0;
            okCount += 1;
            pushLog("delivery/catalog \u2192 " + name + "_cover.png, " + name + "_catalog_layers.tiff, " + name + ".yaml", "");
            pushLog(name + ": saved " + elapsed.toFixed(1) + "s \u2714", "ok");
            setSamples((arr) => arr.map((s) => s.id === id ? { ...s, status: "done", elapsed, progress: 100, hasYaml: true, yamlName: name + ".yaml" } : s));
            setRunDone((d) => d + 1);
            idx += 1;
            const tm = setTimeout(processNext, 180);
            timers.current.push(tm);
          } else {
            if (p > 45 && p < 62) { setStatusText("Rendering cover \u2014 " + name + "\u2026"); }
            setSamples((arr) => arr.map((s) => s.id === id ? { ...s, progress: Math.min(99, Math.round(p)) } : s));
            const tm = setTimeout(tick, 60 + Math.random() * 50);
            timers.current.push(tm);
          }
        };
        const tm = setTimeout(tick, 140);
        timers.current.push(tm);
      };
      const tm0 = setTimeout(processNext, 200);
      timers.current.push(tm0);
    };

    const saveSelected = () => startSave(selectedIds.length ? selectedIds : (targets[0] ? [targets[0].id] : []));
    const saveAll = () => startSave(samples.map((s) => s.id));
    const openOutput = () => { if (canOpen) toast("info", "Opening output folder", output); };

    // selection summary
    const needCount = samples.filter((s) => s.status === "needs").length;

    return React.createElement(React.Fragment, null,
      React.createElement("div", { className: "app" },
        // titlebar
        React.createElement("div", { className: "titlebar" },
          React.createElement("div", { className: "brand" },
            React.createElement("span", { className: "mark" }, IconEl("yarn", { size: 15 })),
            "Knit Grid Catalog"),
          React.createElement("div", { className: "spacer" }),
          React.createElement("button", {
            className: "ttl-btn", onClick: () => setTweak("dark", !t.dark),
            "aria-label": "Toggle dark mode", title: t.dark ? "Light mode" : "Dark mode",
          }, IconEl(t.dark ? "sun" : "moon", { size: 16 })),
          React.createElement("button", {
            className: "ttl-btn", onClick: () => setTweak("density", t.density === "compact" ? "regular" : "compact"),
            "aria-label": "Toggle density", title: "Density",
          }, IconEl(t.density === "compact" ? "maximizeWin" : "minimize", { size: 16 })),
          React.createElement("div", { style: { width: 8 } }),
          React.createElement("button", { className: "ttl-btn", "aria-label": "Minimize", tabIndex: -1 }, IconEl("minimize", { size: 15 })),
          React.createElement("button", { className: "ttl-btn", "aria-label": "Maximize", tabIndex: -1 }, IconEl("maximizeWin", { size: 13 })),
          React.createElement("button", { className: "ttl-btn close", "aria-label": "Close", tabIndex: -1 }, IconEl("x", { size: 16 }))
        ),

        // toolbar
        React.createElement("div", { className: "toolbar" },
          React.createElement("div", { className: "app-title" },
            React.createElement("b", null, "Catalog delivery"),
            React.createElement("span", null, "v13 analysis \u00b7 v14 delivery")),
          needCount > 0
            ? React.createElement(React.Fragment, null,
                React.createElement("div", { className: "divider" }),
                React.createElement("span", { className: "chip needs" },
                  IconEl("alert", { size: 12 }), needCount + " need info"))
            : null,

          React.createElement("div", { className: "spacer" }),

          React.createElement("div", { className: "output-pill" },
            React.createElement("span", { className: "label" }, "Out"),
            React.createElement("span", { className: "path", title: output }, output),
            React.createElement("button", { className: "mini", onClick: () => toast("info", "Choose output folder", "Pick where catalog runs are written.") }, "Browse")),
          React.createElement("button", {
            className: "btn subtle", onClick: openOutput, disabled: !canOpen,
            title: canOpen ? "Open the output folder" : "Available after a save completes",
          }, IconEl("folderOpen", { size: 15 }), "Open output")
        ),

        // main split
        React.createElement("div", { className: "main" },
          React.createElement(QueuePanel, {
            samples, selectedIds, onRowClick, onToggle, onSelectAll, onClearSel,
            onAdd, onRemove, onRunSelected: saveSelected, onEditTogether: () => {},
          }),
          React.createElement("div", { className: "detail-col" },
            React.createElement(Inspector, {
              targets, batch, onChange,
              onSaveYaml, onReload, onReset, onAttach, onDetect,
            }),
            React.createElement(RunDock, {
              running, statusText, done: runDone, total: runTotal,
              logOpen, onToggleLog: () => setLogOpen((o) => !o),
              lines: logLines,
              onSaveSelected: saveSelected, onSaveAll: saveAll,
              selCount: selectedIds.length, sampleCount: samples.length,
            })
          )
        )
      ),

      // toasts
      React.createElement("div", { className: "toasts" },
        toasts.map((to) =>
          React.createElement("div", { key: to.id, className: "toast " + to.type },
            React.createElement("div", { className: "tic" },
              IconEl(to.type === "success" ? "check" : to.type === "error" ? "alert" : "info", { size: 17 })),
            React.createElement("div", { className: "tbody" },
              React.createElement("b", null, to.title),
              to.msg ? React.createElement("span", null, to.msg) : null),
            React.createElement("button", { className: "tclose", onClick: () => setToasts((ts) => ts.filter((x) => x.id !== to.id)) },
              IconEl("x", { size: 14 }))))
      ),

      // tweaks panel
      React.createElement(TweaksPanel, null,
        React.createElement(TweakSection, { label: "Appearance" }),
        React.createElement(TweakToggle, { label: "Dark mode", value: t.dark, onChange: (v) => setTweak("dark", v) }),
        React.createElement(TweakColor, {
          label: "Accent", value: t.accent,
          options: ACCENTS.map((a) => a.hex),
          onChange: (v) => setTweak("accent", v),
        }),
        React.createElement(TweakRadio, {
          label: "Density", value: t.density, options: ["compact", "regular"],
          onChange: (v) => setTweak("density", v),
        }),
        React.createElement(TweakSlider, {
          label: "UI scale", value: t.uiScale, min: 12, max: 17, step: 1, unit: "px",
          onChange: (v) => setTweak("uiScale", v),
        })
      )
    );
  }

  window.KGApp = App;
})();
