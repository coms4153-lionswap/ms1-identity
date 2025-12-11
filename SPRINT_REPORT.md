# Identity & Accounts Service (Sally)

**Owns:** Users

**Responsibilities:** Columbia LionMail OAuth2/OIDC, User Profile Management

**Deployment:** Cloud Run (Containerized)

**Swagger URL:** https://ms1-identity-157498364441.us-east1.run.app/swagger

**Database:** Cloud SQL (MySQL)

## Infrastructure:

- Containerized using Docker with multi-stage builds
- Cloud Run service with automatic scaling
- Service account with Cloud SQL Client role for secure database access
- Environment variables configured for Cloud SQL connection
- CORS middleware configured for web UI access
- Session middleware for OAuth2/OIDC authentication (CSRF protection)

## APIs Implemented:

### User Management APIs:

1. **List Users:** `GET /users`
   - Returns all users with HATEOAS links
   - Each user includes `_links` for navigation

2. **Create User:** `POST /users`
   - Returns `201 Created` with `Location` header
   - Includes HATEOAS links in response body
   - Required fields: `uni`, `student_name`, `email`

3. **Get User by ID:** `GET /users/by-id/{user_id}`
   - Returns user information by `user_id` (integer)
   - Supports ETag with `If-None-Match` header (returns `304 Not Modified`)
   - Returns ETag header for caching
   - Includes HATEOAS links

4. **Get User by Email:** `GET /users/by-email/{email}`
   - Returns `user_id` only for the user with the given email address
   - Validates email format (only accepts valid email addresses)
   - Returns `400 Bad Request` for invalid email format
   - Returns `404 Not Found` if user doesn't exist
   - Example: `GET /users/by-email/user@example.com` → `{"user_id": 123}`

5. **Get User by UNI:** `GET /users/{uni}`
   - Returns user information by `uni` (string identifier)
   - Supports ETag with `If-None-Match` header (returns `304 Not Modified`)
   - Returns ETag header for caching
   - Includes HATEOAS links

6. **Replace User:** `PUT /users/{uni}`
   - Validates `If-Match` header (returns `412 Precondition Failed` if mismatch)
   - Returns `428 Precondition Required` if `If-Match` header missing
   - Updates ETag on modification
   - Includes HATEOAS links
   - Allowed fields: `student_name`, `dept_name`, `phone`

7. **Delete User:** `DELETE /users/{uni}`
   - Returns `200 OK` with success message

8. **Get User Profile (Relative Path):** `GET /users/{uni}/profile`
   - Demonstrates HATEOAS relative paths
   - Returns subset of user data (profile information)
   - Supports ETag with `If-None-Match` header
   - Includes HATEOAS links

### OAuth2/OIDC Authentication APIs:

9. **Google OAuth2/OIDC Login:** `GET /auth/google/login`
   - Initiates Google OAuth2/OIDC login flow
   - Redirects to Google authentication page
   - Implements OpenID Connect (OIDC) protocol
   - Uses `state` parameter for CSRF protection
   - Scope: `openid email profile`

10. **OAuth2 Callback:** `GET /auth/google/callback`
   - Handles Google's OAuth2/OIDC callback
   - Validates `state` parameter (CSRF protection)
   - Retrieves user information from Google
   - Creates or updates user in database
   - Links Google account to existing user by email if `google_id` not found
   - Returns user information (delegates JWT generation to separate JWT service)

11. **Get Current User:** `GET /auth/me`
    - Retrieves current authenticated user information
    - Proxies JWT verification to separate JWT service
    - Falls back to session-based authentication for testing

12. **Verify JWT Token:** `POST /auth/verify-jwt`
    - Proxies JWT token verification to separate JWT service
    - Used by other microservices to validate user tokens
    - Returns user information if token is valid

13. **Logout:** `POST /auth/logout`
    - Clears session cookies
    - Returns success message

## RESTful Features:

- **ETag support** for optimistic locking and caching
- **HATEOAS** (Hypermedia as the Engine of Application State) with `_links` in all responses
- **Relative paths** (`/users/{uni}/profile`) following RESTful best practices
- **Proper HTTP status codes** (201 Created, 304 Not Modified, 412 Precondition Failed, 428 Precondition Required)
- **Location header** for created resources

## OAuth2/OIDC Features:

- **OpenID Connect (OIDC)** protocol implementation
- **Google OAuth2** integration for Columbia LionMail authentication
- **CSRF protection** via `state` parameter
- **Session management** with secure cookies (same_site="none" for Cloud Run, https_only=True)
- **Automatic user creation/update** from Google profile information
- **Email-based account linking** (links Google account to existing user by email)
- **JWT service integration** (delegates token generation to separate microservice)

## Database Schema:

**Users Table:**
- `user_id` (INT UNSIGNED, PRIMARY KEY, AUTO_INCREMENT)
- `uni` (VARCHAR(32), NOT NULL) - Unique identifier
- `student_name` (VARCHAR(120), NOT NULL)
- `dept_name` (VARCHAR(120))
- `email` (VARCHAR(255), NOT NULL)
- `phone` (VARCHAR(32))
- `avatar_url` (VARCHAR(512))
- `credibility_score` (DECIMAL(4, 2), NOT NULL, DEFAULT 0.00)
- `last_seen_at` (TIMESTAMP) - Used for ETag generation
- `google_id` (VARCHAR(255), UNIQUE, NULLABLE) - Google OAuth ID for account linking

## Inter-Service Integration:

- **Logical Foreign Key Constraints:** Other microservices reference `user_id` from Identity service
- **JWT Service Integration:** Delegates JWT token generation and verification to separate microservice
- **User Validation:** Other services can validate user existence via:
  - `GET /users/by-id/{user_id}` - Get user by integer ID
  - `GET /users/{uni}` - Get user by UNI string
  - `GET /users/by-email/{email}` - Get user_id by email address

