const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

/* ------------------------------------------------------------------ */
/* Customer id — generated once per browser, reused for every          */
/* customer-scoped request.                                            */
/* ------------------------------------------------------------------ */

function getCustomerId() {
  let id = localStorage.getItem('mercury_customer_id')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('mercury_customer_id', id)
  }
  return id
}

export const customerId = getCustomerId()

/* ------------------------------------------------------------------ */
/* Fetch helper                                                        */
/* ------------------------------------------------------------------ */

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || 'Something went wrong. Please try again.')
  return data
}

/* ------------------------------------------------------------------ */
/* Catalog                                                             */
/* ------------------------------------------------------------------ */

export function fetchCatalog() {
  return request('/catalog')
}

/* ------------------------------------------------------------------ */
/* Negotiation + payment                                               */
/* ------------------------------------------------------------------ */

export function negotiate({ userRequirement, productSku, buyerMaxPrice, maxRounds = 4 }) {
  return request('/negotiate', {
    method: 'POST',
    body: JSON.stringify({
      user_requirement: userRequirement,
      product_sku: productSku,
      buyer_max_price: buyerMaxPrice,
      max_rounds: maxRounds,
      customer_id: customerId,
    }),
  })
}

export function createPayment(negotiationId) {
  return request('/payment/create', {
    method: 'POST',
    body: JSON.stringify({ negotiation_id: negotiationId, customer_id: customerId }),
  })
}

/* ------------------------------------------------------------------ */
/* Customer persistence                                                */
/* ------------------------------------------------------------------ */

export function fetchCustomerSummary() {
  return request(`/customer/${customerId}`)
}

export function fetchCustomerHistory() {
  return request(`/customer/${customerId}/history`)
}

export function fetchCustomerAudit() {
  return request(`/customer/${customerId}/audit`)
}