# 1xBet India: Endpoint List

## Base Domain
- `https://1-x-bet-india.com`

## Auth Login
| Method | Endpoint | Fungsi |
|--------|----------|--------|
| POST | `/web-api/user/auth` | Login (base64 uLogin/uPassword + comp_d) → 200 `application/vnd.api+json` |

**URL:** `https://1-x-bet-india.com/web-api/user/auth`
**Request Headers:**
```
content-type: application/json
accept: application/vnd.api+json
x-hd: <fingerprint>
x-svc-source: __WELCOME_APP__
x-app-n: __WELCOME_APP__
```
**Request Body:**
```json
{
  "uLogin": "<base64-login>",
  "uPassword": "<base64-password>",
  "comp_d": "<long fingerprint>",
  "b4odk323": "..."
}
// uLogin=base64(<LOGIN>), uPassword=base64(<PASSWORD>)
```
**Response 200:**
```json
{"success":true,"type":35,"user":{"id":<USER_ID>,"country":"<COUNTRY>","country_id":72},"token":"<JWT>"}
```
**Cookies:** `authenticated=<USER_ID>`, `access_token=<JWT>`, `platform_type`, `lng`, `che_g`, `fatman_uuid`
**localStorage:** `fp_d.token`, `__fatman_ab_tests`, `fp_d.comp_d`

## Account & Auth (requires auth cookie)
| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/account-api/user/balance` | Cek balance user |
| GET | `/account-api/office/user-config` | Config user office |
| GET | `/token-auth/v1/sessions?count=1&type=0` | Session auth |
| GET | `/web-api/officeapi/getaccountdata` | Data akun |
| GET | `/web-api/api/web/user/v1/settings` | Settings user |
| GET | `/web-api/officeapi/getLeftMenuData` | Menu office |
| POST | `/web-api/officeapi/gethistorypaymentmainaccount` | Riwayat payment |

## Config & BFF
| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/bff-api/config/group/get?groups=...&lang=en&d=1-x-bet-india.com&g=ID&p=413` | Config BFF grup (b.core,d.core,d.customize, dll) |
| GET | `/bff-api/config/licenses.json?lang=en&d=1-x-bet-india.com&g=ID&p=413` | Licensi |
| GET | `/bff-api/config/video.json?d=1-x-bet-india.com&g=ID&p=413&m=0` | Video config |
| GET | `/bff-api/event-logo/v2/suitable.json?lang=en&d=1-x-bet-india.com&g=ID&p=413` | Event logos |
| GET | `/bff-api/config/v2/contacts.json?lang=en&country=72&isVipUser=false&d=1-x-bet-india.com&g=ID&p=413` | Kontak |
| GET | `/analytics-module-api/v1/analytics?projectId=413&domain=1-x-bet-india.com` | Analytics |

## Live Feed & Betting
| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/service-api/main-live-feed/v3/games1x2?cfView=3&count=20&fcountry=72&gr=413&grMode=4&lng=en&ref=71` | Game list live |
| GET | `/service-api/main-line-feed/v3/games1x2?cfView=3&count=20&fcountry=72&gr=413&grMode=4&lng=en&ref=71` | Game list line |
| GET | `/service-api/main-live-feed/v3/topGamesByStat?cfView=3&fcountry=72&gr=413&lng=en&ref=71&sportIds=66` | Top games by stat |
| GET | `/service-api/main-live-feed/v3/topChamps?fcountry=72&gr=413&lng=en&ref=71` | Top championship |
| GET | `/service-api/main-live-feed/v3/leftMenuSports?fcountry=72&gr=413&lng=en&ref=71` | Menu sport |
| GET | `/service-api/main-live-feed/v3/expressDay?cfView=3&fcountry=72&gr=413&lng=en&ref=71` | Express day |
| GET | `/service-api/main-live-feed/v3/betsOnFavoriteEvents?cfView=3&fcountry=72&gr=413&lng=en&ref=71` | Bet favorit |
| GET | `/service-api/gamespreview/getbanner?whence=55&ref=71&gr=413&lng=en&fCountry=72` | Banner game |
| GET | `/service-api/gamespreview/GetGamesPreviewLight?whence=55&lng=en&ref=71&gr=413&fcountry=72&includeCategories=true` | Preview games |
| GET | `/service-api/webmessage/v2/Web/GetMessages?supportedTypes=1146815&tz=7&timeDesc=true&lng=en` | Web message |
| GET | `/service-api/accountService/PromoSettings?countryId=72&currencyId=147` | Promo settings |

## Office Apps (lazy-loaded route components)
| Method | Endpoint |
|--------|----------|
| GET | `/sys-office-app-front/{lng}/office/account` |
| GET | `/sys-welcome-app-front/{lng}/office/account` |
| GET | `/sys-games-app-front/{lng}` |
| GET | `/sys-payment-client-front/{lng}/office/account` |
| GET | `/sys-loyalty-program-app-front/{lng}` |
| GET | `/sys-banners-client-front/{lng}` |
| GET | `/sys-platform-apps-front/{lng}` |
| GET | `/sys-nuxt-third-party-front/{lng}` |
| GET | `/flexreg-api/v1/registration/form/widget?projectId=413&country=id&language=en` |

## Games Service
| Method | Endpoint |
|--------|----------|
| GET | `/games-app-public-service/translations/version` |
| GET | `/games-app-public-service/service-api/games-preview/GetGamesPreviewLight?language=en&whence=55&top=15` |

## Bonuses
| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/web-api/api/v3/bonuses/welcome-bonuses` | Welcome bonus |
| GET | `/web-api/api/v3/bonuses/first-deposit` | First deposit bonus |
| HEAD | `/bonus-api/page/loyalty/loyalty-program/exist?language=en&country=id` | Loyalty exist → [404] |

