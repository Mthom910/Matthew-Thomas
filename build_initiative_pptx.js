const pptxgen = require("pptxgenjs");
const fs = require("fs");

const D = JSON.parse(fs.readFileSync("initiative_data.json", "utf8"));
const K = D.kpis;

// ── PALETTE ────────────────────────────────────────────────
const NAVY   = "1E3A5F";
const BLUE   = "2E6DB4";
const TEAL   = "028090";
const GREEN  = "059669";
const RED    = "DC2626";
const PURPLE = "7C3AED";
const LIGHT  = "F1F5F9";
const WHITE  = "FFFFFF";
const SLATE  = "64748B";
const AMBER  = "D97706";

// ── FORMATTERS ─────────────────────────────────────────────
const fmtM  = v => { const a = Math.abs(v); if (a >= 1e6) return "$" + (v/1e6).toFixed(2) + "M"; if (a >= 1e3) return "$" + Math.round(v/1e3) + "K"; return "$" + Math.round(v); };
const fmtN  = v => v.toLocaleString();
const fmtPct= v => v.toFixed(1) + "%";
const yoy   = (a,b) => { const d = ((a-b)/b*100); return (d>=0?"+":"")+d.toFixed(1)+"% YoY"; };
const delta = (a,b) => { const d = a - b; return (d>=0?"▲ ":"▼ ") + fmtM(Math.abs(d)); };
const makeShadow = () => ({ type:"outer", color:"000000", blur:8, offset:2, angle:45, opacity:0.10 });

// ── MONTH LABELS ───────────────────────────────────────────
const mLabels26 = D.monthly26.map(m => { const [,mo]=m.month.split("-"); return ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+mo-1]+" 2026"; });
const mLabels25 = D.monthly25.map(m => { const [,mo]=m.month.split("-"); return ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+mo-1]+" 2025"; });
const mRevs26   = D.monthly26.map(m => Math.round(m.rev/1000));
const mRevs25   = D.monthly25.map(m => Math.round(m.rev/1000));
const mJobs26   = D.monthly26.map(m => m.jobs);
const mJobs25   = D.monthly25.map(m => m.jobs);
const mInits26  = D.monthly26.map(m => m.init);

// Bucket data
const bLabels = D.buckets.map(b => b.label);
const bCount26 = D.buckets.map(b => b.count26);
const bCount25 = D.buckets.map(b => b.count25);
const bRev26   = D.buckets.map(b => Math.round(b.rev26/1000));
const bRev25   = D.buckets.map(b => Math.round(b.rev25/1000));

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title  = "Revenue Management Initiative — YTD Results 2026";
pres.author = "Hunter Douglas";

// ─────────────────────────────────────────────────────────
// SLIDE 1 — COVER
// ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };

  // Big teal circle decoration (top right)
  s.addShape(pres.shapes.OVAL, { x:7.8, y:-1.2, w:3.8, h:3.8, fill:{ color:TEAL, transparency:78 }, line:{ color:TEAL, width:0 } });
  s.addShape(pres.shapes.OVAL, { x:8.6, y:-0.4, w:2.2, h:2.2, fill:{ color:BLUE, transparency:60 }, line:{ color:BLUE, width:0 } });

  // Tag
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.55, y:1.0, w:2.6, h:0.32, fill:{ color:TEAL }, rectRadius:0.05, line:{color:TEAL,width:0} });
  s.addText("SENIOR MANAGEMENT BRIEFING", { x:0.55, y:1.0, w:2.6, h:0.32, fontSize:7.5, color:WHITE, bold:true, align:"center", valign:"middle", margin:0, charSpacing:1.5 });

  s.addText("Revenue Management\nInitiative", { x:0.55, y:1.45, w:8.5, h:1.6, fontSize:46, color:WHITE, bold:true, fontFace:"Cambria", lineSpacingMultiple:1.1 });
  s.addText("YTD Performance Review  |  Jan – Jun 2026 vs Jan – Jun 2025", { x:0.55, y:3.15, w:8.5, h:0.4, fontSize:14, color:"A0C4E8", fontFace:"Calibri" });
  s.addText("35–40% Commission Bracket Initiative  ·  $5K+ Job Analysis  ·  Ex-GST", { x:0.55, y:3.6, w:8.5, h:0.35, fontSize:11, color:"7AA8CC", fontFace:"Calibri" });

  // Bottom strip of KPIs
  const cards = [
    { label:"Revenue 2026",  val: fmtM(K.rev26),    sub: yoy(K.rev26,K.rev25) },
    { label:"Jobs Won",      val: fmtN(K.jobs26),   sub: yoy(K.jobs26,K.jobs25) },
    { label:"Initiative Adoption", val: fmtPct(K.init_pct26), sub: `${K.init_jobs26} jobs in 35–40%` },
    { label:"Gross Profit",  val: fmtM(K.gp26),     sub: fmtPct(K.gp_pct26)+" GP%" },
  ];
  cards.forEach((c, i) => {
    const x = 0.55 + i * 2.28;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y:4.35, w:2.1, h:0.95, fill:{ color:WHITE, transparency:90 }, rectRadius:0.08, line:{color:WHITE,transparency:70,width:1} });
    s.addText(c.label, { x, y:4.38, w:2.1, h:0.22, fontSize:7.5, color:"A0C4E8", bold:true, align:"center", charSpacing:0.8, margin:0 });
    s.addText(c.val,   { x, y:4.58, w:2.1, h:0.38, fontSize:20,  color:WHITE,    bold:true, align:"center", fontFace:"Cambria", margin:0 });
    s.addText(c.sub,   { x, y:4.96, w:2.1, h:0.22, fontSize:8,   color:"7AA8CC", align:"center", margin:0 });
  });

  s.addNotes(
    "Welcome to the H1 2026 Revenue Management Initiative update.\n\n" +
    "This presentation covers the performance of the 35–40% commission bracket initiative " +
    "introduced to drive higher-value order conversion. All revenue figures are ex-GST, " +
    "covering confirmed orders (OrderDate) on jobs over $5,000.\n\n" +
    "Key headline: Revenue up " + yoy(K.rev26,K.rev25) + " with initiative bracket adoption growing from " +
    K.init_pct25 + "% to " + K.init_pct26 + "% of all $5K+ jobs."
  );
}

