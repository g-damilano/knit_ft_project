/* Data model — final recommended field set, tiered by priority */
(function () {
  const OPTS = {
    measurement_state: ["measured", "estimated", "target", "nominal"],
    gauge_source: ["image analysis", "manual count", "datasheet", "operator entry"],
    machine_ref: ["Benchmark scan", "Shima SES", "Stoll ADF", "Brother KH-970"],
    bed_setup: ["single bed", "double bed", "rib", "interlock", "links-links"],
    structure_ref: ["plain / stockinette", "rib 1x1", "rib 2x2", "fuzzy / brushed", "cable", "tuck", "intarsia"],
    axis_order: ["needle / row", "row / needle"],
    manual_override: ["off", "on"],
  };

  /* Field schema drives the metadata form. tier ∈ required | optional
     A measured gauge (needles/rows per 10 cm) is only meaningful once the
     swatch it came from is identifiable — so the lattice gauge AND the fields
     that identify the swatch (yarn, tension, machine, structure…) are all
     required together. Everything else is optional / advanced detail. */
  const FIELDS = [
    // ---- Required: the lattice gauge + what makes the swatch identifiable ----
    { key: "needles_per_10cm",  label: "Needles / 10 cm",   tier: "required", type: "num", unit: "wales", mono: true, gauge: true },
    { key: "rows_per_10cm",     label: "Rows / 10 cm",      tier: "required", type: "num", unit: "rows", mono: true, gauge: true },
    // measurement_state + gauge_source are set automatically (detection vs manual) and shown in the card, not edited
    { key: "measurement_state", label: "Measurement state", tier: "required", type: "select" },
    { key: "gauge_source",      label: "Gauge source",      tier: "required", type: "select" },
    { key: "sample_id",         label: "Sample ID",         tier: "required", type: "text", mono: true, placeholder: "sample" },
    { key: "yarn_ref",          label: "Yarn",              tier: "required", type: "text", placeholder: "e.g. Cima 4/15" },
    { key: "tension_ref",       label: "Carriage tension",  tier: "required", type: "text", mono: true, placeholder: "n/a" },
    { key: "yarn_tension",      label: "Yarn tension",      tier: "required", type: "text", mono: true, placeholder: "n/a" },
    { key: "machine_ref",       label: "Machine",           tier: "required", type: "select" },
    { key: "bed_setup",         label: "Bed setup",         tier: "required", type: "select" },
    { key: "structure_ref",     label: "Structure",         tier: "required", type: "select" },

    // ---- Lattice-detection outputs (shown inside the detection card, fixed by the script) ----
    // axis_order: orientation, defined once (a/b or b/a). confidence: numeric, from the script.
    // needle/row period are computed in cm from the /10 cm values, so they aren't stored fields.
    { key: "axis_order",        label: "Axis order",        tier: "optional", type: "seg" },
    { key: "confidence",        label: "Confidence",        tier: "optional", type: "num" },

    // ---- Optional / advanced ----
    { key: "weighting_ref",     label: "Weighting",         tier: "optional", type: "num", unit: "g/needle", mono: true, placeholder: "0" },
    { key: "dye_lot",           label: "Dye lot",           tier: "optional", type: "text", mono: true, placeholder: "n/a" },
    { key: "fibre_composition", label: "Fibre composition", tier: "optional", type: "text", placeholder: "e.g. 100% merino wool", span: true },
    { key: "yarn_count",        label: "Yarn count",        tier: "optional", type: "text", mono: true, placeholder: "e.g. 2/30" },
    { key: "thread_count",      label: "Thread count",      tier: "optional", type: "num", unit: "strands", mono: true, placeholder: "1" },
    { key: "colour_ref",        label: "Colour",            tier: "optional", type: "text", placeholder: "e.g. ecru" },
    { key: "notes",             label: "Notes",             tier: "optional", type: "textarea", span: true },
  ];

  const TIERS = [
    { id: "required",    label: "Required \u2014 lattice gauge + swatch identity", icon: "ruler" },
    { id: "optional",    label: "Optional / advanced",                             icon: "sliders" },
  ];

  /* Plain-language explanations surfaced via the info (i) dots in the UI. */
  const INFO = {
    needles_per_10cm: "Wales \u2014 the stitch columns \u2014 counted across 10 cm of fabric width. This is the horizontal stitch density.",
    rows_per_10cm: "Courses \u2014 the stitch rows \u2014 counted up 10 cm of fabric height. This is the vertical stitch density.",
    measurement_state: "How the gauge was obtained. Set automatically: \u201cmeasured\u201d when read from detection, and kept \u201cmeasured\u201d after a manual correction.",
    gauge_source: "Where the gauge came from. Set automatically: \u201cimage analysis\u201d when the lattice detector measured it, or \u201cmanual entry\u201d when typed by hand.",
    axis_order: "Which image axis maps to needles (wales) versus rows. The detector fixes this once per scan \u2014 flip it to row / needle if they came out swapped.",
    confidence: "The detection script\u2019s confidence score (0\u2013100%) that the lattice it locked onto matches the real stitch grid. Low scores want a manual check.",
    needle_period: "Spacing between neighbouring wales, in cm. Fixed by the gauge: 10 cm \u00f7 (needles / 10 cm).",
    row_period: "Spacing between neighbouring courses, in cm. Fixed by the gauge: 10 cm \u00f7 (rows / 10 cm).",
    sample_id: "Unique identifier for this swatch sample.",
    source_image_name: "Filename of the scan this card was measured from.",
    yarn_ref: "The yarn used \u2014 its name or supplier reference.",
    tension_ref: "The carriage stitch-cam / tension-dial setting used to knit the swatch. Higher numbers make looser, longer stitches.",
    yarn_tension: "Tension on the yarn as it feeds into the machine (the tension mast / spring). It affects loop size and stitch evenness.",
    machine_ref: "The knitting machine or scanner this sample came from.",
    bed_setup: "Needle-bed configuration used: single bed, double bed, rib, interlock or links-links.",
    structure_ref: "The stitch structure knitted \u2014 e.g. plain stockinette, 1\u00d71 rib, cable, tuck.",
    yarn_count: "Yarn grist in count / ply notation, e.g. 2/30 = two plies of a 30-count single. First number = plies, second = base count (higher is finer).",
    thread_count: "How many strands of the same yarn are held together and knitted as one (1 = single strand, 2 = doubled, and so on).",
    weighting_ref: "Take-down weight applied per needle to keep the fabric under tension while knitting, in grams per needle.",
    fibre_composition: "What the yarn is made of, e.g. 100% merino wool or 90% cashmere / 10% silk.",
    dye_lot: "The dye-lot code for the yarn \u2014 useful when matching colour across cones.",
    colour_ref: "Colour name or reference for the swatch.",
  };

  const REQUIRED = FIELDS.filter((f) => f.tier === "required").map((f) => f.key);
  const LABELS = {}; FIELDS.forEach((f) => { LABELS[f.key] = f.label; });
  const BLANK = {}; FIELDS.forEach((f) => { BLANK[f.key] = ""; });

  let uid = 100;
  function makeSample(p) {
    uid += 1;
    return Object.assign({}, BLANK, {
      id: "s" + uid,
      // low-friction non-empty defaults for selects/toggles
      machine_ref: "Benchmark scan",
      bed_setup: "single bed",
      structure_ref: "plain / stockinette",
      axis_order: "needle / row",
      manual_override: "off",
      thread_count: "1",
      detect_state: "",
      status: "ready",   // ready | needs | queued | running | done | failed
      elapsed: null,
      progress: 0,
      hasYaml: false,
      yamlName: "",
    }, p);
  }

  const SEED = [
    makeSample({
      source_image_name: "merino_dk_18g_001.tif", sample_id: "merino_dk_18g_001",
      detect_state: "detected",
      measurement_state: "measured", gauge_source: "image analysis",
      needles_per_10cm: "32", rows_per_10cm: "44",
      machine_ref: "Shima SES", bed_setup: "single bed", structure_ref: "plain / stockinette",
      yarn_ref: "Cima 4/15", tension_ref: "8.2", yarn_tension: "3.5", recipe_ref: "DK-standard", confidence: "0.96",
      axis_order: "needle / row",
      fibre_composition: "100% merino wool", yarn_count: "4/15", colour_ref: "moss",
      dye_lot: "LC-2231", weighting_ref: "0.5", operator: "G. Rossi",
      hasYaml: true, yamlName: "merino_dk_18g_001.yaml",
      notes: "Reference scan for the autumn merino line.",
    }),
    makeSample({
      source_image_name: "cashmere_fuzzy_02.png", sample_id: "cashmere_fuzzy_02",
      detect_state: "detected",
      measurement_state: "measured", gauge_source: "image analysis",
      needles_per_10cm: "28", rows_per_10cm: "38",
      machine_ref: "Stoll ADF", bed_setup: "single bed", structure_ref: "fuzzy / brushed",
      yarn_ref: "Baby Soft 2/28", tension_ref: "6.9", yarn_tension: "3.0", recipe_ref: "fine-fuzzy", confidence: "0.82",
      fibre_composition: "90% cashmere / 10% silk", yarn_count: "2/28", colour_ref: "dove",
      thread_count: "2",
      operator: "G. Rossi", hasYaml: true, yamlName: "cashmere_fuzzy_02.yaml",
    }),
    makeSample({
      source_image_name: "cotton_rib_A14.jpg", sample_id: "cotton_rib_A14",
      measurement_state: "", gauge_source: "", needles_per_10cm: "", rows_per_10cm: "",
      machine_ref: "Benchmark scan", bed_setup: "rib", structure_ref: "rib 1x1",
      status: "needs",
    }),
    makeSample({
      source_image_name: "lambswool_test_07.tif", sample_id: "lambswool_test_07",
      detect_state: "failed",
      measurement_state: "measured", gauge_source: "image analysis",
      needles_per_10cm: "30", rows_per_10cm: "",
      machine_ref: "Shima SES", bed_setup: "single bed", structure_ref: "plain / stockinette",
      yarn_ref: "Geelong 2/30", tension_ref: "7.5", yarn_tension: "3.2", operator: "M. Conti",
      status: "needs",
    }),
    makeSample({
      source_image_name: "alpaca_blend_22.png", sample_id: "alpaca_blend_22",
      detect_state: "manual",
      measurement_state: "measured", gauge_source: "manual count",
      needles_per_10cm: "26", rows_per_10cm: "34",
      machine_ref: "Stoll ADF", bed_setup: "single bed", structure_ref: "fuzzy / brushed",
      yarn_ref: "Suri 1/15", tension_ref: "5.8", yarn_tension: "2.5", recipe_ref: "fine-fuzzy", confidence: "0.95",
      fibre_composition: "70% alpaca / 30% nylon", yarn_count: "1/15", manual_override: "on",
      operator: "M. Conti", hasYaml: true, yamlName: "alpaca_blend_22.yaml",
    }),
    makeSample({
      source_image_name: "cable_aran_15g.tiff", sample_id: "cable_aran_15g",
      detect_state: "detected",
      measurement_state: "measured", gauge_source: "image analysis",
      needles_per_10cm: "22", rows_per_10cm: "30",
      machine_ref: "Brother KH-970", bed_setup: "double bed", structure_ref: "cable",
      yarn_ref: "Aran Tweed", tension_ref: "9.4", yarn_tension: "4.0", recipe_ref: "heavy-cable", confidence: "0.80",
      fibre_composition: "100% lambswool", operator: "G. Rossi",
    }),
  ];

  window.KGModel = {
    OPTS, FIELDS, TIERS, REQUIRED, LABELS, INFO, makeSample, SEED,
    nextNames: (i) => `dropped_scan_${String(i).padStart(3, "0")}`,
  };
})();
