import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Bell,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Clock3,
  FileHeart,
  Heart,
  HeartPulse,
  History,
  Languages,
  LogOut,
  Menu,
  Plus,
  QrCode,
  ShieldCheck,
  Siren,
  Stethoscope,
  UserRound,
  UsersRound,
  Volume2,
  X,
} from 'lucide-react'
import { api, API_BASE, ApiError } from './api'
import BodyMap from './BodyMap'
import './App.css'

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'health', label: 'Health record', icon: HeartPulse },
  { id: 'consent', label: 'Consent & access', icon: ShieldCheck },
  { id: 'timeline', label: 'Activity timeline', icon: History },
  { id: 'admission', label: 'Admission', icon: ClipboardList },
]

const CONSENT_LABELS = {
  blood_group: 'Blood group',
  allergies: 'Allergies',
  medications: 'Medications',
  conditions: 'Health conditions',
  contacts: 'Trusted contacts',
  injuries: 'Injury history',
  insurer: 'Insurer notice',
}

const enHi = {
  Overview: 'डैशबोर्ड',
  'Health record': 'स्वास्थ्य रिकॉर्ड',
  'Consent & access': 'सहमति और पहुँच',
  'Activity timeline': 'गतिविधि',
  Admission: 'अस्पताल में भर्ती',
  'Good morning': 'सुप्रभात',
  'Your health, safely connected.': 'आपका स्वास्थ्य, सुरक्षित रूप से जुड़ा हुआ।',
}

function formatDate(value, options = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!value) return 'Date not recorded'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date not recorded' : date.toLocaleDateString('en-IN', options)
}

function initials(value = '') {
  return value
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function getErrorMessage(error) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Please try again.'
}

function LoginScreen({ onLogin }) {
  const [role, setRole] = useState('guardian')
  const [phone, setPhone] = useState('+91 98990 11223')
  const [challenge, setChallenge] = useState(null)
  const [code, setCode] = useState('')
  const [name, setName] = useState('Demo responder')
  const [organization, setOrganization] = useState('City Care Ambulance')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function requestCode(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api('/auth/otp/request', {
        method: 'POST',
        body: JSON.stringify({ phone }),
      })
      setChallenge(result)
      setCode(result.demo_code || '')
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  async function verifyCode(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api('/auth/otp/verify', {
        method: 'POST',
        body: JSON.stringify({ challenge_id: challenge.challenge_id, code }),
      })
      onLogin(result, phone)
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  async function loginResponder(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api('/auth/responder/login', {
        method: 'POST',
        body: JSON.stringify({ name, organization }),
      })
      onLogin(result, name)
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-screen">
      <div className="login-brand">
        <div className="brand-mark"><HeartPulse size={25} /></div>
        <span>care<span>link</span></span>
      </div>
      <section className="login-card">
        <div className="login-illustration">
          <div className="login-orbit orbit-one" />
          <div className="login-orbit orbit-two" />
          <div className="login-heart"><HeartPulse size={48} strokeWidth={1.7} /></div>
          <span className="floating-cross">+</span>
          <span className="floating-pulse"><Activity size={19} /></span>
        </div>
        <p className="eyebrow">CARELINK EMERGENCY BRIDGE</p>
        <h1>Your health, <span>within reach.</span></h1>
        <p className="login-copy">A trusted circle for the moments that matter most.</p>
        <div className="role-switch">
          <button className={role === 'guardian' ? 'selected' : ''} onClick={() => { setRole('guardian'); setChallenge(null) }}>
            <UsersRound size={17} /> Family guardian
          </button>
          <button className={role === 'responder' ? 'selected' : ''} onClick={() => { setRole('responder'); setChallenge(null) }}>
            <Siren size={17} /> Responder
          </button>
        </div>
        {role === 'guardian' ? (
          challenge ? (
            <form className="login-form" onSubmit={verifyCode}>
              <label htmlFor="otp">Demo verification code</label>
              <input id="otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value)} required />
              <div className="demo-hint"><CheckCircle2 size={16} /> Demo OTP generated locally: <strong>{challenge.demo_code || 'check SMS'}</strong></div>
              <button className="primary-button full-width" disabled={busy || code.length !== 6}>
                {busy ? 'Verifying…' : 'Verify & continue'} <ArrowRight size={17} />
              </button>
              <button type="button" className="text-button" onClick={() => setChallenge(null)}>Use another number</button>
            </form>
          ) : (
            <form className="login-form" onSubmit={requestCode}>
              <label htmlFor="phone">Guardian mobile number</label>
              <input id="phone" type="tel" autoComplete="tel" value={phone} onChange={(event) => setPhone(event.target.value)} required />
              <p className="field-helper">Demo guardian: +91 98990 11223</p>
              <button className="primary-button full-width" disabled={busy}>
                {busy ? 'Sending…' : 'Continue with OTP'} <ArrowRight size={17} />
              </button>
            </form>
          )
        ) : (
          <form className="login-form" onSubmit={loginResponder}>
            <label htmlFor="responder-name">Responder name</label>
            <input id="responder-name" value={name} onChange={(event) => setName(event.target.value)} required />
            <label htmlFor="organization">Organization</label>
            <input id="organization" value={organization} onChange={(event) => setOrganization(event.target.value)} required />
            <button className="primary-button full-width" disabled={busy}>
              {busy ? 'Signing in…' : 'Open responder console'} <ArrowRight size={17} />
            </button>
            <p className="field-helper">Simulated responder sign-in for demo use.</p>
          </form>
        )}
        {error && <div className="inline-error" role="alert">{error}</div>}
        <div className="login-security"><ShieldCheck size={16} /> Your records are shared only with your consent.</div>
      </section>
      <p className="demo-disclaimer">Demo experience · Synthetic patient records only</p>
    </main>
  )
}

function Sidebar({ active, onChange, patient, mode, onLogout, mobileOpen, closeMobile }) {
  return (
    <>
      {mobileOpen && <button aria-label="Close menu" className="mobile-scrim" onClick={closeMobile} />}
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark"><HeartPulse size={22} /></div>
          <span>care<span>link</span></span>
          <button className="mobile-close icon-button" aria-label="Close navigation" onClick={closeMobile}><X size={19} /></button>
        </div>
        <div className="sidebar-patient">
          <div className="avatar avatar-large">{initials(patient?.name)}</div>
          <div className="patient-name-wrap">
            <strong>{patient?.name || 'CareLink demo'}</strong>
            <span>{patient ? `Patient · Age ${patient.age}` : 'Emergency access'}</span>
          </div>
          <ChevronDown size={16} className="muted-icon" />
        </div>
        <p className="nav-caption">MENU</p>
        <nav className="main-nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <button key={item.id} className={`nav-item ${active === item.id ? 'nav-active' : ''}`} onClick={() => { onChange(item.id); closeMobile() }}>
                <Icon size={19} strokeWidth={active === item.id ? 2.2 : 1.8} />
                <span>{item.label}</span>
                {active === item.id && <i />}
              </button>
            )
          })}
          {mode === 'responder' && (
            <button className={`nav-item ${active === 'scan' ? 'nav-active' : ''}`} onClick={() => { onChange('scan'); closeMobile() }}>
              <QrCode size={19} /><span>Scan patient card</span>{active === 'scan' && <i />}
            </button>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon"><Heart size={17} /></div>
            <strong>Here for you</strong>
            <span>Your care circle is always close.</span>
          </div>
          <button className="profile-row" onClick={onLogout}>
            <div className="avatar">{initials(mode === 'responder' ? 'Responder' : patient?.guardian_name || 'Care giver')}</div>
            <span><strong>{mode === 'responder' ? 'Responder' : patient?.guardian_name || 'Family guardian'}</strong><small>{mode === 'responder' ? 'Demo access' : 'Guardian account'}</small></span>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
    </>
  )
}

