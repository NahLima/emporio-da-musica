# Empório da Música — Políticas da loja (resumo estruturado)

> Source: `data/politicas_da_loja.pdf` — Manual de Políticas e Procedimentos,
> Atendimento ao Cliente, version 2.1, June 2025 (8 pages, internal document).
> This file is a faithful, section-by-section transcription of that manual,
> written so the agent can retrieve one section at a time. The original PDF
> is the authoritative source; if this file and the PDF disagree, the PDF wins.
>
> NOTE ON CONFLICTING CONTACT DATA (assumption, see README): the cover page
> lists WhatsApp (67) 3341-4444 and e-mail contato@emporiodamusica.com.br,
> while section 1.2 prints an e-mail with an accent (invalid) and section 7
> lists WhatsApp (67) 3321-4500. The agent uses the cover-page values
> (67) 3341-4444 / contato@emporiodamusica.com.br and must flag the conflict
> instead of silently picking one.

## 1. About the store

- Empório da Música Instrumentos Musicais Ltda., founded in 2008 in Campo
  Grande, Mato Grosso do Sul. Regional reference for beginner, intermediate
  and professional musicians.
- The manual claims a catalog of 300+ instruments (guitars, basses, acoustic
  guitars, drums, keyboards, wind instruments, orchestral strings, ukuleles).
  NOTE: the CSV catalog supplied with this challenge contains only 65 products,
  and categories 6 (woodwind), 7 (brass) and 8 (orchestral strings) have zero
  products. The agent must answer from the CSV catalog, not from the "300+"
  claim.
- The store sells instruments ONLY. It does NOT sell accessories such as
  strings, picks, cables, cases, pedals or amplifiers.
- Address: Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, CEP 79202-333.
- Phone / WhatsApp: (67) 3341-4444. E-mail: contato@emporiodamusica.com.br.
- CNPJ: 12.345.678/0001-90.

## 2. Opening hours

- Monday to Friday: 09:00 to 18:00.
- Saturday: 09:00 to 13:00.
- Sunday and holidays: closed.
- WhatsApp follows the same hours; automatic replies outside business hours.
- On special dates (Black Friday, store anniversary, Christmas) hours may be
  extended; changes are announced in advance on social media and WhatsApp.

## 3. Payment methods

- PIX: upfront, 5% discount on the list price.
- Debit card: upfront, all major brands accepted.
- Credit card: up to 12 installments, interest-free. Minimum installment
  R$ 100.00 (for 7x–12x).
- Bank slip (boleto): upfront, clearing within up to 3 business days.
- Installments: up to 3x interest-free, no minimum installment (except below
  R$ 50.00); 4x–6x interest-free, minimum installment R$ 80.00; 7x–12x
  interest-free, minimum installment R$ 100.00.
- Combining payment methods (e.g. PIX + card) is allowed for purchases above
  R$ 2,000.00.

## 4. Exchanges and returns

### 4.1 Right of withdrawal (online purchases)

- The customer may request a return within 7 (seven) calendar days AFTER
  RECEIVING the product, no justification required.
- The product must be in its original packaging, with no signs of use, with
  all accessories and manuals.
- The refund is made to the original payment method within up to 10 business
  days.
- Return shipping is paid by the store in case of withdrawal.

### 4.2 Exchange for defect

- Products with a manufacturing defect may be exchanged within 30 (thirty)
  calendar days after purchase.
- After 30 days, the customer must claim the warranty directly with the
  manufacturer. The store may intermediate the process on request.
- Damage caused by misuse, falls, excessive humidity or unauthorized
  modifications is not covered.

### 4.3 Exchange by preference

- Exchanges by preference (color, model, size) are allowed within 7 days,
  subject to availability of the desired product.
- The product must be in perfect condition and in its original packaging.
- Price differences are charged or refunded as applicable.

### 4.4 Items not eligible for exchange

- Instruments with personalization or made-to-order adjustments (setup,
  special regulation).
- Products bought in liquidation promotions with an explicit "final sale"
  notice.
- Wind-instrument mouthpieces, for hygiene reasons.

## 5. Shipping and delivery

### 5.1 Campo Grande metropolitan area

