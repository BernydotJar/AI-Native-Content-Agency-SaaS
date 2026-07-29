# `public-error.v1`

Required fields:

- `code`: stable lowercase snake-case identifier;
- `detail`: safe client-facing English sentence fragment;
- `request_id`: validated correlation identifier from `X-Request-ID` or opaque generated value.

Optional field:

- `errors`: validation-only list of `{location: [string|integer], type: string}`.

The response must not include internal exception text or input values. `WWW-Authenticate` and `Retry-After` headers remain available where required. Frontend clients may branch on status/code but must show the request ID for support correlation.