// ─────────────────────────────────────────────────────────
// SLIDE 2 — EXECUTIVE SUMMARY
// ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };

  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.8, fill:{ color:NAVY }, line:{color:NAVY,width:0} });
  s.addText("Executive Summary", { x:0.4, y:0, w:9, h:0.8, fontSize:22, color:WHITE, bold:true, fontFace:"Cambria", valign:"middle", margin:0 });
  s.addText("$5K+ Confirmed Orders  |  Ex-GST  |  Jan–Jun 2026 vs Jan–Jun 2025", { x:0.4, y:0.5, w:9, h:0.3, fontSize:9, color:"A0C4E8", margin:0 });

  const kpis = [
    { title:"Order Intake Revenue", v26:fmtM(K.rev26), v25:fmtM(K.rev25), delta:yoy(K.rev26,K.rev25), col:GREEN, up:K.rev26>K.rev25 },
    { title:"Jobs Won ($5K+)",     v26:fmtN(K.jobs26), v25:fmtN(K.jobs25), delta:yoy(K.jobs26,K.jobs25), col:BLUE, up:K.jobs26>K.jobs25 },
    { title:"Avg Discount (Won)",  v26:fmtPct(K.avg_disc26), v25:fmtPct(K.avg_disc25), delta:((K.avg_disc26-K.avg_disc25)>=0?"+":"")+( K.avg_disc26-K.avg_disc25).toFixed(1)+"pp YoY", col:AMBER, up:false },
    { title:"Gross Profit %",      v26:fmtPct(K.gp_pct26), v25:fmtPct(K.gp_pct25), delta:((K.gp_pct26-K.gp_pct25)>=0?"+":"")+(K.gp_pct26-K.gp_pct25).toFixed(1)+"pp YoY", col:RED, up:false },
  ];

  kpis.forEach((k, i) => {
    const x = 0.3 + i * 2.36;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y:1.0, w:2.2, h:2.15, fill:{ color:LIGHT }, rectRadius:0.12, line:{color:"E2E8F0",width:1}, shadow:makeShadow() });
    s.addText(k.title, { x:x+0.1, y:1.05, w:2.0, h:0.35, fontSize:9, color:SLATE, bold:true, align:"center", margin:0 });
    s.addShape(pres.shapes.RECTANGLE, { x:x+0.75, y:1.38, w:0.7, h:0.04, fill:{color:k.col}, line:{color:k.col,width:0} });
    s.addText(k.v26, { x:x+0.1, y:1.45, w:2.0, h:0.55, fontSize:28, color:k.col, bold:true, fontFace:"Cambria", align:"center", margin:0 });
    s.addText("2026 YTD", { x:x+0.1, y:1.98, w:2.0, h:0.18, fontSize:7.5, color:SLATE, align:"center", margin:0 });
    s.addText("vs "+k.v25+" (2025)", { x:x+0.1, y:2.18, w:2.0, h:0.2, fontSize:8.5, color:"94A3B8", align:"center", margin:0 });
    const dCol = k.up ? GREEN : RED;
    s.addText(k.delta, { x:x+0.1, y:2.42, w:2.0, h:0.22, fontSize:9.5, color:dCol, bold:true, align:"center", margin:0 });
  });

  // Key insight box
  const revGrowth = Math.round((K.rev26-K.rev25)/K.rev25*100*10)/10;
  const initGrowth = Math.round((K.init_pct26-K.init_pct25)*10)/10;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.3, y:3.35, w:9.4, h:1.9, fill:{color:"EFF6FF"}, rectRadius:0.12, line:{color:BLUE,width:1.5}, shadow:makeShadow() });
  s.addText("Key Findings", { x:0.55, y:3.45, w:3, h:0.3, fontSize:10, color:NAVY, bold:true, margin:0 });
  const findings = [
    `Revenue grew ${fmtPct(revGrowth)} YoY to ${fmtM(K.rev26)} on ${K.jobs26} confirmed jobs ($5K+), driven by initiative bracket adoption`,
    `Initiative bracket (35–40% discount) usage surged from ${K.init_pct25}% to ${K.init_pct26}% of won jobs — ${K.init_jobs26} jobs vs ${K.init_jobs25} in 2025 (+${Math.round((K.init_jobs26-K.init_jobs25)/K.init_jobs25*100)}%)`,
    `Appointment-to-order conversion improved from ${K.conv_all25}% to ${K.conv_all26}% — the initiative is supporting close rates`,
    `GP% has eased ${Math.abs(K.gp_pct26-K.gp_pct25).toFixed(1)}pp YoY (${K.gp_pct26}% vs ${K.gp_pct25}%) — gross profit dollars grew ${fmtPct(Math.round((K.gp26-K.gp25)/K.gp25*100*10)/10)} to ${fmtM(K.gp26)}`,
  ];
  s.addText(findings.map((t, i) => [
    { text: `${i+1}. `, options:{ bold:true, color:BLUE } },
    { text: t + (i<findings.length-1?"\n":""), options:{ color:NAVY } },
  ]).flat(), { x:0.55, y:3.8, w:9.0, h:1.35, fontSize:9.5, fontFace:"Calibri", lineSpacingMultiple:1.35 });

  s.addNotes(
    "Executive summary — four headline numbers.\n\n" +
    "1. Revenue: $" + (K.rev26/1e6).toFixed(2) + "M vs $" + (K.rev25/1e6).toFixed(2) + "M, up " + revGrowth + "% YoY. Strong volume growth.\n" +
    "2. Jobs: " + K.jobs26 + " won vs " + K.jobs25 + " — more conversions at higher volumes.\n" +
    "3. Average discount increased from " + K.avg_disc25 + "% to " + K.avg_disc26 + "% — the initiative is working as designed; reps are using the expanded bracket.\n" +
    "4. GP% eased 2pp but gross profit dollars still grew. The trade-off is working — more volume at marginally lower margin is the intended outcome of the initiative."
  );
}

