// The factory floor behind the home page story. Everything is built in code: no models
// or textures to download. One number drives it: `s`, the scene the reader has scrolled
// to (0 = Friday afternoon ... 5 = Monday morning), fractions included.
import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'

const GREEN = 0x14e8a0
const AMBER = 0xffb84d
const RED = 0xff5c6c
const AGENT_COLORS = [0x4d9bff, 0x14e8a0, 0xa78bfa, 0xffb84d, 0xff6b81]
const ALERTS = 22000 // one dot per alert the plant raises in a day

const clamp01 = (t) => Math.min(1, Math.max(0, t))
const smooth = (t) => t * t * (3 - 2 * t)
const ramp = (x, a, b) => smooth(clamp01((x - a) / (b - a)))
const lerp = (a, b, t) => a + (b - a) * t

// camera position, what it looks at, and how far the picture shifts sideways to leave
// room for the text (0 = centred), one entry per scene
const SHOTS = [
  { p: [-9.5, 4.4, 13.5], t: [0, 1.4, 0], x: 0.17, y: 0 },
  { p: [-3.6, 2.5, 6.4], t: [0.3, 1.6, 0], x: 0.17, y: 0 },
  { p: [4.8, 3.7, 7.6], t: [0, 1.9, 0], x: 0.17, y: 0 },
  { p: [0, 3.4, 13.5], t: [0, 1.5, 0], x: 0, y: 0.25 },
  { p: [7.6, 3.5, 8.8], t: [1.8, 1.2, 0], x: 0.17, y: 0 },
  { p: [-2, 9.5, 18], t: [0, 1, -2], x: 0, y: 0.1 },
]

function glowTexture() {
  const c = document.createElement('canvas')
  c.width = c.height = 128
  const g = c.getContext('2d')
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64)
  grad.addColorStop(0, 'rgba(255,255,255,1)')
  grad.addColorStop(0.25, 'rgba(255,255,255,0.55)')
  grad.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = grad
  g.fillRect(0, 0, 128, 128)
  return new THREE.CanvasTexture(c)
}

function numberTexture(text, bright) {
  const c = document.createElement('canvas')
  c.width = 256; c.height = 160
  const g = c.getContext('2d')
  g.fillStyle = bright ? '#eef4f8' : '#8597a8'
  g.font = '700 120px system-ui, sans-serif'
  g.textAlign = 'center'; g.textBaseline = 'middle'
  g.fillText(text, 128, 86)
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

function makeMachine(mats, number, detailed) {
  const g = new THREE.Group()
  const add = (geo, mat, x, y, z) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); g.add(m); return m }
  add(new THREE.BoxGeometry(2.6, 0.7, 1.8), mats.steel, 0, 0.35, 0)            // bed
  add(new THREE.BoxGeometry(0.8, 2.2, 0.6), mats.steel, 0, 1.8, -0.75)         // column
  add(new THREE.BoxGeometry(0.6, 0.5, 1.0), mats.dark, 0, 2.5, -0.2)           // arm
  const strip = add(new THREE.BoxGeometry(2.6, 0.06, 0.06),
    new THREE.MeshBasicMaterial({ color: GREEN }), 0, 0.72, 0.91)              // status light
  g.userData.strip = strip.material
  if (!detailed) return g

  add(new THREE.BoxGeometry(1.4, 0.12, 1.1), mats.table, 0, 0.82, 0.1)         // table
  add(new THREE.CylinderGeometry(0.2, 0.2, 0.6, 20), mats.dark, 0, 2.05, 0.15) // spindle housing
  const spin = new THREE.Group()
  spin.position.set(0, 1.72, 0.15)
  const chuck = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.07, 0.09), mats.bright)
  const tool = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.03, 0.42, 10), mats.bright)
  tool.position.y = -0.22
  spin.add(chuck, tool)
  g.add(spin)
  g.userData.spin = spin
  if (number) {
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(0.62, 0.39),
      new THREE.MeshBasicMaterial({ map: numberTexture(number, number === '7'), transparent: true }))
    plate.position.set(-0.85, 0.36, 0.905)
    g.add(plate)
  }
  return g
}