function Topbar({ title, subtitle, language, onLanguage, onNotifications, notificationCount, onMenu }) {
  return (
    <header className="topbar">
      <button className="mobile-menu icon-button" aria-label="Open navigation" onClick={onMenu}><Menu size={21} /></button>
      <div className="page-heading">
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="topbar-actions">
        <span className="live-status"><i /> Demo data</span>
        <button className="language-button" onClick={onLanguage}><Languages size={17} /> {language === 'en' ? 'हिन्दी' : 'English'}</button>
        <button className="notification-button icon-button" aria-label="Notifications" onClick={onNotifications}>
          <Bell size={20} />{notificationCount > 0 && <i>{Math.min(notificationCount, 9)}</i>}
        </button>
        <div className="avatar">{initials('Family guardian')}</div>
      </div>
    </header>
  )
}

function StatCard({ label, value, detail, icon: Icon, tone = 'blue' }) {
  return (
    <article className="stat-card">
      <div className={`stat-icon ${tone}`}><Icon size={20} /></div>
      <div className="stat-text"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>
      <span className="stat-sparkline" aria-hidden="true">⌁</span>
    </article>
  )
}

function SectionTitle({ eyebrow, title, action, onAction }) {
  return (
    <div className="section-title">
      <div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{title}</h2></div>
      {action && <button className="text-link" onClick={onAction}>{action} <ChevronRight size={16} /></button>}
    </div>
  )
}

function ConditionBadge({ type }) {
  const labels = { condition: 'Condition', injury: 'Injury', surgery: 'Procedure', device: 'Device' }
  return <span className={`condition-badge badge-${type || 'condition'}`}>{labels[type] || 'Health record'}</span>
}

function TimelineItem({ item, compact = false }) {
  return (
    <article className={`timeline-item ${compact ? 'timeline-compact' : ''}`}>
      <div className={`timeline-dot ${item.is_active ? 'dot-active' : ''}`}><Activity size={14} /></div>
      <div className="timeline-content">
        <div className="timeline-title-row">
          <strong>{item.name || item.event || 'Care activity'}</strong>
          <ConditionBadge type={item.condition_type || 'condition'} />
        </div>
        <p>{item.notes || item.hospital_name || `Recorded by ${item.source_name || 'CareLink'}`}</p>
        <span className="timeline-date"><Clock3 size={13} /> {formatDate(item.occurred_at || item.created_at)}</span>
      </div>
    </article>
  )
}