## Analytics & A/B Testing
| Method | Endpoint | Fungsi |
|--------|----------|--------|
| POST | `/fatman-api/{id}/event.json` | A/B test events |
| POST | `/fatman-api/{id}/ab.json` | A/B test config |
| POST | `/analytics.google.com/g/collect` | GA4 collect |
| POST | `/ad.doubleclick.net/activity` | DoubleClick tracking |

## Decor & UI
| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/decor-api/v1/decor` | Decor config |
| GET | `/event-logos-api/v1/event-logos?lng=en` | Event logos |
| GET | `/paysystems/api/v3/payment-client/` | Payment methods |
| GET | `/web-api/api/third-party/banner-for-header` | Header banner |

## OAuth / Social
| Method | Endpoint |
|--------|----------|
| GET | `/social-api/oauth/google-one-tap/clientId?refId=71&projectId=413` |
| GET | `accounts.google.com/gsi/status` (Google SSO) |

## CDN Assets
| Method | Endpoint |
|--------|----------|
| GET | `v3.traincdn.com/version.json` | CDN version |
| GET | `v3.traincdn.com/sys-icons/{version}/285/{name}.svg` | SVG icons (common, logos, country, sports, status) |
| GET | `v3.traincdn.com/genfiles/web-app-v2/dictionary2/v3_{module}/en/dictionary_{hash}.json` | i18n dictionaries |
| GET | `v3.traincdn.com/genfiles/cms/betstemplates/bets_model_short_en_{id}.json` | Bet templates |

### Dictionary Modules
- `v3_main`, `v3_auth`, `v3_office`, `v3_game`, `v3_coupon`, `v3_bonuses`, `v3_registration`, `v3_forgot_password`, `v3_reset_password`, `v3_header`, `v3_favorites`, `v3_top_events`, `v3_responsible_gaming`, `v3_payments`, `v3_cyber`, `v3_widget_consultant`, `v3_marketing_modules`, `v3_statistic_game`, `v3_support_multi_button`, `v3_home_showcase`, `v3_identification`, `v3_identification_modal`, `v3_popup`, `v3_express_day`, `v3_mini_games_sette_e_mezzo`, `v3_support_call_back`, `v3_desktop_app`, `v3_mobile_app`, `v3_on_pay_app`, `v3_datepicker`, `v3_main`, `xgames`

## Widgets
| Method | Endpoint |
|--------|----------|
| GET | `widget.suphelper.top/api/env` |
| GET | `widget.suphelper.top/api/country` |
| GET | `widget.suphelper.top/cdn/widget/sounds/new-message.mp3` |

## Legacy / Mobile
| Method | Endpoint |
|--------|----------|
| POST | `/platform-apps-legacy-api/mobile` |

## SEO
| Method | Endpoint |
|--------|----------|
| GET | `/frontend-api/seo/seodata?language=en&domain=1-x-bet-india.com&path=/office/account&name=office_account&params=...&project=...` |

## Login Flow Selectors (verified)
1. Open modal: `browser_find text="Log in"` → `browser_click ref` (header button)
2. Switch tab: klik `<span class="ui-caption--size-m ui-caption">By email / ID</span>` di `#modals-container .auth-form-extended`
3. Fill: `input#username[name="username"]` → `<LOGIN>`, `input#username-password[type="password"]` → `<PASSWORD>` via `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set` + `input`/`change` events
4. Submit: `Array.from(dlg.querySelectorAll('button')).find(b=>b.textContent.trim()==='Log in').click()` di `#modals-container` → `POST /web-api/user/auth`
5. Verify: `My account` visible, saldo tampil, `authenticated` cookie, `access_token` JWT, `localStorage fp_d.token`

```
Tab By email / ID : span.ui-caption--size-m.ui-caption (text: "By email / ID")
Input username    : input#username, input[name="username"]
Input password    : input#username-password, input[type="password"]
Button Log in     : #modals-container button:has(span:text("Log in"))
Modal container   : #modals-container .auth-form-extended
```
