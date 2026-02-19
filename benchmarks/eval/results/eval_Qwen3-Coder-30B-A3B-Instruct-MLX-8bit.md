# Eval Report: Qwen3-Coder-30B-A3B-Instruct-MLX-8bit

**Score: 66/76 (86.8%)**

## By Issue Type

| Issue Type | Passed | Total | Score |
|------------|--------|-------|-------|
| amount_format | 6 | 6 | 100.0% |
| category_case | 3 | 8 | 37.5% |
| date_format | 9 | 9 | 100.0% |
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
| date_joined | 9 | 9 | 100.0% |
| description | 5 | 7 | 71.4% |
| email | 4 | 4 | 100.0% |
| name | 7 | 7 | 100.0% |
| notes | 3 | 6 | 50.0% |
| phone | 8 | 8 | 100.0% |
| status | 8 | 8 | 100.0% |
| tags | 6 | 6 | 100.0% |
| weight | 7 | 7 | 100.0% |

## Failures

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