function Overview({ patient, conditions, logs, admissions, onNavigate, onAddCondition, selectedCondition, onSelectCondition }) {
  const activeCount = conditions.filter((condition) => condition.is_active).length
  const historyCount = conditions.filter((condition) => !condition.is_active).length
  const recent = [...conditions].sort((a, b) => new Date(b.occurred_at || 0) - new Date(a.occurred_at || 0)).slice(0, 3)
  return (
    <>
      <section className="welcome-banner">
        <div className="welcome-copy">
          <span className="welcome-label"><span className="welcome-icon"><HeartPulse size={16} /></span> YOUR CARE CIRCLE, CONNECTED</span>
          <h2>Good morning, {patient?.guardian_name?.split(' ')[0] || 'there'} <span className="wave">✦</span></h2>
          <p>Your health, safely connected. Keep the important details close when they matter most.</p>
          <button className="banner-button" onClick={() => onNavigate('health')}>View health record <ArrowRight size={16} /></button>
        </div>
        <div className="banner-art" aria-hidden="true">
          <div className="banner-circle circle-back" />
          <div className="banner-circle circle-front" />
          <div className="banner-pulse"><HeartPulse size={45} /></div>
          <div className="banner-plus">+</div>
          <div className="banner-wave"><Activity size={84} strokeWidth={1.2} /></div>
        </div>
      </section>
      <section className="stats-grid" aria-label="Patient overview">
        <StatCard label="Health records" value={conditions.length} detail="Across your health history" icon={FileHeart} tone="blue" />
        <StatCard label="Current conditions" value={activeCount} detail="Shared with your care circle" icon={HeartPulse} tone="mint" />
        <StatCard label="Past injuries" value={historyCount} detail="Visible on your body map" icon={Activity} tone="peach" />
        <StatCard label="Emergency scans" value={logs.length} detail="Every access is recorded" icon={ShieldCheck} tone="lavender" />
      </section>
      <div className="content-grid overview-grid">
        <section className="panel body-panel">
          <SectionTitle eyebrow="YOUR BODY, YOUR STORY" title="Health map" action="Full health record" onAction={() => onNavigate('health')} />
          <div className="overview-body-content">
            <BodyMap conditions={conditions} selectedId={selectedCondition?.id} onSelect={onSelectCondition} />
            <div className="body-summary">
              {selectedCondition ? (
                <div className="selected-condition-card">
                  <span className="summary-chip"><span className="chip-dot" /> Selected area</span>
                  <h3>{selectedCondition.name}</h3>
                  <p>{selectedCondition.notes || `This ${selectedCondition.condition_type} is marked on your body map.`}</p>
                  <div className="summary-meta"><ConditionBadge type={selectedCondition.condition_type} /><span>{formatDate(selectedCondition.occurred_at)}</span></div>
                </div>
              ) : (
                <>
                  <span className="summary-chip"><span className="chip-dot" /> At a glance</span>
                  <h3>Every detail, in its place.</h3>
                  <p>Select a marker on the map to see a condition or a past injury.</p>
                  <div className="summary-stat-line"><HeartPulse size={18} /><span>Blood group</span><strong>{patient?.blood_group || 'Not recorded'}</strong></div>
                </>
              )}
              <button className="outline-button" onClick={onAddCondition}><Plus size={16} /> Add health record</button>
            </div>
          </div>
        </section>
        <section className="panel activity-panel">
          <SectionTitle eyebrow="KEEP IN THE LOOP" title="Recent activity" action="View all" onAction={() => onNavigate('timeline')} />
          {recent.length ? (
            <div className="mini-timeline">{recent.map((item) => <TimelineItem key={item.id} item={item} compact />)}</div>
          ) : (
            <EmptyState icon={History} title="Nothing here yet" body="Your health updates and care activity will appear here." />
          )}
          {admissions[0] && (
            <div className="admission-nudge">
              <div className="nudge-icon"><CalendarDays size={19} /></div>
              <div><strong>Care journey</strong><span>{admissions[0].status === 'pending' ? 'Admission form ready' : 'Latest hospital visit'} · {admissions[0].hospital_name}</span></div>
              <button className="icon-button" aria-label="View admission" onClick={() => onNavigate('admission')}><ChevronRight size={18} /></button>
            </div>
          )}
        </section>
      </div>
      <section className="panel quick-actions">
        <SectionTitle eyebrow="READY WHEN YOU ARE" title="Your care, your choice" />
        <div className="quick-action-grid">
          <button onClick={() => onNavigate('consent')}><span className="quick-icon quick-blue"><ShieldCheck size={20} /></span><span><strong>Review consent</strong><small>Choose what responders see</small></span><ChevronRight size={17} /></button>
          <button onClick={() => onNavigate('admission')}><span className="quick-icon quick-peach"><ClipboardList size={20} /></span><span><strong>Admission form</strong><small>Pre-fill trusted details</small></span><ChevronRight size={17} /></button>
          <button onClick={() => onNavigate('timeline')}><span className="quick-icon quick-mint"><History size={20} /></span><span><strong>Access timeline</strong><small>See who viewed your record</small></span><ChevronRight size={17} /></button>
        </div>
      </section>
    </>
  )
}

function HealthRecord({ patient, conditions, prefill, selectedCondition, onSelectCondition, onAddCondition, onReadAloud }) {
  const allergies = prefill?.allergies || []
  const medications = prefill?.medications || []
  return (
    <div className="health-page">
      <section className="panel health-map-panel">
        <div className="health-map-intro">
          <div><span className="eyebrow">INTERACTIVE BODY MAP</span><h2>See your health at a glance</h2><p>Tap any marker to explore a condition or a past injury.</p></div>
          <button className="outline-button" onClick={onAddCondition}><Plus size={16} /> Add record</button>
        </div>
        <div className="health-map-layout">
          <BodyMap conditions={conditions} selectedId={selectedCondition?.id} onSelect={onSelectCondition} />
          <div className="map-detail-column">
            {selectedCondition ? (
              <div className="map-detail-card">
                <span className="eyebrow">SELECTED RECORD</span>
                <h3>{selectedCondition.name}</h3>
                <ConditionBadge type={selectedCondition.condition_type} />
                <dl>
                  <div><dt>Body area</dt><dd>{selectedCondition.body_region.replaceAll('_', ' ')}</dd></div>
                  <div><dt>Recorded</dt><dd>{formatDate(selectedCondition.occurred_at)}</dd></div>
                  <div><dt>Source</dt><dd>{selectedCondition.source_name}</dd></div>
                  <div><dt>Status</dt><dd>{selectedCondition.is_active ? 'Current' : 'Past history'}</dd></div>
                </dl>
                {selectedCondition.notes && <p className="detail-notes">{selectedCondition.notes}</p>}
                <button className="read-button" onClick={() => onReadAloud(`${selectedCondition.name}. ${selectedCondition.notes || ''}`)}><Volume2 size={17} /> Read this aloud</button>
              </div>
            ) : (
              <div className="map-detail-card map-intro-card">
                <div className="soft-icon"><UserRound size={24} /></div>
                <span className="eyebrow">PATIENT SNAPSHOT</span>
                <h3>{patient?.name}</h3>
                <p>{patient?.age} years old <span className="separator-dot">·</span> {patient?.primary_condition}</p>
                <div className="blood-type-card"><span>Blood group</span><strong>{patient?.blood_group || '—'}</strong></div>
                <p className="map-hint-text">The body map shows only records you have added. Tap a colored marker for details.</p>
              </div>
            )}
          </div>
        </div>
      </section>
      <div className="content-grid health-lower-grid">
        <section className="panel">
          <SectionTitle eyebrow="YOUR CARE INFORMATION" title="Health details" />
          <div className="health-detail-list">
            <div className="health-detail-row"><span className="detail-icon allergy-icon"><Activity size={18} /></span><div><strong>Allergies</strong><small>{allergies.length ? allergies.join(', ') : 'No allergies recorded'}</small></div><span className="source-pill">Hospital A</span></div>
            {medications.map((medicine, index) => (
              <div className="health-detail-row" key={`${medicine.name}-${index}`}><span className="detail-icon medication-icon"><HeartPulse size={18} /></span><div><strong>{medicine.name}</strong><small>{medicine.dose} {medicine.conflict ? '· Dose conflict' : ''}</small></div><span className="source-pill">{medicine.source}</span></div>
            ))}
            <div className="health-detail-row"><span className="detail-icon condition-icon"><Stethoscope size={18} /></span><div><strong>Primary condition</strong><small>{patient?.primary_condition || 'No primary condition recorded'}</small></div><span className="source-pill">Clinic B</span></div>
          </div>
          <p className="medical-note"><ShieldCheck size={15} /> Always confirm medical details with the patient or clinician.</p>
        </section>
        <section className="panel">
          <SectionTitle eyebrow="RECORD HISTORY" title="Conditions & injuries" />
          {conditions.length ? (
            <div className="record-list">
              {conditions.map((condition) => (
                <button className={`record-list-item ${selectedCondition?.id === condition.id ? 'record-selected' : ''}`} key={condition.id} onClick={() => onSelectCondition(condition)}>
                  <span className={`record-type-icon ${condition.is_active ? 'type-current' : 'type-history'}`}><Activity size={17} /></span>
                  <span className="record-text"><strong>{condition.name}</strong><small>{condition.body_region.replaceAll('_', ' ')} · {formatDate(condition.occurred_at)}</small></span>
                  <ChevronRight size={16} />
                </button>
              ))}
            </div>
          ) : <EmptyState icon={FileHeart} title="No health records yet" body="Add a condition or injury to place a marker on your map." />}
        </section>
      </div>
    </div>
  )
}

