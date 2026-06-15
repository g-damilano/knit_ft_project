/* Inspector: single sample detail + multi-sample BATCH editing.
   Schema-driven metadata form (window.KGModel.FIELDS). The lattice gauge and
   the fields that identify the swatch are one required group (a measured
   gauge means nothing without the swatch identified) — a Required / All
   filter hides the optional/advanced detail. */
(function () {
  const { useState, useRef } = React;
  const { FIELDS, OPTS, TIERS, REQUIRED, LABELS, INFO } = window.KGModel;
  const MIXED = "\u0000MIXED";

  /* Info (i) dot with a hover/focus tooltip, portalled to <body> so it never
     clips inside the scrolling inspector. */
  function InfoTip({ text }) {
    const [open, setOpen] = useState(false);
    const [pos, setPos] = useState({ top: 0, left: 0 });
    const ref = useRef(null);
    if (!text) return null;
    const show = () => {
      const el = ref.current; if (!el) return;
      const r = el.getBoundingClientRect();
      const left = Math.min(Math.max(r.left + r.width / 2, 140), window.innerWidth - 140);
      setPos({ top: r.bottom + 9, left });
      setOpen(true);
    };
    const hide = () => setOpen(false);
    return React.createElement(React.Fragment, null,
      React.createElement("button", {
        ref, type: "button", className: "info-dot", "aria-label": "More information",
        onMouseEnter: show, onMouseLeave: hide, onFocus: show, onBlur: hide,
        onClick: (e) => { e.preventDefault(); e.stopPropagation(); open ? hide() : show(); },
      }, "i"),
      open ? ReactDOM.createPortal(
        React.createElement("div", { className: "info-pop", role: "tooltip", style: { top: pos.top, left: pos.left } }, text),
        document.body
      ) : null
    );
  }

  function mixedOf(targets, key) {
    if (targets.length === 0) return { value: "", mixed: false };
    const first = targets[0][key];
    const allSame = targets.every((t) => String(t[key]) === String(first));
    return { value: allSame ? first : MIXED, mixed: !allSame };
  }

  // which tiers are visible for a given scope
  function tierVisible(tier, scope) {
    if (scope === "required") return tier === "required";
    return true; // all
  }

  function Field({ label, required, mixed, unit, span, info, children }) {
    return React.createElement("div", { className: "field" + (span ? " span2" : "") + (unit ? " with-unit" : "") },
      React.createElement("label", null,
        label,
        required ? React.createElement("span", { className: "req", title: "Required for a complete catalog card" }, "*") : null,
        info ? React.createElement(InfoTip, { text: info }) : null,
        mixed ? React.createElement("span", { className: "mixed-tag" }, "Multiple") : null
      ),
      children,
      unit ? React.createElement("span", { className: "unit" }, unit) : null
    );
  }

  function Seg({ options, value, mixed, onChange }) {
    return React.createElement("div", { className: "seg", role: "radiogroup" },
      options.map((opt) =>
        React.createElement("button", {
          key: opt, role: "radio", "aria-checked": !mixed && value === opt,
          className: (!mixed && value === opt ? "on" : ""),
          onClick: () => onChange(opt),
        }, opt)
      )
    );
  }

  // build the control element for one field spec
  function control(spec, targets, onChange) {
    const f = mixedOf(targets, spec.key);
    const mixed = f.mixed;

    if (spec.type === "select") {
      const opts = OPTS[spec.key] || [];
      return React.createElement("select", {
        className: "inp", value: mixed ? "__mixed__" : (f.value || ""),
        onChange: (e) => { if (e.target.value !== "__mixed__") onChange(spec.key, e.target.value); },
        "aria-label": spec.label,
      },
        mixed ? React.createElement("option", { key: "__m", value: "__mixed__" }, "Multiple values\u2026") : null,
        (!mixed && !f.value) ? React.createElement("option", { key: "__b", value: "" }, "Select\u2026") : null,
        opts.map((o) => React.createElement("option", { key: o, value: o }, o))
      );
    }

    if (spec.type === "seg") {
      return React.createElement(Seg, {
        options: OPTS[spec.key], value: f.value, mixed,
        onChange: (val) => onChange(spec.key, val),
      });
    }

    if (spec.type === "textarea") {
      return React.createElement("textarea", {
        className: "inp", rows: 3,
        value: mixed ? "" : (f.value || ""),
        placeholder: mixed ? "Multiple values\u2014 typing replaces all selected\u2026" : (spec.placeholder || "Notes, anomalies, references\u2026"),
        onChange: (e) => onChange(spec.key, e.target.value), "aria-label": spec.label,
      });
    }

    // text / num
    return React.createElement("input", {
      className: "inp" + (spec.mono ? " mono" : ""),
      value: mixed ? "" : (f.value == null ? "" : String(f.value)),
      placeholder: mixed ? "Multiple values\u2026" : (spec.placeholder || ""),
      inputMode: spec.type === "num" ? "decimal" : undefined,
      spellCheck: spec.mono ? false : undefined,
      onChange: (e) => onChange(spec.key, e.target.value), "aria-label": spec.label,
    });
  }

  function MetadataForm({ targets, onChange, scope, onDetect }) {
    return React.createElement(React.Fragment, null,
      TIERS.filter((tier) => tierVisible(tier.id, scope)).map((tier) => {
        const fields = FIELDS.filter((f) => f.tier === tier.id && DETECTION_KEYS.indexOf(f.key) === -1);
        return React.createElement("div", { className: "form-section", key: tier.id },
          React.createElement("p", { className: "legend" }, IconEl(tier.icon, { size: 13 }), tier.label),
          // The lattice detection (which owns the gauge fields) leads the required group.
          tier.id === "required" ? React.createElement(DetectionCard, { targets, onChange, onDetect }) : null,
          React.createElement("div", { className: "fgrid" },
            fields.map((spec) =>
              React.createElement(Field, {
                key: spec.key, label: spec.label, required: spec.tier === "required",
                mixed: mixedOf(targets, spec.key).mixed, unit: spec.unit, span: spec.span,
                info: INFO[spec.key],
              }, control(spec, targets, onChange))
            )
          )
        );
      })
    );
  }

  /* ---- lattice detection (owns the gauge + script-derived geometry) ---- */
  const DETECTION_KEYS = ["needles_per_10cm", "rows_per_10cm", "axis_order", "confidence", "measurement_state", "gauge_source"];

  const DSTATE = {
    pending:   { label: "Not detected",  cls: "ready",   desc: "Run lattice detection to measure stitch gauge from the scan." },
    detecting: { label: "Detecting\u2026", cls: "running", desc: "Analysing the swatch lattice\u2026" },
    detected:  { label: "Detected",      cls: "done",    desc: "Gauge measured from the lattice \u2014 correct below if it looks off." },
    failed:    { label: "Check needed",  cls: "needs",   desc: "Low-confidence lattice. Verify and fix the gauge by hand." },
    manual:    { label: "Manual",        cls: "queued",  desc: "Gauge was corrected by hand and flagged as a manual override." },
    batch:     { label: "",              cls: "ready",   desc: "" },
  };

  function detectStateOf(s) {
    if (s.detect_state) return s.detect_state;
    const has = String(s.needles_per_10cm).trim() && String(s.rows_per_10cm).trim();
    return has ? "detected" : "pending";
  }

  function DetectChip({ state }) {
    const m = DSTATE[state] || DSTATE.pending;
    return React.createElement("span", { className: "chip " + m.cls },
      state === "detecting"
        ? React.createElement("span", { className: "ic" }, IconEl("spinner", { size: 12, className: "spin" }))
        : React.createElement("span", { className: "dot" }),
      m.label);
  }

  function gaugeInput(spec, targets, onChange) {
    return React.createElement(Field, {
      label: spec.label, required: true, unit: spec.unit, info: INFO[spec.key],
      mixed: mixedOf(targets, spec.key).mixed,
    }, control(spec, targets, onChange));
  }

  // period in cm is fixed in relation to the /10 cm gauge (period = 10 / count)
  function periodCm(count) {
    const n = Number(count);
    return n > 0 ? (10 / n).toFixed(2) + " cm" : "\u2014";
  }
  // confidence is a numeric score from the detection script (0–1)
  function confPct(v) {
    const n = Number(v);
    if (v === "" || v == null || isNaN(n)) return "\u2014";
    return Math.round(n * 100) + "%";
  }

  function Readout({ label, value, info }) {
    return React.createElement("div", { className: "ro" },
      React.createElement("span", { className: "ro-k" }, label, info ? React.createElement(InfoTip, { text: info }) : null),
      React.createElement("span", { className: "ro-v" }, value)
    );
  }

  // axis order is defined once (a/b or b/a); source, state, periods + confidence are fixed by the script
  function DetectReadouts({ targets, onChange }) {
    const single = targets.length === 1 ? targets[0] : null;
    const axisF = mixedOf(targets, "axis_order");
    const np = single ? periodCm(single.needles_per_10cm) : "\u2014";
    const rp = single ? periodCm(single.rows_per_10cm) : "\u2014";
    const conf = single ? confPct(single.confidence) : "\u2014";
    const src = single && String(single.gauge_source).trim() ? single.gauge_source : "\u2014";
    const ms = single && String(single.measurement_state).trim() ? single.measurement_state : "\u2014";
    return React.createElement("div", { className: "detect-readouts" },
      React.createElement("div", { className: "ro ro-axis" },
        React.createElement("span", { className: "ro-k" }, "Axis order (x / y)", React.createElement(InfoTip, { text: INFO.axis_order })),
        React.createElement(Seg, { options: OPTS.axis_order, value: axisF.value, mixed: axisF.mixed, onChange: (v) => onChange("axis_order", v) })
      ),
      React.createElement(Readout, { label: "Gauge source", value: src, info: INFO.gauge_source }),
      React.createElement(Readout, { label: "Measurement state", value: ms, info: INFO.measurement_state }),
      React.createElement(Readout, { label: "Needle period", value: np, info: INFO.needle_period }),
      React.createElement(Readout, { label: "Row period", value: rp, info: INFO.row_period }),
      React.createElement(Readout, { label: "Confidence", value: conf, info: INFO.confidence })
    );
  }

  function DetectionCard({ targets, onChange, onDetect }) {
    const single = targets.length === 1 ? targets[0] : null;
    const states = targets.map(detectStateOf);
    const detecting = states.indexOf("detecting") !== -1;
    const state = single ? detectStateOf(single) : (detecting ? "detecting" : "batch");
    const desc = single ? DSTATE[state].desc
                        : "Detect lattice for all " + targets.length + " selected, then correct any outliers per sample.";
    const settled = single && ["detected", "failed", "manual"].indexOf(state) !== -1;
    const needleSpec = FIELDS.find((f) => f.key === "needles_per_10cm");
    const rowSpec = FIELDS.find((f) => f.key === "rows_per_10cm");
    const showReadouts = single
      ? !!(String(single.needles_per_10cm).trim() || String(single.rows_per_10cm).trim())
      : true;

    return React.createElement("div", { className: "detect-card" + (state === "failed" ? " alert" : "") },
      React.createElement("div", { className: "detect-head" },
        React.createElement("div", { className: "dh-ic" }, IconEl("grid", { size: 18 })),
        React.createElement("div", { className: "dh-text" },
          React.createElement("b", null, "Lattice detection"),
          React.createElement("span", { className: "sub" }, desc)),
        single ? React.createElement(DetectChip, { state }) : (detecting ? React.createElement(DetectChip, { state: "detecting" }) : null)
      ),
      React.createElement("div", { className: "detect-body" },
        React.createElement("div", { className: "detect-gauge" },
          gaugeInput(needleSpec, targets, onChange),
          React.createElement("span", { className: "times" }, "\u00d7"),
          gaugeInput(rowSpec, targets, onChange)
        ),
        React.createElement("button", {
          className: "btn " + (settled ? "subtle" : "primary"),
          onClick: () => onDetect(targets.map((t) => t.id)), disabled: detecting,
        }, IconEl(detecting ? "spinner" : "scan", { size: 14, className: detecting ? "spin" : "" }),
           settled ? "Re-detect" : "Detect lattice")
      ),
      showReadouts ? React.createElement(DetectReadouts, { targets, onChange }) : null
    );
  }

  function ScopeBar({ scope, setScope, visible, total }) {
    const opts = [
      { id: "required", label: "Required" },
      { id: "all", label: "All fields" },
    ];
    return React.createElement("div", { className: "scope-bar" },
      React.createElement("div", { className: "scope-info" },
        React.createElement("span", { className: "scope-title" }, "Fields shown"),
        React.createElement("span", { className: "scope-count" }, visible + " of " + total + " fields")
      ),
      React.createElement("div", { className: "seg scope-seg", role: "radiogroup", "aria-label": "Field priority" },
        opts.map((o) =>
          React.createElement("button", {
            key: o.id, role: "radio", "aria-checked": scope === o.id,
            className: scope === o.id ? "on" : "",
            onClick: () => setScope(o.id),
          }, o.label)
        )
      )
    );
  }

  function missingFields(s) {
    return REQUIRED.filter((k) => !String(s[k] || "").trim());
  }

  function metaItem(k, v) {
    return React.createElement("div", { className: "metaitem", key: k },
      React.createElement("span", { className: "mk" }, k),
      React.createElement("span", { className: "mv" }, v));
  }

  function SingleHeader({ sample }) {
    const url = thumbFor(sample);
    const n = Number(sample.needles_per_10cm), r = Number(sample.rows_per_10cm);
    const hasGauge = n > 0 && r > 0;
    const clamp = (v) => Math.max(6, Math.min(40, v));
    // cell size faithful to gauge: a single px/cm scale, so wales (10/n) and rows (10/r) keep their aspect
    const cw = hasGauge ? clamp(460 / n) : 14;
    const ch = hasGauge ? clamp(460 / r) : 11;
    const gauge = (String(sample.needles_per_10cm).trim() && String(sample.rows_per_10cm).trim())
      ? sample.needles_per_10cm + " \u00d7 " + sample.rows_per_10cm
      : "not set";
    return React.createElement("div", { className: "single-head" },
      React.createElement("div", { className: "sh-preview" },
        React.createElement("img", { src: url, alt: "Scan preview of " + sample.sample_id }),
        React.createElement("div", {
          className: "grid-overlay" + (hasGauge ? "" : " empty"),
          style: { "--cw": cw + "px", "--ch": ch + "px" },
          title: hasGauge ? "Detected lattice: " + sample.needles_per_10cm + " wales \u00d7 " + sample.rows_per_10cm + " rows / 10 cm" : "Run detection to preview the lattice",
        }, hasGauge ? null : React.createElement("span", { className: "go-hint" }, "detect to\npreview grid")),
        React.createElement("span", { className: "badge-tl" }, sample.structure_ref || "scan")
      ),
      React.createElement("div", { className: "sh-id" },
        React.createElement("div", { className: "sh-top" },
          React.createElement("span", { className: "crumbs" }, "Sample"),
          React.createElement(StatusChip, { status: sample.status })
        ),
        React.createElement("h2", null, sample.sample_id || "(untitled)"),
        React.createElement("div", { className: "sh-files" },
          React.createElement("span", { className: "filechip", title: sample.source_image_name },
            IconEl("image", { size: 13 }),
            React.createElement("span", { className: "v" }, sample.source_image_name || "no image")),
          sample.hasYaml
            ? React.createElement("span", { className: "filechip", title: sample.yamlName },
                IconEl("doc", { size: 13 }),
                React.createElement("span", { className: "v" }, sample.yamlName))
            : React.createElement("span", { className: "filechip missing" },
                IconEl("doc", { size: 13 }),
                React.createElement("span", { className: "v" }, "no sidecar YAML"))
        ),
        React.createElement("div", { className: "sh-meta" },
          metaItem("Machine", sample.machine_ref || "\u2014"),
          metaItem("Structure", sample.structure_ref || "\u2014"),
          metaItem("Gauge / 10cm", gauge),
          sample.elapsed != null ? metaItem("Last run", sample.elapsed.toFixed(1) + "s") : null
        )
      )
    );
  }

  function BatchHeader({ targets }) {
    const shown = targets.slice(0, 4);
    const extra = targets.length - shown.length;
    return React.createElement("div", { className: "batch-head" },
      React.createElement("div", { className: "bh-ic" }, IconEl("layers", { size: 20 })),
      React.createElement("div", { style: { flex: 1, minWidth: 0 } },
        React.createElement("h2", null, "Editing " + targets.length + " samples together"),
        React.createElement("p", null, "Any change applies to all ", String(targets.length),
          ". Fields that differ show ", React.createElement("b", null, "Multiple"), ".")
      ),
      React.createElement("div", { className: "stack" },
        shown.map((s) => React.createElement("div", {
          key: s.id, className: "av", style: { backgroundImage: `url(${thumbFor(s)})` }, title: s.sample_id })),
        extra > 0 ? React.createElement("div", { className: "av more" }, "+" + extra) : null
      )
    );
  }

  function Inspector(props) {
    const { targets, batch, onChange, onSaveYaml, onReload, onReset, onAttach, onDetect } = props;
    const [scope, setScope] = useState("required");

    if (targets.length === 0) {
      return React.createElement("div", { className: "inspector" },
        React.createElement("div", { className: "insp-empty" },
          React.createElement("div", { className: "big-ic" }, IconEl("scan", { size: 32 })),
          React.createElement("div", null,
            React.createElement("b", { style: { display: "block", color: "var(--text-muted)", fontSize: 15 } }, "No sample selected"),
            React.createElement("span", null, "Pick a sample to review its scan and metadata, or select several to edit together."))
        ));
    }

    const visibleCount = FIELDS.filter((f) => tierVisible(f.tier, scope)).length;

    return React.createElement("div", { className: "inspector" },
      batch ? React.createElement(BatchHeader, { targets })
            : React.createElement(SingleHeader, { sample: targets[0] }),

      React.createElement(ScopeBar, { scope, setScope, visible: visibleCount, total: FIELDS.length }),

      React.createElement(MetadataForm, { targets, onChange, scope, onDetect }),

      React.createElement("div", { className: "form-actions" },
        React.createElement("button", { className: "btn sm", onClick: onSaveYaml },
          IconEl("save", { size: 14 }), !batch ? "Save YAML" : "Save YAML (" + targets.length + ")"),
        React.createElement("button", { className: "btn sm subtle", onClick: onAttach, title: "Attach a YAML sidecar" },
          IconEl("link", { size: 14 }), "Attach"),
        React.createElement("button", { className: "btn sm ghost", onClick: onReload, title: "Reload from YAML" },
          IconEl("refresh", { size: 14 })),
        React.createElement("button", { className: "btn sm ghost", onClick: onReset, title: "Reset to defaults" },
          IconEl("reset", { size: 14 }))
      )
    );
  }

  Object.assign(window, { Inspector, missingFields });
})();
