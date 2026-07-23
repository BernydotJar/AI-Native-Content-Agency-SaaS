# Research notes

## X

- App credentials identify the developer application.
- User-context authorization is required to create a post for an account.
- The create-post API is `POST /2/tweets`.
- OAuth 2.0 Authorization Code with PKCE and OAuth 1.0a user context are official options.

Primary references:

- https://docs.x.com/fundamentals/authentication/guides/v2-authentication-mapping
- https://docs.x.com/x-api/posts/create-post
- https://docs.x.com/x-api/getting-started/pricing

## Instagram

- Publishing is limited to Instagram Professional accounts.
- Instagram Login uses `instagram_business_basic` and
  `instagram_business_content_publish` for account/content access.
- Content publishing creates a media container and then publishes it.

Primary references:

- https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api
- https://www.postman.com/meta/instagram/request/ss8k7b2/create-a-reel-container
- https://www.postman.com/meta/instagram/request/lc4lbyq/publish-the-container
