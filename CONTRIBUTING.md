# Contributing

Thanks for helping improve global financial-AI discovery.

## Report a missed or incorrect case

Use the repository Issue forms and provide, whenever possible:

- the product or institution name;
- what happened: launch, pilot, go-live, contract or scaled rollout;
- the real event date and its precision;
- at least one public evidence URL;
- why the case is financially relevant;
- whether the current result is a miss, false positive, duplicate, wrong stage or wrong summary.

## Add a source

Small source additions belong in `config/sources.json`. New source types should implement a focused adapter in `src/openfinai_radar/fetchers.py`, fail independently, use a descriptive user agent, and include fixture-based tests. Do not add scraping that bypasses access controls or publisher restrictions.

## Development checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m openfinai_radar run --days 3
```

Pull requests should explain the expected recall or precision improvement and any new legal, rate-limit or maintenance risk.

