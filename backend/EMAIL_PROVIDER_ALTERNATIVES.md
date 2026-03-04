# Email Provider Alternatives (Replace SendGrid)

If you are having issues with `SENDGRID_API_KEY`, you can switch the backend to `EMAIL_SERVICE=smtp` and use any provider that supports SMTP relay.

## Current backend support
- `EMAIL_SERVICE=sendgrid` (API)
- `EMAIL_SERVICE=resend` (API)
- `EMAIL_SERVICE=smtp` (SMTP relay)
- `EMAIL_SERVICE=mock` (dev/testing only)

## Direct Resend API mode
If you have a Resend API key (starts with `re_...`), you can use direct API mode:

```env
EMAIL_SERVICE=resend
RESEND_API_KEY=<your_resend_api_key>
EMAIL_FROM=no-reply@yourdomain.com
EMAIL_FROM_NAME=CryptoVault
```

## Recommended replacements

### 1) Resend (Recommended for modern DX)
Use SMTP relay mode in this backend.
- SMTP host: `smtp.resend.com`
- SMTP port: `587` (STARTTLS)
- Username: `resend`
- Password: your Resend SMTP key

### 2) Postmark
- SMTP host: `smtp.postmarkapp.com`
- SMTP port: `587`
- Username: Postmark server token
- Password: Postmark server token

### 3) Mailgun
- SMTP host: `smtp.mailgun.org`
- SMTP port: `587`
- Username: Mailgun SMTP login
- Password: Mailgun SMTP password

### 4) Brevo (Sendinblue)
- SMTP host: `smtp-relay.brevo.com`
- SMTP port: `587`
- Username: Brevo SMTP login
- Password: Brevo SMTP key

### 5) AWS SES SMTP
- SMTP host: region-specific (e.g. `email-smtp.us-east-1.amazonaws.com`)
- SMTP port: `587`
- Username: SES SMTP username
- Password: SES SMTP password

## Environment variables to switch to SMTP

```env
EMAIL_SERVICE=smtp
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=<your_smtp_password>
SMTP_USE_TLS=true
SMTP_USE_SSL=false
EMAIL_FROM=no-reply@yourdomain.com
EMAIL_FROM_NAME=CryptoVault
```

## Production notes
- Verify your sending domain (SPF + DKIM + DMARC).
- Keep `EMAIL_SERVICE=mock` **disabled** in production.
- Use `/api/monitoring/health/detailed` to confirm email mode/provider after deployment.
