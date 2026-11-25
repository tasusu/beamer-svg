(() => {
  "use strict";

  const SVG = "http://www.w3.org/2000/svg";
  const HTML = "http://www.w3.org/1999/xhtml";
  const deck = document.querySelector("#bw-deck");
  const slides = Array.from(deck.querySelectorAll(":scope > .bw-slide"));
  const metadata = JSON.parse(document.querySelector("#bw-metadata").textContent);
  const registry = new Map();
  const states = new Map();
  let active = -1;
  let mounted = [];

  function registerWidget(name, mount) {
    if (typeof name !== "string" || typeof mount !== "function" || registry.has(name)) {
      throw new TypeError(`Invalid or duplicate widget registration: ${name}`);
    }
    registry.set(name, mount);
  }

  function emit(context, type, detail) {
    context.events.dispatchEvent(new CustomEvent(type, {detail}));
  }

  function placeWidgets() {
    for (const {marker, host, layer} of mounted) {
      if (!layer) continue;
      const matrix = marker.getScreenCTM();
      if (!matrix) continue;
      const origin = new DOMPoint(marker.x.baseVal.value, marker.y.baseVal.value)
        .matrixTransform(matrix);
      const bounds = layer.getBoundingClientRect();
      host.style.transform = `matrix(${matrix.a}, ${matrix.b}, ${matrix.c}, ${matrix.d}, ${origin.x - bounds.left}, ${origin.y - bounds.top})`;
    }
  }

  function mountWidgets(slide, page) {
    const svg = slide.querySelector(":scope > svg");
    const layer = slide.querySelector(".bw-widget-layer");
    const counts = new Map();
    const markers = Array.from(svg.querySelectorAll("[data-web-widget]")).filter(
      marker => getComputedStyle(marker).visibility === "visible"
    );
    return markers.map(marker => {
      const name = marker.dataset.webWidget;
      const occurrence = counts.get(name) || 0;
      counts.set(name, occurrence + 1);
      const stateKey = JSON.stringify([page.frame ?? `page-${page.physicalPage}`, name, occurrence]);
      if (!states.has(stateKey)) states.set(stateKey, {});
      const host = document.createElementNS(HTML, "div");
      host.className = "bw-widget";
      const width = marker.width.baseVal.value;
      const height = marker.height.baseVal.value;
      let container = host;
      let overlayLayer = layer;
      if (deck.dataset.placement === "foreign-object") {
        container = document.createElementNS(SVG, "foreignObject");
        for (const attr of ["x", "y", "width", "height", "transform"]) {
          if (marker.hasAttribute(attr)) container.setAttribute(attr, marker.getAttribute(attr));
        }
        container.append(host);
        marker.after(container);
        overlayLayer = null;
      } else {
        host.classList.add("bw-widget-overlay");
        layer.append(host);
      }
      host.style.width = `${width}px`;
      host.style.height = `${height}px`;

      const controller = new AbortController();
      const {signal} = controller;
      const events = new EventTarget();
      const getAll = id => Array.from(svg.querySelectorAll("[data-web-id]"))
        .filter(node => node.dataset.webId === id);
      const api = {
        get: id => getAll(id)[0] ?? null,
        getAll,
        on: (id, type, listener) => {
          for (const node of getAll(id)) node.addEventListener(type, listener, {signal});
        },
        onSlideEnter: listener => events.addEventListener("slideenter", listener, {signal}),
        onSlideLeave: listener => events.addEventListener("slideleave", listener, {signal}),
        onOverlayEnter: listener => events.addEventListener("overlayenter", listener, {signal}),
        onOverlayLeave: listener => events.addEventListener("overlayleave", listener, {signal}),
        signal,
      };
      const context = {marker, host, container, layer: overlayLayer, controller, events};
      const factory = registry.get(name);
      try {
        if (factory) {
          context.cleanup = factory({host, slide, svg, page, state: states.get(stateKey), api});
        } else {
          const message = `Widget "${name}" is not registered`;
          console.warn(message);
          if (deck.dataset.production !== "true") host.textContent = message;
        }
      } catch (error) {
        console.error(`Widget "${name}" failed to mount`, error);
        if (deck.dataset.production !== "true") host.textContent = `Widget "${name}" failed`;
      }
      return context;
    });
  }

  function navigate(index) {
    const next = Math.max(0, Math.min(slides.length - 1, index));
    if (active === next) return;
    if (active >= 0) {
      for (const context of mounted) {
        emit(context, "overlayleave", metadata[active]);
        emit(context, "slideleave", metadata[active]);
        try {
          if (typeof context.cleanup === "function") context.cleanup();
        } catch (error) {
          console.error("Widget cleanup failed", error);
        } finally {
          context.controller.abort();
          context.container.remove();
        }
      }
      slides[active].hidden = true;
    }

    active = next;
    const slide = slides[active];
    const page = metadata[active];
    slide.hidden = false;
    mounted = mountWidgets(slide, page);
    placeWidgets();
    for (const context of mounted) {
      emit(context, "slideenter", page);
      emit(context, "overlayenter", page);
    }
    document.querySelector("#bw-counter").value = `${active + 1} / ${slides.length}`;
    document.querySelector("#bw-prev").disabled = active === 0;
    document.querySelector("#bw-next").disabled = active === slides.length - 1;
  }

  function go(index) {
    navigate(index);
    const hash = `#/${active + 1}`;
    if (location.hash !== hash) location.hash = hash;
  }

  function readHash() {
    const match = /^#\/(\d+)$/.exec(location.hash);
    navigate(match ? Number(match[1]) - 1 : 0);
  }

  async function fullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (error) {
      console.warn("Fullscreen unavailable", error);
    }
  }

  function onKey(event) {
    if (event.defaultPrevented || event.ctrlKey || event.altKey || event.metaKey ||
        event.composedPath().some(node => node instanceof Element && (
          node.matches("input, textarea, select, button, a, [role=button], .bw-widget") ||
          node.isContentEditable
        ))) return;
    switch (event.key) {
      case "ArrowRight": case " ": case "PageDown": go(active + 1); break;
      case "ArrowLeft": case "PageUp": go(active - 1); break;
      case "Home": go(0); break;
      case "End": go(slides.length - 1); break;
      case "f": case "F": fullscreen(); break;
      default: return;
    }
    event.preventDefault();
  }

  window.BeamerWeb = Object.freeze({registerWidget});
  document.addEventListener("DOMContentLoaded", () => {
    readHash();
    window.addEventListener("hashchange", readHash);
    window.addEventListener("resize", placeWidgets);
    window.visualViewport?.addEventListener("resize", placeWidgets);
    document.addEventListener("fullscreenchange", placeWidgets);
    new ResizeObserver(placeWidgets).observe(deck);
    document.addEventListener("keydown", onKey);
    document.querySelector("#bw-prev").addEventListener("click", () => go(active - 1));
    document.querySelector("#bw-next").addEventListener("click", () => go(active + 1));
    document.querySelector("#bw-fullscreen").addEventListener("click", fullscreen);
  });
})();
