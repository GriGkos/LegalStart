# Supabase PostgreSQL CA

Public root certificate distributed by Supabase for its PostgreSQL endpoints.
Source: https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt
Documentation: https://supabase.com/docs/guides/platform/ssl-enforcement
Downloaded: 2026-10-07. Expires: 2031-04-26.
SHA-256 (file): `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`

This is a public CA certificate, not a token, password or private key.
`storage.py` adds it only for Supabase PostgreSQL hostnames. TLS chain and
hostname verification remain enabled. Runtime downloads are unnecessary.

## MAX API — Russian Trusted Root CA

Public root certificate from the Ministry of Digital Development and Communications.
Source: https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt
Portal: https://www.gosuslugi.ru/crt
MAX requirement: https://dev.max.ru/docs-api
Downloaded: 2026-10-07. Expires: 2032-02-27 21:04:15 UTC.
SHA-256 (DER fingerprint):
`d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31`

`max_bot.py` loads this certificate only in its dedicated MAX API client's TLS
context. It is not installed in the operating system and does not change
Telegram or PostgreSQL trust settings. TLS verification remains enabled.
