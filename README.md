# ms1-identity
microservice 1(Sally) - Identity & Account

## Completed Work ✅

### Microservice Deployment Architecture [ms1-identity]
**Identity & Accounts Service (Sally)**

**Deployment:** Cloud Run (Containerized)

**Database:** Cloud SQL (MySQL)

**Infrastructure:**
- Cloud Run service with automatic scaling
- Service account with Cloud SQL Client role for secure database access
- Environment variables configured for Cloud SQL connection
- CORS middleware configured for web UI access

**APIs Implemented:**

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

**OAuth2/OIDC Authentication (Google):**

7. **Google OAuth2 Login:** `GET /auth/google/login`
   - Initiates Google OAuth2/OIDC login flow
   - Redirects to Google authentication page
   - Supports OpenID Connect (OIDC) protocol

9. **OAuth2 Callback:** `GET /auth/google/callback`
   - Handles Google OAuth2/OIDC callback
   - Validates `state` parameter (CSRF protection)
   - Retrieves user information from Google
   - Creates or updates user in database
   - Links Google account to existing user by email if `google_id` not found
   - Redirects to frontend homepage after successful authentication

10. **Get Current User:** `GET /auth/me`
    - Retrieves current authenticated user information
    - Proxies JWT verification to separate JWT service
    - Falls back to session-based authentication for testing

11. **Verify JWT Token:** `POST /auth/verify-jwt`
    - Proxies JWT token verification to separate JWT service
    - Used by other microservices to validate user tokens
    - Returns user information if token is valid

12. **Logout:** `POST /auth/logout`
    - Clears session cookies
    - Returns success message

**OAuth2/OIDC Features:**
- ✅ OpenID Connect (OIDC) protocol implementation
- ✅ Google OAuth2 integration for Columbia LionMail authentication
- ✅ CSRF protection via `state` parameter
- ✅ Session management with secure cookies (same_site="none" for Cloud Run, https_only=True)
- ✅ Automatic user creation/update from Google profile information
- ✅ Email-based account linking (links Google account to existing user by email)
- ✅ JWT service integration (delegates token generation to separate microservice)

**RESTful Features:**
- ✅ ETag support for optimistic locking and caching
- ✅ HATEOAS (Hypermedia as the Engine of Application State) with `_links` in all responses
- ✅ Relative paths (`/users/{uni}/profile`) following RESTful best practices
- ✅ Proper HTTP status codes (201 Created, 304 Not Modified, 412 Precondition Failed, 428 Precondition Required)
- ✅ Location header for created resources

## OAuth2/OIDC Setup Instructions

### 1. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create a project
3. Navigate to **APIs & Services** > **Credentials**
4. Click **Create Credentials** > **OAuth client ID**
5. Select Application type: **Web application**
6. Add the following to Authorized redirect URIs:
   - Local: `http://localhost:8080/auth/google/callback`
   - Production: `https://your-domain.com/auth/google/callback`
7. Copy Client ID and Client Secret

### 2. Environment Variables

Add the following variables to `.env` file:

```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
JWT_SERVICE_URL=http://localhost:8001  # JWT microservice URL (optional)
```

### 3. Database Migration

The `google_id` field has been added to the User model. Recreate the database or run migrations.

### 4. Usage

1. **Start Login:**
   ```
   GET /auth/google/login
   ```
   Visiting this endpoint in a browser will redirect to Google login page.

2. **Callback Handling:**
   After Google authentication, it automatically redirects to `/auth/google/callback`, creates/updates the user in the database, and redirects to the frontend homepage.

3. **Get User Info with JWT Token:**
   ```
   GET /auth/me
   Authorization: Bearer <jwt-token-from-other-service>
   ```
   Validates JWT token from another microservice and returns user information

5. **Verify JWT Token:**
   ```
   POST /auth/verify-jwt
   {
     "token": "<jwt-token>"
   }
   ```
   Proxies token verification request to JWT service
