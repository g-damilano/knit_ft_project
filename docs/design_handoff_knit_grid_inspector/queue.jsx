/* Queue panel: status chips, sample cards, multi-select, bulk bar, dropzone */
(function () {
  const { useState } = React;

  const STATUS = {
    ready:   { label: "Ready",     cls: "ready",   icon: "check" },
    needs:   { label: "Needs info", cls: "needs",  icon: "alert" },
    queued:  { label: "Queued",    cls: "queued",  icon: "inbox" },
    running: { label: "Running",   cls: "running", icon: "spinner" },
    done:    { label: "Done",      cls: "done",    icon: "check" },
    failed:  { label: "Failed",    cls: "failed",  icon: "x" },
  };

  function StatusChip({ status, size }) {
    const s = STATUS[status] || STATUS.ready;
    return React.createElement("span", { className: "chip " + s.cls },
      status === "running"
        ? React.createElement("span", { className: "ic" },
            IconEl("spinner", { size: size || 12, className: "spin" }))
        : React.createElement("span", { className: "dot" }),
      s.label
    );
  }

  function thumbFor(sample) {
    return knitSwatch(sample.source_image_name || sample.sample_id || sample.id, { fuzzy: /fuzz|alpaca|cashmere|brush/i.test((sample.structure_ref || "") + (sample.source_image_name || "")) });
  }

  function SampleCard({ sample, selected, anySelected, onRowClick, onToggle }) {
    const meta = sample.yarn_ref || sample.structure_ref || "\u2014";

    return React.createElement("div", {
      className: "scard" + (selected ? " sel" : ""),
      onClick: (e) => onRowClick(sample.id, e),
      role: "option", "aria-selected": selected, tabIndex: 0,
      onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onRowClick(sample.id, e); } },
    },
      React.createElement("button", {
        className: "cbox" + (selected ? " on" : ""),
        onClick: (e) => { e.stopPropagation(); onToggle(sample.id, e); },
        "aria-label": selected ? "Deselect" : "Select", "aria-pressed": selected,
      }, IconEl("checkSmall", { size: 13 })),

      React.createElement("div", {
        className: "thumb",
        style: { backgroundImage: `url(${thumbFor(sample)})` },
      }),

      React.createElement("div", { className: "body" },
        React.createElement("div", { className: "sid" }, sample.sample_id || "(untitled)"),
        React.createElement("div", { className: "sub" },
          React.createElement("span", { className: "fname" }, sample.source_image_name || "no image"),
          React.createElement("span", { className: "dot" }),
          React.createElement("span", null, meta)
        )
      ),

      React.createElement("div", { className: "right" },
        React.createElement(StatusChip, { status: sample.status }),
        sample.elapsed != null
          ? React.createElement("span", { className: "time" }, sample.elapsed.toFixed(1) + "s")
          : null
      ),

      sample.status === "running"
        ? React.createElement("div", { className: "rowbar" },
            React.createElement("i", { style: { width: (sample.progress || 0) + "%" } }))
        : null
    );
  }

  function Dropzone({ big, onAdd, label }) {
    const [over, setOver] = useState(false);
    const stop = (e) => { e.preventDefault(); e.stopPropagation(); };
    return React.createElement("div", {
      className: "dropzone" + (big ? " big" : "") + (over ? " over" : ""),
      onClick: () => onAdd("images"),
      onDragOver: (e) => { stop(e); setOver(true); },
      onDragLeave: () => setOver(false),
      onDrop: (e) => { stop(e); setOver(false); onAdd("images", true); },
      role: "button", tabIndex: 0,
      onKeyDown: (e) => { if (e.key === "Enter") onAdd("images"); },
    },
      React.createElement("div", { className: "dz-ic" }, IconEl(big ? "scan" : "plus", { size: big ? 28 : 20 })),
      React.createElement("div", { className: "dz-text" },
        React.createElement("b", null, big ? "Drop swatch scans to begin" : (label || "Add or drop more scans")),
        React.createElement("small", null, big ? "PNG · JPG · TIFF · WEBP — or YAML sidecars" : "images, YAML, or an output folder")
      )
    );
  }

  function QueuePanel(props) {
    const { samples, selectedIds, onRowClick, onToggle, onSelectAll, onClearSel,
            onAdd, onRemove, onRunSelected, onEditTogether } = props;
    const selCount = selectedIds.length;
    const allOn = samples.length > 0 && selCount === samples.length;
    const someOn = selCount > 0 && !allOn;

    if (samples.length === 0) {
      return React.createElement("div", { className: "queue-col" },
        React.createElement("div", { className: "queue-head" },
          React.createElement("h2", null, "Samples",
            React.createElement("span", { className: "count" }, "0"))),
        React.createElement(Dropzone, { big: true, onAdd }),
        React.createElement("p", { className: "empty-hint" },
          "No samples yet. Add swatch scans and matching ", React.createElement("code", null, ".yaml"),
          " sidecars load automatically.")
      );
    }

    return React.createElement("div", { className: "queue-col" },
      React.createElement("div", { className: "queue-head" },
        React.createElement("h2", null, "Samples",
          React.createElement("span", { className: "count" }, String(samples.length))),
        React.createElement("div", { className: "spacer" }),
        React.createElement("button", {
          className: "checkall",
          onClick: allOn ? onClearSel : onSelectAll,
        },
          React.createElement("span", { className: "cbox" + (allOn ? " on" : someOn ? " mixed" : "") },
            IconEl(someOn ? "minus" : "checkSmall", { size: 13 })),
          allOn ? "Clear" : "Select all")
      ),

      selCount > 1
        ? React.createElement("div", { className: "bulkbar" },
            React.createElement("span", { className: "n" }, selCount + " selected"),
            React.createElement("div", { className: "spacer" }),
            React.createElement("button", { className: "btn sm subtle", onClick: onEditTogether },
              IconEl("edit", { size: 13 }), "Edit together"),
            React.createElement("button", { className: "btn sm ghost danger", onClick: onRemove, "aria-label": "Remove selected" },
              IconEl("trash", { size: 14 }))
          )
        : null,

      React.createElement("div", { className: "queue-list", role: "listbox", "aria-label": "Samples", "aria-multiselectable": true },
        samples.map((s) =>
          React.createElement(SampleCard, {
            key: s.id, sample: s,
            selected: selectedIds.includes(s.id),
            anySelected: selCount > 0,
            onRowClick, onToggle,
          })
        )
      ),

      React.createElement(Dropzone, { onAdd })
    );
  }

  Object.assign(window, { QueuePanel, StatusChip, thumbFor });
})();
