import { useState } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const product = { name: 'Winter Jacket', sku: 'WINTER-JACKET-001', category: 'apparel', features: ['waterproof', 'insulated'] }

function money(value) { return value == null ? '--' : `Rs ${Number(value).toFixed(2)}` }
function StatusPill({ value }) { return <span className={`status-pill ${String(value || 'ready').toLowerCase().replace('_', '-')}`}>{value || 'READY'}</span> }

function App() {
  const [request, setRequest] = useState('A waterproof winter jacket')
  const [maxPrice, setMaxPrice] = useState('150')
  const [negotiation, setNegotiation] = useState(null)
  const [payment, setPayment] = useState(null)
  const [loading, setLoading] = useState(false)
  const [stage, setStage] = useState('Ready for a new negotiation')
  const [error, setError] = useState('')

  async function negotiate(event) {
    event.preventDefault(); setLoading(true); setError(''); setPayment(null); setNegotiation(null); setStage('Buyer and seller are negotiating')
    try {
      const response = await fetch(`${API_URL}/negotiate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_requirement: request, buyer_max_price: Number(maxPrice), product_info: product, max_rounds: 4 }) })
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'Negotiation failed.')
      setNegotiation(data); setStage(data.status === 'agreed' ? 'Agreement reached. Policy is evaluating the offer.' : 'Negotiation timed out.')
    } catch (requestError) { setError(requestError.message); setStage('Could not reach the Mercury API') } finally { setLoading(false) }
  }

  async function createPayment() {
    setError(''); setPayment({ status: 'creating' })
    try {
      const response = await fetch(`${API_URL}/payment/create`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ negotiation_id: negotiation.negotiation_id }) })
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'Payment order was not created.'); setPayment(data)
    } catch (requestError) { setPayment(null); setError(requestError.message) }
  }

  const policy = negotiation?.policy; const revenue = negotiation?.revenue || {}; const merchant = negotiation?.merchant?.merchant || {}
  return <main className="app-shell">
    <header className="topbar"><div className="brand-mark">M</div><div><p className="eyebrow">Agentic commerce / test mode</p><h1>Mercury</h1></div><div className="api-state"><span className="pulse" /> API connected <small>{API_URL}</small></div></header>
    <section className="intro"><div><p className="eyebrow accent">Live transaction desk</p><h2>Turn a fair offer into a <em>clean checkout.</em></h2><p className="intro-copy">A small window into Mercury&apos;s buyer, seller, and policy-driven payment loop.</p></div><div className="flow-line"><span>Negotiate</span><b>→</b><span>Policy</span><b>→</b><span>Payment</span></div></section>
    {error && <div className="error-banner"><strong>Transaction blocked</strong><span>{error}</span></div>}
    <div className="workspace-grid">
      <aside className="left-column">
        <section className="panel product-panel">
          <div className="panel-heading"><span className="section-number">01</span><h3>Product & merchant</h3></div>
          <div className="product-art">WJ<span>01</span></div>
          <h4>Waterproof Winter Jacket</h4>
          <p className="muted">{merchant.sku || product.sku} / {merchant.category || product.category}</p>
          <div className="tag-row">{product.features.map((feature) => <span key={feature}>{feature}</span>)}</div>
          <div className="data-grid">
            <div><small>List price</small><strong>{money(merchant.list_price || 140)}</strong></div>
            <div><small>Inventory</small><strong>{merchant.inventory_quantity ?? 12} units</strong></div>
            <div><small>Unit cost</small><strong>{money(merchant.unit_cost || 68)}</strong></div>
            <div><small>Total cost</small><strong>{money(merchant.total_cost || 80)}</strong></div>
          </div>
        </section>
        <section className="panel request-panel">
          <div className="panel-heading"><span className="section-number">02</span><h3>Buyer request</h3></div>
          <form onSubmit={negotiate}>
            <label>What are you looking for?<textarea value={request} onChange={(event) => setRequest(event.target.value)} /></label>
            <label>Maximum buyer offer<input type="number" min="1" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} /></label>
            <button className="primary-button" disabled={loading}>{loading && <span className="button-spinner" />}{loading ? 'Negotiating' : 'Start negotiation'} <span>→</span></button>
          </form>
        </section>
      </aside>

      <section className="center-column">
        <div className="panel negotiation-panel">
          <div className="panel-heading"><span className="section-number">03</span><div><h3>Negotiation room</h3><p className="muted">{stage}</p></div><StatusPill value={negotiation?.status} /></div>
          <div className="conversation">
            {negotiation?.conversation_history?.length
              ? negotiation.conversation_history.map((message, index) => (
                <div className={`message ${message.role}`} key={`${message.role}-${index}`} style={{ animationDelay: `${index * 60}ms` }}>
                  <div className="message-meta"><span>{message.role === 'buyer' ? 'Buyer' : 'Seller'}</span><small>Round {message.round || Math.floor(index / 2) + 1}</small></div>
                  <p>{message.content}</p>
                </div>
              ))
              : loading
                ? <div className="empty-state"><div className="typing-indicator"><span /><span /><span /></div><strong>Working it out</strong><span>Buyer and seller are exchanging offers.</span></div>
                : <div className="empty-state"><div className="empty-icon">↔</div><strong>The room is quiet.</strong><span>Start a negotiation to see both agents work.</span></div>}
          </div>
        </div>
        <div className="offer-strip">
          <div><small>Current agreed offer</small><strong>{money(negotiation?.agreed_price)}</strong></div>
          <div className="offer-detail"><span>Buyer ceiling</span><b>{money(maxPrice)}</b></div>
          <div className="offer-detail"><span>Seller floor</span><b>{money(merchant.minimum_viable_price)}</b></div>
        </div>
      </section>

      <aside className="right-column">
        <section className="panel policy-panel">
          <div className="panel-heading"><span className="section-number">04</span><h3>Policy decision</h3></div>
          <div className={`decision ${policy?.decision?.toLowerCase() || 'pending'}`} key={policy?.decision || 'pending'}>
            <span className="decision-icon">{policy?.decision === 'ALLOW' ? '✓' : policy?.decision ? '!' : '·'}</span>
            <div><strong>{policy?.decision || 'Pending'}</strong><p>{policy?.reason || 'Agreement required before policy evaluation.'}</p></div>
          </div>
          <div className="metric-row"><span>Transaction amount</span><b>{money(policy?.transaction_amount)}</b></div>
          <div className="metric-row"><span>Margin rate</span><b>{policy?.margin_rate != null ? `${(policy.margin_rate * 100).toFixed(1)}%` : '--'}</b></div>
          {policy?.failed_rules?.length > 0 && <div className="failed-rules">Failed rule: {policy.failed_rules.join(', ')}</div>}
          {policy?.decision === 'ALLOW' && <button className="payment-button" onClick={createPayment} disabled={payment?.status === 'creating'}>{payment?.status === 'creating' && <span className="button-spinner" />}{payment?.status === 'creating' ? 'Creating test order' : 'Create Razorpay test order'} <span>↗</span></button>}
        </section>

        <section className="panel revenue-panel">
          <div className="panel-heading"><span className="section-number">05</span><h3>Revenue snapshot</h3></div>
          <div className="revenue-total"><small>Seller revenue</small><strong>{money(revenue.revenue || negotiation?.agreed_price)}</strong></div>
          <div className="metric-row"><span>Profit</span><b>{money(revenue.profit)}</b></div>
          <div className="metric-row"><span>Margin</span><b>{revenue.margin_rate != null ? `${(revenue.margin_rate * 100).toFixed(1)}%` : '--'}</b></div>
        </section>

        <section className="panel payment-panel">
          <div className="panel-heading"><span className="section-number">06</span><h3>Payment status</h3><StatusPill value={payment?.status || 'not started'} /></div>
          {payment?.order_id
            ? <div className="payment-result">
              <small>Razorpay order ID</small><strong>{payment.order_id}</strong>
              <div className="metric-row"><span>Amount</span><b>{money(payment.amount / 100)}</b></div>
              <div className="metric-row"><span>Currency</span><b>{payment.currency}</b></div>
            </div>
            : <p className="muted">A test-mode order appears here after an ALLOW decision.</p>}
        </section>
      </aside>
    </div>

    <section className="audit-bar">
      <div className="panel-heading"><span className="section-number">07</span><h3>Audit trail</h3></div>
      <div className="audit-entry">
        {negotiation?.audit_trail?.length
          ? <><span className="audit-dot" /><strong>policy_decision</strong><span>{negotiation.audit_trail[0].data.decision} / {negotiation.audit_trail[0].data.reason}</span><time>{new Date(negotiation.audit_trail[0].timestamp).toLocaleTimeString()}</time></>
          : <span className="muted">No policy events recorded yet.</span>}
      </div>
    </section>

    <footer><span>Mercury demo</span><span>Decisions stay deterministic. Language stays human.</span></footer>
  </main>
}

export default App