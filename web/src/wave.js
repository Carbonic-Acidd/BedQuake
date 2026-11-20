// Draws the horizon: the logo's zigzag (round joins, flat at both ends) running the full
// width, its height following an alarm type's real envelope (the same steps as pico/shaker.py).
const LIVE_W = 1000, LIVE_H = 200 // the wave's viewBox (index.html)
const LIVE_PAD = 8                // room for the stroke at the top and bottom
const MS_PER_PX = 12              // alarm time per screen pixel (a phone shows a whole classic loop)
const MAX_LOOP_MS = 9000          // longer types (rise) play faster on screen so their shape shows
const ZIG_PX = 14                 // on-screen width of one zig (half an oscillation)
const ZIGS_PER_MS = 0.004         // how fast the ripple runs to the right
const EDGE = 0.1                  // share of each end that stays flat, like the logo's lead-in
const FOLLOW = 0.1                // per frame, how far the height moves toward its target
const STILL_MS = 1500             // with reduced motion, the moment of the type shown

const ease = (p) => (1 - Math.cos(Math.PI * p)) / 2   // smooth ramp between step strengths
const round = (n) => Math.round(n * 10) / 10
const loopMs = (steps) => steps.reduce((sum, step) => sum + step[2], 0)

function smoothstep(from, to, v) {
  const t = Math.min(1, Math.max(0, (v - from) / (to - from)))
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

// Animates `path`. Returns set(steps, height): height 0 settles it into a flat line and stops
// the animation; 1 is full height.
export function liveWave(path, reducedMotion) {
  let steps = null
  let target = 0
  let height = 0
  let frame = 0

  function draw(now) {
    const t = reducedMotion ? STILL_MS : now
    height = reducedMotion ? target : height + (target - height) * FOLLOW
    if (Math.abs(height - target) < 0.002) height = target

    const width = path.ownerSVGElement.clientWidth || LIVE_W
    const zig = (ZIG_PX * LIVE_W) / width                 // one zig in viewBox units
    const speed = steps ? Math.max(1, loopMs(steps) / MAX_LOOP_MS) : 1
    const msPerUnit = (MS_PER_PX * width) / LIVE_W * speed
    const at = (x) => t * speed - x * msPerUnit            // newest at the left, flowing right
    // A zig takes the strongest moment it spans, so a short knock still reaches a full peak.
    const strongest = (x) => steps ? Math.max(...[-0.5, 0, 0.5].map((side) => strengthAt(steps, at(x + side * zig)))) : 0

    const run = t * ZIGS_PER_MS
    const offset = run % 1
    const first = Math.floor(run)
    const middle = LIVE_H / 2
    let d = `M0 ${middle}`
    for (let k = 0; (k + offset) * zig < LIVE_W; k++) {
      const x = (k + offset) * zig
      const u = x / LIVE_W
      const index = k - first   // stays with its zig as it moves, so heights don't jump
      const taper = smoothstep(EDGE * 0.3, EDGE, Math.min(u, 1 - u))
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

  return function set(newSteps, newTarget) {
    steps = newSteps
    target = newTarget
    if (!frame) frame = requestAnimationFrame(draw)
  }
}