// ─────────────────────────────────────────────────────────
// SLIDE 3 — ORDER INTAKE PERFORMANCE
// ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.8, fill:{color:NAVY}, line:{color:NAVY,width:0} });
  s.addText("Order Intake Performance", { x:0.4, y:0, w:7, h:0.8, fontSize:22, color:WHITE, bold:true, fontFace:"Cambria", valign:"middle", margin:0 });
  s.addText("Monthly revenue trend ($K, ex-GST)  ·  $5K+ confirmed orders", { x:0.4, y:0.5, w:7, h:0.3, fontSize:9, color:"A0C4E8", margin:0 });

  // Stat pills
  const pills = [
    { label:"Total Rev 2026", val: fmtM(K.rev26), col:GREEN },
    { label:"vs 2025", val: yoy(K.rev26,K.rev25), col:GREEN },
    { label:"Jobs 2026", val: fmtN(K.jobs26), col:BLUE },
  ];
  pills.forEach((p, i) => {
    const x = 7.1 + i * 0.01; // right column
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:7.0+(i%2)*1.45, y:0.9+(Math.floor(i/2))*0.58, w:1.38, h:0.48, fill:{color:LIGHT}, rectRadius:0.08, line:{color:"E2E8F0",width:1} });
    s.addText(p.label, { x:7.0+(i%2)*1.45, y:0.92+(Math.floor(i/2))*0.58, w:1.38, h:0.16, fontSize:7, color:SLATE, align:"center", margin:0 });
    s.addText(p.val,   { x:7.0+(i%2)*1.45, y:1.08+(Math.floor(i/2))*0.58, w:1.38, h:0.26, fontSize:14, color:p.col, bold:true, align:"center", fontFace:"Cambria", margin:0 });
  });

  // Combo chart — bars = revenue, line = 2025 revenue
  s.addChart(
    [
      { type: pres.charts.BAR,  data: [{ name:"2026 Revenue ($K)", labels: mLabels26, values: mRevs26 }],
        options: { chartColors:[BLUE], barDir:"col", showValue:true, dataLabelFontSize:8, dataLabelColor:NAVY }
      },
      { type: pres.charts.LINE, data: [{ name:"2025 Revenue ($K)", labels: mLabels26, values: mRevs25 }],
        options: { chartColors:[SLATE], lineSize:2 }
      },
    ],
    { x:0.3, y:0.9, w:6.6, h:4.5,
      chartArea:{ fill:{color:WHITE}, roundedCorners:false },
      catAxisLabelColor:SLATE, valAxisLabelColor:SLATE,
      valGridLine:{ color:"E2E8F0", size:0.5 }, catGridLine:{ style:"none" },
      showLegend:true, legendPos:"b", legendFontSize:9,
    }
  );

  // Monthly jobs mini table
  s.addText("Monthly Jobs Won", { x:7.0, y:2.15, w:2.7, h:0.25, fontSize:8.5, color:NAVY, bold:true, margin:0 });
  const tData = [
    [{ text:"Month", options:{bold:true, fill:{color:NAVY}, color:WHITE} }, { text:"2026", options:{bold:true, fill:{color:NAVY}, color:WHITE, align:"right"} }, { text:"2025", options:{bold:true, fill:{color:NAVY}, color:WHITE, align:"right"} }],
    ...D.monthly26.map((m,i) => {
      const [,mo] = m.month.split("-");
      const lbl = ["Jan","Feb","Mar","Apr","May","Jun"][+mo-1];
      const j25 = D.monthly25[i]?.jobs || 0;
      const up = m.jobs >= j25;
      return [lbl, { text:String(m.jobs), options:{align:"right", bold:true, color:up?GREEN:RED} }, { text:String(j25), options:{align:"right", color:SLATE} }];
    })
  ];
  s.addTable(tData, { x:7.0, y:2.42, w:2.7, h:2.8, colW:[1.0,0.85,0.85],
    border:{pt:0.5, color:"E2E8F0"}, fontSize:9,
    rowH:0.35,
  });

  s.addNotes(
    "Order intake overview.\n\n" +
    "Revenue trend: " + mLabels26.map((m,i)=>`${m}: $${mRevs26[i]}K (2025: $${mRevs25[i]}K)`).join(", ") + "\n\n" +
    "H1 2026 total: " + fmtM(K.rev26) + " vs " + fmtM(K.rev25) + " — " + yoy(K.rev26,K.rev25) + "\n\n" +
    "Note: Q1 and Q2 both showed growth vs prior year. Volume in April–June has moderated slightly but remains ahead of 2025 same period."
  );
}

// ─────────────────────────────────────────────────────────
// SLIDE 4 — INITIATIVE ADOPTION
// ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.8, fill:{color:PURPLE}, line:{color:PURPLE,width:0} });
  s.addText("Initiative Bracket Adoption", { x:0.4, y:0, w:7, h:0.8, fontSize:22, color:WHITE, bold:true, fontFace:"Cambria", valign:"middle", margin:0 });
  s.addText("35–40% discount bracket  ·  $5K+ jobs  ·  jobs count comparison", { x:0.4, y:0.5, w:7, h:0.3, fontSize:9, color:"D8B4FE", margin:0 });

  // Hero numbers
  const pctGrowth = Math.round((K.init_jobs26-K.init_jobs25)/K.init_jobs25*100);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.3, y:0.95, w:4.5, h:2.3, fill:{color:"F5F3FF"}, rectRadius:0.15, line:{color:PURPLE,width:1.5}, shadow:makeShadow() });
  s.addText("2026 — Initiative Jobs", { x:0.45, y:1.02, w:4.2, h:0.3, fontSize:10, color:PURPLE, bold:true, align:"center", margin:0 });
  s.addText(String(K.init_jobs26), { x:0.45, y:1.3, w:4.2, h:0.9, fontSize:72, color:PURPLE, bold:true, fontFace:"Cambria", align:"center", margin:0 });
  s.addText("jobs in 35–40% bracket", { x:0.45, y:2.22, w:4.2, h:0.25, fontSize:10, color:"7C3AED", align:"center", margin:0 });
  s.addText(fmtPct(K.init_pct26)+" of all $5K+ won jobs  ·  +" + pctGrowth + "% vs 2025", { x:0.45, y:2.5, w:4.2, h:0.22, fontSize:9, color:PURPLE, bold:true, align:"center", margin:0 });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:5.0, y:0.95, w:4.5, h:2.3, fill:{color:LIGHT}, rectRadius:0.15, line:{color:"CBD5E1",width:1}, shadow:makeShadow() });
  s.addText("2025 — Initiative Jobs", { x:5.15, y:1.02, w:4.2, h:0.3, fontSize:10, color:SLATE, bold:true, align:"center", margin:0 });
  s.addText(String(K.init_jobs25), { x:5.15, y:1.3, w:4.2, h:0.9, fontSize:72, color:"94A3B8", bold:true, fontFace:"Cambria", align:"center", margin:0 });
  s.addText("jobs in 35–40% bracket", { x:5.15, y:2.22, w:4.2, h:0.25, fontSize:10, color:SLATE, align:"center", margin:0 });
  s.addText(fmtPct(K.init_pct25)+" of all $5K+ won jobs  (prior year baseline)", { x:5.15, y:2.5, w:4.2, h:0.22, fontSize:9, color:SLATE, align:"center", margin:0 });

  // Monthly initiative chart
  s.addChart(
    [
      { type:pres.charts.BAR,  data:[{ name:"All $5K+ Jobs", labels:mLabels26, values:mJobs26 }],
        options:{ chartColors:[BLUE+"99"], barDir:"col" }
      },
      { type:pres.charts.BAR,  data:[{ name:"Initiative Bracket", labels:mLabels26, values:mInits26 }],
        options:{ chartColors:[PURPLE], barDir:"col", showValue:true, dataLabelFontSize:8, dataLabelColor:WHITE }
      },
    ],
    { x:0.3, y:3.4, w:9.4, h:2.1,
      barGrouping:"stacked",
      chartArea:{ fill:{color:WHITE} },
      catAxisLabelColor:SLATE, valAxisLabelColor:SLATE,
      valGridLine:{ color:"E2E8F0", size:0.5 }, catGridLine:{ style:"none" },
      showLegend:true, legendPos:"b", legendFontSize:9,
    }
  );

  s.addNotes(
    "Initiative bracket adoption — the headline story.\n\n" +
    "The 35–40% discount commission bracket was introduced to incentivise consultants to use " +
    "a moderate discount band that balances customer conversion with margin protection.\n\n" +
    "Results: " + K.init_jobs26 + " jobs in 2026 YTD vs " + K.init_jobs25 + " in 2025 — a " + pctGrowth + "% increase.\n" +
    "As a share of won $5K+ jobs, the bracket grew from " + K.init_pct25 + "% to " + K.init_pct26 + "% — " +
    "meaning 1 in 3 high-value orders is now using the initiative bracket.\n\n" +
    "The monthly chart shows consistent adoption across all 6 months of 2026, not a one-off spike."
  );
}