function ConsentPage({ consents, onSave, receipts }) {
  const [draft, setDraft] = useState(consents)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  function updateConsent(field, change) {
    setDraft((current) => current.map((item) => item.field_name === field ? { ...item, ...change } : item))
  }

  async function save(event) {
    event.preventDefault()
    setSaving(true)
    setNotice('')
    try {
      const result = await onSave(draft)
      setNotice(`Your choices were saved. Consent receipt #${result.receipt_id} created.`)
    } catch (error) {
      setNotice(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="consent-layout">
      <section className="panel consent-panel">
        <SectionTitle eyebrow="YOU ARE IN CONTROL" title="Choose what to share" />
        <p className="panel-lead">Responders only see the information you allow. You can change these choices at any time.</p>
        <form onSubmit={save}>
          <div className="consent-list">
            {draft.map((item) => (
              <div className="consent-row" key={item.field_name}>
                <div className="consent-icon"><ShieldCheck size={18} /></div>
                <div className="consent-label"><strong>{CONSENT_LABELS[item.field_name] || item.field_name}</strong><small>{item.tier === 'emergency' ? 'Emergency access' : item.tier === 'sensitive' ? 'Requires separate approval' : 'Standard responder access'}</small></div>
                <label className="toggle-control" aria-label={`Allow sharing ${CONSENT_LABELS[item.field_name] || item.field_name}`}>
                  <input type="checkbox" checked={item.consent_value} onChange={(event) => updateConsent(item.field_name, { consent_value: event.target.checked })} />
                  <span className="toggle-track" />
                </label>
              </div>
            ))}
          </div>
          <div className="consent-expiry">
            <div><Clock3 size={18} /><span><strong>Consent expires automatically</strong><small>Choose how long each permission stays active.</small></span></div>
            <select value={draft[0]?.expiry_minutes || 180} onChange={(event) => setDraft((current) => current.map((item) => ({ ...item, expiry_minutes: Number(event.target.value) })))}>
              <option value={60}>1 hour</option><option value={180}>3 hours</option><option value={720}>12 hours</option><option value={1440}>24 hours</option>
            </select>
          </div>
          <button type="submit" className="primary-button save-consent" disabled={saving}><Check size={17} /> {saving ? 'Saving…' : 'Save my choices'}</button>
          {notice && <p className={notice.startsWith('Your choices') ? 'success-notice' : 'inline-error'} role="status">{notice}</p>}
        </form>
      </section>
      <aside className="consent-side">
        <div className="privacy-card">
          <div className="privacy-shield"><ShieldCheck size={26} /></div>
          <h3>Your record stays private.</h3>
          <p>Your QR card contains only a secure code. Your medical details stay protected until a responder checks your consent.</p>
          <div className="privacy-check"><CheckCircle2 size={17} /> You can revoke access anytime</div>
          <div className="privacy-check"><CheckCircle2 size={17} /> Every view is recorded</div>
        </div>
        <div className="receipt-card">
          <div className="receipt-heading"><div><span className="eyebrow">CONSENT HISTORY</span><h3>Recent receipts</h3></div><ClipboardList size={19} /></div>
          {receipts.slice(0, 3).map((receipt) => <div className="receipt-row" key={receipt.id}><CheckCircle2 size={15} /><span>Choices updated</span><small>{formatDate(receipt.created_at)}</small></div>)}
          {!receipts.length && <p className="empty-inline">Your consent changes will appear here.</p>}
        </div>
      </aside>
    </div>
  )
}

function TimelinePage({ logs, notifications, conditions, admissions }) {
  const events = useMemo(() => [
    ...logs.map((log) => ({ ...log, id: `log-${log.id}`, event: 'Emergency record accessed', type: 'access', created_at: log.created_at })),
    ...notifications.map((item) => ({ ...item, id: `notification-${item.id}`, event: item.channel === 'insurer' ? 'Insurer notified' : 'Care circle notified', type: 'notification' })),
    ...admissions.map((item) => ({ ...item, id: `admission-${item.id}`, event: 'Admission recorded', type: 'admission' })),
    ...conditions.map((item) => ({ ...item, id: `condition-${item.id}`, event: item.name, type: 'condition' })),
  ].sort((a, b) => new Date(b.created_at || b.occurred_at || 0) - new Date(a.created_at || a.occurred_at || 0)), [logs, notifications, admissions, conditions])

  return (
    <section className="panel timeline-page">
      <SectionTitle eyebrow="A CLEAR RECORD OF CARE" title="Activity timeline" />
      <p className="panel-lead">See when your information was viewed and what happened next.</p>
      {events.length ? (
        <div className="full-timeline">
          {events.map((event) => (
            <article className="full-timeline-row" key={event.id}>
              <span className={`full-timeline-icon ${event.type}`}><TimelineIcon type={event.type} /></span>
              <div><strong>{event.event}</strong><p>{event.responder_name ? `Viewed by ${event.responder_name}` : event.message || event.notes || event.hospital_name || 'Care record updated'}</p>
                <span className="timeline-date"><Clock3 size={13} /> {formatDate(event.created_at || event.occurred_at)}{event.access_type ? ` · ${event.access_type.replace('_', ' ')}` : ''}</span>
              </div>
              {event.current_hash && <span className="verified-mark" title="Tamper-evident audit entry"><ShieldCheck size={17} /></span>}
            </article>
          ))}
        </div>
      ) : <EmptyState icon={History} title="Your timeline is ready" body="Scans, health updates and admissions will show up here." />}
    </section>
  )
}

function TimelineIcon({ type }) {
  if (type === 'access') return <ShieldCheck size={18} />
  if (type === 'notification') return <Bell size={18} />
  if (type === 'admission') return <ClipboardList size={18} />
  return <HeartPulse size={18} />
}

function CameraQrScanner({ onDecode, onError }) {
  useEffect(() => {
    let scanner
    let cancelled = false
    import('html5-qrcode')
      .then(({ Html5QrcodeScanner }) => {
        if (cancelled) return
        scanner = new Html5QrcodeScanner(
          'carelink-qr-reader',
          { fps: 10, qrbox: { width: 220, height: 220 }, aspectRatio: 1 },
          false,
        )
        scanner.render(onDecode, () => {})
      })
      .catch((error) => onError(error.message || 'Camera could not be started.'))
    return () => {
      cancelled = true
      scanner?.clear().catch((error) => onError(error.message || 'Camera scanner did not close cleanly.'))
    }
  }, [onDecode, onError])

  return <div id="carelink-qr-reader" className="camera-scanner" />
}

function AdmissionPage({ patient, prefill, admissions, onSubmit, loading }) {
  const [hospital, setHospital] = useState('')
  const [reason, setReason] = useState('')
  const [insurerNotice, setInsurerNotice] = useState(false)
  const [result, setResult] = useState('')
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setError('')
    setResult('')
    try {
      await onSubmit({ patient_id: patient.id, hospital_name: hospital, reason, insurer_notice: insurerNotice })
      setResult('Admission saved. Your care circle has been notified.')
      setHospital('')
      setReason('')
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    }
  }

  return (
    <div className="content-grid admission-grid">
      <section className="panel admission-form-panel">
        <SectionTitle eyebrow="A SMOOTHER ARRIVAL" title="Admission handoff" />
        <p className="panel-lead">Start with the details you have already chosen to share. You can review everything before submitting.</p>
        <div className="prefill-strip"><CheckCircle2 size={17} /><span><strong>{prefill?.prefilled_fields?.length || 0} details ready</strong><small>Prefilled from your consented health record</small></span></div>
        <div className="prefill-chips">{(prefill?.prefilled_fields || []).map((field) => <span key={field}><Check size={13} /> {field.replaceAll('_', ' ')}</span>)}</div>
        <form className="admission-form" onSubmit={submit}>
          <label htmlFor="hospital">Hospital or clinic</label>
          <input id="hospital" value={hospital} onChange={(event) => setHospital(event.target.value)} placeholder="Enter facility name" required />
          <label htmlFor="reason">Reason for visit</label>
          <textarea id="reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="A short description for the admission team" rows={3} required />
          <label className="insurer-check"><input type="checkbox" checked={insurerNotice} onChange={(event) => setInsurerNotice(event.target.checked)} /><span><strong>Notify my insurer</strong><small>Shares policy reference, facility and event time only.</small></span></label>
          <button className="primary-button" disabled={loading}>{loading ? 'Submitting…' : 'Save admission & notify circle'} <ArrowRight size={17} /></button>
          {result && <p className="success-notice" role="status">{result}</p>}
          {error && <p className="inline-error" role="alert">{error}</p>}
        </form>
      </section>
      <section className="panel admission-history-panel">
        <SectionTitle eyebrow="CARE JOURNEY" title="Recent admissions" />
        {admissions.length ? admissions.map((item) => (
          <div className="admission-history-item" key={item.id}>
            <span className="admission-history-icon"><CalendarDays size={18} /></span>
            <div><strong>{item.hospital_name}</strong><p>{item.reason}</p><small>{formatDate(item.created_at)}</small></div>
            <span className={`status-pill ${item.status === 'admitted' ? 'status-admitted' : ''}`}>{item.status}</span>
          </div>
        )) : <EmptyState icon={CalendarDays} title="No admissions yet" body="Your admission history will appear here." />}
        <div className="admission-safety"><ShieldCheck size={16} /><span>Insurer notifications never include medical details.</span></div>
      </section>
    </div>
  )
}

function ResponderScan({ onScan, busy }) {
  const [token, setToken] = useState('')
  const [breakGlass, setBreakGlass] = useState(false)
  const [cameraOpen, setCameraOpen] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [reason, setReason] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setError('')
    setResult(null)
    try {
      const response = await onScan({ token, break_glass: breakGlass, reason: breakGlass ? reason : null })
      setResult(response)
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    }
  }

  const handleDecode = useCallback((decodedText) => {
    setToken(decodedText)
    setCameraOpen(false)
    setCameraError('')
  }, [])
  const handleCameraError = useCallback((message) => setCameraError(message), [])

  return (
    <div className="content-grid responder-grid">
      <section className="panel scan-panel">
        <SectionTitle eyebrow="RESPONDER CONSOLE" title="Open emergency record" />
        <p className="panel-lead">Scan the patient's wallet card or enter the secure backup code. Only consented details will be shown.</p>
        <div className="scan-graphic"><div className="scan-frame"><QrCode size={54} strokeWidth={1.3} /><span className="scan-corner corner-a" /><span className="scan-corner corner-b" /><span className="scan-corner corner-c" /><span className="scan-corner corner-d" /></div></div>
        <button className="outline-button camera-launch" onClick={() => { setCameraError(''); setCameraOpen((current) => !current) }} type="button">
          <QrCode size={16} /> {cameraOpen ? 'Close camera scanner' : 'Scan with camera'}
        </button>
        {cameraOpen && <CameraQrScanner onDecode={handleDecode} onError={handleCameraError} />}
        {cameraError && <p className="inline-error" role="alert">{cameraError}</p>}
        <form className="admission-form" onSubmit={submit}>
          <label htmlFor="qr-token">Backup code / QR token</label>
          <input id="qr-token" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Paste the secure code from the card" required />
          <label className="insurer-check breakglass-toggle"><input type="checkbox" checked={breakGlass} onChange={(event) => setBreakGlass(event.target.checked)} /><span><strong>Break-glass access</strong><small>For patients unable to communicate; the event is clearly audited.</small></span></label>
          {breakGlass && <><label htmlFor="break-reason">Reason for emergency access</label><textarea id="break-reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Briefly explain why emergency access is needed" rows={2} required /></>}
          <button className="primary-button" disabled={busy || !token}>{busy ? 'Checking consent…' : 'View consented record'} <ArrowRight size={17} /></button>
          {error && <p className="inline-error" role="alert">{error}</p>}
        </form>
      </section>
      <section className="panel responder-result-panel">
        <SectionTitle eyebrow="PATIENT DETAILS" title={result ? result.patient_name : 'Waiting for a scan'} />
        {result ? (
          <div className="responder-record">
            <div className="scan-access-notice"><ShieldCheck size={18} /><span>Consent checked · Access logged</span></div>
            <div className="responder-record-grid">
              {result.blood_group && <div><small>Blood group</small><strong>{result.blood_group}</strong></div>}
              {!!result.allergies?.length && <div><small>Allergies</small><strong>{result.allergies.join(', ')}</strong></div>}
              {!!result.medications?.length && <div className="wide-detail"><small>Medications</small>{result.medications.map((med) => <strong className="medicine-row" key={med.name}>{med.name} <span>{med.dose}</span>{med.conflict && <em>Conflict</em>}</strong>)}</div>}
              {!!result.conditions?.length && <div className="wide-detail"><small>Conditions</small>{result.conditions.map((condition, i) => <strong key={`${condition.name}-${i}`}>{condition.name} <span>{condition.source}</span></strong>)}</div>}
              {!!result.emergency_contacts?.length && <div className="wide-detail"><small>Emergency contacts</small>{result.emergency_contacts.map((contact) => <strong key={contact.phone}>{contact.name} · {contact.phone}</strong>)}</div>}
            </div>
            {result.conflict_flag && <div className="conflict-warning"><Activity size={17} /><span><strong>Record conflict — confirm before treatment.</strong><small>{result.conflicts.map((item) => `${item.field}: ${item.values.map((v) => `${v.value} (${v.source})`).join(' / ')}`).join('; ')}</small></span></div>}
            <div className="source-chips">{result.source_labels.map((source) => <span key={source}>{source}</span>)}</div>
            <p className="fhir-note">FHIR-shaped records · Family alert queued · Audit hash {result.audit?.current_hash?.slice(0, 12)}</p>
          </div>
        ) : <EmptyState icon={HeartPulse} title="Patient information appears here" body="A successful scan shows the limited, consented emergency summary." />}
      </section>
    </div>
  )
}

