/* Run dock: collapsible log (left) · run status + progress · Run controls (right) */
(function () {
  const { useRef, useEffect } = React;

  function RunDock(props) {
    const { running, statusText, done, total, logOpen, onToggleLog, lines,
            onSaveSelected, onSaveAll, selCount, sampleCount } = props;
    const logRef = useRef(null);
    useEffect(() => {
      if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
    }, [lines, logOpen]);

    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    const allDone = total > 0 && done === total && !running;

    return React.createElement("div", { className: "dock" },
      React.createElement("div", { className: "dock-bar" + (running ? " live" : "") },
        // log toggle — left
        React.createElement("button", { className: "log-toggle", onClick: onToggleLog, "aria-expanded": logOpen },
          IconEl(logOpen ? "chevDown" : "chevRight", { size: 14 }),
          "Log",
          lines.length ? React.createElement("span", { className: "log-count" }, String(lines.length)) : null
        ),

        React.createElement("div", { className: "divider" }),

        // status + overall progress
        React.createElement("div", { className: "run-status" },
          React.createElement("span", { className: "sdot" }),
          React.createElement("span", null, running ? statusText : (statusText || "Idle"))),

        total > 0
          ? React.createElement(React.Fragment, null,
              React.createElement("div", { className: "ovr" + (allDone ? " done" : "") },
                React.createElement("i", { style: { width: pct + "%" } })),
              React.createElement("span", { className: "frac" }, done + " / " + total))
          : null,

        React.createElement("div", { className: "spacer" }),

        // save controls — flush right
        React.createElement("button", {
          className: "btn", onClick: onSaveSelected, disabled: running || selCount === 0,
        }, IconEl("save", { size: 13 }), "Save selected" + (selCount ? " (" + selCount + ")" : "")),
        React.createElement("button", {
          className: "btn primary", onClick: onSaveAll, disabled: running || sampleCount === 0,
        }, IconEl("save", { size: 13 }), "Save all")
      ),

      logOpen
        ? React.createElement("div", { className: "logwrap", style: { height: 180 } },
            React.createElement("div", { className: "log", ref: logRef },
              lines.length === 0
                ? React.createElement("div", { className: "ln", style: { color: "var(--text-faint)" } },
                    "Drag-drop enabled \u2014 drop images, YAML files, or an output folder onto the window. Logs from analysis and delivery appear here.")
                : lines.map((l, i) =>
                    React.createElement("div", { key: i, className: "ln " + (l.kind || "") },
                      React.createElement("span", { className: "ts" }, l.ts),
                      l.text))
            ))
        : null
    );
  }

  window.RunDock = RunDock;
})();