// ─────────────────────────────────────────────────────────
// SLIDE 5 — DISCOUNT BUCKET DISTRIBUTION
// ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.8, fill:{color:NAVY}, line:{color:NAVY,width:0} });
  s.addText("Discount Bracket Distribution", { x:0.4, y:0, w:7, h:0.8, fontSize:22, color:WHITE, bold:true, fontFace:"Cambria", valign:"middle", margin:0 });
  s.addText("Jobs count and revenue shift by discount band  ·  $5K+ jobs  ·  2026 vs 2025", { x:0.4, y:0.5, w:7, h:0.3, fontSize:9, color:"A0C4E8", margin:0 });

  // Jobs count chart
  s.addText("Jobs Won by Bracket", { x:0.3, y:0.88, w:4.5, h:0.28, fontSize:10, color:NAVY, bold:true, margin:0 });
  s.addChart(pres.charts.BAR,
    [
      { name:"2026", labels:bLabels, values:bCount26 },
      { name:"2025", labels:bLabels, values:bCount25 },
    ],
    { x:0.3, y:1.15, w:4.5, h:2.45, barDir:"col", barGrouping:"clustered",
      chartColors:[PURPLE, SLATE+"99"],
      chartArea:{ fill:{color:WHITE} },
      catAxisLabelColor:SLATE, valAxisLabelColor:SLATE,
      valGridLine:{ color:"E2E8F0", size:0.5 }, catGridLine:{ style:"none" },
      showLegend:true, legendPos:"b", legendFontSize:8,
      showValue:true, dataLabelFontSize:7, dataLabelColor:NAVY,
    }
  );

  // Revenue chart
  s.addText("Revenue by Bracket ($K)", { x:5.1, y:0.88, w:4.5, h:0.28, fontSize:10, color:NAVY, bold:true, margin:0 });
  s.addChart(pres.charts.BAR,
    [
      { name:"2026", labels:bLabels, values:bRev26 },
      { name:"2025", labels:bLabels, values:bRev25 },
    ],
    { x:5.1, y:1.15, w:4.5, h:2.45, barDir:"col", barGrouping:"clustered",
      chartColors:[BLUE, SLATE+"99"],
      chartArea:{ fill:{color:WHITE} },
      catAxisLabelColor:SLATE, valAxisLabelColor:SLATE,
      valGridLine:{ color:"E2E8F0", size:0.5 }, catGridLine:{ style:"none" },
      showLegend:true, legendPos:"b", legendFontSize:8,
    }
  );

  // Key observation callout
  const initB = D.buckets[4];
  const revGrowth = Math.round((initB.rev26-initB.rev25)/initB.rev25*100);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.3, y:3.72, w:9.4, h:1.65, fill:{color:"F5F3FF"}, rectRadius:0.1, line:{color:PURPLE,width:1}, shadow:makeShadow() });
  s.addText("★  35–40% Initiative Bracket Spotlight", { x:0.5, y:3.79, w:9, h:0.28, fontSize:10, color:PURPLE, bold:true, margin:0 });
  s.addText([
    { text:`Jobs: `, options:{bold:true} },
    { text:`${K.init_jobs25} → ${K.init_jobs26}  (+${Math.round((K.init_jobs26-K.init_jobs25)/K.init_jobs25*100)}%)   `, options:{} },
    { text:`Revenue: `, options:{bold:true} },
    { text:`${fmtM(initB.rev25)} → ${fmtM(initB.rev26)}  (+${revGrowth}%)   `, options:{} },
    { text:`GP%: `, options:{bold:true} },
    { text:`${Math.round(initB.gp25/initB.rev25*1000)/10}% → ${Math.round(initB.gp26/initB.rev26*1000)/10}%   `, options:{} },
    { text:`Avg Job Value: `, options:{bold:true} },
    { text:`${fmtM(initB.rev26/initB.count26)}`, options:{} },
  ], { x:0.5, y:4.08, w:9, h:0.3, fontSize:10, color:NAVY, margin:0 });
  s.addText(
    "The 30–35% bracket contracted significantly (280 → 206 jobs), suggesting consultants shifted upward into the initiative bracket — " +
    "a positive migration driven by the enhanced commission structure.",
    { x:0.5, y:4.4, w:9, h:0.38, fontSize:9, color:"4B5563", italic:true, margin:0 }
  );

  s.addNotes(
    "Discount bracket distribution — where the shift is happening.\n\n" +
    "The data reveals a clear migration pattern: the 30–35% bracket shrunk from 280 to 206 jobs (-26%), " +
    "while the 35–40% initiative bracket grew from 152 to 246 jobs (+62%). " +
    "This is the intended behaviour — reps are using slightly deeper discounts where needed, " +
    "supported by the enhanced commission rate.\n\n" +
    "Revenue in the initiative bracket: " + fmtM(initB.rev25) + " → " + fmtM(initB.rev26) + " (+" + revGrowth + "%)\n" +
    "Revenue in 30–35% bracket: " + fmtM(D.buckets[3].rev25) + " → " + fmtM(D.buckets[3].rev26) + " (" +
    Math.round((D.buckets[3].rev26-D.buckets[3].rev25)/D.buckets[3].rev25*100) + "% YoY)"
  );
}

