import { useEffect, useState } from 'react'
import Logo from './Logo.jsx'
import IELogo from './IELogo.jsx'
import { TEAM, GUEST } from './team.js'

const REEL = [
  { name: 'Coordinator', role: 'decides who goes next', color: '#ffd479' },
  { name: 'Maintenance', role: 'what is failing, and when', color: '#4d9bff' },
  { name: 'Purchasing', role: 'finds the parts and the price', color: '#14e8a0' },
  { name: 'Production', role: 'keeps the line running', color: '#a78bfa' },
  { name: 'Quality', role: 'checks for defects', color: '#ffb84d' },
  { name: 'Safety', role: 'can stop the whole plan', color: '#ff6b81' },
]

export default function SignIn({ onEnter }) {
  const [i, setI] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % REEL.length), 2400)
    return () => clearInterval(id)
  }, [])
  const agent = REEL[i]

  return (
    <div className="signin" style={{ '--accent': agent.color }}>
      {/* atmosphere */}
      <div className="si-aura a1" /><div className="si-aura a2" /><div className="si-stars" />

      {/* corner brands, IE University (left) · course wordmark (right) */}
      <div className="si-corner tl" aria-label="IE University">
        <IELogo size={30} color="#fff" />
        <span className="ie-word">University</span>
      </div>
      <div className="si-corner tr" aria-label="Agentic AI for IT">
        <span className="si-script">Agentic AI for IT</span>
      </div>
      {/* wavy bottom, color shifts with the active agent */}
      <svg className="si-waves" viewBox="0 0 1440 320" preserveAspectRatio="none" aria-hidden="true">
        <path className="si-wave w1" d="M0,160 C320,260 520,80 760,150 C1040,230 1240,90 1440,160 L1440,320 L0,320 Z" />
        <path className="si-wave w2" d="M0,210 C300,150 560,290 820,210 C1100,130 1300,250 1440,200 L1440,320 L0,320 Z" />
      </svg>

      <div className="si-card">
        <div className="si-brand"><Logo size={40} accent={agent.color} /> <span>Operations Sentinel</span></div>
        <div className="si-tagline">One sensor alert.<br />Five specialists.<br /><em>One costed plan.</em></div>
        <p className="si-what">An AI team for a factory. When a machine starts to fail, it works out what is wrong, what the fix costs and whether it is safe, then asks a manager to approve the spend.</p>

        {/* agent showreel, cycles agent → agent like a video */}
        <div className="si-reel">
          <span className="si-reel-eyebrow">Meet the team</span>
          <div className="si-reel-stage" key={i}>
            <span className="si-reel-dot" style={{ background: agent.color }} />
            <div className="si-reel-txt">
              <div className="si-reel-name">{agent.name}</div>
              <div className="si-reel-role">{agent.role}</div>
            </div>
          </div>
          <div className="si-reel-track">
            {REEL.map((a, j) => <span key={j} className={`si-pip ${j === i ? 'on' : ''}`} style={{ background: j === i ? agent.color : undefined }} />)}
          </div>
        </div>

        {/* visitors go straight in; presenters can still sign in as themselves */}
        <button className="si-demo" onClick={() => onEnter(GUEST)}>See the demo <span aria-hidden="true">→</span></button>
        <p className="si-demo-note">A recorded run plays in your browser. No account, nothing to install.</p>
        <div className="si-team">
          <span className="si-team-label">Presenting? Sign in as</span>
          {TEAM.map((m) => (
            <button key={m.name} className="si-ava" onClick={() => onEnter(m)} style={{ '--mc': m.color }}
              title={m.name} aria-label={`Sign in as ${m.name}`}>{m.initials}</button>
          ))}
        </div>
      </div>
    </div>
  )
}
