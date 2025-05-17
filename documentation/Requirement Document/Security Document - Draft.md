**Document: Security Document \- Knowledge Card System**

Version: 0.2  
Date: 2025-04-21  
Status: Draft (Updated)  
**1\. Introduction & Goals**

* **1.1 Overview:** This document outlines the security requirements, principles, potential threats, and mitigation strategies for the Web-Based Knowledge Card System. Security is a primary concern, especially considering user authentication and the storage of potentially sensitive personal or organizational knowledge.  
* **1.2 Goals:**  
  * **Confidentiality:** Protect user data (credentials, card content, personal information) from unauthorized access.  
  * **Integrity:** Ensure data is accurate and cannot be modified by unauthorized parties or through system vulnerabilities.  
  * **Availability:** Ensure the application is available to authorized users when needed (primarily addressed by infrastructure design and NFRs, but security incidents can impact availability).  
* **1.3 Security Principles:**  
  * **Defense in Depth:** Employ multiple layers of security controls.  
  * **Principle of Least Privilege:** Grant users and system components only the permissions necessary to perform their functions.  
  * **Secure Defaults:** Configure components and features securely by default.  
  * **Fail Securely:** Ensure failures do not leave the system in an insecure state.  
  * **Don't Trust User Input:** Validate and sanitize all input from users or external systems.

**2\. Scope**

* This document covers the security aspects of the web application, including:  
  * Frontend (Next.js/React/Chakra UI)  
  * Backend API (Next.js API Routes)  
  * Database (PostgreSQL with Prisma)  
  * Authentication/Authorization (NextAuth.js)  
  * File Storage (Local for Stage 1, AWS S3 for Stage 2\)  
  * Background Job Processing (BullMQ/Redis for Stage 2\)  
  * Cloud Infrastructure (AWS for Stage 2\)  
  * Third-party integrations (e.g., OpenAI API, Social Login Providers)

**3\. Key Security Requirements & Mitigations**

* **3.1 Authentication:**  
  * **Requirement:** Securely verify user identities. Prevent credential stuffing, brute-force attacks. Secure session management.  
  * **Mitigation:**  
    * Use **NextAuth.js** for managing authentication flows (Credentials, Google/GitHub providers planned).  
    * Store passwords securely using **bcrypt** hashing (as implemented, see TDD/Code).  
    * Implement rate limiting on login endpoints (e.g., using next-auth callbacks or middleware).  
    * Use secure, HTTP-only cookies for session tokens (managed by NextAuth.js).  
    * Enforce defined password policy (**min 6 chars, 1 upper, 1 lower, 1 number, 1 special char**) via UI feedback and backend validation.  
    * Secure handling of OAuth tokens and secrets for social logins (managed by NextAuth.js).  
* **3.2 Authorization:**  
  * **Requirement:** Ensure users can only access and modify their own data (cards, folders, tags) unless sharing features are explicitly implemented later. Prevent privilege escalation.  
  * **Mitigation:**  
    * Implement strict ownership checks in all API endpoints handling data access/modification (e.g., ensure card.userId \=== session.user.id before allowing reads/updates/deletes). Prisma middleware or service-layer checks can help enforce this consistently.  
    * Use NextAuth.js getSession/getServerSession to reliably identify the authenticated user making the request.  
    * Apply Principle of Least Privilege for any potential future roles (e.g., admin).  
* **3.3 Data Protection:**  
  * **Requirement:** Protect data at rest and in transit. Prevent sensitive data exposure.  
  * **Mitigation:**  
    * **In Transit:** Enforce **HTTPS** for all communication between the client, server, and external APIs. Use Strict-Transport-Security (HSTS) header.  
    * **At Rest (Stage 1 \- Local):** Filesystem permissions on the local machine. PostgreSQL data directory permissions. *Note: Limited protection.*  
    * **At Rest (Stage 2 \- Cloud):**  
      * Enable encryption at rest for **AWS RDS (PostgreSQL)** instances.  
      * Enable encryption at rest for **AWS S3** buckets (Server-Side Encryption, e.g., SSE-S3 or SSE-KMS).  
      * Enable encryption at rest for **AWS ElastiCache (Redis)** if storing sensitive temporary data (consider if needed).  
      * Securely manage database credentials, API keys (OpenAI), and NextAuth.js secrets using a secrets manager (e.g., AWS Secrets Manager, Doppler, or environment variables with restricted access). **Do not commit secrets to Git.**  
    * Avoid storing sensitive information unnecessarily (e.g., raw API keys in database).  
    * Sanitize data returned by APIs to avoid exposing internal IDs or excessive user information.  