// ─────────────────────────────────────────────────────────
// SLIDE 6 — CONVERSION ANALYSIS
// ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.8, fill:{color:TEAL}, line:{color:TEAL,width:0} });
  s.addText("Appointment-to-Order Conversion", { x:0.4, y:0, w:7, h:0.8, fontSize:22, color:WHITE, bold:true, fontFace:"Cambria", valign:"middle", margin:0 });
  s.addText("Won jobs as % of total appointments  ·  Jan–Jun comparison", { x:0.4, y:0.5, w:7, h:0.3, fontSize:9, color:"A5F3FC", margin:0 });

  const convData = [
    { label:"All Orders", v26:K.conv_all26, v25:K.conv_all25, col:TEAL },
    { label:"$5K+ Orders", v26:K.conv_over26, v25:K.conv_over25, col:BLUE },
    { label:"<$5K Orders", v26:K.conv_under26, v25:K.conv_under25, col:AMBER },
  ];

  convData.forEach((c, i) => {
    const x = 0.3 + i * 3.12;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y:0.95, w:2.95, h:2.5, fill:{color:LIGHT}, rectRadius:0.12, line:{color:"E2E8F0",width:1}, shadow:makeShadow() });
    s.addText(c.label, { x:x+0.1, y:1.02, w:2.75, h:0.28, fontSize:10, color:NAVY, bold:true, align:"center", margin:0 });
    s.addText(fmtPct(c.v26), { x:x+0.1, y:1.35, w:2.75, h:0.72, fontSize:46, color:c.col, bold:true, fontFace:"Cambria", align:"center", margin:0 });
    s.addText("2026 conversion rate", { x:x+0.1, y:2.08, w:2.75, h:0.22, fontSize:8, color:SLATE, align:"center", margin:0 });
    s.addText("vs " + fmtPct(c.v25) + " in 2025", { x:x+0.1, y:2.3, w:2.75, h:0.2, fontSize:9, color:"94A3B8", align:"center", margin:0 });
    const d = c.v26 - c.v25;
    s.addText((d>=0?"▲ ":"▼ ") + Math.abs(d).toFixed(1)+"pp", { x:x+0.1, y:2.52, w:2.75, h:0.26, fontSize:11, color:d>=0?GREEN:RED, bold:true, align:"center", margin:0 });
  });

  // Appointments context
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.3, y:3.6, w:4.4, h:1.75, fill:{color:LIGHT}, rectRadius:0.1, line:{color:"E2E8F0",width:1}, shadow:makeShadow() });
  s.addText("Appointments Conducted", { x:0.45, y:3.68, w:4.1, h:0.28, fontSize:10, color:NAVY, bold:true, margin:0 });
  s.addText([
    {text:"2026: ", options:{bold:true, color:BLUE}}, {text:fmtN(K.acts26)+"\n", options:{color:NAVY}},
    {text:"2025: ", options:{bold:true, color:SLATE}}, {text:fmtN(K.acts25)+"\n", options:{color:"64748B"}},
    {text:"Change: ", options:{bold:true, color:RED}}, {text:fmtN(K.acts26-K.acts25)+" ("+yoy(K.acts26,K.acts25)+")", options:{color:RED}},
  ], { x:0.45, y:3.98, w:4.1, h:1.25, fontSize:11, fontFace:"Calibri", lineSpacingMultiple:1.5, margin:0 });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:5.0, y:3.6, w:4.7, h:1.75, fill:{color:"ECFDF5"}, rectRadius:0.1, line:{color:GREEN,width:1}, shadow:makeShadow() });
  s.addText("Conversion Quality Insight", { x:5.15, y:3.68, w:4.4, h:0.28, fontSize:10, color:GREEN, bold:true, margin:0 });
  s.addText(
    "Despite " + Math.abs(K.acts26-K.acts25).toLocaleString() + " fewer appointments in 2026, " +
    "the team converted more orders — driven by better quality leads and the initiative enabling consultants " +
    "to close higher-value customers with a competitive discount position.",
    { x:5.15, y:3.98, w:4.4, h:1.28, fontSize:9.5, color:"1F4033", lineSpacingMultiple:1.4, margin:0 }
  );

  s.addNotes(
    "Conversion analysis.\n\n" +
    "Total appointments: " + K.acts26.toLocaleString() + " in 2026 vs " + K.acts25.toLocaleString() + " in 2025 — fewer appointments but more conversions.\n\n" +
    "All-orders conversion: " + K.conv_all25 + "% → " + K.conv_all26 + "% (+2.6pp)\n" +
    "$5K+ conversion: " + K.conv_over25 + "% → " + K.conv_over26 + "% (+0.4pp)\n" +
    "<$5K conversion: " + K.conv_under25 + "% → " + K.conv_under26 + "% (+2.3pp)\n\n" +
    "The key message: quality over quantity. The team is doing more with fewer visits. " +
    "The initiative discount enables consultants to close when a customer is on the fence."
  );
}

