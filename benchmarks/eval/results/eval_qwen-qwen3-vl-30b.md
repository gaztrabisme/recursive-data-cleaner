# Eval Report: qwen-qwen3-vl-30b

**Score: 64/76 (84.2%)**

## By Issue Type

| Issue Type | Passed | Total | Score |
|------------|--------|-------|-------|
| amount_format | 6 | 6 | 100.0% |
| category_case | 3 | 8 | 37.5% |
| date_format | 7 | 9 | 77.8% |
| email_case | 4 | 4 | 100.0% |
| enum_typo | 8 | 8 | 100.0% |
| html_cleanup | 5 | 7 | 71.4% |
| null_empty | 3 | 6 | 50.0% |
| phone_format | 8 | 8 | 100.0% |
| tag_format | 6 | 6 | 100.0% |
| weight_unit | 7 | 7 | 100.0% |
| whitespace | 7 | 7 | 100.0% |

## By Field

| Field | Passed | Total | Score |
|-------|--------|-------|-------|
| amount | 6 | 6 | 100.0% |
| category | 3 | 8 | 37.5% |
| date_joined | 7 | 9 | 77.8% |
| description | 5 | 7 | 71.4% |
| email | 4 | 4 | 100.0% |
| name | 7 | 7 | 100.0% |
| notes | 3 | 6 | 50.0% |
| phone | 8 | 8 | 100.0% |
| status | 8 | 8 | 100.0% |
| tags | 6 | 6 | 100.0% |
| weight | 7 | 7 | 100.0% |

## Failures

- **Record 3.date_joined** (date_format): expected `2024-01-15`, got `1705276800`
- **Record 8.date_joined** (date_format): expected `2024-03-22`, got `1711065600`
- **Record 1.category** (category_case): expected `Electronics`, got `electronics`
- **Record 2.category** (category_case): expected `Electronics`, got `ELECTRONICS`
- **Record 3.category** (category_case): expected `Electronics`, got `eLECTRONICS`
- **Record 5.category** (category_case): expected `Clothing`, got `CLOTHING`
- **Record 8.category** (category_case): expected `Home & Garden`, got `HOME & GARDEN`
- **Record 1.description** (html_cleanup): expected `Purchased & returned item`, got `Purchased &amp; returned item`
- **Record 6.description** (html_cleanup): expected `Left for competitor & unlikely to return`, got `Left for competitor &amp; unlikely to return`
- **Record 1.notes** (null_empty): expected `None`, got ``
- **Record 3.notes** (null_empty): expected `None`, got `   `
- **Record 6.notes** (null_empty): expected `None`, got ``
