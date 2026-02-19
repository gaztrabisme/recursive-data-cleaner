# Eval Report: Qwen3-Coder-Next-MLX-4bit

**Score: 43/76 (56.6%)**

## By Issue Type

| Issue Type | Passed | Total | Score |
|------------|--------|-------|-------|
| amount_format | 6 | 6 | 100.0% |
| category_case | 3 | 8 | 37.5% |
| date_format | 9 | 9 | 100.0% |
| email_case | 4 | 4 | 100.0% |
| enum_typo | 7 | 8 | 87.5% |
| html_cleanup | 5 | 7 | 71.4% |
| null_empty | 3 | 6 | 50.0% |
| phone_format | 1 | 8 | 12.5% |
| tag_format | 1 | 6 | 16.7% |
| weight_unit | 3 | 7 | 42.9% |
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
| phone | 1 | 8 | 12.5% |
| status | 7 | 8 | 87.5% |
| tags | 1 | 6 | 16.7% |
| weight | 3 | 7 | 42.9% |

## Failures

- **Record 1.phone** (phone_format): expected `+14155551234`, got `(415) 555-1234`
- **Record 2.phone** (phone_format): expected `+14155551234`, got `4155551234`
- **Record 3.phone** (phone_format): expected `+14155551234`, got `415-555-1234`
- **Record 4.phone** (phone_format): expected `+442079460958`, got `+44 20 7946 0958`
- **Record 6.phone** (phone_format): expected `+12125556789`, got `(212) 555-6789`
- **Record 7.phone** (phone_format): expected `+12125556789`, got `2125556789`
- **Record 11.phone** (phone_format): expected `+16505553333`, got `(650) 555-3333`
- **Record 9.status** (enum_typo): expected `active`, got `acitve`
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
- **Record 0.weight** (weight_unit): expected `5.20 kg`, got `5.2 kg`
- **Record 3.weight** (weight_unit): expected `5.20 kg`, got `5.2kg`
- **Record 5.weight** (weight_unit): expected `3.10 kg`, got `3.1 kg`
- **Record 7.weight** (weight_unit): expected `22.50 kg`, got `22.5 kg`
- **Record 1.tags** (tag_format): expected `['electronics', 'sale']`, got `electronics, sale`
- **Record 2.tags** (tag_format): expected `['electronics', 'sale']`, got `electronics;sale`
- **Record 5.tags** (tag_format): expected `['clothing', 'corporate']`, got `clothing, corporate`
- **Record 7.tags** (tag_format): expected `['home', 'garden']`, got `home, garden`
- **Record 8.tags** (tag_format): expected `['home', 'garden', 'bulk']`, got `home;garden;bulk`
- **Record 1.notes** (null_empty): expected `None`, got ``
- **Record 3.notes** (null_empty): expected `None`, got `   `
- **Record 6.notes** (null_empty): expected `None`, got ``
