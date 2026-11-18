# Price Monitoring: a Python project

A small working project: it crawls an online store catalog, keeps a history of snapshots, compares the last two
and builds an Excel report plus a short Telegram summary.

**Live demo page:** https://skayman777-svg.github.io/price-monitoring/

**Tested on a mock store.** The TechnoHome store is fictional; it runs on your machine together with the project
(`mock_shop/`). No real websites were scraped, products and prices are made up.

## Quick start

```bash
pip install -r requirements.txt
python run.py
```

What happens: the mock store starts, snapshot #1 is taken, the store changes prices, stock and assortment,
snapshot #2 is taken, then comparison, report and summary. At the end a failure check runs: a section is down,
the snapshot is marked incomplete and excluded from comparison.

Output goes to `out/`: `price_report.xlsx` (report), `prices.db` (snapshot history, SQLite), `run.log` (log).

Tests (31 checks, no external libraries): `python -m unittest discover -s tests -t .`

## Test run results

| Metric | Value |
|---|---|
| Products in snapshot #1 / #2 | 36 / 37 |
| Pages crawled per snapshot | 7 (4 sections, duplicates across sections removed by SKU) |
| Price down / price up | 11 / 3 |
| New / removed products | 3 / 2 |
| Back in stock / out of stock | 3 / 3 |
| Parser warnings | 1 (card without a price, product saved with a note) |

A temporary 503 on one page: the parser retried and got the page. A whole section down: the snapshot is saved as
incomplete, and no report is built on incomplete data.

## How to connect your own site

1. Copy `config.json`, set `base_url` and the catalog sections.
2. Adjust the selectors in `monitor/parse.py` to the site markup: card, title, price, old price, stock,
   “next page” link.
3. Run on a schedule (cron or Windows Task Scheduler):
   `python -m monitor run --config my.json --db out/prices.db --out out/report.xlsx`

The first run takes snapshot #1; from the second run on there is something to compare. Exit code `1` means an
incomplete snapshot (handy for failure alerts). Separate commands: `crawl` (snapshot only) and `report` (report only).
Sending the summary to Telegram: the `--send` flag and the `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` environment variables.

## Features

- Polite crawling: an honest `User-Agent` (no spoofing), `robots.txt` (`Disallow` and `Crawl-delay`), delays between
  requests, timeouts, retries with logging.
- Parsing of real-world markup: non-breaking spaces in prices, “from $89”, “Price on request”, strikethrough prices,
  cards without a price; banners and recommendation blocks with prices are not picked up.
- SQLite storage, money stored in minor units (no rounding errors).
- False alarm protection: if a section failed to load, the catalog is empty, or the product count dropped by more than
  half, the snapshot is excluded from comparison.
- Comparison: price down and up, new, removed, back in stock, out of stock.
- Excel report: summary with a chart, list of changes with colors and filters, full price list.
- Messenger summary with a threshold on the price change percentage.

## Limitations

- Tested only on the mock store. Every real site needs its selectors tuned and checked.
- If prices are loaded by JavaScript, scraping goes through a browser (Playwright) or an official API or export.
  That is a separate estimate.
- The project does not bypass anti-bot protection (captchas, Cloudflare and the like). Before working with someone
  else’s site, check its terms of use and `robots.txt`; where an official API or feed exists, use it.
- Telegram sending is implemented but has not been run against a real bot.
- The report contains values, not formulas, so it opens the same way in any spreadsheet app.

## Structure

```
run.py             end-to-end test run
config.json        site, sections, delays, alert threshold
monitor/           fetch, parse, crawl, store (SQLite),
                   diff (comparison), report (Excel), notify (summary), cli
mock_shop/         the fictional TechnoHome store used for testing
tests/             unittest: parser, comparison, end-to-end run
```
