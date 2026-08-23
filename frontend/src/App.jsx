import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

import {
  fetchCatalog,
  negotiate as negotiateRequest,
  createPayment as createPaymentRequest,
  fetchCustomerSummary,
  fetchCustomerHistory,
  fetchCustomerAudit,
} from './Api'

const PRODUCT_IMAGES = {
  'WINTER-JACKET-001': [
    'https://images.unsplash.com/photo-1544923246-77307dd654cb?auto=format&fit=crop&w=1200&q=80',
    'https://images.unsplash.com/photo-1548883354-94bcfe321cbb?auto=format&fit=crop&w=1200&q=80',
  ],
  'TRAIL-RUNNER-014': [
    'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=1200&q=80',
    'https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?auto=format&fit=crop&w=1200&q=80',
  ],
  'AUDIO-OVER-EAR-220': [
    'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1200&q=80',
    'https://images.unsplash.com/photo-1583394838336-acd977736f90?auto=format&fit=crop&w=1200&q=80',
  ],
  'LEATHER-PACK-07': [
    'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=1200&q=80',
    'https://images.unsplash.com/photo-1548036328-c9fa89d128fa?auto=format&fit=crop&w=1200&q=80',
  ],
  'CHRONO-WATCH-45': [
    'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=1200&q=80',
    'https://images.unsplash.com/photo-1524592094714-0f0654e20314?auto=format&fit=crop&w=1200&q=80',
  ],
  'ESPRESSO-BAR-3': [
    'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=1200&q=80',
    'https://images.unsplash.com/photo-1517701604599-bb29b565090c?auto=format&fit=crop&w=1200&q=80',
  ],
  'MIRROR-CAM-X2': [
    'https://images.unsplash.com/photo-1502920917128-1aa500764cbd?auto=format&fit=crop&w=1200&q=80',
    'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=1200&q=80',
  ],
  'SUNGLASS-RIDGE-9': [
    'https://images.unsplash.com/photo-1572635196237-14b3f281503f?auto=format&fit=crop&w=1200&q=80',
    'https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=1200&q=80',
  ],
}

const CATEGORY_FALLBACK_IMAGE = {
  apparel: 'https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=1200&q=80',
  footwear: 'https://images.unsplash.com/photo-1519744792095-2f2205e87b6f?auto=format&fit=crop&w=1200&q=80',
  electronics: 'https://images.unsplash.com/photo-1518444065439-e933c06ce9cd?auto=format&fit=crop&w=1200&q=80',
  accessories: 'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=1200&q=80',
  home: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=1200&q=80',
  default: 'https://images.unsplash.com/photo-1441984904996-e0b6ba687e04?auto=format&fit=crop&w=1200&q=80',
}

function getGallery(product) {
  return (
    PRODUCT_IMAGES[product.sku] || [
      CATEGORY_FALLBACK_IMAGE[product.category] ||
        CATEGORY_FALLBACK_IMAGE.default,
    ]
  )
}