function TokenCard({ patient, tokens, onCreate, onRevoke, createdToken, onDismiss }) {
  return (
    <section className="panel token-panel">
      <div className="section-title"><div><span className="eyebrow">PRINTABLE WALLET CARD</span><h2>Emergency QR card</h2></div><button className="primary-button" onClick={onCreate}><Plus size={16} /> Create new code</button></div>
      <p className="panel-lead">Your QR contains a secure code only. It never contains health information.</p>
      {createdToken && (
        <div className="new-token-banner">
          <CheckCircle2 size={20} />
          <div><strong>New emergency code created</strong><span>Copy or print the card now. This code is only shown once.</span><code>{createdToken.token}</code></div>
          <button className="icon-button" aria-label="Dismiss new code" onClick={onDismiss}><X size={18} /></button>
        </div>
      )}
      <div className="wallet-card" id="wallet-card">
        <div className="wallet-content">
          <div className="wallet-brand"><div className="brand-mark"><HeartPulse size={16} /></div> care<span>link</span></div>
          <span className="eyebrow">IN CASE OF EMERGENCY</span>
          <h3>{patient?.name}</h3>
          <p>{patient?.age} years old <span>·</span> Blood group {patient?.blood_group || '—'}</p>
          <div className="wallet-emergency"><Siren size={15} /> Please scan to view consented emergency details</div>
          <small>This card contains no medical information.</small>
        </div>
        <div className="wallet-qr">
          {createdToken ? <QRCodeSVG value={createdToken.token} size={108} level="M" /> : <div className="qr-empty"><QrCode size={45} /><span>Generate a secure code</span></div>}
        </div>
      </div>
      <div className="wallet-actions">
        <button className="outline-button" onClick={() => window.print()}><ArrowDownToLine size={16} /> Print wallet card</button>
        {createdToken && <span className="token-expiry">Expires {formatDate(createdToken.expires_at)}</span>}
      </div>
      <div className="token-history">
        <div className="token-history-heading"><strong>Active codes</strong><span>{tokens.filter((item) => item.is_active).length} active</span></div>
        {tokens.length ? tokens.map((item) => (
          <div className="token-row" key={item.id}>
            <span className={`token-status ${item.is_active ? 'token-active' : ''}`}><QrCode size={17} /></span>
            <span><strong>Emergency code ·••••{String(item.id).padStart(4, '0')}</strong><small>{item.single_use ? 'Single use' : 'Reusable'} · expires {formatDate(item.expires_at)}</small></span>
            {item.is_active && <button className="revoke-button" onClick={() => onRevoke(item.id)}>Revoke</button>}
            {!item.is_active && <span className="revoked-label">Inactive</span>}
          </div>
        )) : <p className="empty-inline">No QR codes yet. Create one to print a wallet card.</p>}
      </div>
    </section>
  )
}

