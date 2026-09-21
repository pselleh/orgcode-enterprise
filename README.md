# CBA OrgCode Enterprise

Version: 1.1.1
Target: Tutor 22 / Open edX Verawood

This Tutor/Open edX extension converts an organization code entered during
registration into a durable learner access grant. The code adds designated
private catalog products to the learner's access; it never removes access to
public courses or programs.

## Security and data flow

1. The learner enters an organization code during registration.
2. After the account is authenticated, the registration client submits the code
   once to `POST /api/orgcode/v1/redeem/`.
3. The LMS matches a salted password hash. Plaintext codes are never stored.
4. Redemption creates or reactivates an enterprise learner profile,
   organization membership, durable access grant, discount entitlement,
   validity dates, and permitted product access through the policy.
5. Wagtail obtains the learner's grants from `GET /api/orgcode/v1/access/` and
   combines those private products with every public Discovery listing.
6. Checkout/enrollment calls `POST /api/orgcode/v1/authorize/` immediately
   before issuing private access.

The non-secret `AccessPolicy.key` must exactly match Discovery's
`access_policy_key`. Discovery never stores organization codes.

## API

All endpoints require an authenticated learner. Rate limits are configured by
the Tutor plugin.

### Redeem at registration

```http
POST /api/orgcode/v1/redeem/
Content-Type: application/json

{"code": "EXAMPLE-2027"}
```

The response never echoes the submitted code.

### Obtain effective catalog grants

```http
GET /api/orgcode/v1/access/
```

The response always includes `public_catalog_access: true`, followed by active
organization grants, permitted product identifiers, discount, and dates.

### Reauthorize a private product

```http
POST /api/orgcode/v1/authorize/
Content-Type: application/json

{
  "access_policy_key": "cba-restricted-risk-intelligence-2027",
  "product_type": "course",
  "product_key": "course-v1:CBA+ETR211+2027"
}
```

Public products do not require this endpoint. Program-only labs must be reached
through an authorized certificate-program enrollment and must not be listed as
standalone products.

## Installation checks

After rebuilding the Open edX image with the Tutor plugin:

```bash
tutor local exec lms ./manage.py lms migrate orgcode_enterprise
tutor local exec lms ./manage.py lms check
tutor local exec lms ./manage.py lms showmigrations orgcode_enterprise
```

Migration `0004` adds the access-grant schema on top of the repaired production
identity migration. Migration `0005` hashes every legacy plaintext code and
creates grants for existing code usages and matching learner-profile codes.
Migration `0006` removes plaintext codes and legacy single-product columns only
after conversion checks pass.