* **3.4 Input Validation & Sanitization:**  
  * **Requirement:** Prevent injection attacks (SQL Injection, Cross-Site Scripting \- XSS) by validating and sanitizing all external input.  
  * **Mitigation:**  
    * Use **Prisma** ORM for database interactions; it generally prevents SQL injection by using parameterized queries. Avoid raw SQL queries where possible; if necessary, ensure proper parameterization.  
    * Validate all API input data types, formats, lengths, and ranges (e.g., using libraries like Zod). Reject invalid input early.  
    * Sanitize output before rendering it in the HTML DOM to prevent Stored/Reflected XSS.  
      * React inherently helps by escaping content rendered directly in JSX.  
      * **Crucially:** For rendering block editor JSON content (ADR-004), **do not** use dangerouslySetInnerHTML. Map JSON blocks to safe React components, ensuring any user-provided text within blocks is treated as text, not HTML. Sanitize any URLs or attributes within the JSON content.  
      * Use libraries like dompurify if absolutely necessary to render user-generated HTML fragments (should be avoided with block editor).  
* **3.5 Session Management:**  
  * **Requirement:** Protect session identifiers from hijacking or fixation. Ensure secure session lifecycle.  
  * **Mitigation:**  
    * Rely on **NextAuth.js** for robust session management (secure cookie flags, session expiration, token rotation where applicable).  
    * Implement secure logout functionality (invalidate session on server and client).  
* **3.6 Cross-Site Request Forgery (CSRF):**  
  * **Requirement:** Prevent attackers from tricking authenticated users into performing unwanted actions.  
  * **Mitigation:**  
    * **NextAuth.js** provides built-in CSRF protection using the double-submit cookie method for relevant actions (e.g., form submissions handled via its providers).  
    * For custom API routes performing state-changing operations (POST, PUT, DELETE), ensure appropriate CSRF protection mechanisms are in place if not automatically handled by NextAuth.js (e.g., verify custom header, use synchronizer token pattern if needed – though NextAuth.js often covers this).  
* **3.7 Security Headers:**  
  * **Requirement:** Use HTTP security headers to instruct browsers to enable security features.  
  * **Mitigation:**  
    * Configure Next.js (or edge middleware/reverse proxy) to send headers like:  
      * Strict-Transport-Security (HSTS): Enforce HTTPS.  
      * Content-Security-Policy (CSP): Define allowed sources for scripts, styles, images, etc., to mitigate XSS. Requires careful configuration.  
      * X-Content-Type-Options: nosniff: Prevent MIME-sniffing.  
      * X-Frame-Options: DENY or SAMEORIGIN: Prevent clickjacking.  
      * Referrer-Policy: strict-origin-when-cross-origin or same-origin: Control referrer information leakage.  
* **3.8 Dependency Management:**  
  * **Requirement:** Avoid using third-party libraries with known vulnerabilities.  
  * **Mitigation:**  
    * Regularly scan dependencies for known vulnerabilities using tools like npm audit, GitHub Dependabot, or Snyk.  
    * Keep dependencies updated, prioritizing security patches.  
    * Minimize the number of dependencies; vet new dependencies carefully.  
* **3.9 Error Handling & Logging:**  
  * **Requirement:** Avoid leaking sensitive information (stack traces, internal paths) in error messages to users. Log relevant security events.  
  * **Mitigation:**  
    * Implement generic error messages for users in production.  
    * Log detailed error information (including stack traces) securely on the server-side for debugging.  
    * Log key security events (e.g., login success/failure, significant data changes, authorization failures) to aid in monitoring and incident response. Use structured logging. Integrate with a logging service (e.g., AWS CloudWatch Logs) in Stage 2\.

**4\. Threat Model (Simplified \- Examples based on OWASP Top 10\)**