function AddConditionModal({ onClose, onAdd }) {
  const [name, setName] = useState('')
  const [bodyRegion, setBodyRegion] = useState('chest')
  const [conditionType, setConditionType] = useState('injury')
  const [notes, setNotes] = useState('')
  const [date, setDate] = useState('')
  const [isActive, setIsActive] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await onAdd({
        name,
        body_region: bodyRegion,
        condition_type: conditionType,
        notes,
        source_name: 'Guardian entry',
        occurred_at: date ? new Date(`${date}T12:00:00`).toISOString() : null,
        is_active: isActive,
      })
      onClose()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="add-record-title">
        <div className="modal-heading"><div><span className="eyebrow">PATIENT HEALTH RECORD</span><h2 id="add-record-title">Add a health record</h2></div><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={20} /></button></div>
        <p className="panel-lead">Add the record to the timeline and place a marker on the 2D body map.</p>
        <form className="modal-form" onSubmit={submit}>
          <label htmlFor="record-name">Condition or injury</label>
          <input id="record-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Previous wrist fracture" required />
          <div className="form-two-col">
            <div><label htmlFor="record-type">Record type</label><select id="record-type" value={conditionType} onChange={(event) => setConditionType(event.target.value)}><option value="injury">Past injury</option><option value="condition">Condition</option><option value="surgery">Surgery / procedure</option><option value="device">Medical device</option></select></div>
            <div><label htmlFor="record-region">Body area</label><select id="record-region" value={bodyRegion} onChange={(event) => setBodyRegion(event.target.value)}><option value="head">Head</option><option value="chest">Chest</option><option value="abdomen">Abdomen</option><option value="left_arm">Left arm</option><option value="right_arm">Right arm</option><option value="left_knee">Left knee</option><option value="right_knee">Right knee</option><option value="left_leg">Left leg</option><option value="right_leg">Right leg</option></select></div>
          </div>
          <label htmlFor="record-date">Date (optional)</label>
          <input id="record-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          <label htmlFor="record-notes">Notes</label>
          <textarea id="record-notes" value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} placeholder="Add helpful context for your care team" />
          <label className="insurer-check"><input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} /><span><strong>This is a current health issue</strong><small>Leave unchecked for a past injury or resolved issue.</small></span></label>
          {error && <p className="inline-error" role="alert">{error}</p>}
          <div className="modal-actions"><button type="button" className="outline-button" onClick={onClose}>Cancel</button><button className="primary-button" disabled={busy}>{busy ? 'Adding…' : 'Add to health map'} <Plus size={16} /></button></div>
        </form>
      </section>
    </div>
  )
}

