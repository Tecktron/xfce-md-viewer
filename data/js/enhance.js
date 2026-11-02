// xfce-md-viewer page script.
//
// Injected by the viewer as a WebKit user script into the isolated "md-viewer"
// script world (see ui/window.py). The document's own scripts are blocked by its
// Content-Security-Policy and cannot see or call anything defined here.
// KaTeX / Mermaid are injected into the same world only when a page needs them.
"use strict";

globalThis.mdViewer = {
  /** Render math and diagrams. Returns a JSON summary for the viewer. */
  async enhance({ scheme }) {
    const dark =
      scheme === "dark" || (scheme === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
    const summary = { math: 0, diagrams: 0, errors: [] };

    if (globalThis.katex) {
      for (const el of document.querySelectorAll(".math.inline, .math.display, .math.block")) {
        // Older pandoc wraps formulas in \( \) or \[ \]; KaTeX wants them bare.
        const tex = el.textContent
          .trim()
          .replace(/^\\\(([\s\S]*)\\\)$/, "$1")
          .replace(/^\\\[([\s\S]*)\\\]$/, "$1");
        try {
          katex.render(tex, el, { displayMode: !el.classList.contains("inline"), throwOnError: false });
          summary.math++;
        } catch (e) {
          summary.errors.push(`math: ${e}`);
        }
      }
    }

    if (globalThis.mermaid) {
      mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: dark ? "dark" : "default" });
      const blocks = [...document.querySelectorAll("pre > code.language-mermaid")];
      for (const [i, code] of blocks.entries()) {
        const id = `md-viewer-mermaid-${i}`;
        try {
          const { svg } = await mermaid.render(id, code.textContent);
          const figure = document.createElement("div");
          figure.className = "mermaid";
          figure.innerHTML = svg;
          code.parentElement.replaceWith(figure);
          summary.diagrams++;
        } catch (e) {
          // Leave the source visible; remove Mermaid's temporary error element.
          document.getElementById(`d${id}`)?.remove();
          summary.errors.push(`diagram ${i + 1}: ${e?.message ?? e}`);
        }
      }
    }
    return JSON.stringify(summary);
  },

  /** Scroll a heading into view (table of contents). */
  scrollToId(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ block: "start" });
    return Boolean(el);
  },
};
