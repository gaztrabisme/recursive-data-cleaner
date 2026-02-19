# Eval Report: Qwen3-4B-Instruct-2507-MLX-8bit

**Score: 58/76 (76.3%)**

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
| weight_unit | 5 | 7 | 71.4% |
| whitespace | 1 | 7 | 14.3% |

## By Field

| Field | Passed | Total | Score |
|-------|--------|-------|-------|
| amount | 6 | 6 | 100.0% |
| category | 3 | 8 | 37.5% |
| date_joined | 9 | 9 | 100.0% |
| description | 5 | 7 | 71.4% |
| email | 4 | 4 | 100.0% |
| name | 1 | 7 | 14.3% |
| notes | 3 | 6 | 50.0% |
| phone | 8 | 8 | 100.0% |
| status | 8 | 8 | 100.0% |
| tags | 6 | 6 | 100.0% |
| weight | 5 | 7 | 71.4% |

## Failures

- **Record 1.category** (category_case): expected `Electronics`, got `electronics`
- **Record 2.category** (category_case): expected `Electronics`, got `ELECTRONICS`
- **Record 3.category** (category_case): expected `Electronics`, got `eLECTRONICS`
- **Record 5.category** (category_case): expected `Clothing`, got `CLOTHING`
- **Record 8.category** (category_case): expected `Home & Garden`, got `HOME & GARDEN`
- **Record 1.description** (html_cleanup): expected `Purchased & returned item`, got `Purchased &amp; returned item`
- **Record 6.description** (html_cleanup): expected `Left for competitor & unlikely to return`, got `Left for competitor &amp; unlikely to return`
- **Record 1.name** (whitespace): expected `Bob Smith`, got `Bob  Smith`
- **Record 2.name** (whitespace): expected `Carol Davis`, got ` Carol Davis`
- **Record 4.name** (whitespace): expected `Eva Martinez`, got `Eva Martinez `
- **Record 5.name** (whitespace): expected `Frank Wilson`, got `Frank  Wilson`
- **Record 7.name** (whitespace): expected `Hannah Brown`, got ` Hannah Brown `
- **Record 9.name** (whitespace): expected `Julia Chen`, got `Julia  Chen`
- **Record 1.weight** (weight_unit): expected `5.22 kg`, got `None`
- **Record 4.weight** (weight_unit): expected `5.22 kg`, got `None`
- **Record 1.notes** (null_empty): expected `None`, got ``
- **Record 3.notes** (null_empty): expected `None`, got `   `
- **Record 6.notes** (null_empty): expected `None`, got ``