- Free shipping for orders above R$ 500.00.
- For orders below R$ 500.00, a fixed fee of R$ 35.00.
- Delivery time: 1 to 3 business days, by the store's own courier. The
  customer is contacted by phone before delivery.

### 5.2 Other cities

- Via Correios (PAC and SEDEX) and Jadlog.
- PAC: 5 to 12 business days. SEDEX: 2 to 5 business days. Jadlog: 3 to 8
  business days. All with tracking and insurance included.
- Shipping cost is calculated from the destination ZIP code, weight and
  dimensions. Large instruments (acoustic drums, digital pianos, basses) may
  require special freight with an individual quote.
- All shipments include insurance against loss and damage in transit. In case
  of damage, the customer must refuse delivery and contact the store
  immediately.

### 5.3 Tracking code

- The tracking code is sent automatically by e-mail and WhatsApp once the
  order is shipped. Standard format: BR + 9 alphanumeric characters + BR
  (example: BR4K7M2X9P1BR). Tracking can be checked on the Correios or Jadlog
  website.

## 6. Promotions and discounts

- Campaigns: store anniversary (August, 10%–25% off selected items), Black
  Friday (November, 15%–30% off the whole catalog), back to school (February),
  clearance (queima de estoque), Musician's Week (week of 22 November).
- Promotions are NOT cumulative. The PIX discount (5%) does NOT apply to
  prices that are already promotional.
- Promotions are subject to stock availability. Products sold out during a
  promotion do not give a right to a rain check (price reservation).
- Promotional prices must always be shown together with the original price
  and the discount percentage.
- NOTE: only promotions with `is_active=1` in `data/promotions.csv` are
  actually active. Most promotions in the file are inactive and must never be
  offered. See `src/tools.py` (`get_active_promotion`).

## 7. WhatsApp service

- Tone of voice: informal but professional. The customer should feel welcome,
  as if talking to a friend who understands music. Avoid excessively formal or
  robotic language.
- Maximum response time: 5 minutes during business hours. Outside business
  hours, the virtual assistant must inform the return time.
- Never provide price, stock or deadline information without checking the
  system. Incorrect information frustrates customers and may be misleading
  advertising.
- Scope: the store works exclusively with musical instruments. Requests for
  accessories (strings, cables, picks, pedals, amplifiers, cases) must be
  politely redirected. Suggest partner stores when possible.
- Standard flow: (1) greet the customer by name when available and ask how
  to help; (2) understand the need; (3) check the system; (4) answer clearly
  with prices and conditions; (5) confirm whether anything else is needed and
  close cordially.
- Out of stock: say the product is temporarily unavailable and suggest similar
  available alternatives. Never confirm availability without checking stock.
- Discontinued product: say it is no longer in the catalog and offer
  equivalent or successor models.
- Expired promotion: check whether it is active in the system. If expired, say
  so transparently and give the current price. Never promise a discount that
  is no longer valid.
- Complaint: listen with empathy, register the complaint and forward it to the
  responsible person. Return time: 24 business hours.

## 8. Warranty

- Legal warranty: 90 (ninety) days against manufacturing defects, counted
  from the date the customer receives the product (Consumer Defense Code).
- Manufacturer warranty: most manufacturers offer their own warranty, from
  6 months to 2 years. Exact terms are in the warranty certificate that comes
  with each product.
- Not covered: natural wear of parts (frets, strings, felts, wind reeds);
  damage from misuse, falls or extreme weather; modifications or repairs by
  unauthorized third parties; cosmetic damage that does not affect function.

## 9. Privacy and data protection

- The store complies with the LGPD (Law 13,709/2018). Personal data collected
  during service (name, phone, e-mail, address) is used exclusively for order
  processing and delivery, order-status communication, promotions and news
  (only with explicit consent) and legal/fiscal obligations.
- Customer data is not shared with third parties for marketing. The customer
  may request deletion of their data at any time via WhatsApp or e-mail.
- The agent must not reveal order data without validating the customer first
  (ask for the order number and confirm the customer's name).

## 10. Final provisions

- This manual is an internal document and must be used as a reference by all
  service team members, including the virtual assistant. Policies are subject
  to periodic updates.
- If in doubt about how to apply any policy, the attendant must consult
  management before giving information to the customer.
