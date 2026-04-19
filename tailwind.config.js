/** @type {import('tailwindcss').Config} */
//
// ForgedCA brand palette (from the logo exploration, April 2026)
//   Steel       #6B89B8   primary action colour
//   Steel Deep  #4E6A94   secondary / hover-darker
//   Charcoal    #1B1F26   dark canvas + text on light
//   Forge Spark #E08B3B   accent / warnings
//   Bone        #EDE7DB   light canvas + text on dark
//
// Two custom DaisyUI themes, `forgedca-light` and `forgedca-dark`, drive every
// card, button, form control, alert, and nav surface. Flipping `data-theme`
// on the <html> element in base.html switches the whole UI.
//
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        steel: "#6B89B8",
        "steel-deep": "#4E6A94",
        charcoal: "#1B1F26",
        "forge-spark": "#E08B3B",
        bone: "#EDE7DB",
      },
      fontFamily: {
        // System UI stack keeps the admin dense and familiar without
        // forcing a web-font download; swap to a branded face later if
        // the logo designer proposes one.
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "Liberation Mono",
          "Courier New",
          "monospace",
        ],
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/typography"),
    require("daisyui"),
  ],
  daisyui: {
    themes: [
      {
        "forgedca-light": {
          "primary": "#6B89B8",
          "primary-content": "#FFFFFF",
          "secondary": "#4E6A94",
          "secondary-content": "#FFFFFF",
          "accent": "#E08B3B",
          "accent-content": "#1B1F26",
          "neutral": "#1B1F26",
          "neutral-content": "#EDE7DB",
          "base-100": "#EDE7DB",   // Bone — page canvas
          "base-200": "#E2DBCB",   // warmer bone for cards
          "base-300": "#CDC4AE",   // borders / dividers
          "base-content": "#1B1F26",
          "info": "#4E6A94",       // Steel Deep — readable on bone
          "info-content": "#FFFFFF",
          "success": "#3F7A52",    // green that harmonises with steel
          "success-content": "#FFFFFF",
          "warning": "#E08B3B",    // Forge Spark doubles as warning
          "warning-content": "#1B1F26",
          "error": "#A83F3F",      // muted brick red
          "error-content": "#FFFFFF",
          "--rounded-box": "0.5rem",
          "--rounded-btn": "0.375rem",
          "--rounded-badge": "0.5rem",
          "--border-btn": "1px",
          "--tab-radius": "0.375rem",
        },
      },
      {
        "forgedca-dark": {
          "primary": "#6B89B8",
          "primary-content": "#FFFFFF",
          "secondary": "#4E6A94",
          "secondary-content": "#EDE7DB",
          "accent": "#E08B3B",
          "accent-content": "#1B1F26",
          "neutral": "#12151A",
          "neutral-content": "#EDE7DB",
          "base-100": "#1B1F26",   // Charcoal — page canvas
          "base-200": "#232831",   // cards
          "base-300": "#2D343E",   // borders / dividers
          "base-content": "#EDE7DB",
          "info": "#4E6A94",       // Match light — steel-blue info card stays identical in both modes
          "info-content": "#FFFFFF",
          "success": "#6FB67C",    // brighter for dark surfaces
          "success-content": "#0D1117",
          "warning": "#E08B3B",
          "warning-content": "#1B1F26",
          "error": "#D76868",
          "error-content": "#0D1117",
          "--rounded-box": "0.5rem",
          "--rounded-btn": "0.375rem",
          "--rounded-badge": "0.5rem",
          "--border-btn": "1px",
          "--tab-radius": "0.375rem",
        },
      },
    ],
    darkTheme: "forgedca-dark",
    base: true,
    styled: true,
    utils: true,
    logs: false,
  },
};
