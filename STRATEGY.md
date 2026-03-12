# STRATEGY.md

This file documents the non-LLM quantitative strategy logic implemented in this repository.

## Scope

- Included:
  - statistical strategy engine in `backend/app/strategies/mean_reversion.py`
  - regression trend strategy in `backend/app/strategies/regression.py`
- Excluded: LLM-guided strategy (`backend/app/strategies/llm_strategy.py`)

## Strategy 1: Mean-Reversion Baseline

### Objective

Detect short-term over/under-pricing in Yes probabilities and issue:

- `buy_yes`
- `buy_no`
- `hold`

### Universe Filter ("Minor Incidents")

An event is eligible only if:

- participant count \(N < 500\)
- Yes probability \(p\) is near 50%:
  \[
  |p - 0.5| < 0.15
  \]

This reduces exposure to crowded/high-attention markets.

### Data Pipeline

1. Fetch event candidates from Gamma.
2. Extract market identifier for CLOB history.
3. Pull price history from CLOB.
4. Clean price points to valid probability domain:
   \[
   p_t \in [0, 1]
   \]
5. If daily candles are too sparse, fallback to hourly candles for evaluation.

### Signal Logic

Parameters:

- Lookback window: \(W = 7\)
- Deviation threshold: \(\theta = 0.10\)

At time \(t\):

\[
\mu_t = \frac{1}{W}\sum_{i=t-W+1}^{t} p_i
\]

\[
d_t = \frac{p_t - \mu_t}{\mu_t}
\]

Decision rule:

- If \(d_t \le -\theta\): `buy_yes`
- If \(d_t \ge \theta\): `buy_no`
- Else: `hold`

### Confidence Function

For directional signals (`buy_yes` / `buy_no`):

\[
c_t = \min(0.95,\ 0.55 + |d_t|)
\]

For `hold`:

\[
c_t = \max(0.35,\ 0.55 - |d_t|)
\]

### Expected Return Estimator

Backtest window: last \(B = 30\) points.

For each index \(i\), compute rolling mean \(\mu_i\) over previous \(W\) points and one-step-ahead return:

- If \(d_i \le -\theta\) (Yes long):
  \[
  r_i^{yes} = \frac{p_{i+1} - p_i}{p_i}
  \]
- If \(d_i \ge \theta\) (No long via complement \(q_i = 1 - p_i\)):
  \[
  r_i^{no} = \frac{q_{i+1} - q_i}{q_i}
  \]

Estimated expected return:

\[
\hat{R} = 100 \cdot \frac{1}{K}\sum_{j=1}^{K} r_j
\]

where \(K\) is number of valid simulated trades. If \(K=0\), return \(0\).

### Output Schema

Per event:

```json
{
  "event_id": "string",
  "signal": "buy_yes | buy_no | hold",
  "confidence": 0.0,
  "expected_return_pct": 0.0,
  "rationale": "string"
}
```

The simulation endpoint also computes:

\[
\text{earnings\_rate\_pct} = \text{confidence} \times \text{expected\_return\_pct}
\]

## Pros and Cons

| Aspect | Pros | Cons |
|---|---|---|
| Interpretability | Fully transparent rules and thresholds. | Fixed thresholds can be regime-dependent. |
| Data requirements | Works with lightweight price history. | Sparse/irregular history can weaken signal quality. |
| Runtime | Fast and deterministic; easy to test. | Limited adaptivity to changing market microstructure. |
| Risk behavior | Minor-incident filter reduces crowding risk. | Filter may miss large opportunities in high-volume events. |
| Implementation complexity | Simple to maintain and debug. | Simplicity may underfit complex market dynamics. |

## Strategy 2: Regression Trend Baseline

### Objective

Fit a short rolling linear trend on Yes probability and trade with the predicted
one-step direction:

- `buy_yes` if predicted price is meaningfully above current price
- `buy_no` if predicted price is meaningfully below current price
- `hold` otherwise

### Universe Filter ("Minor Incidents")

Uses the same universe filter as mean reversion:

- participant count \(N < 500\)
- near-even market:
  \[
  |p - 0.5| < 0.15
  \]

### Data Pipeline

1. Fetch candidate events from Gamma.
2. Resolve CLOB market identifier per event.
3. Pull daily price history, fallback to hourly when sparse.
4. Keep only valid probabilities:
   \[
   p_t \in [0, 1]
   \]

### Signal Logic

Default parameters:

- Lookback window: \(W = 12\)
- Forecast horizon: \(H = 1\)
- Edge threshold: \(\theta = 0.02\)
- Confidence scale: \(s = 4.0\)

For each event, fit OLS on recent window:

\[
\hat{p}_t = \beta_1 t + \beta_0
\]

Forecast:

\[
\tilde{p}_{t+H} = \beta_1 (t+H) + \beta_0
\]

Directional edge:

\[
e_t = \tilde{p}_{t+H} - p_t
\]

Decision rule:

- If \(e_t \ge \theta\): `buy_yes`
- If \(e_t \le -\theta\): `buy_no`
- Else: `hold`

### Confidence Function

For directional signals:

\[
c_t = \min(0.95,\ 0.55 + s \cdot |e_t|)
\]

For `hold`:

\[
c_t = \max(0.35,\ 0.55 - s \cdot |e_t|)
\]

### Expected Return Estimator

Backtest window default: \(B = 60\).

For each index \(i\), use the preceding \(W\) points to fit trend and predict
\(\tilde{p}_{i+1}\), then evaluate realized one-step return:

- If \(e_i \ge \theta\) (Yes long):
  \[
  r_i^{yes} = \frac{p_{i+1} - p_i}{p_i}
  \]
- If \(e_i \le -\theta\) (No long with \(q_i = 1 - p_i\)):
  \[
  r_i^{no} = \frac{q_{i+1} - q_i}{q_i}
  \]

Aggregate:

\[
\hat{R} = 100 \cdot \frac{1}{K}\sum_{j=1}^{K} r_j
\]

where \(K\) is valid simulated trades; if \(K=0\), return \(0\).

### Output Schema

Same output schema as Strategy 1:

```json
{
  "event_id": "string",
  "signal": "buy_yes | buy_no | hold",
  "confidence": 0.0,
  "expected_return_pct": 0.0,
  "rationale": "string"
}
```

### Pros and Cons

| Aspect | Pros | Cons |
|---|---|---|
| Trend sensitivity | Captures directional drift that mean reversion can miss. | Can chase noise in highly mean-reverting markets. |
| Adaptivity | Regression slope updates continuously from latest window. | Linear assumption may underfit nonlinear order-flow dynamics. |
| Interpretability | Coefficients and forecast edge are easy to inspect. | Requires careful threshold tuning across regimes. |
| Runtime | Still lightweight and deterministic. | More floating-point sensitivity than simple threshold rules. |
| Robustness | Hourly fallback improves sparse-history coverage. | Thin markets can still produce unstable slopes. |

## Failure Modes and Practical Notes

- If price history length \(< W+1\): strategy returns `hold` with zero expected return.
- If no valid backtest trades exist: expected return is zero.
- Prices outside \([0,1]\) are discarded.
- Daily history can be too thin; hourly fallback is used for runtime robustness.

## Maintenance Rule for Future Strategies

When adding any new non-LLM strategy:

1. Add a new section in this file with:
   - objective
   - full algorithm definition
   - mathematical notation
   - parameters and defaults
   - output fields
   - pros/cons table row(s)
2. Keep legacy strategy sections intact for comparability/history.
3. Update this file in the same PR as the strategy code and tests.
