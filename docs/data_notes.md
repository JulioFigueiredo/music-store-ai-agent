# Data inspection notes

Findings from inspecting `data/` with code (pandas + pypdf). Every later design
decision is based on these notes. The files in `data/` are read-only; all
cleaning happens in code at load time.

Items marked **(new)** were not listed in `CLAUDE.md` and were found during
inspection.

## 1. Files

| File | Size | Notes |
|---|---|---|
| `desafio_tecnico_ai_eng - categories.csv` | 9 rows | |
| `desafio_tecnico_ai_eng - products.csv` | 65 rows | |
| `desafio_tecnico_ai_eng - customers.csv` | 50 rows | |
| `desafio_tecnico_ai_eng - orders.csv` | 20 rows | |
| `desafio_tecnico_ai_eng - order_items.csv` | 22 rows | |
| `desafio_tecnico_ai_eng - promotions.csv` | 25 rows | |
| `políticas_da_loja.pdf` | 8 pages | Google Docs export of `políticas_da_loja.docx` |

- **(new) File names use `" - "` (space, dash, space)**, not `_-_` as stated in
  `CLAUDE.md`. The exact names are constants in `config.py` (no globbing).
- **(new) `order_items` has 22 rows**, not 23.
- All CSVs are valid UTF-8, no BOM, CRLF line endings. On Windows the console
  shows broken accents, but the files are fine. The loader passes
  `encoding="utf-8"` explicitly so it never depends on the OS default.
- No fully duplicated rows in any table. No missing values except in `orders`
  (see section 5).

## 2. Categories

| id | name | products |
|---|---|---|
| 1 | Guitarras | 5 |
| 2 | Baixos | 4 |
| 3 | Baterias e Percussão | 3 |
| 4 | Teclados e Pianos | 3 |
| 5 | Violões | 35 |
| 6 | Instrumentos de Sopro (Madeiras) | **0** |
| 7 | Instrumentos de Sopro (Metais) | **0** |
| 8 | Cordas Orquestrais | **0** |
| 9 | Ukuleles | 15 |

Categories 6, 7 and 8 exist but are empty. The agent must say these items are
not currently available (not "out of stock") and must not invent products.

## 3. Products

Columns: `product_id` (int), `price_brl` (float), `name`, `category_id` (int),
`description`, `stock_quantity` (int), `status`, `specs` (JSON string),
`created_at` (`YYYY-MM-DD`, 2020-02-28 to 2025-05-15).

- IDs 81–145, unique, **not sorted** (145 appears before 131). Never rely on row
  order.
- Prices: R$ 159.90 to R$ 19,567.00, median R$ 1,299.00. All plain floats (no
  currency strings to clean).
- No duplicated names. Typo: `Giannini GN-15 Nylon Cedr Natural` (fuzzy matching
  handles it).
- Names use `GD20`, not `GD-20` (`Takamine GD20 Dreadnought Natural`). Matching
  must ignore punctuation so "GD-20" still finds it.
- The manual claims "more than 300 instruments"; the CSV has 65. **The CSV is
  the source of truth.**

### Status and stock

| Status | Count |
|---|---|
| `active` | 62 |
| `discontinued` | 2 (113, 136) |
| `coming_soon` | 1 (130) |

| id | name | status | stock | how the agent describes it |
|---|---|---|---|---|
| 96 | Giannini GF-3D Dreadnought Sunburst | active | 0 | temporarily unavailable + alternatives |
| 113 | Shelby SN-7C 7 Cordas Nylon Natural | discontinued | 0 | no longer in the catalog + equivalents |
| 130 | Kala KA-ABP-CTG Barítono Cedar | coming_soon | 2 | "em breve" |
| 136 | Ibanez Bass 2X Electric Bass | discontinued | 13 | no longer in the catalog (do not sell, despite stock) |

Rule: **available = `status == "active"` and `stock_quantity > 0`.**

### Specs

`specs` is valid JSON for all 65 rows (`json.loads` works). Keys by category:

| Category | Keys |
|---|---|
| Guitarras, Baixos | `body`, `neck`, `strings`, `color` |
| Baterias | `shells`, `pieces`, `hardware`, `color` |
| Teclados | `keys`, `type`, `polyphony`, `color` |
| Violões, Ukuleles | `top`, `back_sides`, `neck`, `strings`, `scale`, `electronics`, `color` |

10 rows (135–144) use `": "` spacing; `json.loads` handles both forms.

