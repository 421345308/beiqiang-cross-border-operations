# Authentication and signing

## Local configuration

The credential file is outside the repository:

`C:/Users/spq/.config/beiqiang/alibaba-openapi.json`

Expected keys are `appKey`, `appSecret`, optional `redirectUri`, `accessToken`, `refreshToken`, and expiry timestamps. Never copy its values into this skill or Git.

## Current official endpoints

- Authorization: `https://open-api.alibaba.com/oauth/authorize`
- API server: `https://open-api.alibaba.com`
- Token creation: GOP `POST /rest/auth/token/create`
- Token refresh: GOP `POST /rest/auth/token/refresh`
- Seller business APIs: TOP-compatible `POST /sync?method={api_name}`

Do not use the legacy `oauth.alibaba.com` or `gw.api.taobao.com` endpoints for this application.

## OAuth authorization

Use the exact registered callback URL and these official parameters:

`response_type=code&force_auth=true&redirect_uri={callback}&client_id={appKey}`

The returned code expires in 30 minutes. Exchange it through `/auth/token/create`, save both returned tokens, and always replace the stored refresh token after a refresh response.

Authorization policy depends on the application category. If it is `Allow binding user to authorize`, the seller must first be in APP Console → App Management → Auth Management → Authorized Seller Whitelist. If it is `Allow login users to authorize`, no whitelist is needed.

### `InvalidAppKey` diagnostic

First verify the exact official host is `open-api.alibaba.com` (with the hyphen), then verify the current AppKey/App Secret and whether the application is online. The official error reference lists an offline/nonexistent application or an invalid App Secret as possible causes. Do not conclude that the application registry is unsynchronized until the host, credentials and application state have all been verified.

## GOP token signing

Token APIs use the GOP protocol:

1. Build parameters with `app_key`, millisecond `timestamp`, `sign_method=sha256`, `simplify=true`, and the business parameter (`code` or `refresh_token`).
2. Exclude `sign` and empty values.
3. Sort names by ASCII and concatenate every `name + value`.
4. Prefix the API path, such as `/auth/token/create`.
5. HMAC-SHA256 the UTF-8 string with App Secret and uppercase the hex digest.
6. POST to `https://open-api.alibaba.com/rest{api_path}`.

The local client includes an official-example signature self-test.

## Verified connection baseline

Verified against Beiqiang's live seller application on 2026-09-03:

- OAuth authorization and token exchange succeed on `open-api.alibaba.com`.
- `alibaba.icbu.product.list` succeeds with `language=ENGLISH`, `current_page=1`, and `page_size=1`.
- `alibaba.icbu.photobank.list` succeeds with `extra_context={}`, `location_type=ALL_GROUP`, `current_page=1`, and `page_size=1`.
- `alibaba.icbu.video.query` succeeds with `current_page=1` and `page_size=1`.

These checks prove that the AppKey, App Secret, access token, raw-HTTP signing, and the `access_token` parameter are accepted by the current gateway. They are read-only smoke tests and do not prove that every write API payload is correct.

## TOP-compatible seller API signing

Alibaba.com seller business API documentation uses `Protocol.TOP` on the new API server:

1. For raw HTTP calls, common parameters are `app_key`, millisecond `timestamp`, `method`, `access_token`, `sign_method=sha256`, and `simplify=true`; `format=json` is optional. The official Java SDK may internally expose the token argument as `session`, but the current migrated-API HTTP example names the transmitted parameter `access_token`.
2. Include all non-empty common and business parameters in the signature, excluding `sign` and binary file bytes.
3. Sort by ASCII and concatenate every `name + value`; do not prefix an API path.
4. HMAC-SHA256 with App Secret and uppercase the hex digest.
5. POST business parameters to `https://open-api.alibaba.com/sync?method={api_name}` with signed common parameters in the query string.

For file uploads, sign the text fields but exclude the binary file body. Recompute timestamp and signature for every retry. Never log App Secret or full access/refresh tokens.

## Authorization boundary

Opening the OAuth grant page and approving persistent access is a sensitive authorization action. Obtain action-time confirmation before approval. CAPTCHA always stays with the user unless separately authorized under the active browser policy.

## Primary sources

- Alibaba.com Open Platform overview and seller authorization: https://open.alibaba.com/doc/doc.htm
- Alibaba.com API reference: https://open.alibaba.com/doc/api.htm
- Official Alibaba.com IOP Java SDK 1.3.18 linked from the API reference
