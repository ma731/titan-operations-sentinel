// Titan's voice. Lines that were pre-recorded with a neural voice play as audio files
// (natural, the same in every browser, works on the static demo). Anything else, such
// as a live model answer, uses the most natural voice this browser offers.
import MANIFEST from './voiceManifest.json'


let current = null
const pickVoice = () => {
  const vs = window.speechSynthesis?.getVoices?.() || []
  const en = vs.filter((v) => /^en[-_]/i.test(v.lang))
  const rank = (v) => (/natural|neural/i.test(v.name) ? 4 : 0) + (/online/i.test(v.name) ? 2 : 0)
    + (/(ava|aria|jenny|sonia|libby|emma|samantha|google uk english female|google us english)/i.test(v.name) ? 3 : 0)
    + (/en-gb|en-us/i.test(v.lang) ? 1 : 0)
  return en.sort((a, b) => rank(b) - rank(a))[0] || null
}

export function stopSpeaking() {
  if (current) { current.pause(); current = null }
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel()
}

export function speak(text) {
  if (!text) return
  stopSpeaking()
  const file = MANIFEST[text]
  if (file) {
    const a = new Audio(`${import.meta.env.BASE_URL}voice/${file}`)
    current = a
    // A pause() from stopSpeaking or mute rejects play() with AbortError: stay quiet then.
    a.play().catch((e) => { if (current === a && e?.name !== 'AbortError') fallback(text) })
    return
  }
  fallback(text)
}

function fallback(text) {
  if (!('speechSynthesis' in window)) return
  const u = new SpeechSynthesisUtterance(text.replace(/€/g, ' euros ').replace(/\s+/g, ' '))
  const v = pickVoice()
  if (v) { u.voice = v; u.lang = v.lang } else u.lang = 'en-GB'
  u.rate = 0.97; u.pitch = 0.95
  window.speechSynthesis.speak(u)
}

export const canSpeak = () => typeof window !== 'undefined' && ('speechSynthesis' in window || typeof Audio !== 'undefined')