// ─────────────────────────────────────────────────────────
// SLIDE 7 — AVERAGE ORDER VALUE
// ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.8, fill:{color:NAVY}, line:{color:NAVY,width:0} });
  s.addText("Average Order Value", { x:0.4, y:0, w:7, h:0.8, fontSize:22, color:WHITE, bold:true, fontFace:"Cambria", valign:"middle", margin:0 });
  s.addText("Confirmed order intake  ·  Ex-GST  ·  Segmented by job size", { x:0.4, y:0.5, w:7, h:0.3, fontSize:9, color:"A0C4E8", margin:0 });

  const aovData = [
    { label:"All Confirmed\nOrders", v26:K.aov_all26, v25:K.aov_all25, col:BLUE },
    { label:"Orders ≥ $5K\n(Initiative scope)", v26:K.aov_over26, v25:K.aov_over25, col:PURPLE },
    { label:"Orders < $5K\n(Smaller jobs)", v26:K.aov_under26, v25:K.aov_under25, col:AMBER },
  ];

  aovData.forEach((a, i) => {
    const x = 0.3 + i * 3.12;
    const diff = a.v26 - a.v25;
    const up = diff >= 0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y:0.95, w:2.9, h:2.2, fill:{color:LIGHT}, rectRadius:0.12, line:{color:"E2E8F0",width:1}, shadow:makeShadow() });
    s.addText(a.label, { x:x+0.1, y:1.02, w:2.7, h:0.44, fontSize:9.5, color:NAVY, bold:true, align:"center", margin:0 });
    s.addText(fmtM(a.v26), { x:x+0.1, y:1.48, w:2.7, h:0.62, fontSize:38, color:a.col, bold:true, fontFace:"Cambria", align:"center", margin:0 });
    s.addText("2026 YTD avg", { x:x+0.1, y:2.12, w:2.7, h:0.2, fontSize:8, color:SLATE, align:"center", margin:0 });
    s.addText("vs "+fmtM(a.v25)+" (2025)", { x:x+0.1, y:2.32, w:2.7, h:0.2, fontSize:9, color:"94A3B8", align:"center", margin:0 });
    s.addText((up?"▲":"▼")+" "+fmtM(Math.abs(diff))+" ("+yoy(a.v26,a.v25)+")", { x:x+0.1, y:2.55, w:2.7, h:0.22, fontSize:9, color:up?GREEN:RED, bold:true, align:"center", margin:0 });
  });

  // AOV bar chart
  s.addText("Average Order Value — 2026 vs 2025 (Ex-GST)", { x:0.3, y:3.28, w:9.4, h:0.28, fontSize:10, color:NAVY, bold:true, margin:0 });
  s.addChart(pres.charts.BAR,
    [
      { name:"2026", labels:["All Orders","≥ $5K","< $5K"], values:[K.aov_all26, K.aov_over26, K.aov_under26] },
      { name:"2025", labels:["All Orders","≥ $5K","< $5K"], values:[K.aov_all25, K.aov_over25, K.aov_under25] },
    ],
    { x:0.3, y:3.55, w:9.4, h:1.85, barDir:"col", barGrouping:"clustered",
      chartColors:[BLUE, SLATE+"99"],
      chartArea:{ fill:{color:WHITE} },
      catAxisLabelColor:SLATE, valAxisLabelColor:SLATE,
      valGridLine:{ color:"E2E8F0", size:0.5 }, catGridLine:{ style:"none" },
      showLegend:true, legendPos:"r", legendFontSize:9,
      showValue:true, dataLabelFontSize:8.5, dataLabelColor:NAVY,
    }
  );

  s.addNotes(
    "Average order value analysis.\n\n" +
    "Key observation: AOV on $5K+ jobs is broadly stable — " + fmtM(K.aov_over25) + " → " + fmtM(K.aov_over26) + " (-1.2%). " +
    "The slight decline is expected given the initiative encourages the 35–40% bracket which slightly reduces per-job revenue, " +
    "offset by higher volume.\n\n" +
    "The $5K+ segment remains the engine: avg job of " + fmtM(K.aov_over26) + " drives " + fmtM(K.rev26) + " of recognised revenue.\n\n" +
    "All-orders AOV includes many small jobs (< $5K) which naturally dilutes the average."
  );
}

// ─────────────────────────────────────────────────────────
// SLIDE 8 — MARGIN IMPACT
// ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.8, fill:{color:NAVY}, line:{color:NAVY,width:0} });
  s.addText("Gross Profit & Margin Impact", { x:0.4, y:0, w:7, h:0.8, fontSize:22, color:WHITE, bold:true, fontFace:"Cambria", valign:"middle", margin:0 });
  s.addText("Revenue and GP$ by discount bracket  ·  $5K+ jobs  ·  Ex-GST", { x:0.4, y:0.5, w:7, h:0.3, fontSize:9, color:"A0C4E8", margin:0 });

  // GP KPI strip
  const gpCards = [
    { label:"GP$ 2026", val:fmtM(K.gp26), sub:"vs "+fmtM(K.gp25)+" 2025", col:GREEN, delta:yoy(K.gp26,K.gp25), up:K.gp26>K.gp25 },
    { label:"GP% 2026", val:fmtPct(K.gp_pct26), sub:"vs "+fmtPct(K.gp_pct25)+" 2025", col:AMBER, delta:((K.gp_pct26-K.gp_pct25)>=0?"+":"")+(K.gp_pct26-K.gp_pct25).toFixed(1)+"pp", up:false },
    { label:"Revenue 2026", val:fmtM(K.rev26), sub:"vs "+fmtM(K.rev25)+" 2025", col:BLUE, delta:yoy(K.rev26,K.rev25), up:K.rev26>K.rev25 },
  ];
  gpCards.forEach((c, i) => {
    const x = 0.3 + i * 3.2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y:0.92, w:3.0, h:1.2, fill:{color:LIGHT}, rectRadius:0.1, line:{color:"E2E8F0",width:1}, shadow:makeShadow() });
    s.addText(c.label, { x:x+0.1, y:0.98, w:2.8, h:0.24, fontSize:9, color:SLATE, bold:true, align:"center", margin:0 });
    s.addText(c.val,   { x:x+0.1, y:1.2, w:2.8, h:0.5, fontSize:30, color:c.col, bold:true, fontFace:"Cambria", align:"center", margin:0 });
    s.addText(c.sub,   { x:x+0.1, y:1.7, w:2.8, h:0.2, fontSize:8, color:"94A3B8", align:"center", margin:0 });
    s.addText(c.delta, { x:x+0.1, y:1.9, w:2.8, h:0.16, fontSize:8.5, color:c.up?GREEN:RED, bold:true, align:"center", margin:0 });
  });

  // GP by bucket table
  const tHdr = [
    [
      { text:"Bracket",    options:{fill:{color:NAVY}, color:WHITE, bold:true} },
      { text:"2026 Jobs",  options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"2026 Rev",   options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"Rev vs '25", options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"2026 GP$",   options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"2026 GP%",   options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"2025 GP%",   options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"GP% Δ",      options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
    ]
  ];
  const tRows = D.buckets.map(b => {
    const gp26pct = b.rev26>0 ? Math.round(b.gp26/b.rev26*1000)/10 : 0;
    const gp25pct = b.rev25>0 ? Math.round(b.gp25/b.rev25*1000)/10 : 0;
    const gpDelta = Math.round((gp26pct-gp25pct)*10)/10;
    const revDelta = b.rev26 - b.rev25;
    const bg = b.initiative ? "F5F3FF" : "FFFFFF";
    const lbl = b.initiative ? b.label+" ★" : b.label;
    return [
      { text:lbl, options:{fill:{color:bg}, bold:b.initiative, color:b.initiative?PURPLE:NAVY} },
      { text:String(b.count26), options:{fill:{color:bg}, align:"right"} },
      { text:fmtM(b.rev26), options:{fill:{color:bg}, align:"right", color:GREEN} },
      { text:(revDelta>=0?"+":"-")+fmtM(Math.abs(revDelta)), options:{fill:{color:bg}, align:"right", color:revDelta>=0?GREEN:RED, bold:true} },
      { text:fmtM(b.gp26), options:{fill:{color:bg}, align:"right"} },
      { text:fmtPct(gp26pct), options:{fill:{color:bg}, align:"right"} },
      { text:fmtPct(gp25pct), options:{fill:{color:bg}, align:"right", color:SLATE} },
      { text:(gpDelta>=0?"+":"")+gpDelta+"pp", options:{fill:{color:bg}, align:"right", color:gpDelta>=0?GREEN:RED, bold:true} },
    ];
  });
  s.addTable([...tHdr, ...tRows], {
    x:0.3, y:2.22, w:9.4, h:3.1, colW:[1.35, 0.75, 1.0, 1.0, 1.0, 0.85, 0.85, 0.8],
    border:{ pt:0.5, color:"E2E8F0" }, fontSize:8.5, rowH:0.36,
  });

  s.addNotes(
    "Margin analysis.\n\n" +
    "GP dollars: " + fmtM(K.gp25) + " → " + fmtM(K.gp26) + " (+" + Math.round((K.gp26-K.gp25)/K.gp25*100*10)/10 + "% YoY) — gross profit grew in absolute terms.\n" +
    "GP%: " + K.gp_pct25 + "% → " + K.gp_pct26 + "% (-2pp) — the initiative discount is reducing margin rate.\n\n" +
    "Initiative bracket (35–40%): GP% = " + Math.round(D.buckets[4].gp26/D.buckets[4].rev26*1000)/10 + "% on " + fmtM(D.buckets[4].rev26) + " revenue.\n\n" +
    "The board question will be: is the GP% dilution acceptable? Answer: yes, because revenue volume and absolute GP$ both grew. " +
    "The initiative is working as a volume driver at a sustainable margin."
  );
}