const fallbackCatalog = [
  {
    sku: 'WINTER-JACKET-001',
    name: 'Alpine Waterproof Parka',
    category: 'apparel',
    list_price: 6999,
    unit_cost: 3400,
    fulfillment_cost: 250,
    marketing_cost: 150,
    minimum_margin_rate: 0.2,
    inventory_quantity: 14,
    features: ['Waterproof shell', 'Insulated lining', 'Adjustable hood'],
    description:
      'A three-layer shell built for sideways rain and long commutes. Sealed seams, a storm hood, and enough room to layer underneath.',
  },
  {
    sku: 'TRAIL-RUNNER-014',
    name: 'Trailhead Running Shoes',
    category: 'footwear',
    list_price: 4499,
    unit_cost: 1900,
    fulfillment_cost: 120,
    marketing_cost: 90,
    minimum_margin_rate: 0.22,
    inventory_quantity: 6,
    features: ['Breathable mesh', 'Cushioned sole', 'Reflective trim'],
    description:
      'Light enough for tempo days, grippy enough for loose gravel. A wide toe box and a compression-molded midsole for the long runs.',
  },
  {
    sku: 'AUDIO-OVER-EAR-220',
    name: 'Overland Wireless Headphones',
    category: 'electronics',
    list_price: 8999,
    unit_cost: 4200,
    fulfillment_cost: 180,
    marketing_cost: 200,
    minimum_margin_rate: 0.25,
    inventory_quantity: 21,
    features: ['Active noise cancelling', '32-hour battery', 'Fold-flat design'],
    description:
      'Over-ear comfort for full flights and full workdays. Adaptive noise cancelling tunes itself to the room around you.',
  },
  {
    sku: 'LEATHER-PACK-07',
    name: 'Fieldstone Leather Backpack',
    category: 'accessories',
    list_price: 5499,
    unit_cost: 2600,
    fulfillment_cost: 140,
    marketing_cost: 110,
    minimum_margin_rate: 0.2,
    inventory_quantity: 9,
    features: ['Full-grain leather', 'Padded laptop sleeve', 'Brass hardware'],
    description:
      'Cut from full-grain leather that softens and darkens with use. A padded 15" laptop sleeve sits behind a felt-lined pocket for small essentials.',
  },
  {
    sku: 'CHRONO-WATCH-45',
    name: 'Merrow Automatic Watch',
    category: 'accessories',
    list_price: 12999,
    unit_cost: 6800,
    fulfillment_cost: 200,
    marketing_cost: 260,
    minimum_margin_rate: 0.18,
    inventory_quantity: 4,
    features: ['Sapphire crystal', 'Automatic movement', 'Stainless case'],
    description:
      'A self-winding movement in a 39mm stainless case. No battery, no software to update — just a sweeping second hand.',
  },
  {
    sku: 'ESPRESSO-BAR-3',
    name: 'Camden Espresso Machine',
    category: 'home',
    list_price: 15999,
    unit_cost: 8900,
    fulfillment_cost: 320,
    marketing_cost: 300,
    minimum_margin_rate: 0.15,
    inventory_quantity: 7,
    features: ['15-bar pump', 'Steam wand', 'Removable drip tray'],
    description:
      'A 15-bar pump and a proper steam wand, built into a countertop machine that does not need a manual to run.',
  },
  {
    sku: 'MIRROR-CAM-X2',
    name: 'Lumen X2 Mirrorless Camera',
    category: 'electronics',
    list_price: 54999,
    unit_cost: 32000,
    fulfillment_cost: 450,
    marketing_cost: 600,
    minimum_margin_rate: 0.12,
    inventory_quantity: 3,
    features: ['24MP sensor', '4K video', 'Weather-sealed body'],
    description:
      'A 24MP sensor in a weather-sealed body, with in-body stabilization that makes handheld low light footage usable.',
  },
  {
    sku: 'SUNGLASS-RIDGE-9',
    name: 'Ridgeline Polarized Sunglasses',
    category: 'accessories',
    list_price: 2999,
    unit_cost: 1100,
    fulfillment_cost: 60,
    marketing_cost: 80,
    minimum_margin_rate: 0.25,
    inventory_quantity: 0,
    features: ['Polarized lenses', 'UV400 protection', 'Acetate frame'],
    description:
      'Polarized, UV400 lenses set into a hand-polished acetate frame. Cuts glare off water and windshields alike.',
  },
]

const CATEGORY_LABELS = {
  all: 'All',
  apparel: 'Apparel',
  footwear: 'Footwear',
  electronics: 'Electronics',
  accessories: 'Accessories',
  home: 'Home',
}

function money(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `₹${Math.round(Number(value)).toLocaleString('en-IN')}`
}

function compareAtPrice(listPrice) {
  return Math.round(listPrice * 1.18)
}

function discountPercent(listPrice) {
  const was = compareAtPrice(listPrice)
  return Math.round(((was - listPrice) / was) * 100)
}

function stockInfo(qty) {
  if (qty <= 0) return { label: 'Out of stock', tone: 'out' }
  if (qty <= 5) return { label: `Only ${qty} left`, tone: 'low' }
  return { label: 'In stock', tone: 'in' }
}

function StatusPill({ value }) {
  const clean = String(value || 'pending')
    .toLowerCase()
    .replace(/\_/g, '-')

  return (
    <span className={`status-pill ${clean}`}>
      {value || 'Pending'}
    </span>
  )
}