export function createScene(canvas, { mobile = false } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !mobile, powerPreference: 'high-performance' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, mobile ? 1.5 : 2))
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.15

  const scene = new THREE.Scene()
  const night = new THREE.Color(0x05080c)
  const dawn = new THREE.Color(0x2b2530)
  scene.background = night.clone()
  scene.fog = new THREE.FogExp2(night.getHex(), 0.028)

  // something for the metal to reflect, or it renders black
  const pmrem = new THREE.PMREMGenerator(renderer)
  const envMap = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
  scene.environment = envMap
  scene.environmentIntensity = 0.3
  pmrem.dispose()

  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 200)
  const lookAt = new THREE.Vector3()

  // --- light ---
  const hemi = new THREE.HemisphereLight(0x8fb3ff, 0x05070a, 0.55)
  const sun = new THREE.DirectionalLight(0xffffff, 0.7)
  sun.position.set(6, 10, 7)
  const key = new THREE.SpotLight(0xdff3ff, 5.5, 30, 0.5, 0.75, 0)   // on Machine 7
  key.position.set(-1.5, 9, 4.5)
  key.target.position.set(0, 1, 0)
  const human = new THREE.SpotLight(0xffd9a8, 0, 22, 0.36, 0.8, 0)   // the person who decides
  human.position.set(0, 7.5, 8.5)
  human.target.position.set(0, 0.9, 4.3)
  const agentGlow = new THREE.PointLight(0xcfe6ff, 0, 6, 0)
  agentGlow.position.set(0, 3.4, 1.2)
  scene.add(hemi, sun, key, key.target, human, human.target, agentGlow)

  // --- floor ---
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(160, 160),
    new THREE.MeshStandardMaterial({ color: 0x0b1118, roughness: 0.55, metalness: 0.6 }))
  floor.rotation.x = -Math.PI / 2
  const grid = new THREE.GridHelper(160, 80, 0x163944, 0x0e1f28)
  grid.position.y = 0.01
  grid.material.transparent = true
  grid.material.opacity = 0.55
  scene.add(floor, grid)

  // --- machines ---
  const mats = {
    steel: new THREE.MeshStandardMaterial({ color: 0x4a5866, roughness: 0.42, metalness: 0.7 }),
    dark: new THREE.MeshStandardMaterial({ color: 0x1d262f, roughness: 0.6, metalness: 0.5 }),
    table: new THREE.MeshStandardMaterial({ color: 0x70808f, roughness: 0.3, metalness: 0.85 }),
    bright: new THREE.MeshStandardMaterial({ color: 0xcfd9e3, roughness: 0.25, metalness: 0.9 }),
  }
  const front = [['3', -7.2], ['5', -3.6], ['7', 0], ['8', 3.6], ['', 7.2]].map(([n, x]) => {
    const m = makeMachine(mats, n, true)
    m.position.x = x
    scene.add(m)
    return m
  })
  const m7 = front[2]
  const m8 = front[3]
  for (let row = 1; row <= 2; row++) {
    for (let i = -3; i <= 3; i++) {
      const m = makeMachine(mats, '', false)
      m.position.set(i * 3.6 + (row % 2) * 1.8, 0, -row * 6.5)
      scene.add(m)
    }
  }

  // --- the day's alerts: 22,000 dots, one of which matters ---
  const pos = new Float32Array(ALERTS * 3)
  for (let i = 0; i < ALERTS; i++) {
    pos[i * 3] = (Math.random() - 0.5) * 64
    pos[i * 3 + 1] = 0.6 + Math.random() * 15
    pos[i * 3 + 2] = -34 + Math.random() * 46
  }
  const alertGeo = new THREE.BufferGeometry()
  alertGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  const glow = glowTexture()
  const alertMat = new THREE.PointsMaterial({
    color: 0x9fd6e6, size: 0.12, map: glow, transparent: true, opacity: 0,
    depthWrite: false, blending: THREE.AdditiveBlending,
  })
  const alerts = new THREE.Points(alertGeo, alertMat)
  scene.add(alerts)

  const sprite = (color, size) => {
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({
      map: glow, color, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending,
    }))
    sp.scale.setScalar(size)
    scene.add(sp)
    return sp
  }
  const theAlert = sprite(RED, 1.5)
  const alertFrom = new THREE.Vector3(-13, 11, -9)
  const alertTo = new THREE.Vector3(0, 1.72, 0.15)

  // --- the coordinator and the five specialists ---
  const coordinator = sprite(0xffd479, 2.1)
  const coordPos = new THREE.Vector3(0, 4.4, 0.2)
  coordinator.position.copy(coordPos)
  const agents = AGENT_COLORS.map((c) => sprite(c, 1.25))
  const linkPos = new Float32Array(5 * 2 * 3)
  const linkCol = new Float32Array(5 * 2 * 3)
  AGENT_COLORS.forEach((c, k) => {
    const col = new THREE.Color(c)
    for (let v = 0; v < 2; v++) col.toArray(linkCol, (k * 2 + v) * 3)
  })
  const linkGeo = new THREE.BufferGeometry()
  linkGeo.setAttribute('position', new THREE.BufferAttribute(linkPos, 3))
  linkGeo.setAttribute('color', new THREE.BufferAttribute(linkCol, 3))
  const linkMat = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0, depthWrite: false })
  const links = new THREE.LineSegments(linkGeo, linkMat)
  links.frustumCulled = false
  scene.add(links)

  // --- the gate: nothing over 500 euros passes without a person ---
  const ringMat = new THREE.MeshBasicMaterial({ color: AMBER, transparent: true, opacity: 0, depthWrite: false })
  const rings = [3.0, 3.45].map((r) => {
    const m = new THREE.Mesh(new THREE.TorusGeometry(r, 0.028, 8, 128), ringMat)
    m.rotation.x = Math.PI / 2
    scene.add(m)
    return m
  })

  // --- the person ---
  const skin = new THREE.MeshStandardMaterial({ color: 0xbfae98, roughness: 0.95, transparent: true, opacity: 0 })
  const person = new THREE.Group()
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.17, 0.5, 6, 14), skin)
  torso.position.y = 1.15
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.125, 18, 14), skin)
  head.position.y = 1.68
  person.add(torso, head)
  ;[-0.085, 0.085].forEach((x) => {
    const leg = new THREE.Mesh(new THREE.CapsuleGeometry(0.068, 0.62, 4, 10), skin)
    leg.position.set(x, 0.4, 0)
    person.add(leg)
  })
  person.position.set(0, 0, 4.3)
  scene.add(person)

  // --- the bearing on its way, and the five jobs that move to Machine 8 ---
  const parcel = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.22, 0.3),
    new THREE.MeshStandardMaterial({ color: 0xffe2a8, emissive: AMBER, emissiveIntensity: 0.9, roughness: 0.5 }))
  const parcelGlow = sprite(AMBER, 1.3)
  parcel.visible = false
  scene.add(parcel)
  const route = new THREE.CatmullRomCurve3([
    new THREE.Vector3(30, 0.5, -22), new THREE.Vector3(18, 0.5, -6), new THREE.Vector3(8, 0.5, 4.6),
    new THREE.Vector3(2.4, 0.5, 3.4), new THREE.Vector3(0.75, 0.95, 0.5),
  ])
  const jobMat = new THREE.MeshStandardMaterial({ color: 0xb9c6d3, roughness: 0.3, metalness: 0.85 })
  const jobs = [0, 1, 2, 3, 4].map((k) => {
    const j = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.14, 0.2), jobMat)
    scene.add(j)
    j.userData.slot = new THREE.Vector3(-0.44 + k * 0.22, 0.95, 0.42)
    return j
  })

  // --- state ---
  let target = 0
  let s = 0
  let orbit = 0
  let spinAngle = 0
  let raf = 0
  let last = performance.now()
  let width = 1
  let height = 1
  const tmp = new THREE.Vector3()
  const colA = new THREE.Color()
  const colB = new THREE.Color()

  const stripColor = (x) => {
    if (x < 0.8) return colA.set(GREEN)
    if (x < 1.0) return colA.set(GREEN).lerp(colB.set(RED), ramp(x, 0.8, 1.0))
    if (x < 3.45) return colA.set(RED)
    if (x < 4.6) return colA.set(RED).lerp(colB.set(AMBER), ramp(x, 3.45, 3.8))
    return colA.set(AMBER).lerp(colB.set(GREEN), ramp(x, 4.6, 4.9))
  }

  function frame(now) {
    raf = requestAnimationFrame(frame)
    const dt = Math.min(0.05, (now - last) / 1000)
    last = now
    const time = now / 1000
    s += (target - s) * (1 - Math.exp(-Math.max(0, dt) * 5))
    if (!Number.isFinite(s)) s = 0

    // camera: glide between shots, dwell on each one
    const i = Math.max(0, Math.min(SHOTS.length - 2, Math.floor(s)))
    const f = smooth(clamp01(s - i))
    const a = SHOTS[i]
    const b = SHOTS[i + 1]
    const drift = Math.sin(time * 0.22) * 0.25
    camera.position.set(lerp(a.p[0], b.p[0], f) + drift, lerp(a.p[1], b.p[1], f) + Math.sin(time * 0.31) * 0.08, lerp(a.p[2], b.p[2], f))
    lookAt.set(lerp(a.t[0], b.t[0], f), lerp(a.t[1], b.t[1], f), lerp(a.t[2], b.t[2], f))
    camera.lookAt(lookAt)
    const shift = width > 900 ? lerp(a.x, b.x, f) : 0
    const lift = width > 900 ? lerp(a.y, b.y, f) : 0.14
    camera.setViewOffset(width, height, -shift * width, lift * height, width, height)

    // Machine 7: spins, then shakes as the bearing wears, then stops for the repair
    const shake = ramp(s, 0.55, 1.2) * (1 - 0.6 * ramp(s, 3.4, 3.8)) * (1 - ramp(s, 4.0, 4.3))
    m7.position.set(Math.sin(time * 61) * 0.012 * shake, 0, Math.cos(time * 53) * 0.009 * shake)
    m7.rotation.z = Math.sin(time * 47) * 0.004 * shake
    const speed = 16 * (1 - ramp(s, 3.5, 4.0)) + 16 * ramp(s, 4.7, 5)
    spinAngle += dt * speed
    m7.userData.spin.rotation.y = spinAngle
    front.forEach((m, k) => { if (k !== 2 && m.userData.spin) m.userData.spin.rotation.y = time * (k === 3 ? 4 + 12 * ramp(s, 3.6, 4.2) : 15) })
    m7.userData.strip.color.copy(stripColor(s))
    m8.userData.strip.color.set(0x5f7184).lerp(colB.set(GREEN), ramp(s, 3.6, 4.2))

    // the day's alerts, and the one that matters
    alertMat.opacity = 0.8 * ramp(s, 0.3, 0.9) * (1 - 0.8 * ramp(s, 1.5, 2.2))
    alerts.rotation.y = time * 0.012
    const fall = ramp(s, 0.5, 1.0)
    theAlert.position.lerpVectors(alertFrom, alertTo, fall)
    theAlert.material.opacity = ramp(s, 0.4, 0.6) * (1 - ramp(s, 3.5, 4.1)) * (0.75 + 0.25 * Math.sin(time * 6))
    theAlert.scale.setScalar(lerp(0.7, 1.7, fall) * (1 + 0.12 * Math.sin(time * 6)))

    // specialists arrive one at a time and circle the machine; they hold still at the gate
    const hold = ramp(s, 2.7, 2.95) * (1 - ramp(s, 3.35, 3.6))
    orbit += dt * 0.5 * (1 - hold)
    coordinator.material.opacity = 0.95 * ramp(s, 1.2, 1.5) * (1 - ramp(s, 4.4, 4.9))
    coordinator.scale.setScalar(2.1 + 0.18 * Math.sin(time * 2.2))
    let shown = 0
    agents.forEach((ag, k) => {
      const arrive = ramp(s, 1.4 + k * 0.2, 1.65 + k * 0.2)
      const leave = ramp(s, 4.3 + k * 0.05, 4.7 + k * 0.05)
      const ang = orbit + k * ((Math.PI * 2) / 5)
      tmp.set(Math.cos(ang) * 2.35, 1.75 + Math.sin(time * 1.3 + k) * 0.22, Math.sin(ang) * 2.35)
      ag.position.lerpVectors(coordPos, tmp, arrive)
      ag.position.y += leave * 5
      ag.material.opacity = arrive * (1 - leave)
      shown += arrive * (1 - leave)
      coordPos.toArray(linkPos, k * 6)
      ag.position.toArray(linkPos, k * 6 + 3)
    })
    linkGeo.attributes.position.needsUpdate = true
    linkMat.opacity = 0.34 * Math.min(1, shown) * (1 - ramp(s, 4.3, 4.6))
    agentGlow.intensity = 0.22 * shown

    // the gate closes around the machine, waits, then opens green
    const gate = ramp(s, 2.6, 3.0)
    const open = ramp(s, 3.3, 3.75)
    ringMat.opacity = 0.9 * gate * (1 - open)
    ringMat.color.set(AMBER).lerp(colB.set(GREEN), ramp(s, 3.25, 3.4))
    rings.forEach((r, k) => {
      r.position.y = lerp(4.6, 1.15 + k * 0.5, gate)
      r.scale.setScalar(1 + open * 0.9)
      r.rotation.z = time * (k ? -0.25 : 0.25)
    })

    // the person steps into the light
    const here = ramp(s, 2.5, 2.95)
    skin.opacity = here * (1 - ramp(s, 4.5, 4.95))
    person.visible = skin.opacity > 0.01
    human.intensity = 2.6 * here * (1 - ramp(s, 4.4, 4.9))
    hemi.intensity = 0.55 - 0.3 * gate * (1 - open) + 0.75 * ramp(s, 4.35, 5)
    key.intensity = 5.5 - 2.6 * gate * (1 - open)

    // the bearing arrives; the jobs hop over to Machine 8
    const go = clamp01((s - 3.45) / 0.6)
    parcel.visible = go > 0 && go < 1
    if (parcel.visible) {
      route.getPoint(smooth(go), parcel.position)
      parcel.rotation.y = time * 2
      parcelGlow.position.copy(parcel.position)
    }
    parcelGlow.material.opacity = parcel.visible ? 0.9 * Math.sin(go * Math.PI) ** 0.5 : 0
    jobs.forEach((j, k) => {
      const t = ramp(s, 3.55 + k * 0.08, 3.95 + k * 0.08)
      const slot = j.userData.slot
      j.position.set(slot.x + t * 3.6, slot.y + Math.sin(t * Math.PI) * 1.5, slot.z)
      j.rotation.y = t * Math.PI * 2
    })

    // Monday morning
    const day = ramp(s, 4.35, 5)
    scene.environmentIntensity = 0.3 - 0.14 * gate * (1 - open) + 0.5 * day
    scene.background.copy(night).lerp(dawn, day)
    scene.fog.color.copy(scene.background)
    scene.fog.density = lerp(0.028, 0.017, day)
    hemi.color.set(0x8fb3ff).lerp(colB.set(0xffe2bd), day)
    sun.intensity = 0.7 + 1.3 * day
    sun.color.set(0xffffff).lerp(colB.set(0xffc98a), day)

    renderer.render(scene, camera)
  }

  return {
    setProgress(v) { if (Number.isFinite(v)) target = Math.min(SHOTS.length - 1, Math.max(0, v)) },
    setSize(w, h) {
      width = w; height = h
      renderer.setSize(w, h, false)
      camera.aspect = w / h
      camera.fov = w < 700 ? 52 : 38
      camera.updateProjectionMatrix()
    },
    start() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame) } },
    stop() { cancelAnimationFrame(raf); raf = 0 },
    dispose() {
      cancelAnimationFrame(raf); raf = 0
      scene.traverse((o) => {
        o.geometry?.dispose?.()
        const m = o.material
        if (m) (Array.isArray(m) ? m : [m]).forEach((x) => { x.map?.dispose?.(); x.dispose?.() })
      })
      envMap.dispose()
      renderer.dispose()
    },
  }
}
