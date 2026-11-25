BeamerWeb.registerWidget("slider-demo", ({host, state, api}) => {
  host.innerHTML = '<label class="demo-widget">λ = <output></output><input type="range" min="0" max="1" step="0.01"></label>';
  const input = host.querySelector("input");
  const output = host.querySelector("output");
  input.value = state.value ?? 0.43;
  const update = () => {
    state.value = Number(input.value);
    output.value = state.value.toFixed(2);
    api.get("formula").style.opacity = 0.15 + 0.85 * state.value;
  };
  input.addEventListener("input", update, {signal: api.signal});
  update();
});

BeamerWeb.registerWidget("network-selection", ({host, api}) => {
  const edges = {s: ["sv", "sw"], v: ["sv", "vt"], w: ["sw", "wt"], t: ["vt", "wt"]};
  host.textContent = "Select a vertex.";
  const select = vertex => {
    for (const edge of ["sv", "sw", "vt", "wt"]) {
      api.get(`edge-${edge}`).classList.toggle("highlight", edges[vertex].includes(edge));
    }
    host.textContent = `Selected vertex: ${vertex}`;
  };
  for (const vertex of Object.keys(edges)) {
    const node = api.get(`vertex-${vertex}`);
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", "button");
    node.setAttribute("aria-label", `Select vertex ${vertex}`);
    api.on(`vertex-${vertex}`, "click", () => select(vertex));
    api.on(`vertex-${vertex}`, "keydown", event => {
      if (event.key === " " || event.key === "Enter") {
        event.preventDefault();
        select(vertex);
      }
    });
  }
});

BeamerWeb.registerWidget("canvas-demo", ({host, api}) => {
  host.innerHTML = '<div class="demo-widget"><canvas aria-label="Moving blue dot"></canvas><div><button type="button">Play</button> <button type="button">Pause</button> <button type="button">Reset</button></div></div>';
  const canvas = host.querySelector("canvas");
  const [play, pause, reset] = host.querySelectorAll("button");
  const ctx = canvas.getContext("2d");
  let frame = null;
  let start;
  let elapsed = 0;

  function draw() {
    const scale = Math.max(1, devicePixelRatio);
    const width = Math.round(230 * scale);
    const height = Math.round(49 * scale);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.clearRect(0, 0, 230, 49);
    ctx.beginPath();
    ctx.arc(115 + 100 * Math.sin(elapsed / 650), 25, 7, 0, 2 * Math.PI);
    ctx.fillStyle = "#1748b9";
    ctx.fill();
  }

  function tick(time) {
    start ??= time - elapsed;
    elapsed = time - start;
    draw();
    frame = requestAnimationFrame(tick);
  }

  function stop() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    start = undefined;
  }

  play.addEventListener("click", () => {
    if (frame === null) frame = requestAnimationFrame(tick);
  }, {signal: api.signal});
  pause.addEventListener("click", stop, {signal: api.signal});
  reset.addEventListener("click", () => {
    stop();
    elapsed = 0;
    draw();
  }, {signal: api.signal});
  api.onSlideLeave(stop);
  draw();
  return stop;
});
