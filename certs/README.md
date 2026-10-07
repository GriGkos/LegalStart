# Supabase PostgreSQL CA

Public root certificate distributed by Supabase for its PostgreSQL endpoints.
Source: https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt
Documentation: https://supabase.com/docs/guides/platform/ssl-enforcement
Downloaded: 2026-10-07. Expires: 2031-04-26.
SHA-256 (file): `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`

This is a public CA certificate, not a token, password or private key.
`storage.py` adds it only for Supabase PostgreSQL hostnames. TLS chain and
hostname verification remain enabled. Runtime downloads are unnecessary.