### Description vs. name conflicts

Checking descriptions for brand names that do not appear in the product name
flags **six products**, all in 135–144. **(new)** `CLAUDE.md` listed three
examples; the full set is:

| id | name | description says | also contradicts specs |
|---|---|---|---|
| 135 | Music Man Bass 1X | Fender Jazz Bass, Alder body | specs body: Ash |
| 137 | Yamaha Bass 3X | Ibanez, 5 strings | specs strings: 4 |
| 139 | Bateria Acústica Yamaha Kit 1 | Pearl Export, Poplar shells | specs shells: Maple |
| 140 | Bateria Acústica Pearl Kit 2 | Tama, Birch shells | specs shells: Maple |
| 142 | Korg Synth 1 Pro | Roland, 88 keys | specs keys: 61 |
| 144 | Roland Synth 3 Pro | Yamaha arranger | — |

Not flagged by the brand rule, but worth knowing:

- 136 (discontinued) says "Precision", a Fender model name, without naming a
  brand. It is not caught, and it does not matter in practice because the
  product is discontinued.
- 138, 141 and 143 mention the same brand as the name. They are kept (143 says
  "stage piano" while `type` is "Synthesizer", a minor wording issue).
- Products 81–134 and 145 have consistent descriptions.

Resolution: `name`, `price_brl`, `stock_quantity`, `status` and `specs` are
authoritative. If a description mentions a brand from `KNOWN_BRANDS` that is
not in the name, the description is dropped (`None`). The check is generic: no
product IDs are hard-coded.

## 4. Customers

50 rows. Columns: `customer_id`, `name`, `phone`, `email`, `city`.

- All phones follow `(67) 9XXXX-XXXX`, with no duplicates after keeping digits
  only.
- All emails are already lowercase, with no spaces.
- **Duplicate email:** customers 11 (`Bruno Carvalho Martins`) and 43
  (`Bruno Martins`) share `bruno.martins@jmail.com`.
  - **(new)** Customer 11 owns order 10 (R$ 8,732.00). Because the identity
    check compares the contact with *that order's* customer, someone using the
    shared email can still see order 10. This is unavoidable with the data
    (the email really is on file for that customer); the phone number tells
    them apart. It is documented as a known limitation.
- Names are weak identifiers:
  - near duplicates: `Bruno Carvalho` (27) vs. `Bruno Carvalho Martins` (11),
    `Diego Castro` (47) vs. `Diego Fernandes Castro` (13);
  - inconsistent accents: `Joao`, `Leticia`, `Julia` vs. `Letícia`, `Natália`.

  So the identity check is **order ID + email or phone**, never the name.
- Cities: Campo Grande 24, Dourados 7, Três Lagoas 7, Corumbá 6, Ponta Porã 6.
  This matters for the metro vs. other-cities shipping rules.

## 5. Orders and order items

`orders`: `order_id`, `customer_id`, `order_date`, `status`, `total_brl`,
`payment_method`, `tracking_code`, `estimated_delivery`, `notes`. Dates are
`YYYY-MM-DD`, from 2025-10-15 to 2026-03-22.

| Status | Count | pt-BR label |
|---|---|---|
| `delivered` | 7 | entregue |
| `shipped` | 1 | enviado |
| `confirmed` | 4 | confirmado |
| `pending` | 4 | aguardando pagamento/processamento |
| `cancelled` | 4 | cancelado |

Payment methods: `pix` 5, `credit_12x` 4, `credit_6x` 3, `boleto` 3,
`credit_3x` 3, `debit` 2.

- **(new) Only `delivered` and `shipped` orders (8) have `tracking_code` and
  `estimated_delivery`.** The other 12 have them empty, which is expected (they
  were never shipped). The tool must handle missing values.
- All tracking codes match `BR` + 9 alphanumerics + `BR` (manual 5.3).
- `notes` is filled only for the 4 cancelled orders, with a customer-facing
  reason.
- Every order has items, every item points to an existing product, and every
  order points to an existing customer.
- **(new)** Orders 9–12 are still `confirmed` 15–33 days after purchase, with
  no tracking. The tool reports the status as-is, without inventing a reason.

### Totals vs. items

`order_items` has no unit price. Comparing `total_brl` with *current* prices:

| Order | Items at current price | `total_brl` | Difference |
|---|---|---|---|
| 3 | 2 × product 130 = 3,498.00 | 3,450.00 | −48.00 |
| 20 (cancelled) | 799.00 + 689.00 = 1,488.00 | 1,400.00 | −88.00 |

The other 18 orders match exactly. Prices may have changed since the purchase,
so the agent reports `total_brl` as what the customer paid and never recomputes
totals.

### Other inconsistencies

- Product 130 is `coming_soon` but appears in orders 3 (delivered) and 14
  (pending). The order tool just reports the order.
- Historical installments break the current rules (manual 3.1):
  order 9 (`credit_6x`, R$ 58.32/installment), order 16 (`credit_6x`,
  R$ 71.65), order 18 (`credit_12x`, R$ 38.32). Assumed to predate manual
  v2.1 (June 2025) or to be exceptions. The agent does not comment on past
  orders' payment terms.
- Orders have no actual delivery date and no sales channel. For `delivered`
  orders, `estimated_delivery` is used as the **assumed receipt date**, and all
  orders are assumed to be **online** (they are shipped with tracking or
  waiting to be shipped). The tool returns `receipt_date_is_estimated: true` so
  the agent can say so.

### Reference date

`STORE_NOW=2026-03-25T10:30` is a **Wednesday**, during business hours, three
days after the last order (2026-03-22). At that date:

- Order 7 (customer 14, Shelby ukulele, delivered): 50 days since purchase, 36
  since the estimated receipt (2026-02-17). The regret window (7 days) and the
  defect-exchange window (30 days) have passed; the 90-day legal warranty
  (from receipt) still applies.
- Order 8 (customer 2, shipped, `BRJL5544332BR`): estimated delivery
  2026-02-28 is 25 days in the past, so `is_delayed: true`.
- 12 violões up to R$ 1,000 are available (14 in the category, minus 96 out of
  stock and 113 discontinued). The cheapest is R$ 429.90 (Tagima Memphis AC-39).

## 6. Promotions

25 rows: `promotion_id`, `product_id`, `discount_percent` (int), `description`,
`is_active` (0/1). No dates, so `is_active == 1` is the only validity signal.

Active (4):

| Promotion | Product | Price | Discount | Description |
|---|---|---|---|---|
| 12 | 127 Kalani KAL-700T Tenor Natural | 359.00 | 10% | Oferta Especial |
| 14 | 121 Ohana CK-20 Concert Natural | 549.00 | 20% | Desconto Exclusivo |
| 19 | 90 Crafter HT-100 Folk Aço Natural | 2,399.00 | 18% | Desconto Exclusivo |
| 24 | 94 Taylor 110e Dreadnought Natural | 5,999.00 | 8% | Desconto Exclusivo |

- Products with several rows: 93, 96, 99 (all rows inactive). No product has
  two active promotions; if it happened, only the highest would apply
  (promotions are not cumulative, manual 6.2).
- Promotion 4 (product 95 Takamine GD20, 12%, "Oferta Especial") is inactive, so
  it must be reported as expired.
- The same description ("Oferta Especial", "Black Friday"…) is reused across
  products, so a promotion is identified by product, not by name.
- Inactive promotions also exist on the out-of-stock product 96 and the
  discontinued product 113.

## 7. Policies PDF

`políticas_da_loja.pdf`: 8 pages, version 2.1, June 2025.

### Extraction

- **(new)** pypdf's default `extract_text()` returns **one word per line**
  (`"palavra\n \n"`), which breaks line-based parsing. Use
  `extract_text(extraction_mode="layout")`, which keeps lines, tables and
  indentation (~13.8k characters in total, before cleaning).
- Layout mode pads table columns with many spaces; collapse runs of spaces when
  cleaning.
- Every page except the cover starts with the header
  `Empório da Música Manual de Políticas e Procedimentos` and ends with an
  indented footer `Página N` (N = 2–8). Both are stripped.
- Page 1 is a cover (slogan, address, phone, email, version). Its data is
  repeated in section 1.2, so the cover is not needed as a chunk.

### Structure

Top-level sections all start at column 0, matching `^\d{1,2}\.\s+\S`:

1. Sobre a Empório da Música (1.1 Missão, 1.2 Dados da Empresa)
2. Horário de Funcionamento
3. Formas de Pagamento (3.1 Regras de Parcelamento)
4. Política de Trocas e Devoluções (4.1–4.4)
5. Política de Frete e Entregas (5.1–5.3)
6. Promoções e Descontos (6.1, 6.2)
7. Atendimento via WhatsApp (7.1–7.3)
8. Garantia (8.1–8.3)
9. Privacidade e Proteção de Dados
10. Disposições Finais