* **A01: Broken Access Control:** Unauthorized users accessing/modifying others' cards. *Mitigation: Strict ownership checks in API (3.2).*  
* **A02: Cryptographic Failures:** Exposure of passwords or sensitive data. *Mitigation: bcrypt hashing, HTTPS, encryption at rest (3.1, 3.3).*  
* **A03: Injection:** SQL Injection, potentially XSS via JSON content. *Mitigation: Prisma ORM, input validation, careful JSON rendering (3.4).*  
* **A04: Insecure Design:** (Broad category) e.g., lack of rate limiting, insecure file uploads. *Mitigation: Rate limiting (3.1), secure S3 uploads (TDD/Stage 2).*  
* **A05: Security Misconfiguration:** Missing security headers, default credentials, verbose errors. *Mitigation: Secure defaults, security headers (3.7), proper error handling (3.9), secure cloud config (Stage 2).*  
* **A06: Vulnerable and Outdated Components:** Using libraries with known exploits. *Mitigation: Dependency scanning/updates (3.8).*  
* **A07: Identification and Authentication Failures:** Weak passwords, session hijacking. *Mitigation: NextAuth.js, bcrypt, secure session cookies, strong password enforcement (3.1, 3.5).*  
* **A08: Software and Data Integrity Failures:** Modifying data without authorization (related to A01), insecure updates/dependencies. *Mitigation: Authorization checks (3.2), dependency management (3.8).*  
* **A09: Security Logging and Monitoring Failures:** Inability to detect or respond to attacks. *Mitigation: Security event logging (3.9), monitoring setup (Stage 2).*  
* **A10: Server-Side Request Forgery (SSRF):** (Less likely initially, but possible if app fetches external resources based on user input). *Mitigation: Validate and sanitize any user-provided URLs used for server-side requests.*

**5\. Cloud Security (Stage 2 \- AWS Specifics)**

* **IAM:** Apply Principle of Least Privilege for all IAM users, roles, and policies. Use specific roles for services (e.g., ECS tasks, Lambda functions). Avoid using root account.  
* **VPC & Networking:** Use private subnets for backend resources (DB, Redis). Use Security Groups to restrict traffic between resources (e.g., only allow application server SG to access DB SG on the PostgreSQL port). Use Network ACLs as an additional layer if needed.  
* **S3 Bucket Policies:** Configure restrictive bucket policies and ACLs. Consider blocking public access by default. Use pre-signed URLs for controlled uploads/downloads.  
* **Secrets Management:** Use AWS Secrets Manager or Parameter Store for database credentials, API keys, etc.  
* **Monitoring & Logging:** Utilize CloudTrail for API activity logging, CloudWatch Logs for application/system logs, GuardDuty for threat detection. Configure alerts for suspicious activity.

**6\. Open Questions / Future Considerations**

* Need for formal penetration testing (Recommended before major public launch).  
* Specific requirements for compliance standards (e.g., GDPR, CCPA) if handling PII extensively. *(Decision: None required for now).*  
* Detailed Incident Response Plan.  
* Security implications of planned AI features (e.g., prompt injection, data privacy with external APIs).

**Questions for PM/Stakeholders:**

1. **Password Policy:** *Decision Made:* Enforce minimum 6 characters, including at least one uppercase letter, one lowercase letter, one number, and one special character.  
2. **Data Classification:** *Decision Made:* No highly sensitive data (e.g., PII beyond user profile, financial, health info) is expected for the initial versions. Re-evaluate if product direction changes.  
3. **Compliance:** *Decision Made:* No specific compliance frameworks (GDPR, HIPAA, etc.) are required for the initial versions. Re-evaluate if target audience or data scope changes.

**TL Recommendations & Alternatives:**

1. **Penetration Testing:** Strongly recommend budgeting for external penetration testing before a wide public launch (Stage 2).  
2. **Dependency Scanning:** Integrate automated dependency scanning (e.g., Dependabot, Snyk) into the CI/CD pipeline early.  
3. **CSP Header:** Start with a basic Content Security Policy and refine it; implementing a strict CSP can be complex but offers significant XSS protection.

**Draft Rating:**

* **Completion:** 80% (Covers key web application security areas, PM questions answered. Needs refinement based on specific feature implementations. Cloud security section is high-level).  
* **Quality/Accuracy:** High (Based on standard security practices and OWASP guidelines relevant to the tech stack).  
* **Collaboration Needed:** Review updated requirements and mitigations, discuss need for formal pentesting, refine threat model as features evolve.