// ─────────────────────────────────────────────────────────
// SLIDE 9 — CONSULTANT COMMISSION EARNINGS
// ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.8, fill:{color:NAVY}, line:{color:NAVY,width:0} });
  s.addText("Consultant Commission Earnings", { x:0.4, y:0, w:7, h:0.8, fontSize:22, color:WHITE, bold:true, fontFace:"Cambria", valign:"middle", margin:0 });
  s.addText("8% base rate  ·  12% on 35–40% bracket jobs  ·  $5K+ orders  ·  Ex-GST", { x:0.4, y:0.5, w:7, h:0.3, fontSize:9, color:"A0C4E8", margin:0 });

  // Commission KPIs
  const commCards = [
    { label:"Total Commission 2026", val:fmtM(K.comm26), sub:"vs "+fmtM(K.comm25)+" 2025", delta:yoy(K.comm26,K.comm25), col:GREEN, up:true },
    { label:"YoY $ Increase", val:fmtM(K.comm26-K.comm25), sub:"additional consultant earnings", delta:"+"+Math.round((K.comm26-K.comm25)/K.comm25*100)+"% YoY", col:BLUE, up:true },
    { label:"Effective Rate 2026", val:fmtPct(K.comm_rate26), sub:"blended rate on revenue", delta:"vs 8% base rate", col:PURPLE, up:true },
  ];
  commCards.forEach((c, i) => {
    const x = 0.3 + i * 3.2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y:0.92, w:3.0, h:1.3, fill:{color:LIGHT}, rectRadius:0.1, line:{color:"E2E8F0",width:1}, shadow:makeShadow() });
    s.addText(c.label, { x:x+0.1, y:0.98, w:2.8, h:0.3, fontSize:9, color:SLATE, bold:true, align:"center", margin:0 });
    s.addText(c.val,   { x:x+0.1, y:1.25, w:2.8, h:0.55, fontSize:32, color:c.col, bold:true, fontFace:"Cambria", align:"center", margin:0 });
    s.addText(c.sub,   { x:x+0.1, y:1.8, w:2.8, h:0.2, fontSize:8, color:"94A3B8", align:"center", margin:0 });
    s.addText(c.delta, { x:x+0.1, y:2.0, w:2.8, h:0.18, fontSize:8.5, color:GREEN, bold:true, align:"center", margin:0 });
  });

  // Rep table
  const repHdr = [
    [
      { text:"Consultant",        options:{fill:{color:NAVY}, color:WHITE, bold:true} },
      { text:"Jobs '26",          options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"Revenue '26",       options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"Commission '26",    options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"Commission '25",    options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"YoY Change",        options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
      { text:"Init Jobs",         options:{fill:{color:NAVY}, color:WHITE, bold:true, align:"right"} },
    ]
  ];
  const repRows = D.top_reps.map((r, i) => {
    const delta26 = r.comm25 ? r.comm26 - r.comm25 : null;
    const bg = i % 2 === 0 ? "F8FAFC" : "FFFFFF";
    return [
      { text: r.rep.replace(/ \([^)]+\)/,""), options:{fill:{color:bg}, bold:true, color:NAVY} },
      { text: String(r.jobs26), options:{fill:{color:bg}, align:"right"} },
      { text: fmtM(r.rev26), options:{fill:{color:bg}, align:"right", color:GREEN} },
      { text: fmtM(r.comm26), options:{fill:{color:bg}, align:"right", bold:true, color:BLUE} },
      { text: r.comm25 ? fmtM(r.comm25) : "—", options:{fill:{color:bg}, align:"right", color:SLATE} },
      { text: delta26 ? (delta26>=0?"+":"-")+fmtM(Math.abs(delta26)) : "—",
        options:{fill:{color:bg}, align:"right", color:delta26>=0?GREEN:RED, bold:!!delta26} },
      { text: String(r.init26), options:{fill:{color:r.init26>=10?"F5F3FF":bg}, align:"right", color:r.init26>=10?PURPLE:SLATE, bold:r.init26>=10} },
    ];
  });
  // Total row
  const totRev26 = D.top_reps.reduce((s,r)=>s+r.rev26,0);
  const totComm26 = D.top_reps.reduce((s,r)=>s+r.comm26,0);
  const totComm25 = D.top_reps.filter(r=>r.comm25).reduce((s,r)=>s+(r.comm25||0),0);
  const totInit26 = D.top_reps.reduce((s,r)=>s+r.init26,0);
  repRows.push([
    { text:"Top 8 Total", options:{fill:{color:"EFF6FF"}, bold:true, color:NAVY} },
    { text:String(D.top_reps.reduce((s,r)=>s+r.jobs26,0)), options:{fill:{color:"EFF6FF"}, align:"right", bold:true} },
    { text:fmtM(totRev26), options:{fill:{color:"EFF6FF"}, align:"right", bold:true, color:GREEN} },
    { text:fmtM(totComm26), options:{fill:{color:"EFF6FF"}, align:"right", bold:true, color:BLUE} },
    { text:fmtM(totComm25), options:{fill:{color:"EFF6FF"}, align:"right", bold:true, color:SLATE} },
    { text:"+"+ fmtM(totComm26-totComm25), options:{fill:{color:"EFF6FF"}, align:"right", bold:true, color:GREEN} },
    { text:String(totInit26), options:{fill:{color:"EFF6FF"}, align:"right", bold:true, color:PURPLE} },
  ]);

  s.addTable([...repHdr, ...repRows], {
    x:0.3, y:2.38, w:9.4, h:3.02, colW:[2.2, 0.6, 1.05, 1.15, 1.15, 1.05, 0.8],
    border:{ pt:0.5, color:"E2E8F0" }, fontSize:8.2, rowH:0.325,
  });

  s.addNotes(
    "Consultant commission earnings — 2026 vs 2025.\n\n" +
    "Total commission pool: " + fmtM(K.comm25) + " → " + fmtM(K.comm26) + " (+" + Math.round((K.comm26-K.comm25)/K.comm25*100) + "% YoY, +" + fmtM(K.comm26-K.comm25) + ")\n" +
    "Effective blended rate: " + K.comm_rate26 + "% (vs 8% base) — reflecting the premium paid on initiative bracket jobs\n\n" +
    "Top performers by commission earned:\n" +
    D.top_reps.slice(0,5).map(r => `  ${r.rep}: ${fmtM(r.comm26)} (${r.init26} initiative jobs)`).join("\n") + "\n\n" +
    "The commission uplift cost is " + fmtM(K.comm26-K.comm25) + " above the 2025 base — " +
    "offset by " + fmtM(K.rev26-K.rev25) + " in additional revenue and " + fmtM(K.gp26-K.gp25) + " in additional gross profit."
  );
}

