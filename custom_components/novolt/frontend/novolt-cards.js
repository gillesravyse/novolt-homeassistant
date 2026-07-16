/**
 * Novolt Lovelace cards, shipped with the integration and auto-registered in
 * the card picker. Pure vanilla web components: no Lit, no build step, no CDN.
 *
 * Five cards, visually identical to the Novolt app (same OKLCH tokens, same
 * geometry as the app's power-flow/price-bar/plan-chart components):
 *
 *   - novolt-power-flow-card   the live energy flow diagram
 *   - novolt-battery-card      SOC ring + charged/discharged today
 *   - novolt-stats-card        the stat tile row (price, sun, self-sufficiency…)
 *   - novolt-price-card        day-ahead price columns with the cheap EV window
 *   - novolt-forecast-card     24h plan: PV/load forecast, battery plan, SOC
 *
 * Entities are auto-discovered from the entity registry (platform "novolt",
 * matched on translation_key, so it works in every UI language). Every value
 * honours the no-fake-data rule: missing/unavailable data renders as an em-dash
 * placeholder, never as a fabricated zero.
 */
(() => {
  "use strict";

  /* ── design tokens (the app's dark theme, OKLCH) ───────────────────────── */
  const TOKENS = `
    --nv-bg: oklch(0.13 0 0);
    --nv-surface: oklch(0.17 0 0);
    --nv-surface-2: oklch(0.205 0 0);
    --nv-surface-3: oklch(0.24 0 0);
    --nv-border: oklch(0.27 0 0);
    --nv-border-strong: oklch(0.34 0 0);
    --nv-ink: oklch(0.97 0 0);
    --nv-ink-muted: oklch(0.72 0 0);
    --nv-ink-faint: oklch(0.55 0 0);
    --nv-solar: oklch(0.82 0.16 75);
    --nv-battery: oklch(0.78 0.16 150);
    --nv-grid: oklch(0.7 0.17 295);
    --nv-export: oklch(0.72 0.15 230);
    --nv-ev: oklch(0.75 0.15 200);
    --nv-load: oklch(0.74 0.06 250);
  `;

  const BASE_CSS = `
    :host { display: block; height: 100%; ${TOKENS} }
    *, *::before, *::after { box-sizing: border-box; }
    .nv-card {
      background: var(--nv-surface);
      border: 1px solid var(--nv-border);
      border-radius: 16px;
      padding: 16px 20px 20px;
      color: var(--nv-ink);
      font-family: var(--ha-card-font-family, var(--paper-font-body1_-_font-family, system-ui, sans-serif));
      height: 100%;
    }
    .nv-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 6px 14px; flex-wrap: wrap; margin-bottom: 8px; }
    .nv-title { font-size: 15px; font-weight: 600; color: var(--nv-ink); }
    .nv-sub { font-size: 12px; color: var(--nv-ink-muted); margin-top: 2px; }
    .nv-right { font-size: 12px; color: var(--nv-ink-faint); font-variant-numeric: tabular-nums; }
    .nv-missing {
      padding: 18px; text-align: center; font-size: 12px; color: var(--nv-ink-muted);
      background: var(--nv-surface-2); border-radius: 10px;
    }
    .nv-legend { display: flex; gap: 14px; font-size: 12px; color: var(--nv-ink-muted); }
    .nv-legend span { display: inline-flex; align-items: center; gap: 5px; }
    .nv-dot { width: 8px; height: 8px; border-radius: 999px; display: inline-block; }
    .tnum { font-variant-numeric: tabular-nums; }
  `;

  /* ── i18n ──────────────────────────────────────────────────────────────── */
  const STR = {
    en: {
      flowTitle: "Energy flow", live: "Live", solar: "Sun", grid: "Grid",
      home: "Home", battery: "Battery", import: "IMPORT", export: "EXPORT",
      charging: "CHARGING", discharging: "DISCHARGING",
      batteryTitle: "Battery", stored: "stored", chargedToday: "Charged today",
      discharged: "Discharged", priceNow: "Price now", sunToday: "Sun today",
      selfSuff: "Self-sufficiency", savedToday: "Saved today", injectionNow: "Injection now",
      selfSuffSub: "of your usage from own sun", cheapFrom: "Cheap from {h}", cheapNow: "Cheap now",
      priceTitle: "Dynamic price today", priceSub: "{n} cheap hours selected for charging",
      cheap: "cheap", expensive: "expensive", hour: "{h}h",
      forecastTitle: "Next 24 hours forecast", forecastSub: "Sun, consumption, battery plan and state of charge",
      legSolar: "Sun", legLoad: "Consumption", legCharge: "Charging", legDischarge: "Discharging",
      now: "now", missing: "Novolt entities not found. Install and configure the Novolt integration, or set entities in the card config.",
      optColumns: "Width (columns of 12)", optRows: "Height (rows)", optReference: "Reference power (W, flow speed)",
      optHint: "Size applies to sections dashboards; drag the sliders and save.",
    },
    nl: {
      flowTitle: "Energiestroom", live: "Live", solar: "Zon", grid: "Net",
      home: "Huis", battery: "Batterij", import: "IMPORT", export: "EXPORT",
      charging: "LADEN", discharging: "ONTLADEN",
      batteryTitle: "Batterij", stored: "opgeslagen", chargedToday: "Vandaag geladen",
      discharged: "Ontladen", priceNow: "Prijs nu", sunToday: "Zon vandaag",
      selfSuff: "Zelfvoorziening", savedToday: "Bespaard vandaag", injectionNow: "Injectie nu",
      selfSuffSub: "van je verbruik uit eigen zon", cheapFrom: "Goedkoop vanaf {h}", cheapNow: "Nu goedkoop",
      priceTitle: "Dynamische prijs vandaag", priceSub: "{n} goedkope uren geselecteerd voor laden",
      cheap: "goedkoop", expensive: "duur", hour: "{h}u",
      forecastTitle: "Voorspelling komende 24 uur", forecastSub: "Zon, verbruik, batterijplan en laadtoestand",
      legSolar: "Zon", legLoad: "Verbruik", legCharge: "Laden", legDischarge: "Ontladen",
      now: "nu", missing: "Geen Novolt-entiteiten gevonden. Installeer en configureer de Novolt-integratie, of geef entiteiten op in de kaartconfiguratie.",
      optColumns: "Breedte (kolommen van 12)", optRows: "Hoogte (rijen)", optReference: "Referentievermogen (W, stroomsnelheid)",
      optHint: "Formaat geldt voor secties-dashboards; sleep de sliders en sla op.",
    },
    fr: {
      flowTitle: "Flux d'énergie", live: "En direct", solar: "Soleil", grid: "Réseau",
      home: "Maison", battery: "Batterie", import: "IMPORT", export: "EXPORT",
      charging: "CHARGE", discharging: "DÉCHARGE",
      batteryTitle: "Batterie", stored: "stocké", chargedToday: "Chargé aujourd'hui",
      discharged: "Déchargé", priceNow: "Prix actuel", sunToday: "Soleil aujourd'hui",
      selfSuff: "Autosuffisance", savedToday: "Économisé aujourd'hui", injectionNow: "Injection",
      selfSuffSub: "de votre consommation via le soleil", cheapFrom: "Bon marché dès {h}", cheapNow: "Bon marché",
      priceTitle: "Prix dynamique aujourd'hui", priceSub: "{n} heures creuses sélectionnées pour charger",
      cheap: "bon marché", expensive: "cher", hour: "{h}h",
      forecastTitle: "Prévision 24 heures", forecastSub: "Soleil, consommation, plan batterie et charge",
      legSolar: "Soleil", legLoad: "Conso", legCharge: "Charge", legDischarge: "Décharge",
      now: "mnt", missing: "Entités Novolt introuvables. Installez l'intégration Novolt ou renseignez les entités dans la configuration de la carte.",
      optColumns: "Largeur (colonnes sur 12)", optRows: "Hauteur (rangées)", optReference: "Puissance de référence (W)",
      optHint: "La taille s'applique aux tableaux de bord en sections.",
    },
  };
  const lang = (hass) => {
    const l = (hass && (hass.locale?.language || hass.language)) || "en";
    return STR[l.slice(0, 2)] ? l.slice(0, 2) : "en";
  };
  const tr = (hass, key, vars) => {
    let s = (STR[lang(hass)] || STR.en)[key] || STR.en[key] || key;
    if (vars) for (const k in vars) s = s.replace(`{${k}}`, vars[k]);
    return s;
  };
  const numLocale = (hass) => ({ nl: "nl-BE", fr: "fr-BE" })[lang(hass)] || "en-GB";

  /* ── formatting (mirrors the app's lib/format.ts) ──────────────────────── */
  const DASH = "—";
  const fmtPower = (hass, w) => {
    if (w == null) return { value: DASH, unit: "" };
    const abs = Math.abs(w);
    if (abs >= 1000)
      return {
        value: (w / 1000).toLocaleString(numLocale(hass), {
          minimumFractionDigits: 2, maximumFractionDigits: 2,
        }),
        unit: "kW",
      };
    return { value: String(Math.round(w)), unit: "W" };
  };
  const fmtPowerStr = (hass, w) => {
    const { value, unit } = fmtPower(hass, w);
    return unit ? `${value} ${unit}` : value;
  };
  const fmtKwh = (hass, kwh, digits = 1) =>
    kwh == null
      ? DASH
      : kwh.toLocaleString(numLocale(hass), {
          minimumFractionDigits: digits, maximumFractionDigits: digits,
        });
  const fmtEur = (hass, v, digits = 2) =>
    v == null
      ? DASH
      : v.toLocaleString(numLocale(hass), {
          minimumFractionDigits: digits, maximumFractionDigits: digits,
        });

  /* ── entity discovery ──────────────────────────────────────────────────── */
  function novoltMap(hass) {
    const map = {};
    if (!hass || !hass.entities) return map;
    for (const id in hass.entities) {
      const e = hass.entities[id];
      if (e.platform === "novolt" && e.translation_key && !(e.translation_key in map))
        map[e.translation_key] = id;
    }
    return map;
  }
  function pickEntity(card, key) {
    const cfg = card._config || {};
    if (cfg.entities && cfg.entities[key]) return cfg.entities[key];
    if (!card.__map || card.__mapHass !== card._hass) {
      card.__map = novoltMap(card._hass);
      card.__mapHass = card._hass;
    }
    return card.__map[key];
  }
  function numState(hass, id) {
    if (!id) return null;
    const s = hass.states[id];
    if (!s || s.state === "unavailable" || s.state === "unknown") return null;
    const v = Number(s.state);
    return Number.isFinite(v) ? v : null;
  }
  function wireMoreInfo(card) {
    card.shadowRoot.querySelectorAll("[data-entity]").forEach((el) => {
      const entityId = el.getAttribute("data-entity");
      if (!entityId) return;
      el.addEventListener("click", () =>
        card.dispatchEvent(
          new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true })
        )
      );
    });
  }

  function attrs(hass, id) {
    const s = id ? hass.states[id] : undefined;
    return (s && s.attributes) || {};
  }

  /* ── icons (24×24; tower is the app's own path, rest lucide-style) ─────── */
  const stroke = (paths, extra = "") =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ${extra}>${paths}</svg>`;
  const ICONS = {
    solar: stroke(
      `<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>`
    ),
    grid: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8.28,5.45L6.5,4.55L7.76,2H16.23L17.5,4.55L15.72,5.44L15,4H9L8.28,5.45M18.62,8H14.09L13.3,5H10.7L9.91,8H5.38L4.1,10.55L5.89,11.44L6.62,10H17.38L18.1,11.45L19.89,10.56L18.62,8M17.77,22H15.7L15.46,21.1L12,15.9L8.53,21.1L8.3,22H6.23L9.12,11H11.19L10.83,12.35L12,14.1L13.16,12.35L12.81,11H14.88L17.77,22M11.4,15L10.5,13.65L9.32,18.13L11.4,15M14.68,18.12L13.5,13.64L12.6,15L14.68,18.12Z"/></svg>`,
    house: stroke(`<path d="M3 11.5 12 3l9 8.5"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>`),
    battery: stroke(`<rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2"/><path d="M6 11v2M10 11v2"/>`),
    ev: stroke(`<path d="M8 7V3M14 7V3"/><path d="M6 7h10v4a5 5 0 0 1-10 0Z"/><path d="M11 16v3a2 2 0 0 0 2 2h1"/><path d="m19.5 9.5-2 3h3l-2 3"/>`),
    euro: stroke(`<path d="M18 6a7 7 0 0 0-11 6 7 7 0 0 0 11 6"/><path d="M4 10h8M4 14h8"/>`),
    leaf: stroke(`<path d="M11 20A7 7 0 0 1 4 13c0-4 3-8 9-9 5-1 7-1 7-1s0 2-1 7c-1 6-5 10-8 10Z"/><path d="M4 21c3-5 7-8 12-10"/>`),
    trend: stroke(`<path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/>`),
    zap: stroke(`<path d="M13 2 4 13.5h6L11 22l9-11.5h-6L13 2Z"/>`),
  };

  /* ── base card ─────────────────────────────────────────────────────────── */
  class NovoltBaseCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._sig = null;
    }
    setConfig(config) {
      this._config = config || {};
      this._sig = null;
      if (this._hass) this._update();
    }
    set hass(hass) {
      this._hass = hass;
      this._update();
    }
    getCardSize() {
      return this.constructor.cardSize || 4;
    }
    static getStubConfig() {
      return {};
    }
    _update() {
      if (!this._hass) return;
      const view = this._view(this._hass);
      const sig = JSON.stringify(view);
      if (sig === this._sig) return;
      this._sig = sig;
      this.shadowRoot.innerHTML = `<style>${BASE_CSS}${this.constructor.css || ""}</style>${this._render(view)}`;
      if (this._afterRender) this._afterRender(view);
    }
    _missing(hass) {
      return `<div class="nv-card"><div class="nv-missing">${tr(hass, "missing")}</div></div>`;
    }
  }

  /* ── visual config editor: size sliders (writes sections grid_options) ── */
  class NovoltCardEditor extends HTMLElement {
    setConfig(config) {
      this._config = config || {};
      this._render();
    }
    set hass(hass) {
      this._hass = hass;
      this._render();
    }
    set cardDefaults(defaults) {
      this._defaults = defaults || {};
      this._render();
    }
    connectedCallback() {
      this._render();
    }
    _render() {
      if (!this._hass || !this._config || !this._defaults) return;
      if (!this._form) {
        const hint = document.createElement("p");
        hint.style.cssText = "font-size:12px;color:var(--secondary-text-color);margin:0 0 8px";
        hint.textContent = tr(this._hass, "optHint");
        this.appendChild(hint);
        this._form = document.createElement("ha-form");
        this._form.addEventListener("value-changed", (ev) => {
          ev.stopPropagation();
          const value = ev.detail.value || {};
          const config = { ...this._config };
          config.grid_options = {
            ...(config.grid_options || {}),
            columns: value.columns,
            rows: value.rows,
          };
          for (const key of (this._defaults.extraKeys || [])) {
            if (value[key] != null && value[key] !== "") config[key] = value[key];
            else delete config[key];
          }
          this._config = config;
          this.dispatchEvent(
            new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true })
          );
        });
        this.appendChild(this._form);
      }
      const d = this._defaults;
      const go = this._config.grid_options || {};
      this._form.hass = this._hass;
      this._form.schema = [
        { name: "columns", selector: { number: { min: 1, max: 12, step: 1, mode: "slider" } } },
        { name: "rows", selector: { number: { min: 2, max: 16, step: 1, mode: "slider" } } },
        ...(d.extras || []),
      ];
      this._form.data = {
        columns: go.columns === "full" ? 12 : go.columns ?? d.columns ?? 12,
        rows: go.rows ?? d.rows ?? 4,
        ...(d.extraData ? d.extraData(this._config) : {}),
      };
      this._form.computeLabel = (field) =>
        ({ columns: tr(this._hass, "optColumns"), rows: tr(this._hass, "optRows") })[field.name] ||
        (d.labels && d.labels(this._hass, field.name)) || field.name;
    }
  }

  const sizeEditor = (defaults) => {
    const el = document.createElement("novolt-card-editor");
    el.cardDefaults = defaults;
    return el;
  };

  /* ═══════════════════════════ 1. power flow ═════════════════════════════ */

  const VB = { w: 600, h: 570 };
  const LAYOUT = {
    solar: { x: 300, y: 84, r: 44, labelPos: "top" },
    ev1: { x: 510, y: 84, r: 38, labelPos: "top" },
    grid: { x: 90, y: 300, r: 44, labelPos: "bottom" },
    home: { x: 510, y: 300, r: 44, labelPos: "right" },
    battery: { x: 300, y: 500, r: 44, labelPos: "bottom" },
    ev2: { x: 510, y: 500, r: 38, labelPos: "bottom" },
  };
  const EDGES = [
    { id: "solar_home", kind: "solar", d: "M 312 128 Q 312 288 466 288" },
    { id: "solar_grid", kind: "solar", d: "M 288 128 Q 288 288 134 288" },
    { id: "solar_battery", kind: "solar", d: "M 300 130 L 300 448" },
    { id: "grid_home", kind: "grid", d: "M 136 300 L 465 300" },
    { id: "grid_battery", kind: "grid", d: "M 134 312 Q 288 312 288 448" },
    { id: "battery_home", kind: "battery", d: "M 312 448 Q 312 312 466 312" },
    { id: "home_ev1", kind: "ev", d: "M 510 254 L 510 124" },
    { id: "home_ev2", kind: "ev", d: "M 510 346 L 510 460" },
  ];
  const KIND_COLOR = {
    solar: "var(--nv-solar)", grid: "var(--nv-grid)", battery: "var(--nv-battery)",
    ev: "var(--nv-ev)", house: "var(--nv-load)",
  };
  const KIND_ICON = { solar: "solar", grid: "grid", battery: "battery", ev: "ev", house: "house" };
  const TOL = 25;
  const lapDuration = (w, refW) => {
    const norm = Math.abs(w || 0) / Math.max(refW, 1000);
    return Math.max(1.4, Math.min(6, 5.2 - 3.8 * norm));
  };

  class NovoltPowerFlowCard extends NovoltBaseCard {
    static cardSize = 6;
    getGridOptions() {
      return { columns: 12, rows: 8, min_columns: 6, min_rows: 5 };
    }
    static getConfigElement() {
      return sizeEditor({
        columns: 12, rows: 8,
        extras: [{ name: "reference_w", selector: { number: { min: 500, max: 20000, step: 100, mode: "box", unit_of_measurement: "W" } } }],
        extraKeys: ["reference_w"],
        extraData: (config) => ({ reference_w: config.reference_w ?? 2000 }),
        labels: (hass, name) => (name === "reference_w" ? tr(hass, "optReference") : null),
      });
    }
    static css = `
      .nv-card { display: flex; flex-direction: column; }
      .flow-wrap { position: relative; flex: 1; min-height: 0; display: flex; justify-content: center; }
      svg.flow { width: 100%; height: 100%; overflow: visible; }
      .node-box {
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        border-radius: 999px; background: var(--nv-surface);
        transition: border-color .3s, box-shadow .3s, transform .3s;
        cursor: pointer;
      }
      .node-box:hover { transform: scale(1.05); }
      .node-box .icon { width: 22px; height: 22px; }
      .node-box .val { font-size: 12.5px; font-weight: 700; margin-top: 2px; white-space: nowrap; font-variant-numeric: tabular-nums; }
      .node-box .dir { font-size: 9px; font-weight: 600; letter-spacing: .06em; color: var(--nv-ink-muted); }
    `;

    _view(hass) {
      const pv = numState(hass, pickEntity(this, "pv_power"));
      const grid = numState(hass, pickEntity(this, "grid_power"));
      const house = numState(hass, pickEntity(this, "house_power"));
      const batt = numState(hass, pickEntity(this, "battery_power"));
      const soc = numState(hass, pickEntity(this, "battery_soc"));
      const evAttrs = attrs(hass, pickEntity(this, "ev_power"));
      const chargers = (evAttrs.chargers || []).slice(0, 2).map((c) => ({
        name: c.name || c.id || "EV", w: c.power_w || 0,
      }));
      const found = [pv, grid, house, batt].some((v) => v != null);
      return {
        found, pv, grid, house, batt, soc, chargers,
        hasSolar: pickEntity(this, "pv_power") != null,
        hasBattery: pickEntity(this, "battery_power") != null,
        lang: lang(hass),
      };
    }

    _render(v) {
      const hass = this._hass;
      if (!v.found) return this._missing(hass);
      const pv = v.pv ?? 0, house = Math.max(0, v.house ?? 0), batt = v.batt ?? 0, gridNet = v.grid ?? 0;
      const gridImporting = gridNet > TOL, gridExporting = gridNet < -TOL;
      const battCharging = batt > TOL, battDischarging = batt < -TOL;
      const ev1 = v.chargers[0], ev2 = v.chargers[1];

      this._edgeActive = {
        solar_home: pv > TOL && house > TOL,
        solar_grid: pv > TOL && gridExporting,
        solar_battery: pv > TOL && battCharging && !gridImporting,
        grid_home: gridImporting,
        grid_battery: gridImporting && battCharging,
        battery_home: battDischarging,
        home_ev1: !!ev1 && ev1.w > 5,
        home_ev2: !!ev2 && ev2.w > 5,
      };
      this._edgePower = {
        solar_home: Math.min(pv, house), solar_grid: Math.max(0, -gridNet),
        solar_battery: Math.abs(batt), grid_home: Math.max(0, gridNet),
        grid_battery: Math.abs(batt), battery_home: Math.abs(batt),
        home_ev1: ev1 ? ev1.w : 0, home_ev2: ev2 ? ev2.w : 0,
      };
      this._refW = (this._config && this._config.reference_w) || 2000;

      const edges = EDGES.filter(
        (e) =>
          (e.id !== "home_ev1" || !!ev1) &&
          (e.id !== "home_ev2" || !!ev2) &&
          (v.hasBattery || !e.id.includes("battery")) &&
          (v.hasSolar || !e.id.startsWith("solar"))
      );

      const nodes = [];
      const ent = (key) => pickEntity(this, key);
      nodes.push({
        slot: "grid", kind: "grid", label: tr(hass, "grid"), entity: ent("grid_power"),
        value: v.grid == null ? DASH : fmtPowerStr(hass, Math.abs(gridNet) > TOL ? Math.abs(gridNet) : 0),
        sub: gridImporting ? tr(hass, "import") : gridExporting ? tr(hass, "export") : "",
        active: gridImporting || gridExporting,
      });
      nodes.push({
        slot: "home", kind: "house", label: tr(hass, "home"), entity: ent("house_power"),
        value: v.house == null ? DASH : fmtPowerStr(hass, house),
        sub: "", active: house > TOL,
      });
      if (v.hasSolar)
        nodes.push({
          slot: "solar", kind: "solar", label: tr(hass, "solar"), entity: ent("pv_power"),
          value: v.pv == null ? DASH : fmtPowerStr(hass, pv), sub: "", active: pv > TOL,
        });
      if (v.hasBattery)
        nodes.push({
          slot: "battery", kind: "battery", label: tr(hass, "battery"), entity: ent("battery_power"),
          value: v.batt == null ? DASH : fmtPowerStr(hass, battCharging || battDischarging ? Math.abs(batt) : 0),
          sub: battCharging ? tr(hass, "charging") : battDischarging ? tr(hass, "discharging") : "",
          soc: v.soc, active: battCharging || battDischarging,
        });
      if (ev1) nodes.push({ slot: "ev1", kind: "ev", label: ev1.name, value: fmtPowerStr(hass, ev1.w), sub: "", active: ev1.w > 5, entity: ent("ev_power") });
      if (ev2) nodes.push({ slot: "ev2", kind: "ev", label: ev2.name, value: fmtPowerStr(hass, ev2.w), sub: "", active: ev2.w > 5, entity: ent("ev_power") });

      const socArc = v.hasBattery && v.soc != null ? this._socArc(v.soc) : "";

      return `
        <div class="nv-card">
          <div class="nv-head">
            <div><div class="nv-title">${tr(hass, "flowTitle")}</div><div class="nv-sub">${tr(hass, "live")}</div></div>
            <div class="nv-right" id="clock"></div>
          </div>
          <div class="flow-wrap">
            <svg class="flow" viewBox="0 0 ${VB.w} ${VB.h}">
              ${socArc}
              ${edges.map((e) => {
                const c = KIND_COLOR[e.kind];
                const active = this._edgeActive[e.id];
                return `<path data-edge="${e.id}" d="${e.d}" fill="none" stroke="${c}"
                  stroke-width="${active ? 3 : 2}" stroke-linecap="round"
                  style="opacity:${active ? 1 : 0.1};${active ? `filter:drop-shadow(0 0 5px color-mix(in oklch, ${c} 55%, transparent))` : ""}"/>`;
              }).join("")}
              ${edges.map((e) => `<circle data-dot="${e.id}" r="6" fill="${KIND_COLOR[e.kind]}"
                  stroke="var(--nv-surface)" stroke-width="1.5" opacity="0"
                  style="filter:drop-shadow(0 0 4px ${KIND_COLOR[e.kind]})"/>`).join("")}
              ${nodes.map((n) => this._node(n)).join("")}
            </svg>
          </div>
        </div>`;
    }

    _socArc(soc) {
      const b = LAYOUT.battery;
      const r = b.r + 6;
      const circ = 2 * Math.PI * r;
      const pct = Math.max(0, Math.min(100, soc));
      return `
        <circle cx="${b.x}" cy="${b.y}" r="${r}" fill="none" stroke="var(--nv-border)" stroke-width="4" opacity="0.5"/>
        <circle cx="${b.x}" cy="${b.y}" r="${r}" fill="none" stroke="var(--nv-battery)" stroke-width="4"
          stroke-linecap="round" stroke-dasharray="${circ}" stroke-dashoffset="${circ * (1 - pct / 100)}"
          transform="rotate(-90 ${b.x} ${b.y})"/>`;
    }

    _node(n) {
      const slot = LAYOUT[n.slot];
      const color = KIND_COLOR[n.kind];
      const { x, y, r } = slot;
      let lx = x, ly = y, anchor = "middle";
      const labelR = n.kind === "battery" ? r + 6 : r;
      if (slot.labelPos === "top") ly = y - labelR - 12;
      else if (slot.labelPos === "bottom") ly = y + labelR + 28;
      else { lx = x + labelR + 12; ly = y + 5; anchor = "start"; }
      const socLabel = n.soc != null
        ? `<text x="${x - r + 2}" y="${y - r - 8}" text-anchor="middle" fill="${color}" font-size="14" font-weight="700" class="tnum">${Math.round(n.soc)}%</text>`
        : "";
      const glow = n.active
        ? `box-shadow: 0 0 16px -2px color-mix(in oklch, ${color} 70%, transparent), inset 0 0 18px -12px ${color};`
        : "";
      return `
        <text x="${lx}" y="${ly}" text-anchor="${anchor}" fill="var(--nv-ink-muted)" font-size="14" font-weight="500">${n.label}</text>
        ${socLabel}
        <foreignObject x="${x - r}" y="${y - r}" width="${r * 2}" height="${r * 2}" style="overflow:visible">
          <div xmlns="http://www.w3.org/1999/xhtml" class="node-box" data-entity="${n.entity || ""}" style="width:${r * 2}px;height:${r * 2}px;color:${color};border:${n.active ? 2.5 : 2}px solid ${n.active ? color : "var(--nv-border)"};${glow}">
            <span class="icon">${ICONS[KIND_ICON[n.kind]]}</span>
            <span class="val" style="color:${color}">${n.value}</span>
            ${n.sub ? `<span class="dir">${n.sub}</span>` : ""}
          </div>
        </foreignObject>`;
    }

    _afterRender() {
      this._syncClock();
      wireMoreInfo(this);
    }
    connectedCallback() {
      this._phase = this._phase || {};
      this._reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      this._clockTimer = setInterval(() => this._syncClock(), 1000);
      let last = 0;
      const tick = (t) => {
        this._raf = requestAnimationFrame(tick);
        if (this._reduced) return;
        const dt = last ? Math.min(0.1, (t - last) / 1000) : 0;
        last = t;
        const root = this.shadowRoot;
        if (!root || !this._edgeActive) return;
        for (const e of EDGES) {
          const dot = root.querySelector(`[data-dot="${e.id}"]`);
          const path = root.querySelector(`[data-edge="${e.id}"]`);
          if (!dot || !path) continue;
          if (!this._edgeActive[e.id]) { dot.style.opacity = "0"; continue; }
          dot.style.opacity = "1";
          const dur = lapDuration(this._edgePower[e.id], this._refW || 2000);
          const phase = ((this._phase[e.id] ?? Math.random()) + dt / dur) % 1;
          this._phase[e.id] = phase;
          const p = path.getPointAtLength(phase * path.getTotalLength());
          dot.setAttribute("cx", p.x.toFixed(1));
          dot.setAttribute("cy", p.y.toFixed(1));
        }
      };
      this._raf = requestAnimationFrame(tick);
    }
    disconnectedCallback() {
      cancelAnimationFrame(this._raf);
      clearInterval(this._clockTimer);
    }
    _syncClock() {
      const el = this.shadowRoot && this.shadowRoot.getElementById("clock");
      if (el) el.textContent = new Date().toLocaleTimeString(numLocale(this._hass), { hour12: false });
    }
  }

  /* ═══════════════════════════ 2. battery ════════════════════════════════ */

  class NovoltBatteryCard extends NovoltBaseCard {
    static cardSize = 5;
    getGridOptions() {
      return { columns: 6, rows: 7, min_columns: 3, min_rows: 5 };
    }
    static getConfigElement() {
      return sizeEditor({ columns: 6, rows: 7 });
    }
    _afterRender() {
      wireMoreInfo(this);
    }
    static css = `
      .nv-card { display: flex; flex-direction: column; container-type: inline-size; }
      .ring-wrap { flex: 1; min-height: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 12px 0 4px; }
      .ring { position: relative; width: clamp(110px, 52cqw, 230px); aspect-ratio: 1; cursor: pointer; container-type: inline-size; }
      .ring svg { width: 100%; height: 100%; display: block; }
      .ring .center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
      .ring .pct { font-size: 21cqw; font-weight: 700; font-variant-numeric: tabular-nums; }
      .ring .cap { font-size: 7cqw; color: var(--nv-ink-muted); margin-top: 2px; }
      .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(104px, 1fr)); gap: 10px; margin-top: clamp(10px, 5cqw, 24px); width: 100%; }
      .tile { background: var(--nv-surface-2); border-radius: 10px; padding: clamp(8px, 3cqw, 12px); text-align: center; cursor: pointer; }
      .tile .lbl { font-size: clamp(10px, 3.4cqw, 12px); color: var(--nv-ink-faint); }
      .tile .val { font-size: clamp(13px, 4.4cqw, 16px); font-weight: 600; margin-top: 3px; font-variant-numeric: tabular-nums; white-space: nowrap; }
    `;
    _view(hass) {
      return {
        soc: numState(hass, pickEntity(this, "battery_soc")),
        charged: numState(hass, pickEntity(this, "today_battery_charge")),
        discharged: numState(hass, pickEntity(this, "today_battery_discharge")),
        found: pickEntity(this, "battery_soc") != null,
        lang: lang(hass),
      };
    }
    _render(v) {
      const hass = this._hass;
      if (!v.found) return this._missing(hass);
      const pct = v.soc == null ? 0 : Math.max(0, Math.min(100, v.soc));
      const r = 84, circ = 2 * Math.PI * r;
      return `
        <div class="nv-card">
          <div class="nv-head"><div class="nv-title">${tr(hass, "batteryTitle")}</div></div>
          <div class="ring-wrap">
            <div class="ring" data-entity="${pickEntity(this, "battery_soc") || ""}">
              <svg viewBox="0 0 190 190">
                <circle cx="95" cy="95" r="${r}" fill="none" stroke="var(--nv-border)" stroke-width="9" opacity="0.5"/>
                <circle cx="95" cy="95" r="${r}" fill="none" stroke="var(--nv-battery)" stroke-width="9"
                  stroke-linecap="round" stroke-dasharray="${circ}" stroke-dashoffset="${circ * (1 - pct / 100)}"
                  transform="rotate(-90 95 95)"
                  style="filter:drop-shadow(0 0 10px color-mix(in oklch, var(--nv-battery) 60%, transparent))"/>
              </svg>
              <div class="center">
                <span class="pct">${v.soc == null ? DASH : Math.round(pct) + "%"}</span>
                <span class="cap">${tr(hass, "stored")}</span>
              </div>
            </div>
            <div class="tiles">
              <div class="tile" data-entity="${pickEntity(this, "today_battery_charge") || ""}"><div class="lbl">${tr(hass, "chargedToday")}</div>
                <div class="val" style="color:var(--nv-battery)">${v.charged == null ? DASH : fmtKwh(hass, v.charged) + " kWh"}</div></div>
              <div class="tile" data-entity="${pickEntity(this, "today_battery_discharge") || ""}"><div class="lbl">${tr(hass, "discharged")}</div>
                <div class="val" style="color:var(--nv-export)">${v.discharged == null ? DASH : fmtKwh(hass, v.discharged) + " kWh"}</div></div>
            </div>
          </div>
        </div>`;
    }
  }

  /* ═══════════════════════════ 3. stat tiles ═════════════════════════════ */

  class NovoltStatsCard extends NovoltBaseCard {
    static cardSize = 2;
    getGridOptions() {
      return { columns: 12, rows: "auto", min_columns: 6 };
    }
    static getConfigElement() {
      return sizeEditor({ columns: 12, rows: 3 });
    }
    _afterRender() {
      wireMoreInfo(this);
    }
    static css = `
      :host { --nv-tile-min: 150px; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(var(--nv-tile-min), 1fr)); gap: 12px; }
      .stat { background: var(--nv-surface); border: 1px solid var(--nv-border); border-radius: 12px; padding: 14px 16px; }
      .stat[data-entity]:not([data-entity=""]) { cursor: pointer; transition: border-color .2s; }
      .stat[data-entity]:not([data-entity=""]):hover { border-color: var(--nv-border-strong); }
      .stat .top { display: flex; align-items: center; gap: 7px; font-size: 13px; color: var(--nv-ink-muted); }
      .stat .top .ic { width: 15px; height: 15px; display: inline-flex; }
      .stat .val { margin-top: 8px; font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; }
      .stat .val small { font-size: 13px; font-weight: 500; color: var(--nv-ink-faint); margin-left: 3px; }
      .stat .sub { margin-top: 6px; font-size: 12px; color: var(--nv-ink-faint); min-height: 15px; }
      .nv-card { padding: 0; background: transparent; border: none; }
    `;
    _view(hass) {
      const nextCheap = hass.states[pickEntity(this, "ev_next_cheap_start")];
      const cheapNowState = hass.states[pickEntity(this, "ev_cheap_now")];
      let cheapSub = "";
      if (cheapNowState && cheapNowState.state === "on") cheapSub = tr(hass, "cheapNow");
      else if (nextCheap && nextCheap.state && !["unavailable", "unknown"].includes(nextCheap.state)) {
        const d = new Date(nextCheap.state);
        if (!isNaN(d) && d.getTime() > Date.now())
          cheapSub = tr(hass, "cheapFrom", { h: tr(hass, "hour", { h: String(d.getHours()) }) });
      }
      return {
        price: numState(hass, pickEntity(this, "price_current")),
        injection: numState(hass, pickEntity(this, "price_injection")),
        pvToday: numState(hass, pickEntity(this, "today_pv_energy")),
        selfSuff: numState(hass, pickEntity(this, "self_sufficiency")),
        cheapSub,
        found: pickEntity(this, "price_current") != null || pickEntity(this, "today_pv_energy") != null,
        lang: lang(hass),
      };
    }
    _render(v) {
      const hass = this._hass;
      if (!v.found) return this._missing(hass);
      const tile = (icon, color, label, val, unit, sub, entity) => `
        <div class="stat" data-entity="${entity || ""}">
          <div class="top"><span class="ic" style="color:${color}">${icon}</span>${label}</div>
          <div class="val">${val}${unit ? `<small>${unit}</small>` : ""}</div>
          <div class="sub">${sub || ""}</div>
        </div>`;
      return `
        <div class="nv-card"><div class="grid">
          ${tile(ICONS.euro, "var(--nv-grid)", tr(hass, "priceNow"),
            v.price == null ? DASH : fmtEur(hass, v.price) + " €", v.price == null ? "" : "/kWh", v.cheapSub,
            pickEntity(this, "price_current"))}
          ${tile(ICONS.solar, "var(--nv-solar)", tr(hass, "sunToday"),
            v.pvToday == null ? DASH : fmtKwh(hass, v.pvToday), v.pvToday == null ? "" : "kWh", "",
            pickEntity(this, "today_pv_energy"))}
          ${tile(ICONS.leaf, "var(--nv-battery)", tr(hass, "selfSuff"),
            v.selfSuff == null ? DASH : Math.round(v.selfSuff) + "%", "", v.selfSuff == null ? "" : tr(hass, "selfSuffSub"),
            pickEntity(this, "self_sufficiency"))}
          ${tile(ICONS.trend, "var(--nv-battery)", tr(hass, "savedToday"), DASH, "", "", "")}
          ${tile(ICONS.zap, "var(--nv-export)", tr(hass, "injectionNow"),
            v.injection == null ? DASH : fmtEur(hass, v.injection) + " €", v.injection == null ? "" : "/kWh", "",
            pickEntity(this, "price_injection"))}
        </div></div>`;
    }
  }

  /* ═══════════════════════════ 4. price bars ═════════════════════════════ */

  class NovoltPriceCard extends NovoltBaseCard {
    static cardSize = 4;
    getGridOptions() {
      return { columns: 12, rows: 5, min_columns: 6, min_rows: 4 };
    }
    static getConfigElement() {
      return sizeEditor({ columns: 12, rows: 5 });
    }
    static css = `
      .nv-card { display: flex; flex-direction: column; }
      .bars { display: flex; align-items: flex-end; gap: 3px; flex: 1; min-height: 110px; margin-top: 14px; }
      .barcol { flex: 1; display: flex; align-items: flex-end; height: 100%; position: relative; }
      .bar { width: 100%; border-radius: 3px 3px 0 0; transition: height .3s, background .3s; }
      .bar-tip {
        display: none; position: absolute; bottom: calc(100% + 6px); left: 50%;
        transform: translateX(-50%); background: var(--nv-surface-2);
        border: 1px solid var(--nv-border); border-radius: 6px; padding: 3px 8px;
        font-size: 11px; white-space: nowrap; z-index: 3; pointer-events: none;
        font-variant-numeric: tabular-nums;
      }
      .barcol:hover .bar-tip { display: block; }
      .barcol:hover .bar { filter: brightness(1.2); }
      .hours { display: flex; justify-content: space-between; font-size: 11px; color: var(--nv-ink-faint); margin-top: 8px; }
    `;
    _view(hass) {
      const priceAttrs = attrs(hass, pickEntity(this, "price_current"));
      const evAttrs = attrs(hass, pickEntity(this, "ev_cheap_now"));
      const cheapHours = new Set(
        (evAttrs.schedule || []).filter((s) => s.charge).map((s) => new Date(s.date).getTime())
      );
      const raw = (priceAttrs.raw_today || []).map((p) => ({
        t: new Date(p.start).getTime(), price: p.price,
      }));
      return {
        raw, cheap: [...cheapHours], nowH: new Date().getHours(),
        found: pickEntity(this, "price_current") != null,
        lang: lang(hass),
      };
    }
    _render(v) {
      const hass = this._hass;
      if (!v.found) return this._missing(hass);
      if (!v.raw.length)
        return `<div class="nv-card">
          <div class="nv-head"><div class="nv-title">${tr(hass, "priceTitle")}</div></div>
          <div class="nv-missing">${DASH}</div></div>`;
      const cheapSet = new Set(v.cheap);
      const max = Math.max(...v.raw.map((p) => p.price), 0.01);
      const nCheap = v.raw.filter((p) => cheapSet.has(p.t)).length;
      const bars = v.raw.map((p) => {
        const h = new Date(p.t).getHours();
        const isNow = h === v.nowH;
        const pct = Math.max((p.price / max) * 100, 3);
        const color = cheapSet.has(p.t)
          ? "var(--nv-battery)"
          : p.price > 0.28
            ? "var(--nv-grid)"
            : "var(--nv-surface-3)";
        const hourLbl = tr(hass, "hour", { h: String(h).padStart(2, "0") });
        return `<div class="barcol"><div class="bar-tip"><b>${hourLbl}</b> · ${fmtEur(hass, p.price)} €</div><div class="bar" style="height:${pct}%;background:${color};${isNow ? "outline:1.5px solid var(--nv-solar);outline-offset:1px;" : ""}"></div></div>`;
      }).join("");
      const hourMark = (h) => tr(hass, "hour", { h });
      return `
        <div class="nv-card">
          <div class="nv-head">
            <div><div class="nv-title">${tr(hass, "priceTitle")}</div>
            <div class="nv-sub">${tr(hass, "priceSub", { n: nCheap })}</div></div>
            <div class="nv-legend">
              <span><span class="nv-dot" style="background:var(--nv-battery)"></span>${tr(hass, "cheap")}</span>
              <span><span class="nv-dot" style="background:var(--nv-grid)"></span>${tr(hass, "expensive")}</span>
            </div>
          </div>
          <div class="bars">${bars}</div>
          <div class="hours"><span>${hourMark("00")}</span><span>${hourMark("06")}</span><span>${hourMark("12")}</span><span>${hourMark("18")}</span><span>${hourMark("24")}</span></div>
        </div>`;
    }
  }

  /* ═══════════════════════════ 5. forecast ═══════════════════════════════ */

  class NovoltForecastCard extends NovoltBaseCard {
    static cardSize = 5;
    getGridOptions() {
      return { columns: 12, rows: 6, min_columns: 6, min_rows: 4 };
    }
    static getConfigElement() {
      return sizeEditor({ columns: 12, rows: 6 });
    }
    static css = `
      .nv-card { display: flex; flex-direction: column; }
      .chart { margin-top: 10px; position: relative; flex: 1; min-height: 0; }
      .chart svg { width: 100%; height: auto; display: block; overflow: visible; }
      .axis { font-size: 11px; fill: var(--nv-ink-faint); font-variant-numeric: tabular-nums; }
      .fc-line { display: none; position: absolute; top: 0; width: 1px; background: var(--nv-border-strong); pointer-events: none; }
      .fc-tip {
        display: none; position: absolute; background: var(--nv-surface-2);
        border: 1px solid var(--nv-border); border-radius: 6px; padding: 6px 10px;
        font-size: 11px; z-index: 3; pointer-events: none; min-width: 132px;
      }
      .fc-tip .t { font-weight: 600; color: var(--nv-ink); margin-bottom: 3px; }
      .fc-tip .row { display: flex; justify-content: space-between; gap: 12px; color: var(--nv-ink-muted); }
      .fc-tip .row b { color: var(--nv-ink); font-weight: 600; font-variant-numeric: tabular-nums; }
    `;
    connectedCallback() {
      this._ro = new ResizeObserver(() => {
        const rect = this.getBoundingClientRect();
        const w = Math.round(rect.width / 20) * 20;
        const h = Math.round(rect.height / 20) * 20;
        if ((w && w !== this._wb) || (h && h !== this._hb)) {
          this._wb = w;
          this._hb = h;
          this._sig = null;
          this._update();
        }
      });
      this._ro.observe(this);
    }
    disconnectedCallback() {
      if (this._ro) this._ro.disconnect();
    }
    _view(hass) {
      const planAttrs = attrs(hass, pickEntity(this, "battery_plan_power"));
      const schedule = (planAttrs.schedule || []).map((s) => ({
        t: s.time, pv: s.pv_w || 0, load: s.load_w || 0,
        charge: s.batt_w < 0 ? -s.batt_w : 0, discharge: s.batt_w > 0 ? s.batt_w : 0,
        soc: s.soc_pct,
      }));
      return {
        schedule,
        found: pickEntity(this, "battery_plan_power") != null,
        lang: lang(hass),
      };
    }
    _render(v) {
      const hass = this._hass;
      if (!v.found) return this._missing(hass);
      const legend = `
        <div class="nv-legend">
          <span><span class="nv-dot" style="background:var(--nv-solar)"></span>${tr(hass, "legSolar")}</span>
          <span><span class="nv-dot" style="background:var(--nv-load)"></span>${tr(hass, "legLoad")}</span>
          <span><span class="nv-dot" style="background:var(--nv-battery)"></span>${tr(hass, "legCharge")}</span>
          <span><span class="nv-dot" style="background:var(--nv-export)"></span>${tr(hass, "legDischarge")}</span>
          <span><span class="nv-dot" style="background:var(--nv-ink-muted)"></span>SOC</span>
        </div>`;
      const head = `
        <div class="nv-head">
          <div><div class="nv-title">${tr(hass, "forecastTitle")}</div>
          <div class="nv-sub">${tr(hass, "forecastSub")}</div></div>
          ${legend}
        </div>`;
      if (v.schedule.length < 2)
        return `<div class="nv-card">${head}<div class="nv-missing">${DASH}</div></div>`;
      return `<div class="nv-card">${head}<div class="chart">${this._chart(v.schedule)}<div class="fc-line"></div><div class="fc-tip"></div></div></div>`;
    }

    _afterRender() {
      const chart = this.shadowRoot.querySelector(".chart");
      const svg = chart && chart.querySelector("svg");
      const line = this.shadowRoot.querySelector(".fc-line");
      const tip = this.shadowRoot.querySelector(".fc-tip");
      if (!chart || !svg || !line || !tip || !this._slots || this._slots.length < 2) return;
      const kw = (w) =>
        (w / 1000).toLocaleString(numLocale(this._hass), {
          minimumFractionDigits: 1, maximumFractionDigits: 1,
        }) + " kW";
      chart.addEventListener("pointermove", (ev) => {
        const m = this._metrics;
        const slots = this._slots;
        const rect = svg.getBoundingClientRect();
        if (!m || !rect.width) return;
        const scale = rect.width / m.W;
        const vx = (ev.clientX - rect.left) / scale;
        let idx = Math.round(((vx - m.padL) / m.iw) * (slots.length - 1));
        idx = Math.max(0, Math.min(slots.length - 1, idx));
        const slot = slots[idx];
        const px = (m.padL + (idx / (slots.length - 1)) * m.iw) * scale;
        line.style.display = "block";
        line.style.left = `${px.toFixed(1)}px`;
        line.style.height = `${rect.height}px`;
        const rows = [
          [tr(this._hass, "legSolar"), "var(--nv-solar)", kw(slot.pv)],
          [tr(this._hass, "legLoad"), "var(--nv-load)", kw(slot.load)],
        ];
        if (m.hasBattery) {
          rows.push([tr(this._hass, "legCharge"), "var(--nv-battery)", kw(slot.charge)]);
          rows.push([tr(this._hass, "legDischarge"), "var(--nv-export)", kw(slot.discharge)]);
          if (slot.soc != null) rows.push(["SOC", "var(--nv-ink-muted)", `${Math.round(slot.soc)}%`]);
        }
        const time = new Date(slot.t).toLocaleTimeString(numLocale(this._hass), {
          hour: "2-digit", minute: "2-digit", hour12: false,
        });
        tip.innerHTML =
          `<div class="t">${time}</div>` +
          rows.map(([label, color, value]) =>
            `<div class="row"><span><span class="nv-dot" style="background:${color};margin-right:5px"></span>${label}</span><b>${value}</b></div>`
          ).join("");
        tip.style.display = "block";
        let left = px + 12;
        if (left + tip.offsetWidth > rect.width) left = px - tip.offsetWidth - 12;
        tip.style.left = `${Math.max(0, left).toFixed(1)}px`;
        tip.style.top = "6px";
      });
      chart.addEventListener("pointerleave", () => {
        line.style.display = "none";
        tip.style.display = "none";
      });
    }

    _chart(slots) {
      const W = Math.max(this._wb || 640, 340), padL = 38, padB = 22, padT = 8;
      // Height follows the tile too: whatever the host offers minus the header,
      // clamped so tiny/huge tiles stay readable.
      const H = Math.max(170, Math.min(430, (this._hb || 330) - 96));
      this._slots = slots;
      const iw = W - padL - 8, ih = H - padT - padB;
      const maxW = Math.max(...slots.map((s) => Math.max(s.pv, s.load, s.charge, s.discharge)), 1000);
      const yMax = Math.ceil(maxW / 2000) * 2000;
      const x = (i) => padL + (i / (slots.length - 1)) * iw;
      const y = (w) => padT + ih - (w / yMax) * ih;
      const ySoc = (pct) => padT + ih - (pct / 100) * ih;

      const line = (key, yFn) => {
        let d = "";
        slots.forEach((s, i) => {
          const val = key === "soc" ? s.soc : s[key];
          if (val == null) return;
          d += (d ? " L " : "M ") + x(i).toFixed(1) + " " + yFn(val).toFixed(1);
        });
        return d;
      };
      const stepPath = (key) => {
        let d = "", prevY = null;
        slots.forEach((s, i) => {
          const yy = y(s[key]).toFixed(1);
          const xx = x(i).toFixed(1);
          if (prevY == null) d = `M ${xx} ${yy}`;
          else d += ` L ${xx} ${prevY} L ${xx} ${yy}`;
          prevY = yy;
        });
        return d;
      };

      const area = (key) => {
        const top = line(key, y);
        if (!top) return "";
        return `${top} L ${x(slots.length - 1).toFixed(1)} ${(padT + ih).toFixed(1)} L ${x(0).toFixed(1)} ${(padT + ih).toFixed(1)} Z`;
      };

      // "now" marker: the slot containing the current time.
      const nowMs = Date.now();
      let nowIdx = -1;
      slots.forEach((s, i) => { if (new Date(s.t).getTime() <= nowMs) nowIdx = i; });

      const yTicks = [];
      for (let v2 = 0; v2 <= yMax; v2 += 2000) yTicks.push(v2);
      // Label roughly six ticks whatever the horizon length is; a short
      // horizon (evening, day-ahead not published yet) labels every slot.
      const every = Math.max(1, Math.round(slots.length / 6));
      const xLabels = slots
        .map((s, i) => ({ i, label: new Date(s.t).toLocaleTimeString(numLocale(this._hass), { hour: "2-digit", minute: "2-digit", hour12: false }) }))
        .filter((_, idx) => idx % every === 0);

      const hasBattery = slots.some((s) => s.soc != null || s.charge > 1 || s.discharge > 1);
      this._metrics = { W, H, padL, padT, ih, iw, hasBattery };

      return `
        <svg viewBox="0 0 ${W} ${H}">
          <defs>
            <linearGradient id="nvPv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--nv-solar)" stop-opacity="0.35"/>
              <stop offset="100%" stop-color="var(--nv-solar)" stop-opacity="0.02"/>
            </linearGradient>
            <linearGradient id="nvLoad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--nv-load)" stop-opacity="0.22"/>
              <stop offset="100%" stop-color="var(--nv-load)" stop-opacity="0.02"/>
            </linearGradient>
          </defs>
          ${yTicks.map((t) => `
            <text class="axis" x="${padL - 6}" y="${(y(t) + 4).toFixed(1)}" text-anchor="end">${t / 1000}k</text>`).join("")}
          <line x1="${padL}" y1="${padT + ih}" x2="${padL + iw}" y2="${padT + ih}" stroke="var(--nv-border)"/>
          <path d="${area("pv")}" fill="url(#nvPv)"/>
          <path d="${line("pv", y)}" fill="none" stroke="var(--nv-solar)" stroke-width="2"/>
          <path d="${area("load")}" fill="url(#nvLoad)"/>
          <path d="${line("load", y)}" fill="none" stroke="var(--nv-load)" stroke-width="1.5"/>
          ${hasBattery ? `
            <path d="${stepPath("charge")}" fill="none" stroke="var(--nv-battery)" stroke-width="2"/>
            <path d="${stepPath("discharge")}" fill="none" stroke="var(--nv-export)" stroke-width="2" stroke-dasharray="3 3"/>
            <path d="${line("soc", ySoc)}" fill="none" stroke="var(--nv-ink-muted)" stroke-width="1.5"/>` : ""}
          ${nowIdx >= 0 ? `
            <line x1="${x(nowIdx).toFixed(1)}" y1="${padT}" x2="${x(nowIdx).toFixed(1)}" y2="${padT + ih}"
              stroke="var(--nv-solar)" stroke-dasharray="4 3"/>
            <text class="axis" x="${(x(nowIdx) + 4).toFixed(1)}" y="${padT + 10}" fill="var(--nv-solar)" style="fill:var(--nv-solar)">${tr(this._hass, "now")}</text>` : ""}
          ${xLabels.map((l) => `
            <text class="axis" x="${x(l.i).toFixed(1)}" y="${H - 6}" text-anchor="middle">${l.label}</text>`).join("")}
        </svg>`;
    }
  }

  /* ── registration ──────────────────────────────────────────────────────── */
  const CARDS = [
    ["novolt-power-flow-card", NovoltPowerFlowCard, "Novolt Energy Flow", "Live energy flow between sun, grid, home, battery and EV chargers."],
    ["novolt-battery-card", NovoltBatteryCard, "Novolt Battery", "State of charge ring with today's charged and discharged energy."],
    ["novolt-stats-card", NovoltStatsCard, "Novolt Stats", "Stat tiles: current price, sun today, self-sufficiency and injection."],
    ["novolt-price-card", NovoltPriceCard, "Novolt Prices", "Day-ahead price columns with the selected cheap charging hours."],
    ["novolt-forecast-card", NovoltForecastCard, "Novolt Forecast", "24h forecast: sun, consumption, battery plan and state of charge."],
  ];
  window.customCards = window.customCards || [];
  for (const [tag, , name, description] of CARDS) {
    if (!window.customCards.some((c) => c.type === tag))
      window.customCards.push({ type: tag, name, description, preview: true });
  }

  const defineAll = () => {
    if (!customElements.get("novolt-card-editor")) {
      try {
        customElements.define("novolt-card-editor", NovoltCardEditor);
      } catch (err) {
        console.warn("novolt-cards: could not define editor", err);
      }
    }
    for (const [tag, cls] of CARDS) {
      if (!customElements.get(tag)) {
        try {
          customElements.define(tag, cls);
        } catch (err) {
          console.warn(`novolt-cards: could not define ${tag}`, err);
        }
      }
    }
    console.info("%c NOVOLT-CARDS %c ready ", "background:#e8b54a;color:#111;font-weight:700", "background:#222;color:#e8b54a");
  };

  // Loaded via the integration's extra_module_url this script runs BEFORE the
  // frontend installs its scoped custom-element registry polyfill. Elements
  // defined that early land in the native registry only, and Home Assistant's
  // later customElements.get() lookups cannot see them ("Custom element not
  // found"). So: wait until the app shell itself is defined (which happens
  // after the polyfill), then register. Poll instead of whenDefined() so it
  // works both with and without the polyfill, with a timeout safety net.
  const started = Date.now();
  const waitForHa = () => {
    if (customElements.get("home-assistant") || Date.now() - started > 30000) {
      defineAll();
      return;
    }
    setTimeout(waitForHa, 50);
  };
  waitForHa();
})();