function EmptyState({ icon: Icon, title, body }) {
  return <div className="empty-state"><span><Icon size={23} /></span><strong>{title}</strong><p>{body}</p></div>
}

function NotificationsDrawer({ notifications, onClose }) {
  return (
    <div className="drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <aside className="notification-drawer" aria-label="Notifications">
        <div className="drawer-heading"><div><span className="eyebrow">CARE CIRCLE UPDATES</span><h2>Notifications</h2></div><button className="icon-button" aria-label="Close notifications" onClick={onClose}><X size={20} /></button></div>
        {notifications.length ? notifications.map((item) => (
          <div className="drawer-notice" key={item.id}><span className={`drawer-notice-icon ${item.channel === 'insurer' ? 'notice-insurer' : ''}`}><Bell size={17} /></span><div><strong>{item.channel === 'insurer' ? 'Insurer update' : 'Care circle'}</strong><p>{item.message}</p><small>{formatDate(item.created_at)}</small></div></div>
        )) : <EmptyState icon={Bell} title="You're all caught up" body="Updates from your trusted circle will appear here." />}
      </aside>
    </div>
  )
}

function App() {
  const [session, setSession] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('carelink-session')) } catch { return null }
  })
  const [patient, setPatient] = useState(null)
  const [conditions, setConditions] = useState([])
  const [consents, setConsents] = useState([])
  const [receipts, setReceipts] = useState([])
  const [tokens, setTokens] = useState([])
  const [logs, setLogs] = useState([])
  const [notifications, setNotifications] = useState([])
  const [admissions, setAdmissions] = useState([])
  const [prefill, setPrefill] = useState(null)
  const [activePage, setActivePage] = useState('overview')
  const [selectedCondition, setSelectedCondition] = useState(null)
  const [createdToken, setCreatedToken] = useState(null)
  const [showAddCondition, setShowAddCondition] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const [notificationToast, setNotificationToast] = useState('')
  const [language, setLanguage] = useState('en')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [auditVerified, setAuditVerified] = useState(true)
  const previousNotificationCount = useRef(0)
  const mode = session?.role || 'guardian'
  const token = session?.access_token

  const loadPatientData = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      if (mode === 'responder') {
        setPatient(null)
        return
      }
      const patientList = await api('/patients', { token })
      if (!patientList.length) throw new ApiError('No patient profile is linked to this guardian account.', 404)
      const patientId = patientList[0].id
      const [profile, health, consentData, receiptData, tokenData, audit, noticeData, admissionData, admissionPrefill] = await Promise.all([
        api(`/patients/${patientId}`, { token }),
        api(`/patients/${patientId}/conditions`, { token }),
        api(`/patients/${patientId}/consents`, { token }),
        api(`/patients/${patientId}/consent-receipts`, { token }),
        api(`/patients/${patientId}/tokens`, { token }),
        api(`/patients/${patientId}/access-log`, { token }),
        api(`/patients/${patientId}/notifications`, { token }),
        api(`/patients/${patientId}/admissions`, { token }),
        api(`/patients/${patientId}/admission-prefill`, { token }),
      ])
      setPatient(profile)
      setConditions(health)
      setConsents(consentData)
      setReceipts(receiptData)
      setTokens(tokenData)
      setLogs(audit.entries)
      setAuditVerified(audit.verified)
      setNotifications(noticeData)
      previousNotificationCount.current = noticeData.length
      setAdmissions(admissionData)
      setPrefill(admissionPrefill)
    } catch (loadError) {
      setError(getErrorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [mode, token])

  useEffect(() => {
    if (!session?.access_token) return
    sessionStorage.setItem('carelink-session', JSON.stringify(session))
    const timeout = window.setTimeout(loadPatientData, 0)
    return () => window.clearTimeout(timeout)
  }, [loadPatientData, session])

  useEffect(() => {
    if (!session || mode !== 'guardian') return undefined
    const interval = window.setInterval(async () => {
      try {
        const noticeData = await api(`/patients/${patient?.id || 1}/notifications`, { token })
        if (noticeData.length > previousNotificationCount.current) {
          setNotificationToast('A new care circle update has arrived.')
        }
        previousNotificationCount.current = noticeData.length
        setNotifications(noticeData)
      } catch (pollError) {
        setError(getErrorMessage(pollError))
      }
    }, 3000)
    return () => window.clearInterval(interval)
  }, [mode, patient?.id, session, token])

  useEffect(() => {
    if (!notificationToast) return undefined
    const timeout = window.setTimeout(() => setNotificationToast(''), 4000)
    return () => window.clearTimeout(timeout)
  }, [notificationToast])

  const pageTitle = NAV_ITEMS.find((item) => item.id === activePage)?.label || (activePage === 'scan' ? 'Responder console' : 'Overview')
  const subtitle = mode === 'responder' ? 'Consent-based emergency record access' : 'Your health, safely connected.'
  const selectedHealthCondition = conditions.find((condition) => condition.id === selectedCondition?.id) || null

  function login(result, identity) {
    const nextSession = { access_token: result.access_token, role: result.role, identity }
    sessionStorage.setItem('carelink-session', JSON.stringify(nextSession))
    setSession(nextSession)
    setActivePage(result.role === 'responder' ? 'scan' : 'overview')
  }

  function logout() {
    sessionStorage.removeItem('carelink-session')
    setSession(null)
    setPatient(null)
    setActivePage('overview')
  }

  async function saveConsents(draft) {
    const result = await api(`/patients/${patient.id}/consents`, {
      token,
      method: 'POST',
      body: JSON.stringify({
        consents: draft.map(({ field_name, consent_value, tier, expiry_minutes }) => ({ field_name, consent_value, tier, expiry_minutes })),
      }),
    })
    await loadPatientData()
    return result
  }

  async function createToken() {
    setBusy(true)
    setError('')
    try {
      const result = await api(`/patients/${patient.id}/tokens`, {
        token,
        method: 'POST',
        body: JSON.stringify({ expiry_hours: 8, single_use: false }),
      })
      setCreatedToken(result)
      await loadPatientData()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  async function revokeToken(tokenId) {
    setBusy(true)
    setError('')
    try {
      await api(`/patients/${patient.id}/tokens/${tokenId}`, { token, method: 'DELETE' })
      await loadPatientData()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  async function addCondition(payload) {
    await api(`/patients/${patient.id}/conditions`, {
      token,
      method: 'POST',
      body: JSON.stringify(payload),
    })
    await loadPatientData()
  }

  async function submitAdmission(payload) {
    setBusy(true)
    try {
      await api('/admission', { token, method: 'POST', body: JSON.stringify(payload) })
      await loadPatientData()
    } finally {
      setBusy(false)
    }
  }

  async function scanToken(payload) {
    setBusy(true)
    try {
      return await api('/access/scan', { token, method: 'POST', body: JSON.stringify(payload) })
    } finally {
      setBusy(false)
    }
  }

  function readAloud(text) {
    if (!('speechSynthesis' in window)) {
      setError('Read-aloud is not supported by this browser.')
      return
    }
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = language === 'hi' ? 'hi-IN' : 'en-IN'
    window.speechSynthesis.speak(utterance)
  }

  if (!session?.access_token) return <LoginScreen onLogin={login} />

  return (
    <div className="app-shell">
      <Sidebar
        active={activePage}
        onChange={setActivePage}
        patient={patient}
        mode={mode}
        onLogout={logout}
        mobileOpen={mobileOpen}
        closeMobile={() => setMobileOpen(false)}
      />
      <main className="main-shell">
        <Topbar
          title={language === 'hi' ? enHi[pageTitle] || pageTitle : pageTitle}
          subtitle={language === 'hi' && activePage === 'overview' ? enHi['Your health, safely connected.'] : subtitle}
          language={language}
          onLanguage={() => setLanguage((current) => current === 'en' ? 'hi' : 'en')}
          onNotifications={() => setShowNotifications(true)}
          notificationCount={notifications.length}
          onMenu={() => setMobileOpen(true)}
        />
        <div className="main-content">
          {error && <div className="error-banner" role="alert"><span>{error}</span><button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={17} /></button></div>}
          {mode === 'guardian' && (
            <div className="privacy-status"><ShieldCheck size={16} /><span>Connected securely</span><i /> <span>{auditVerified ? 'Audit trail verified' : 'Audit verification needs attention'}</span></div>
          )}
          {loading && !patient && mode === 'guardian' ? <div className="loading-state"><span className="spinner" /> Loading your care circle…</div> : null}
          {mode === 'guardian' && patient && activePage === 'overview' && (
            <Overview
              patient={patient}
              conditions={conditions}
              logs={logs}
              admissions={admissions}
              onNavigate={setActivePage}
              onAddCondition={() => setShowAddCondition(true)}
              selectedCondition={selectedHealthCondition}
              onSelectCondition={setSelectedCondition}
            />
          )}
          {mode === 'guardian' && patient && activePage === 'health' && (
            <HealthRecord
              patient={patient}
              conditions={conditions}
              prefill={prefill}
              selectedCondition={selectedHealthCondition}
              onSelectCondition={setSelectedCondition}
              onAddCondition={() => setShowAddCondition(true)}
              onReadAloud={readAloud}
            />
          )}
          {mode === 'guardian' && patient && activePage === 'consent' && (
            <>
              <ConsentPage consents={consents} onSave={saveConsents} receipts={receipts} />
              <TokenCard patient={patient} tokens={tokens} onCreate={createToken} onRevoke={revokeToken} createdToken={createdToken} onDismiss={() => setCreatedToken(null)} />
            </>
          )}
          {mode === 'guardian' && patient && activePage === 'timeline' && (
            <TimelinePage logs={logs} notifications={notifications} conditions={conditions} admissions={admissions} />
          )}
          {mode === 'guardian' && patient && activePage === 'admission' && (
            <AdmissionPage patient={patient} prefill={prefill} admissions={admissions} onSubmit={submitAdmission} loading={busy} />
          )}
          {mode === 'responder' && activePage === 'scan' && <ResponderScan onScan={scanToken} busy={busy} />}
          <footer className="app-footer"><span>CareLink Emergency Bridge <i>·</i> Demo mode — synthetic patient information</span><button onClick={() => window.open(`${API_BASE}/docs`, '_blank', 'noopener,noreferrer')}>API documentation <ArrowRight size={13} /></button></footer>
        </div>
      </main>
      {showAddCondition && <AddConditionModal onClose={() => setShowAddCondition(false)} onAdd={addCondition} />}
      {showNotifications && <NotificationsDrawer notifications={notifications} onClose={() => setShowNotifications(false)} />}
      {notificationToast && <div className="toast-message"><Bell size={17} /> {notificationToast} <button className="icon-button" aria-label="Dismiss notification" onClick={() => setNotificationToast('')}><X size={15} /></button></div>}
      {mode === 'guardian' && patient && activePage === 'consent' && createdToken && (
        <div className="print-only"><h2>CareLink Emergency Record</h2><p>{patient.name} · {patient.age} years</p><QRCodeSVG value={createdToken.token} size={160} /><p>Scan to request consented emergency information.</p></div>
      )}
    </div>
  )
}

export default App