// ─────────────────────────────────────────────────────────
// SLIDE 10 — CONCLUSION & RECOMMENDATIONS
// ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };

  s.addShape(pres.shapes.OVAL, { x:7.5, y:3.2, w:4.5, h:4.5, fill:{color:TEAL, transparency:82}, line:{color:TEAL,width:0} });

  s.addText("Conclusion & Recommendations", { x:0.5, y:0.25, w:9, h:0.6, fontSize:26, color:WHITE, bold:true, fontFace:"Cambria", margin:0 });
  s.addText("Revenue Management Initiative  ·  H1 2026", { x:0.5, y:0.85, w:9, h:0.28, fontSize:11, color:"7AA8CC", margin:0 });

  const conclusions = [
    { icon:"✓", title:"Initiative is Working", body:`Bracket adoption grew from ${K.init_pct25}% to ${K.init_pct26}% of $5K+ jobs. Revenue up ${Math.round((K.rev26-K.rev25)/K.rev25*100)}% YoY to ${fmtM(K.rev26)}.`, col:GREEN },
    { icon:"✓", title:"Conversion Improving", body:`Appointment-to-order rate up from ${K.conv_all25}% to ${K.conv_all26}% despite ${(K.acts25-K.acts26).toLocaleString()} fewer appointments — quality over quantity.`, col:TEAL },
    { icon:"⚠", title:"Monitor GP% Erosion", body:`Margin rate declined ${Math.abs(K.gp_pct26-K.gp_pct25).toFixed(1)}pp to ${K.gp_pct26}%. Gross profit dollars still grew to ${fmtM(K.gp26)}. Watch the 40%+ brackets for outliers.`, col:AMBER },
    { icon:"→", title:"Recommendation: Expand & Refine", body:`Set rep-level adoption targets for 35–40% bracket. Consider a formal review at Q3 to assess whether the bracket floor should tighten to 35–38% to recover 1pp of margin.`, col:BLUE },
  ];

  conclusions.forEach((c, i) => {
    const y = 1.25 + i * 1.02;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.45, y, w:8.8, h:0.9, fill:{color:WHITE, transparency:88}, rectRadius:0.1, line:{color:c.col, transparency:40, width:1} });
    s.addShape(pres.shapes.OVAL, { x:0.55, y:y+0.16, w:0.58, h:0.58, fill:{color:c.col}, line:{color:c.col,width:0} });
    s.addText(c.icon, { x:0.55, y:y+0.16, w:0.58, h:0.58, fontSize:16, color:WHITE, bold:true, align:"center", valign:"middle", margin:0 });
    s.addText(c.title, { x:1.25, y:y+0.06, w:7.8, h:0.28, fontSize:10.5, color:WHITE, bold:true, margin:0 });
    s.addText(c.body,  { x:1.25, y:y+0.34, w:7.8, h:0.48, fontSize:9,   color:"CBD5E1", margin:0, lineSpacingMultiple:1.3 });
  });

  s.addText("Prepared by Sales Analytics  ·  Data as at 26 June 2026  ·  Ex-GST  ·  $5K+ confirmed orders", {
    x:0.5, y:5.3, w:9, h:0.22, fontSize:7.5, color:"475569", align:"center", margin:0
  });

  s.addNotes(
    "Closing slide — summary and next steps for management.\n\n" +
    "1. Initiative is delivering: revenue and volume both up YoY. The core premise — that enhanced commission drives higher-value conversions — is validated.\n\n" +
    "2. Conversion improvement is meaningful: even with fewer total appointments, the team closed more orders. The initiative gives consultants a credible discount position.\n\n" +
    "3. The GP% watch: -2pp is within acceptable bounds given volume growth, but should be monitored monthly. " +
    "Particularly watch the 40–50% and 50%+ brackets which grew from 26 to 90 jobs combined.\n\n" +
    "4. Recommended actions:\n" +
    "   a) Set quarterly initiative adoption targets per consultant (suggested: 30%+ of $5K+ jobs)\n" +
    "   b) Review bracket boundaries at Q3 — consider 35–38% with 12% rate, 38–40% with 10% rate\n" +
    "   c) Share this analysis with all consultants — recognition drives behaviour\n" +
    "   d) Explore whether the initiative model can be adapted for commercial/contract segment\n\n" +
    "Questions likely from management: \n" +
    "Q: Are reps giving deeper discounts they would have given anyway? \n" +
    "A: The migration from 30–35% to 35–40% suggests reps are nudging discounts upward to access the bracket — this is the intended behaviour, and revenue still grew."
  );
}

// ─────────────────────────────────────────────────────────
// WRITE
// ─────────────────────────────────────────────────────────
pres.writeFile({ fileName: "Revenue_Initiative_H1_2026.pptx" })
  .then(() => { console.log("Done — Revenue_Initiative_H1_2026.pptx written"); })
  .catch(e => { console.error("Error:", e); process.exit(1); });
