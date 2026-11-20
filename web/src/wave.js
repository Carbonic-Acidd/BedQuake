// Draws the live trace in the logo's style: a zigzag with round joins whose height follows an
// alarm type's envelope (the same steps as pico/shaker.py). How a type is drawn (its "view"):
//   "scroll": flows through in real time at a fixed scale (Classic, Waves)
//   "cycle":  flows through, zoomed so one cycle fills the width (Knock's short taps stay apart)
//   "pinned": one whole cycle that stays put, start at the left (Rise's climb from silence)
const LIVE_W = 1000, LIVE_H = 200 // the trace's viewBox (index.html)
const LIVE_PAD = 8                // room for the stroke at the top and bottom
const MS_PER_PX = 12              // scrolling: alarm time per screen pixel (a phone shows a whole classic loop)
const MAX_LOOP_MS = 9000          // scrolling: longer types play faster on screen so their shape shows
const ZIG_PX = 14                 // on-screen width of one zig (half an oscillation) ...
const ZIG_MIN_PX = 5              // ... narrower if a tap is too short to fit
const ZIGS_PER_TAP = 1.75         // this many zigs (keeps Classic and Knock at the full width)
const CYCLE_MIN_MS = 2800         // "cycle": one cycle crosses the screen no faster than this
const ZIGS_PER_MS = 0.004         // how fast the ripple runs to the right
const EDGE = 0.1                  // scrolling: share of each end kept flat, like the logo's lead-in
const EDGE_PINNED = 0.04          // pinned: a smaller lead-in, so the climb starts near the left
const FOLLOW = 0.1                // per frame, how far the height moves toward its target
const STILL_MS = 1500             // with reduced motion, the moment of the type shown

const ease = (p) => (1 - Math.cos(Math.PI * p)) / 2   // smooth ramp between step strengths
const round = (n) => Math.round(n * 10) / 10
const clamp = (v, low, high) => Math.min(high, Math.max(low, v))
const loopMs = (steps) => steps.reduce((sum, step) => sum + step[2], 0)

function smoothstep(from, to, v) {
  const t = clamp((v - from) / (to - from), 0, 1)
  return t * t * (3 - 2 * t)
}

// Strength (0..1) of a looped alarm type at time t in ms.
function strengthAt(steps, t) {
  const length = loopMs(steps)
  let ms = ((t % length) + length) % length
  for (const [from, to, duration] of steps) {
    if (ms < duration) return from + (to - from) * ease(ms / duration)
    ms -= duration
  }
  return 0
}

// Animates `path`. Returns set(steps, height, view): height 0 settles it into a flat line and
// stops the animation; 1 is full height; view is "scroll", "cycle" or "pinned" (see the top).
export function liveWave(path, reducedMotion) {
  let steps = null
  let target = 0
  let height = 0
  let view = 'scroll'
  let frame = 0

  function draw(now) {
    const t = reducedMotion ? STILL_MS : now
    height = reducedMotion ? target : height + (target - height) * FOLLOW
    if (Math.abs(height - target) < 0.002) height = target

    const width = path.ownerSVGElement.clientWidth || LIVE_W
    const loop = steps ? loopMs(steps) : 1
    // How much alarm time one viewBox unit covers, how fast it flows, and the time at each x
    const whole = view !== 'scroll'   // one cycle across the width
    const speed = view === 'cycle' ? loop / Math.max(loop, CYCLE_MIN_MS) : steps ? Math.max(1, loop / MAX_LOOP_MS) : 1
    const msPerUnit = whole ? loop / LIVE_W : (MS_PER_PX * width) / LIVE_W * speed
    const at = (x) => view === 'pinned' ? x * msPerUnit : t * speed - x * msPerUnit   // flowing: newest at the left

    const taps = steps ? steps.filter((step) => step[0] || step[1]).map((step) => step[2]) : []
    const tapPx = taps.length ? Math.min(...taps) / msPerUnit * (width / LIVE_W) : Infinity
    const zigPx = clamp(tapPx / ZIGS_PER_TAP, ZIG_MIN_PX, ZIG_PX)
    const zig = (zigPx * LIVE_W) / width                       // one zig in viewBox units
    // A zig takes the strongest moment it spans, so a short tap still reaches a full peak.
    const strongest = (x) => steps ? Math.max(...[-0.5, 0, 0.5].map((side) => strengthAt(steps, at(x + side * zig)))) : 0

    const edge = view === 'pinned' ? EDGE_PINNED : EDGE
    const run = t * ZIGS_PER_MS
    const offset = run % 1
    const first = Math.floor(run)
    const middle = LIVE_H / 2
    let d = `M0 ${middle}`
    for (let k = 0; (k + offset) * zig < LIVE_W; k++) {
      const x = (k + offset) * zig
      const u = x / LIVE_W
      const index = k - first   // stays with its zig as it moves, so heights don't jump
      const taper = smoothstep(edge * 0.3, edge, Math.min(u, 1 - u))
      const vary = 0.8 + 0.2 * Math.abs(Math.sin(index * 2.39))   // uneven peaks, like the logo
      const sign = index % 2 ? -1 : 1
      d += ` L${round(x)} ${round(middle - sign * height * taper * vary * strongest(x) * (middle - LIVE_PAD))}`
    }
    path.setAttribute('d', d + ` L${LIVE_W} ${middle}`)

    const moving = !reducedMotion && !document.hidden && (target > 0 || height > 0)
    frame = moving ? requestAnimationFrame(draw) : 0
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !frame) frame = requestAnimationFrame(draw)
  })

  return function set(newSteps, newTarget, newView = 'scroll') {
    steps = newSteps
    target = newTarget
    view = newView
    if (!frame) frame = requestAnimationFrame(draw)
  }
}
