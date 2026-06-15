/* Simple stroke icon set + chevron data-URI for selects */
(function () {
  const S = ({ d, size = 16, fill, stroke = 2, children, ...rest }) =>
    React.createElement(
      "svg",
      {
        width: size, height: size, viewBox: "0 0 24 24",
        fill: fill || "none", stroke: "currentColor",
        strokeWidth: stroke, strokeLinecap: "round", strokeLinejoin: "round",
        ...rest,
      },
      children || React.createElement("path", { d })
    );

  const P = (d, extra) => (props) => React.createElement(S, { ...props, ...extra }, typeof d === "function" ? d() : React.createElement("path", { d }));

  const Icon = {
    image: P("M3 5.5A1.5 1.5 0 0 1 4.5 4h15A1.5 1.5 0 0 1 21 5.5v13A1.5 1.5 0 0 1 19.5 20h-15A1.5 1.5 0 0 1 3 18.5z M3 16l5-5 4 4 3-3 6 6", null),
    imageSimple: () => (p) => null,
    doc: P("M14 3v5h5 M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"),
    plus: P("M12 5v14 M5 12h14"),
    trash: P("M4 7h16 M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2 M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"),
    play: (p) => React.createElement(S, { ...p, fill: "currentColor", stroke: "none" }, React.createElement("path", { d: "M7 4.5v15l13-7.5z" })),
    folder: P("M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"),
    folderOpen: P("M3 7a2 2 0 0 1 2-2h4l2 2.5h6a2 2 0 0 1 2 2H8a2 2 0 0 0-1.9 1.4L3.5 18 M3 7v10.5"),
    check: P("M5 12.5l4.5 4.5L19 7"),
    checkSmall: P("M5 12l4 4 10-10"),
    alert: P("M12 3l9.5 16.5a1 1 0 0 1-.87 1.5H3.37a1 1 0 0 1-.87-1.5z M12 9.5v4.5 M12 17.5h.01"),
    x: P("M6 6l12 12 M18 6L6 18"),
    chevDown: P("M6 9l6 6 6-6"),
    chevRight: P("M9 6l6 6-6 6"),
    sun: () => (
      React.createElement(React.Fragment, null,
        React.createElement("circle", { cx: 12, cy: 12, r: 4 }),
        React.createElement("path", { d: "M12 2v2 M12 20v2 M4.9 4.9l1.4 1.4 M17.7 17.7l1.4 1.4 M2 12h2 M20 12h2 M4.9 19.1l1.4-1.4 M17.7 6.3l1.4-1.4" })
      )),
    moon: P("M21 12.8A8.5 8.5 0 1 1 11.2 3a6.5 6.5 0 0 0 9.8 9.8z"),
    search: () => React.createElement(React.Fragment, null,
      React.createElement("circle", { cx: 11, cy: 11, r: 7 }),
      React.createElement("path", { d: "M20 20l-3.5-3.5" })),
    sliders: P("M4 6h10 M18 6h2 M4 12h2 M10 12h10 M4 18h8 M16 18h4 M14 4v4 M6 10v4 M12 16v4"),
    layers: P("M12 3l9 5-9 5-9-5z M3 13l9 5 9-5 M3 16.5l9 5 9-5"),
    spinner: () => React.createElement("path", { d: "M12 3a9 9 0 1 0 9 9", opacity: 1 }),
    droplet: P("M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"),
    dropletOff: () => React.createElement(React.Fragment, null,
      React.createElement("path", { d: "M12 3s6 6.5 6 11a6 6 0 0 1-9.6 4.8" }),
      React.createElement("path", { d: "M6.3 9.6C6.1 10.6 6 11.4 6 12a6 6 0 0 0 2 4.5" }),
      React.createElement("path", { d: "M4 4l16 16" })),
    grid: P("M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z"),
    save: P("M5 4h11l3 3v13H5z M8 4v5h7V4 M8 20v-6h8v6"),
    refresh: P("M21 8a9 9 0 0 0-15.5-2.5L3 8 M3 4v4h4 M3 16a9 9 0 0 0 15.5 2.5L21 16 M21 20v-4h-4"),
    reset: P("M3 12a9 9 0 1 0 3-6.7L3 8 M3 3v5h5"),
    info: () => React.createElement(React.Fragment, null,
      React.createElement("circle", { cx: 12, cy: 12, r: 9 }),
      React.createElement("path", { d: "M12 11v5 M12 8h.01" })),
    edit: P("M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17z"),
    link: P("M9 15l6-6 M10.5 6.5l1-1a4 4 0 0 1 6 6l-1 1 M13.5 17.5l-1 1a4 4 0 0 1-6-6l1-1"),
    minus: P("M5 12h14"),
    square: () => React.createElement("rect", { x: 5, y: 5, width: 14, height: 14, rx: 2 }),
    tag: P("M3 12V5a2 2 0 0 1 2-2h7l9 9-9 9z M7.5 7.5h.01"),
    ruler: P("M3 8l5-5 13 13-5 5z M7 7l2 2 M10 4l2 2 M4 10l2 2 M13 7l2 2 M7 13l2 2"),
    user: () => React.createElement(React.Fragment, null,
      React.createElement("circle", { cx: 12, cy: 8, r: 4 }),
      React.createElement("path", { d: "M4 20a8 8 0 0 1 16 0" })),
    scan: P("M4 8V6a2 2 0 0 1 2-2h2 M16 4h2a2 2 0 0 1 2 2v2 M20 16v2a2 2 0 0 1-2 2h-2 M8 20H6a2 2 0 0 1-2-2v-2 M4 12h16"),
    inbox: P("M3 13h5l1.5 3h5L21 13 M3 13l3-8h12l3 8v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"),
    yarn: () => React.createElement(React.Fragment, null,
      React.createElement("circle", { cx: 12, cy: 12, r: 8 }),
      React.createElement("path", { d: "M8 5c3 4 3 6 0 14 M16 5c-3 4-3 6 0 14 M4.5 9c5 1 10 1 15 0 M4.5 15c5-1 10-1 15 0" })),
    minimize: P("M5 12h14"),
    maximizeWin: () => React.createElement("rect", { x: 5, y: 5, width: 14, height: 14, rx: 1 }),
  };

  function IconEl(name, props) {
    const Comp = Icon[name];
    if (!Comp) return null;
    const { size = 16, stroke, ...rest } = props || {};
    return React.createElement(S, { size, stroke: stroke || 2, ...rest }, Comp());
  }

  // chevron data-uri for <select>
  function setChevron() {
    const stroke = getComputedStyle(document.documentElement).getPropertyValue("--text-faint").trim() || "#888";
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='${stroke}' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><path d='M6 9l6 6 6-6'/></svg>`;
    document.documentElement.style.setProperty("--chev", `url("data:image/svg+xml,${encodeURIComponent(svg)}")`);
  }

  window.IconEl = IconEl;
  window.IconCat = Icon;
  window.setChevron = setChevron;
})();