**(new) Splitting trap:** section 7.2 contains a numbered list
(`1. Saudação` … `5. Fechamento`), and its item `3. Consulta:` starts page 7.
These items are **indented** in layout mode, so a regex anchored at column 0
does not match them. Splitting is also validated to produce exactly sections
1–10 in order.

### Key rules (confirmed)

- **Hours (2):** Mon–Fri 09:00–18:00, Sat 09:00–13:00, closed on Sundays and
  holidays. Hours may be extended on special dates. WhatsApp follows the same
  hours, with automatic replies outside them.
- **Payments (3, 3.1):** PIX 5% off the list price; debit; credit up to 12x
  interest-free; boleto (clears in up to 3 business days). Tiers: up to 3x,
  4x–6x (min. installment R$ 80), 7x–12x (min. R$ 100). Combining methods is
  allowed for purchases **above** R$ 2,000.00.
- **Returns (4):** regret (online purchases), 7 calendar days after **receipt**,
  refund in up to 10 business days, return shipping paid by the store. Defect:
  30 calendar days after **purchase**; after that, warranty with the
  manufacturer, which the store can mediate. Preference exchange: 7 days, subject
  to availability. Ineligible items: customized/setup, "venda final" clearance,
  wind-instrument mouthpieces.
- **Shipping (5):** Campo Grande metro area, free above R$ 500, otherwise
  R$ 35, 1–3 business days by the store's own motorbike courier. Other cities:
  PAC 5–12, SEDEX 2–5, Jadlog 3–8 business days, price by CEP/weight/size,
  large instruments (acoustic drums, digital pianos, double basses) may need a
  special quote. Tracking format: `BR` + 9 characters + `BR`.
- **Promotions (6.2):** not cumulative; no PIX discount on promotional prices;
  no rain check; always show the original price and the discount %.
- **Service (7.1–7.3):** tone informal but professional; tell customers when
  staff will be back outside business hours; never state prices, stock or
  delivery times without checking the system; redirect accessory requests
  (strings, cables, picks, pedals, amplifiers, cases); special situations; 24
  business-hour response for complaints.
- **Warranty (8):** 90-day legal warranty from receipt, plus the manufacturer's
  (6 months to 2 years, varies).
- **Privacy (9):** LGPD (Lei 13.709/2018); data is used only for orders,
  communication, consented marketing and legal duties.

### Inconsistencies → `POLICY_CORRECTIONS`

| Issue | Where | Resolution |
|---|---|---|
| WhatsApp `(67) 3321-4500` vs. `(67) 3341-4444` | 7 vs. cover + 1.2 | Use `(67) 3341-4444` (appears twice, including the official company data table, labeled "Telefone / WhatsApp"). |
| Email `contato@empóriodamusica.com.br` (accented domain, invalid) | 1.2 | Use `contato@emporiodamusica.com.br`, as on the cover. |
| Credit table "min. installment R$ 100" vs. tiered rules | 3 vs. 3.1 | 3.1 is authoritative (more specific); the table only states the 12x limit. |
| "Up to 3x: no minimum installment (except below R$ 50.00)" | 3.1 | Read as a minimum installment of R$ 50.00 for 1x–3x. |

### Other ambiguities **(new)**

| Issue | Where | Resolution |
|---|---|---|
| "Free above R$ 500" and "R$ 35 below R$ 500": exactly R$ 500.00 is not covered | 5.1 | No tool computes shipping; the agent quotes the rule as written. Assumption: R$ 500.00 pays the R$ 35 fee ("above" is strict). |
| Defect after 30 days: "go to the manufacturer" vs. 90-day legal warranty from receipt | 4.2 vs. 8.1 | Both are shown: after 30 days the exchange path ends, but the legal warranty (90 days from receipt) and the manufacturer warranty still apply, with the store able to mediate. |
| Preference exchange "up to 7 days" without a start date | 4.3 | Not computed by any tool; the agent says "7 days" as written. Assumption: counted from receipt, like the regret right. |
| Holidays: "closed on holidays", but no holiday list | 2 | Not modeled. Opening hours use the weekday only; documented as a limitation. |
| Store hours may be "extended on special dates" | 2 | Not modeled; the agent quotes the regular hours. |
