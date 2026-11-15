// Official IE University mark (vector from the public brand asset), rendered in a single ink
// so it can be flipped white for the dark sign-in. currentColor drives all three shapes.
export default function IELogo({ size = 34, color = '#fff' }) {
  const h = size
  const w = (319.663 / 337.5947) * size
  return (
    <svg width={w} height={h} viewBox="0 0 319.66299 337.5947" fill="none" aria-hidden="true" style={{ color }}>
      <path
        d="M 42.52,0 C 65.949,0 85.04,19.02 85.04,42.491 85.04,65.962 65.949,85.039 42.52,85.039 19.033,85.039 0,65.962 0,42.491 0,19.02 19.033,0 42.52,0"
        fill="currentColor"
      />
      <polygon points="8.4851,110.551 8.4851,331.653 76.5161,331.653 76.5161,110.551" fill="currentColor" />
      <path
        d="m 208.36,192.04 -43.705,0 c 4.179,-17.235 18.202,-32.849 43.705,-32.849 25.503,0 39.526,15.614 43.705,32.849 l -43.705,0 z m 111.303,29.763 -0.001,-1.208 c -0.233,-64.087 -43.085,-115.95 -113.068,-115.95 -69.984,0 -112.8352,51.863 -113.0682,115.95 l -0.002,1.208 c 0,70.3837 54.4912,115.7917 122.6062,115.7917 35.419,0 71.292,-15.892 93.089,-43.593 l -46.353,-33.992 c -12.229,14.337 -27.664,25.82 -49.915,25.82 -26.337,0 -45.863,-16.802 -51.312,-42.6847 l 156.229,0 c 1.158,-6.828 1.795,-13.938 1.795,-21.342 l 0,0 z"
        fill="currentColor"
      />
    </svg>
  )
}
