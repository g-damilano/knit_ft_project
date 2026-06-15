/* Procedural knit-swatch thumbnail generator.
   Produces a data URL that reads as a scanned stockinette fabric square,
   tinted per-sample. Cached by key. */
(function () {
  const cache = new Map();

  function hashStr(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function rng(seed) {
    let s = seed >>> 0;
    return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  }

  // hue in degrees, returns {bg, light, dark} css rgb via hsl conversion done by canvas
  function knitSwatch(key, opts = {}) {
    const ck = key + "|" + (opts.fuzzy ? "f" : "p");
    if (cache.has(ck)) return cache.get(ck);

    const W = 360, H = 270;
    const c = document.createElement("canvas");
    c.width = W; c.height = H;
    const ctx = c.getContext("2d");
    const rand = rng(hashStr(key) || 7);

    const hue = Math.floor(rand() * 360);
    const sat = 22 + rand() * 30;          // muted yarn colors
    const baseL = 52 + rand() * 22;
    const hsl = (l, dh = 0, ds = 0) => `hsl(${(hue + dh + 360) % 360} ${Math.max(8, sat + ds)}% ${Math.max(6, Math.min(94, l))}%)`;

    // paper/scan background (very light, slightly warm)
    ctx.fillStyle = "#efece6";
    ctx.fillRect(0, 0, W, H);

    // fabric region inset (like a swatch laid on a scanner bed)
    const pad = 16;
    const fx = pad, fy = pad, fw = W - pad * 2, fh = H - pad * 2;

    // base fill
    ctx.fillStyle = hsl(baseL);
    roundRect(ctx, fx, fy, fw, fh, 8);
    ctx.fill();
    ctx.save();
    roundRect(ctx, fx, fy, fw, fh, 8);
    ctx.clip();

    // stockinette: columns of V stitches
    const cols = 18;
    const sw = fw / cols;
    const rows = Math.round(fh / (sw * 0.78));
    const sh = fh / rows;

    for (let r = 0; r < rows; r++) {
      for (let col = 0; col < cols; col++) {
        const x = fx + col * sw;
        const y = fy + r * sh;
        const jitter = (rand() - 0.5) * (opts.fuzzy ? 3.4 : 1.0);
        const lv = baseL + (rand() - 0.5) * (opts.fuzzy ? 16 : 7);

        // the V leg shadows / highlights
        ctx.lineCap = "round";
        ctx.lineWidth = sw * (opts.fuzzy ? 0.46 : 0.40);

        // dark right leg
        ctx.strokeStyle = hsl(lv - 14, 0, 2);
        ctx.beginPath();
        ctx.moveTo(x + sw * 0.5 + jitter, y + sh * 0.12);
        ctx.lineTo(x + sw * 0.92 + jitter, y + sh * 0.92);
        ctx.stroke();
        // dark left leg
        ctx.beginPath();
        ctx.moveTo(x + sw * 0.5 + jitter, y + sh * 0.12);
        ctx.lineTo(x + sw * 0.08 + jitter, y + sh * 0.92);
        ctx.stroke();

        // highlight overlay on legs
        ctx.lineWidth = sw * 0.16;
        ctx.strokeStyle = hsl(lv + 16, 0, -4);
        ctx.beginPath();
        ctx.moveTo(x + sw * 0.5 + jitter, y + sh * 0.18);
        ctx.lineTo(x + sw * 0.86 + jitter, y + sh * 0.84);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x + sw * 0.5 + jitter, y + sh * 0.18);
        ctx.lineTo(x + sw * 0.14 + jitter, y + sh * 0.84);
        ctx.stroke();
      }
    }

    // fuzzy halo
    if (opts.fuzzy) {
      ctx.globalAlpha = 0.10;
      for (let i = 0; i < 1400; i++) {
        ctx.fillStyle = hsl(baseL + (rand() - 0.5) * 30);
        const px = fx + rand() * fw, py = fy + rand() * fh;
        ctx.fillRect(px, py, 1.4, 1.4);
      }
      ctx.globalAlpha = 1;
    }

    // soft vignette / scan lighting
    const g = ctx.createRadialGradient(W * 0.42, H * 0.38, 40, W * 0.5, H * 0.5, W * 0.7);
    g.addColorStop(0, "rgba(255,255,255,0.10)");
    g.addColorStop(1, "rgba(0,0,0,0.16)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.restore();

    // subtle inner border
    ctx.strokeStyle = "rgba(0,0,0,0.10)";
    ctx.lineWidth = 1;
    roundRect(ctx, fx + 0.5, fy + 0.5, fw - 1, fh - 1, 8);
    ctx.stroke();

    const url = c.toDataURL("image/jpeg", 0.82);
    cache.set(ck, url);
    return url;
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  window.knitSwatch = knitSwatch;
})();
