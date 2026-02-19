# Eval Report: Qwen3-14B-MLX-8bit

**Score: 47/76 (61.8%)**

## By Issue Type

| Issue Type | Passed | Total | Score |
|------------|--------|-------|-------|
| amount_format | 6 | 6 | 100.0% |
| category_case | 3 | 8 | 37.5% |
| date_format | 8 | 9 | 88.9% |
| email_case | 4 | 4 | 100.0% |
| enum_typo | 2 | 8 | 25.0% |
| html_cleanup | 5 | 7 | 71.4% |
| null_empty | 3 | 6 | 50.0% |
| phone_format | 8 | 8 | 100.0% |
| tag_format | 1 | 6 | 16.7% |
| weight_unit | 0 | 7 | 0.0% |
| whitespace | 7 | 7 | 100.0% |

## By Field

| Field | Passed | Total | Score |
|-------|--------|-------|-------|
| amount | 6 | 6 | 100.0% |
| category | 3 | 8 | 37.5% |
| date_joined | 8 | 9 | 88.9% |
| description | 5 | 7 | 71.4% |
| email | 4 | 4 | 100.0% |
| name | 7 | 7 | 100.0% |
| notes | 3 | 6 | 50.0% |
| phone | 8 | 8 | 100.0% |
| status | 2 | 8 | 25.0% |
| tags | 1 | 6 | 16.7% |
| weight | 0 | 7 | 0.0% |

## Failures

- **Record 4.date_joined** (date_format): expected `2024-01-15`, got `January 15, 2024`
- **Record 1.status** (enum_typo): expected `active`, got `actve`
- **Record 3.status** (enum_typo): expected `active`, got `Active`
- **Record 4.status** (enum_typo): expected `active`, got `ACTIVE`
- **Record 5.status** (enum_typo): expected `pending`, got `pendng`
- **Record 7.status** (enum_typo): expected `churned`, got `chruned`
- **Record 9.status** (enum_typo): expected `active`, got `acitve`
- **Record 1.category** (category_case): expected `Electronics`, got `electronics`
- **Record 2.category** (category_case): expected `Electronics`, got `ELECTRONICS`
- **Record 3.category** (category_case): expected `Electronics`, got `eLECTRONICS`
- **Record 5.category** (category_case): expected `Clothing`, got `CLOTHING`
- **Record 8.category** (category_case): expected `Home & Garden`, got `HOME & GARDEN`
- **Record 1.description** (html_cleanup): expected `Purchased & returned item`, got `Purchased &amp; returned item`
- **Record 6.description** (html_cleanup): expected `Left for competitor & unlikely to return`, got `Left for competitor &amp; unlikely to return`
- **Record 0.weight** (weight_unit): expected `5.20 kg`, got `5.2 kg`
- **Record 1.weight** (weight_unit): expected `5.22 kg`, got `11.5 lbs`
- **Record 2.weight** (weight_unit): expected `5.20 kg`, got `5200 g`
- **Record 3.weight** (weight_unit): expected `5.20 kg`, got `5.2kg`
- **Record 4.weight** (weight_unit): expected `5.22 kg`, got `11.5 lbs.`
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