function ProductCard({ product, onOpen, onNegotiate }) {
  const stock = stockInfo(product.inventory_quantity)
  const image = getGallery(product)[0]

  return (
    <article className="product-card" onClick={() => onOpen(product)}>
      <div className="product-card-media">
        <img src={image} alt={product.name} loading="lazy" />
        <span className="discount-chip">
          {discountPercent(product.list_price)}% off
        </span>
        {stock.tone !== 'in' && (
          <span className={`stock-chip ${stock.tone}`}>{stock.label}</span>
        )}
      </div>

      <div className="product-card-body">
        <span className="product-card-category">
          {CATEGORY_LABELS[product.category] || product.category}
        </span>

        <h3>{product.name}</h3>

        <div className="product-card-price">
          <strong>{money(product.list_price)}</strong>
          <s>{money(compareAtPrice(product.list_price))}</s>
        </div>

        <button
          type="button"
          className="negotiate-chip"
          disabled={stock.tone === 'out'}
          onClick={(event) => {
            event.stopPropagation()
            onNegotiate(product)
          }}
        >
          Negotiate price
        </button>
      </div>
    </article>
  )
}

function NegotiationLedger({ history }) {
  const rounds = []

  for (let i = 0; i < history.length; i += 2) {
    rounds.push({
      buyer: history[i],
      seller: history[i + 1],
    })
  }

  return (
    <div className="ledger">
      {rounds.map((round, index) => (
        <div className="ledger-round" key={index}>
          <span className="ledger-round-label">Round {index + 1}</span>

          <div className="ledger-row buyer-row">
            <span className="ledger-role">You offered</span>
            <p>{round.buyer?.content}</p>
          </div>

          {round.seller && (
            <div className="ledger-row seller-row">
              <span className="ledger-role">Seller replied</span>
              <p>{round.seller.content}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function AuditTrail({ entries, fallbackProductName }) {
  if (!entries.length) return null

  return (
    <div className="audit-list">
      {entries.map((entry, index) => {
        const data = entry?.data || {}
        const decision =
          data.decision || data.status || entry?.event || 'Unknown'
        const reason = data.reason || 'No reason recorded.'
        const productName = data.product || fallbackProductName
        const price =
          data.agreed_price ?? data.attempted_price ?? data.amount
        const failedRule =
          data.failed_rule ||
          (Array.isArray(data.failed_rules) ? data.failed_rules[0] : null)

        return (
          <div
            key={`${entry?.timestamp || index}-${index}`}
            className="audit-entry"
          >
            <div className="audit-header">
              <strong>{decision}</strong>
              <span>
                {new Date(entry?.timestamp || Date.now()).toLocaleString(
                  'en-IN',
                  {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  },
                )}
              </span>
            </div>

            <div className="audit-grid">
              <div>
                <span>Reason</span>
                <b>{reason}</b>
              </div>

              {productName && (
                <div>
                  <span>Product</span>
                  <b>{productName}</b>
                </div>
              )}

              {price != null && (
                <div>
                  <span>Price</span>
                  <b>{money(price)}</b>
                </div>
              )}

              {failedRule && (
                <div>
                  <span>Failed rule</span>
                  <b>{failedRule}</b>
                </div>
              )}

              {data.inventory != null && (
                <div>
                  <span>Inventory</span>
                  <b>{data.inventory}</b>
                </div>
              )}

              {data.margin != null && (
                <div>
                  <span>Margin</span>
                  <b>{Number(data.margin * 100).toFixed(1)}%</b>
                </div>
              )}

              {data.discount != null && (
                <div>
                  <span>Discount</span>
                  <b>{Number(data.discount * 100).toFixed(1)}%</b>
                </div>
              )}

              {data.amount != null && (
                <div>
                  <span>Amount</span>
                  <b>{money(data.amount)}</b>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ProductDrawer({ product, onClose, onNegotiate }) {
  const [activeImage, setActiveImage] = useState(0)
  const gallery = getGallery(product)
  const stock = stockInfo(product.inventory_quantity)

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={(event) => event.stopPropagation()}>
        <button
          type="button"
          className="drawer-close"
          onClick={onClose}
          aria-label="Close"
        >
          Close
        </button>

        <div className="drawer-gallery">
          <div className="drawer-gallery-main">
            <img src={gallery[activeImage]} alt={product.name} />
          </div>

          {gallery.length > 1 && (
            <div className="drawer-thumbs">
              {gallery.map((src, index) => (
                <button
                  type="button"
                  key={src}
                  className={`drawer-thumb ${
                    index === activeImage ? 'active' : ''
                  }`}
                  onClick={() => setActiveImage(index)}
                >
                  <img src={src} alt="" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="drawer-info">
          <span className="product-card-category">
            {CATEGORY_LABELS[product.category] || product.category}
          </span>

          <h2>{product.name}</h2>

          <p className="drawer-description">{product.description}</p>

          <ul className="feature-list">
            {product.features.map((feature) => (
              <li key={feature}>{feature}</li>
            ))}
          </ul>

          <div className="drawer-price-row">
            <div className="product-card-price large">
              <strong>{money(product.list_price)}</strong>
              <s>{money(compareAtPrice(product.list_price))}</s>
            </div>

            <span className={`stock-chip ${stock.tone}`}>
              {stock.label}
            </span>
          </div>

          <button
            type="button"
            className="primary-button"
            disabled={stock.tone === 'out'}
            onClick={() => onNegotiate(product)}
          >
            Negotiate this price <span>→</span>
          </button>
        </div>
      </div>
    </div>
  )
}

function NegotiationPage({ product, onBack, onDone }) {
  const [request, setRequest] = useState(
    `I'd like the ${product.name}`,
  )
  const [maxPrice, setMaxPrice] = useState(String(product.list_price))
  const [negotiation, setNegotiation] = useState(null)
  const [payment, setPayment] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const ledgerEndRef = useRef(null)

  const image = getGallery(product)[0]
  const stock = stockInfo(product.inventory_quantity)
  const policy = negotiation?.policy
  const revenue = negotiation?.revenue || {}
  const started = !!negotiation || loading
  const auditEntries = Array.isArray(negotiation?.audit_trail)
    ? negotiation.audit_trail
    : []

  useEffect(() => {
    ledgerEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    })
  }, [negotiation?.conversation_history?.length])

  async function negotiate(event) {
    event.preventDefault()

    setLoading(true)
    setError('')
    setPayment(null)
    setNegotiation(null)

    try {
      const data = await negotiateRequest({
        userRequirement: request,
        productSku: product.sku,
        buyerMaxPrice: Number(maxPrice),
        maxRounds: 4,
      })

      setNegotiation(data)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  async function createPayment() {
    setError('')
    setPayment({ status: 'creating' })

    try {
      const data = await createPaymentRequest(
        negotiation.negotiation_id,
      )
      setPayment(data)
    } catch (requestError) {
      setPayment(null)
      setError(requestError.message)
    }
  }

  function resetOffer() {
    setNegotiation(null)
    setPayment(null)
    setError('')
  }

  return (
    <div className="negotiation-page">
      <button type="button" className="back-link" onClick={onBack}>
        ← Back to shop
      </button>

      <div className="summary-strip">
        <img src={image} alt={product.name} />

        <div className="summary-strip-info">
          <span className="product-card-category">
            {CATEGORY_LABELS[product.category] || product.category}
          </span>

          <h1>{product.name}</h1>

          <div className="product-card-price">
            <strong>{money(product.list_price)}</strong>
            <s>{money(compareAtPrice(product.list_price))}</s>
          </div>
        </div>

        <span className={`stock-chip ${stock.tone}`}>
          {stock.label}
        </span>
      </div>

      {error && (
        <div className="error-banner">
          <strong>Could not continue</strong>
          <span>{error}</span>
        </div>
      )}

      {!started && !negotiation && (
        <form className="offer-form page-offer-form" onSubmit={negotiate}>
          <div className="offer-form-heading">
            <h3>Your offer</h3>
            <p>
              Tell the seller what you're looking for and the most
              you're willing to pay. Negotiation happens automatically
              from here.
            </p>
          </div>

          <label>
            What are you looking for
            <textarea
              value={request}
              onChange={(event) => setRequest(event.target.value)}
              rows={2}
            />
          </label>

          <label>
            Your maximum price
            <input
              type="number"
              min="1"
              value={maxPrice}
              onChange={(event) => setMaxPrice(event.target.value)}
            />
          </label>

          <button
            className="primary-button"
            disabled={loading}
            type="submit"
          >
            {loading && <span className="button-spinner" />}
            {loading ? 'Sending offer' : 'Send offer'} <span>→</span>
          </button>
        </form>
      )}

      {started && (
        <div className="offer-recap">
          <div>
            <span>Your request</span>
            <p>{request}</p>
          </div>

          <div className="offer-recap-price">
            <span>Your ceiling</span>
            <b>{money(maxPrice)}</b>
          </div>

          {negotiation && !payment?.order_id && (
            <button
              type="button"
              className="text-link"
              onClick={resetOffer}
            >
              Edit offer
            </button>
          )}
        </div>
      )}

      {started && (
        <section className="conversation-card">
          <div className="conversation-card-heading">
            <h2>Negotiation</h2>
            {negotiation && <StatusPill value={negotiation.status} />}
          </div>

          {negotiation ? (
            <>
              <NegotiationLedger
                history={negotiation.conversation_history || []}
              />
              <div ref={ledgerEndRef} />
            </>
          ) : (
            <div className="conversation-loading">
              <span className="loading-dot" />
              <p>
                Negotiating on your behalf
                <span className="ellipsis" />
              </p>
            </div>
          )}
        </section>
      )}

      {negotiation && (
        <div className="offer-summary page-offer-summary">
          <div>
            <span>Your ceiling</span>
            <b>{money(maxPrice)}</b>
          </div>

          <div>
            <span>
              {negotiation.status === 'agreed'
                ? 'Agreed price'
                : 'Best offer reached'}
            </span>
            <b className="accent-value">
              {money(negotiation.agreed_price)}
            </b>
          </div>
        </div>
      )}

      {negotiation && negotiation.status !== 'agreed' && (
        <div className="decision timeout">
          <div>
            <strong>No agreement reached</strong>
            <p>
              The seller and buyer could not settle within the round
              limit. Try a higher ceiling.
            </p>
          </div>
        </div>
      )}

      {negotiation &&
        negotiation.status === 'agreed' &&
        policy && (
          <div
            className={`decision ${policy.decision?.toLowerCase()}`}
          >
            <div>
              <strong>
                {policy.decision === 'ALLOW'
                  ? 'Order approved'
                  : 'Order needs review'}
              </strong>

              <p>{policy.reason}</p>

              <div className="decision-meta">
                <span>Decision: {policy.decision}</span>
                <span>Product: {product.name}</span>
                <span>
                  Price: {money(negotiation.agreed_price)}
                </span>
                <span>
                  Inventory: {product.inventory_quantity ?? '—'}
                </span>
              </div>
            </div>
          </div>
        )}

      {auditEntries.length > 0 && (
        <section className="audit-panel">
          <div className="conversation-card-heading">
            <h2>Audit trail</h2>
          </div>

          <AuditTrail
            entries={auditEntries}
            fallbackProductName={product.name}
          />
        </section>
      )}

      {negotiation &&
        negotiation.status === 'agreed' &&
        policy?.decision === 'ALLOW' &&
        !payment?.order_id && (
          <button
            type="button"
            className="payment-button"
            onClick={createPayment}
            disabled={payment?.status === 'creating'}
          >
            {payment?.status === 'creating' && (
              <span className="button-spinner" />
            )}

            {payment?.status === 'creating'
              ? 'Creating order'
              : `Accept & pay ${
                  money(
                    revenue.revenue ?? negotiation.agreed_price,
                  )
                } · Razorpay test`}

            <span>↗</span>
          </button>
        )}

      {payment?.order_id && (
        <div className="order-confirmation">
          <span className="order-confirmation-mark">
            Order placed
          </span>

          <h3>Thanks — your order is confirmed</h3>

          <div className="order-details">
            <div>
              <span>Order ID</span>
              <b>{payment.order_id}</b>
            </div>

            <div>
              <span>Amount</span>
              <b>{money(payment.amount / 100)}</b>
            </div>

            <div>
              <span>Currency</span>
              <b>{payment.currency}</b>
            </div>
          </div>

          <p className="muted">
            This is a Razorpay test-mode order — no funds move.
          </p>

          <button
            type="button"
            className="secondary-button"
            onClick={onDone}
          >
            Continue shopping
          </button>
        </div>
      )}

      {negotiation &&
        (negotiation.status !== 'agreed' ||
          policy?.decision !== 'ALLOW') &&
        !payment?.order_id && (
          <button
            type="button"
            className="secondary-button"
            onClick={resetOffer}
          >
            Make a new offer
          </button>
        )}
    </div>
  )
}

function formatDate(value) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return '—'

  return date.toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function AccountPage({ onBack }) {
  const [summary, setSummary] = useState(null)
  const [history, setHistory] = useState(null)
  const [auditEntries, setAuditEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    setLoading(true)
    setError('')

    Promise.all([
      fetchCustomerSummary(),
      fetchCustomerHistory(),
      fetchCustomerAudit(),
    ])
      .then(([summaryData, historyData, auditData]) => {
        if (cancelled) return

        setSummary(summaryData)
        setHistory(historyData)

        setAuditEntries(
          Array.isArray(auditData?.events)
            ? auditData.events
            : Array.isArray(auditData)
              ? auditData
              : [],
        )
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const negotiations = Array.isArray(history?.negotiations)
    ? history.negotiations
    : []

  const payments = Array.isArray(history?.payments)
    ? history.payments
    : []

  return (
    <div className="negotiation-page account-page">
      <button type="button" className="back-link" onClick={onBack}>
        ← Back to shop
      </button>

      <div className="account-heading">
        <h1>My activity</h1>
        <p className="muted">
          Your negotiations, orders, and policy decisions with
          Mercury.
        </p>
      </div>

      {error && (
        <div className="error-banner">
          <strong>Could not load activity</strong>
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="conversation-card">
          <div className="conversation-loading">
            <span className="loading-dot" />
            <p>
              Loading your activity
              <span className="ellipsis" />
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <span>Total orders</span>
              <strong>{summary?.total_orders ?? 0}</strong>
            </div>

            <div className="stat-card">
              <span>Total spend</span>
              <strong>{money(summary?.total_spend)}</strong>
            </div>

            <div className="stat-card">
              <span>Total profit</span>
              <strong>{money(summary?.total_profit)}</strong>
            </div>

            <div className="stat-card">
              <span>CLV score</span>
              <strong>{summary?.clv_score ?? '—'}</strong>
            </div>
          </div>

          <section className="conversation-card">
            <div className="conversation-card-heading">
              <h2>Negotiation history</h2>

              <span className="muted">
                {negotiations.length} negotiation
                {negotiations.length === 1 ? '' : 's'}
              </span>
            </div>

            {negotiations.length ? (
              <div className="history-list">
                {negotiations.map((entry, index) => (
                  <div
                    className="history-row"
                    key={entry.negotiation_id || index}
                  >
                    <div className="history-row-main">
                      <strong>
                        {entry.sku || 'Product'}
                      </strong>

                      <span className="muted">
                        {entry.status || '—'}
                      </span>
                    </div>

                    <StatusPill value={entry.status} />

                    <b className="accent-value">
                      {money(entry.final_price)}
                    </b>

                    <span className="history-date">
                      {formatDate(entry.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">
                No negotiations yet — start one from any product
                page.
              </p>
            )}
          </section>

          <section className="conversation-card">
            <div className="conversation-card-heading">
              <h2>Payment history</h2>

              <span className="muted">
                {payments.length} payment
                {payments.length === 1 ? '' : 's'}
              </span>
            </div>

            {payments.length ? (
              <div className="history-list">
                {payments.map((entry, index) => (
                  <div
                    className="history-row"
                    key={entry.order_id || index}
                  >
                    <div className="history-row-main">
                      <strong>
                        {entry.order_id || 'Order'}
                      </strong>

                      <span className="muted">
                        {entry.currency || 'INR'}
                      </span>
                    </div>

                    <StatusPill value={entry.status} />

                    <b className="accent-value">
                      {money(
                        entry.amount != null
                          ? entry.amount / 100
                          : entry.amount,
                      )}
                    </b>

                    <span className="history-date">
                      {formatDate(
                        entry.created_at || entry.timestamp,
                      )}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">No payments yet.</p>
            )}
          </section>

          {auditEntries.length > 0 && (
            <section className="audit-panel">
              <div className="conversation-card-heading">
                <h2>Audit &amp; decision history</h2>
              </div>

              <AuditTrail entries={auditEntries} />
            </section>
          )}
        </>
      )}
    </div>
  )
}

function App() {
  const [catalog, setCatalog] = useState(fallbackCatalog)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [activeProduct, setActiveProduct] = useState(null)
  const [view, setView] = useState('shop')
  const [negotiationProduct, setNegotiationProduct] = useState(null)

  useEffect(() => {
    fetchCatalog()
      .then((data) => {
        if (Array.isArray(data) && data.length) {
          setCatalog(data)
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    function onPopState(event) {
      const nextView =
        event.state?.view === 'account'
          ? 'account'
          : event.state?.view === 'negotiate'
            ? 'negotiate'
            : 'shop'

      setView(nextView)

      if (nextView === 'shop') {
        setNegotiationProduct(null)
      }
    }

    window.addEventListener('popstate', onPopState)

    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const categories = useMemo(
    () => ['all', ...new Set(catalog.map((item) => item.category))],
    [catalog],
  )

  const visible = useMemo(() => {
    return catalog.filter((item) => {
      const matchesCategory =
        category === 'all' || item.category === category

      const matchesQuery =
        !query ||
        item.name.toLowerCase().includes(query.toLowerCase()) ||
        item.category.toLowerCase().includes(query.toLowerCase())

      return matchesCategory && matchesQuery
    })
  }, [catalog, category, query])

  function openProduct(product) {
    setActiveProduct(product)
  }

  function goToNegotiation(product) {
    setActiveProduct(null)
    setNegotiationProduct(product)
    setView('negotiate')
    window.history.pushState(
      { view: 'negotiate' },
      '',
      '#negotiate',
    )
  }

  function goToAccount() {
    setActiveProduct(null)
    setView('account')
    window.history.pushState(
      { view: 'account' },
      '',
      '#account',
    )
  }

  function backToShop() {
    setView('shop')
    setNegotiationProduct(null)

    if (
      window.history.state?.view === 'negotiate' ||
      window.history.state?.view === 'account'
    ) {
      window.history.back()
    }
  }

  if (view === 'account') {
    return (
      <div className="storefront">
        <header className="site-header negotiate-header">
          <div className="site-header-row">
            <div className="logo">Mercury</div>
          </div>
        </header>

        <AccountPage onBack={backToShop} />

        <footer className="site-footer">
          <span>Mercury — test store</span>
          <span>
            Negotiation is AI-assisted; every order still passes a
            fixed approval policy.
          </span>
        </footer>
      </div>
    )
  }

  if (view === 'negotiate' && negotiationProduct) {
    return (
      <div className="storefront">
        <header className="site-header negotiate-header">
          <div className="site-header-row">
            <div className="logo">Mercury</div>
          </div>
        </header>

        <NegotiationPage
          product={negotiationProduct}
          onBack={backToShop}
          onDone={backToShop}
        />

        <footer className="site-footer">
          <span>Mercury — test store</span>
          <span>
            Negotiation is AI-assisted; every order still passes a
            fixed approval policy.
          </span>
        </footer>
      </div>
    )
  }

  return (
    <div className="storefront">
      <div className="announcement-bar">
        Free shipping over ₹2,000 · Test-mode checkout, no real
        charges
      </div>

      <header className="site-header">
        <div className="site-header-row">
          <div className="logo">Mercury</div>

          <div className="search-bar">
            <input
              type="search"
              placeholder="Search products, categories…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              aria-label="Search products"
            />
          </div>

          <nav className="header-links">
            <button
              type="button"
              className="header-link-button"
              onClick={goToAccount}
            >
              My activity
            </button>
          </nav>
        </div>

        <nav className="category-bar">
          {categories.map((cat) => (
            <button
              type="button"
              key={cat}
              className={`category-chip ${
                category === cat ? 'active' : ''
              }`}
              onClick={() => setCategory(cat)}
            >
              {CATEGORY_LABELS[cat] || cat}
            </button>
          ))}
        </nav>
      </header>

      <main className="catalog-section" id="catalog">
        <div className="catalog-heading">
          <h1>
            {category === 'all'
              ? 'Shop all'
              : CATEGORY_LABELS[category] || category}
          </h1>

          <span className="muted">
            {visible.length} item
            {visible.length === 1 ? '' : 's'}
          </span>
        </div>

        {visible.length ? (
          <div className="product-grid">
            {visible.map((product) => (
              <ProductCard
                key={product.sku}
                product={product}
                onOpen={openProduct}
                onNegotiate={goToNegotiation}
              />
            ))}
          </div>
        ) : (
          <div className="empty-catalog">
            <strong>No matches</strong>
            <span>
              Try a different search term or category.
            </span>
          </div>
        )}
      </main>

      <footer className="site-footer">
        <span>Mercury — test store</span>
        <span>
          Negotiation is AI-assisted; every order still passes a
          fixed approval policy.
        </span>
      </footer>

      {activeProduct && (
        <ProductDrawer
          product={activeProduct}
          onClose={() => setActiveProduct(null)}
          onNegotiate={goToNegotiation}
        />
      )}
    </div>
  )
}

export default App