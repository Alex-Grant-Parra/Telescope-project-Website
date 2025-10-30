The client script(s) for a telescope.
Master repo: https://github.com/Alex-Grant-Parra/Telescope-project-Website

## Upload security

Photo uploads use a persistent HTTP session and automatically fetch a CSRF token from `<server_http_url>/security/csrf-token` when needed. The token is cached briefly and included with uploads via the `X-CSRF-Token` header. If the endpoint is unavailable, uploads still proceed without the header.

