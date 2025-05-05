\# JIRA Epic: KC-INFRA \- Cloud Infrastructure & DevOps (Stage 2 \- GCP)

\*\*Rationale:\*\* Build the scalable, secure, and maintainable cloud environment on \*\*Google Cloud Platform (GCP)\*\* required to host the production application, database, cache, storage, and support CI/CD processes.

\---

\#\# Ticket ID: KC-INFRA-DO-1-GCP

\* \*\*Title:\*\* Setup GCP Project & Foundational IAM Roles/Users  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* Implied by Cloud Deployment  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* GCP Project Confirmed  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Establish the GCP project structure and create initial IAM service accounts/roles with appropriate permissions for infrastructure management (Terraform) and CI/CD pipelines, following security best practices.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* GCP project is accessible.  
    \* An IAM service account exists with permissions (roles) to manage necessary resources via Terraform (e.g., Compute Engine for VPC/Networking, Cloud SQL, Cloud Storage, Artifact Registry, Cloud Run, Memorystore, IAM, Secret Manager, Cloud Logging/Monitoring).  
    \* An IAM service account exists, configured for Workload Identity Federation, with permissions needed by the CI/CD pipeline (e.g., push to Artifact Registry, deploy to Cloud Run, manage secrets).  
    \* Least privilege principle is applied.  
    \* User accounts have appropriate roles assigned.  
    \* Billing alerts are configured.  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Create or designate a GCP Project.  
    \* Secure user accounts with MFA.  
    \* Create dedicated IAM Service Accounts:  
        \* \`terraform-executor-sa\`: Service account used by Terraform. Grant necessary roles (e.g., \`roles/owner\` initially for setup, then refine to specific roles like \`roles/compute.admin\`, \`roles/cloudsql.admin\`, \`roles/storage.admin\`, \`roles/artifactregistry.admin\`, \`roles/run.admin\`, \`roles/redis.admin\`, \`roles/secretmanager.admin\`, \`roles/logging.admin\`, \`roles/monitoring.admin\`, \`roles/iam.serviceAccountUser\`). Download key file securely or use Application Default Credentials (ADC) where possible.  
        \* \`cicd-pipeline-sa\`: Service account for CI/CD (e.g., GitHub Actions). Configure Workload Identity Federation to allow GitHub Actions to impersonate this SA. Grant necessary roles like \`roles/artifactregistry.writer\`, \`roles/run.developer\`, \`roles/secretmanager.secretAccessor\`, \`roles/iam.serviceAccountUser\` (to pass runtime SA to Cloud Run).  
    \* Configure GCP credentials securely for Terraform execution (e.g., using \`gcloud auth application-default login\` or service account key file). Configure Workload Identity Federation for CI/CD.  
    \* Set up basic budget alerts in GCP Billing.  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\* GCP Console (IAM & Admin, Billing). \`gcloud\` CLI.  
\* \*\*Testing Considerations (Technical):\*\* Verify Terraform can authenticate (\`terraform plan\`). Verify CI/CD pipeline can authenticate via Workload Identity Federation and perform necessary actions (e.g., push test image to Artifact Registry).  
\* \*\*Dependencies (Technical):\*\* GCP Project access.

\---

\#\# Ticket ID: KC-INFRA-DO-2-GCP

\* \*\*Title:\*\* Define VPC Network & Networking Structure (Terraform)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* Implied by Cloud Deployment  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* KC-INFRA-DO-1-GCP  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Create the foundational network infrastructure within GCP using Terraform, including a Virtual Private Cloud (VPC) network, subnets, firewall rules, and Cloud NAT for secure and scalable resource placement.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* Terraform code defines a custom \`google\_compute\_network\`.  
    \* Subnets (\`google\_compute\_subnetwork\`) are created in desired regions.  
    \* Firewall rules (\`google\_compute\_firewall\`) are defined to control traffic (allow internal, SSH, HTTPS, etc.).  
    \* Cloud Router (\`google\_compute\_router\`) and Cloud NAT (\`google\_compute\_router\_nat\`) are configured to allow outbound internet access from private resources (e.g., Cloud Run, Cloud SQL).  
    \* Terraform state is managed remotely (e.g., using GCS backend).  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Initialize Terraform project (\`terraform init\`). Configure remote state backend (GCS bucket \- create manually first or via separate minimal Terraform).  
    \* Use Terraform Google Provider.  
    \* Define \`google\_compute\_network\` resource (custom mode recommended: \`auto\_create\_subnetworks=false\`).  
    \* Define \`google\_compute\_subnetwork\` resources in the target region(s). Define IP CIDR ranges. Enable \`private\_ip\_google\_access\` for necessary subnets if needed.  
    \* Define default deny ingress/egress \`google\_compute\_firewall\` rules (priority 65534/65535).  
    \* Define specific \`google\_compute\_firewall\` rules allowing necessary traffic (e.g., SSH from IAP, internal traffic within VPC, HTTPS to Load Balancer). Use network tags for targeting.  
    \* Define \`google\_compute\_router\` in the target region.  
    \* Define \`google\_compute\_router\_nat\` associated with the router, configured for relevant subnets (\`source\_subnetwork\_ip\_ranges\_to\_nat \= "LIST\_OF\_SUBNETWORKS"\` or \`ALL\_SUBNETWORKS\_ALL\_IP\_RANGES\`). Allocate NAT IPs.  
    \* Use Terraform variables for region, CIDR blocks, project ID, environment names.  
    \* Structure Terraform code using modules (e.g., \`modules/vpc\`) for reusability.  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* Terraform configuration files (\`.tf\`)  
    \* Terraform Google Provider resources (\`google\_compute\_network\`, \`google\_compute\_subnetwork\`, \`google\_compute\_firewall\`, \`google\_compute\_router\`, \`google\_compute\_router\_nat\`)  
    \* Terraform state backend configuration (GCS).  
\* \*\*Testing Considerations (Technical):\*\* Run \`terraform plan\` and \`terraform apply\`. Verify network resources in GCP console. Verify connectivity rules (e.g., test outbound connection from a VM in a private subnet via NAT).  
\* \*\*Dependencies (Technical):\*\* KC-INFRA-DO-1-GCP (Permissions), Terraform installed.

\---

\#\# Ticket ID: KC-INFRA-DO-13-GCP (Generated)

\* \*\*Title:\*\* Configure Firewall Rules (Terraform)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* NFR-SEC-1 (Implied)  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* KC-INFRA-DO-2-GCP (VPC/Subnets defined)  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Define network security rules using GCP Firewall Rules via Terraform to control ingress and egress traffic for application components (Load Balancer, Cloud Run, Cloud SQL, Memorystore).  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* Terraform code defines necessary \`google\_compute\_firewall\` resources.  
    \* Firewall rule allows ingress HTTP/HTTPS traffic (ports 80/443) from the internet (0.0.0.0/0) to the Load Balancer (using target tags or service accounts).  
    \* Firewall rule allows ingress traffic from the Load Balancer's health check ranges to Cloud Run instances (using target tags).  
    \* Firewall rule allows ingress traffic from Cloud Run service account/network tag to Cloud SQL (Private IP) on the PostgreSQL port (5432).  
    \* Firewall rule allows ingress traffic from Cloud Run service account/network tag to Memorystore (Private IP) on the Redis port (6379).  
    \* Firewall rules follow the principle of least privilege.  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Define \`google\_compute\_firewall\` resources in Terraform.  
    \* Use \`allow\` blocks specifying protocol and ports.  
    \* Use \`source\_ranges\` for IP-based rules (e.g., \`0.0.0.0/0\` for LB ingress, Google health check ranges).  
    \* Use \`target\_tags\` or \`target\_service\_accounts\` to apply rules to specific resources (Load Balancer forwarding rules, Cloud Run instances, potentially VMs if used).  
    \* Use \`source\_tags\` or \`source\_service\_accounts\` for internal traffic rules (e.g., Cloud Run SA accessing Cloud SQL SA/Tag).  
    \* Example Rules (Conceptual \- specific implementation depends on targetting strategy):  
        \* \`fw-allow-http-https\`: Allow TCP 80, 443 from \`0.0.0.0/0\` to \`lb-tag\`.  
        \* \`fw-allow-health-checks\`: Allow TCP 80/other port from Google health check ranges (\`130.211.0.0/22\`, \`35.191.0.0/16\`) to \`app-tag\`.  
        \* \`fw-allow-app-to-sql\`: Allow TCP 5432 from \`app-tag\`/\`app-sa\` to \`sql-tag\`/\`sql-sa\`.  
        \* \`fw-allow-app-to-redis\`: Allow TCP 6379 from \`app-tag\`/\`app-sa\` to \`redis-tag\`/\`redis-sa\`.  
    \* Assign network tags or use service accounts for resources (Cloud Run service, Cloud SQL instance) in their respective Terraform configurations.  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* Terraform configuration files (\`.tf\`)  
    \* \`google\_compute\_firewall\` resources.  
\* \*\*Testing Considerations (Technical):\*\* Run \`terraform plan/apply\`. Verify firewall rules in GCP console. Verify connectivity between resources after deployment (e.g., app connects to DB). Use GCP Connectivity Tests if needed.  
\* \*\*Dependencies (Technical):\*\* KC-INFRA-DO-2-GCP

\---

\#\# Ticket ID: KC-INFRA-DO-3-GCP

\* \*\*Title:\*\* Create Production Dockerfile (Multi-stage)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* Implied by Container Deployment (Cloud Run)  
\* \*\*Team:\*\* BE/DO  
\* \*\*Dependencies (Functional):\*\* KC-SETUP-1 (Next.js project)  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Create an optimized, multi-stage Dockerfile for building the Next.js application container image suitable for production deployment on GCP Cloud Run.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* A \`Dockerfile\` exists at the project root.  
    \* Uses multi-stage builds to minimize final image size.  
    \* Installs dependencies, builds the Next.js application, and copies only necessary artifacts to the final stage.  
    \* Runs the application using a non-root user for security.  
    \* Listens on the port specified by the \`PORT\` environment variable (provided by Cloud Run, typically 8080).  
    \* Includes health check instruction (optional, Cloud Run has its own startup/liveness probes).  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Create \`Dockerfile\`.  
    \* \*\*Stage 1: Dependencies\*\*  
        \`\`\`dockerfile  
        FROM node:18-alpine AS deps  
        WORKDIR /app  
        COPY package.json yarn.lock\* package-lock.json\* ./  
        \# Use ci for consistency, or install if preferred  
        RUN yarn install \--frozen-lockfile \# Or npm ci  
        \`\`\`  
    \* \*\*Stage 2: Builder\*\*  
        \`\`\`dockerfile  
        FROM node:18-alpine AS builder  
        WORKDIR /app  
        COPY \--from=deps /app/node\_modules ./node\_modules  
        COPY . .  
        ENV NODE\_ENV production  
        \# Set build-time env vars if needed (e.g., NEXT\_PUBLIC\_...)  
        RUN yarn build \# Or npm run build  
        \`\`\`  
    \* \*\*Stage 3: Runner (Final Image)\*\*  
        \`\`\`dockerfile  
        FROM node:18-alpine AS runner  
        WORKDIR /app  
        ENV NODE\_ENV production  
        \# PORT env var will be provided by Cloud Run, default 8080  
        \# Create non-root user  
        RUN addgroup \--system \--gid 1001 nodejs && \\  
            adduser \--system \--uid 1001 nextjs

        \# Copy necessary artifacts from builder stage (standalone output)  
        COPY \--from=builder /app/public ./public  
        \# Ensure standalone output is enabled in next.config.js  
        COPY \--from=builder \--chown=nextjs:nodejs /app/.next/standalone ./  
        COPY \--from=builder \--chown=nextjs:nodejs /app/.next/static ./.next/static

        USER nextjs

        \# Expose the port Cloud Run expects (usually 8080\)  
        \# This is informational; Cloud Run uses the PORT env var.  
        EXPOSE 8080

        \# Healthcheck (Optional \- Cloud Run uses probes)  
        \# HEALTHCHECK \--interval=30s \--timeout=5s \--start-period=15s \--retries=3 \\  
        \#   CMD wget \--quiet \--tries=1 \--spider http://localhost:${PORT:-8080}/api/health || exit 1

        \# Run the standalone server  
        CMD \["node", "server.js"\]  
        \`\`\`  
    \* Add \`.dockerignore\` file (node\_modules, .git, .env, etc.).  
    \* Ensure \`next.config.js\` has \`output: 'standalone'\` enabled.  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* \`Dockerfile\`  
    \* \`.dockerignore\`  
    \* \`next.config.js\` (output: 'standalone')  
\* \*\*Testing Considerations (Technical):\*\* Build the Docker image locally (\`docker build .\`). Run the container locally, passing \`-e PORT=8080\` (\`docker run \-p 8080:8080 \-e PORT=8080 ...\`) and verify the application starts and responds on port 8080\. Check image size.  
\* \*\*Dependencies (Technical):\*\* KC-SETUP-1, Docker installed.

\---

\#\# Ticket ID: KC-INFRA-DO-4-GCP

\* \*\*Title:\*\* Setup Artifact Registry Repository (Terraform)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* Implied by Container Deployment  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* KC-INFRA-DO-1-GCP  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Create a private Artifact Registry repository in GCP using Terraform to store the production Docker images built by the CI/CD pipeline.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* A \`google\_artifact\_registry\_repository\` exists in the target GCP region.  
    \* The repository format is \`DOCKER\`.  
    \* The repository is private.  
    \* Vulnerability scanning is enabled (recommended).  
    \* CI/CD pipeline service account (\`cicd-pipeline-sa\`) has permissions (\`roles/artifactregistry.writer\`) to push images.  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Use Terraform Google Provider.  
    \* Define \`google\_artifact\_registry\_repository\` resource:  
        \`\`\`terraform  
        resource "google\_artifact\_registry\_repository" "app" {  
          provider      \= google-beta \# Often needed for latest features  
          location      \= var.region  
          repository\_id \= "knowledge-card-app" \# Or use var.app\_name  
          description   \= "Docker repository for Knowledge Card app"  
          format        \= "DOCKER"

          \# Enable vulnerability scanning (optional)  
          \# cleanup\_policy\_dry\_run \= false \# Set to false to enable cleanup policies  
          \# cleanup\_policies { ... } \# Define cleanup policies if desired

          labels \= {  
            environment \= var.environment \# e.g., "production"  
            project     \= "KnowledgeCard"  
          }  
        }  
        \`\`\`  
    \* Ensure the CI/CD service account (\`cicd-pipeline-sa\`) has the \`roles/artifactregistry.writer\` role granted (can be done via \`google\_project\_iam\_member\` or \`google\_artifact\_registry\_repository\_iam\_member\`).  
    \* Update CI/CD pipeline (KC-INFRA-DO-11-GCP) to authenticate to Artifact Registry, build, tag, and push the Docker image using the repository URL (e.g., \`REGION-docker.pkg.dev/PROJECT\_ID/REPOSITORY\_ID/IMAGE\_NAME\`).  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* Terraform configuration files (\`.tf\`)  
    \* \`google\_artifact\_registry\_repository\`.  
    \* IAM configuration for the CI/CD service account.  
    \* CI/CD pipeline configuration.  
\* \*\*Testing Considerations (Technical):\*\* Run \`terraform plan/apply\`. Verify repository creation in GCP console. Manually push a test image (\`docker push ...\`) or verify CI/CD pipeline can push successfully. Check vulnerability scanning results if enabled.  
\* \*\*Dependencies (Technical):\*\* KC-INFRA-DO-1-GCP

\---

\#\# Ticket ID: KC-INFRA-DO-5-GCP

\* \*\*Title:\*\* Setup Cloud SQL PostgreSQL Instance (Terraform, enable pgvector)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* TC-STACK-3 (PostgreSQL), Vector DB Choice (pgvector)  
\* \*\*Team:\*\* DO/DBA  
\* \*\*Dependencies (Functional):\*\* KC-INFRA-DO-2-GCP (VPC Network), KC-INFRA-DO-13-GCP (Firewall Rules), KC-INFRA-DO-10-GCP (Secrets)  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Provision a managed Cloud SQL instance running PostgreSQL using Terraform, configured for high availability, backups, private IP, and with the pgvector extension enabled.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* Terraform code defines a \`google\_sql\_database\_instance\` resource for PostgreSQL.  
    \* Instance is configured for High Availability (HA).  
    \* Instance uses Private IP within the specified VPC network.  
    \* Appropriate machine type is chosen (start small, e.g., \`db-f1-micro\` or \`db-g1-small\`).  
    \* Automated backups are enabled.  
    \* Database root password is managed via Secret Manager (KC-INFRA-DO-10-GCP).  
    \* Firewall rules allow access only from the application's network tag/service account (KC-INFRA-DO-13-GCP).  
    \* The \`pgvector\` extension is available/enabled on the database instance.  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Use Terraform Google Provider.  
    \* Ensure necessary APIs are enabled (\`sqladmin.googleapis.com\`, \`servicenetworking.googleapis.com\`).  
    \* Configure Private Service Access (\`google\_compute\_global\_address\`, \`google\_service\_networking\_connection\`).  
    \* Define \`google\_sql\_database\_instance\` resource:  
        \`\`\`terraform  
        resource "google\_sql\_database\_instance" "main" {  
          name             \= "knowledge-card-db-${var.environment}"  
          database\_version \= "POSTGRES\_15" \# Verify pgvector support  
          region           \= var.region  
          settings {  
            tier \= var.db\_machine\_type \# e.g., "db-g1-small"  
            availability\_type \= "REGIONAL" \# For HA  
            ip\_configuration {  
              ipv4\_enabled    \= false \# Disable public IP  
              private\_network \= google\_compute\_network.main.id  
              \# allocated\_ip\_range \= google\_compute\_global\_address.private\_ip\_address.name \# Optional: if using specific allocated range  
            }  
            backup\_configuration {  
              enabled \= true  
              \# point\_in\_time\_recovery\_enabled \= true \# Recommended  
            }  
            \# Add database flags if needed for pgvector (check Cloud SQL docs)  
            \# database\_flags {  
            \#   name  \= "cloudsql.extensions"  
            \#   value \= "pgvector" \# Example, confirm correct flag/method  
            \# }  
          }  
          \# Use secret manager for root password  
          root\_password \= data.google\_secret\_manager\_secret\_version.db\_root\_password.secret\_data \# Assumes secret version data source  
          deletion\_protection \= true \# For production  
        }  
        resource "google\_sql\_database" "app\_db" {  
           instance \= google\_sql\_database\_instance.main.name  
           name     \= "knowledge\_cards"  
        }  
        resource "google\_sql\_user" "app\_user" {  
           instance \= google\_sql\_database\_instance.main.name  
           name     \= "app\_user" \# Or read from secret  
           password \= data.google\_secret\_manager\_secret\_version.db\_app\_password.secret\_data \# Separate app user password  
        }  
        \`\`\`  
    \* Define \`google\_secret\_manager\_secret\` and \`google\_secret\_manager\_secret\_version\` for the root password and potentially an application user password.  
    \* \*\*Enabling pgvector:\*\* Check Cloud SQL documentation for enabling extensions. It might involve setting a database flag or running \`CREATE EXTENSION\` after provisioning.  
    \* \*\*Post-Provisioning/Migration:\*\* Ensure the command \`CREATE EXTENSION IF NOT EXISTS vector;\` is run against the provisioned database (e.g., \`knowledge\_cards\`). Recommended approach: Add this command to a new Prisma migration file (\`prisma/migrations/.../migration.sql\`) and run \`prisma migrate deploy\` as part of your deployment process (Needs addressing in CI/CD).  
    \* Ensure the \`DATABASE\_URL\` used by the application points to the Cloud SQL Private IP and uses the correct application user credentials from Secret Manager.  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A (Provisions infrastructure for defined schema)  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* Terraform configuration files (\`.tf\`)  
    \* \`google\_sql\_database\_instance\`, \`google\_sql\_database\`, \`google\_sql\_user\`, \`google\_compute\_global\_address\`, \`google\_service\_networking\_connection\`.  
    \* GCP Secret Manager integration.  
    \* Prisma migration workflow (to ensure pgvector extension exists).  
\* \*\*Testing Considerations (Technical):\*\* Run \`terraform plan/apply\`. Verify instance creation in GCP console. Connect to the DB using \`gcloud sql connect\` or a DB client via Cloud SQL Proxy. Run \`\\dx\` to check for \`vector\` extension. Verify application can connect using Private IP and credentials. Test backups/restore.  
\* \*\*Dependencies (Technical):\*\* KC-INFRA-DO-2-GCP, KC-INFRA-DO-13-GCP, KC-INFRA-DO-10-GCP

\---

\#\# Ticket ID: KC-INFRA-DO-6-GCP

\* \*\*Title:\*\* Setup Memorystore Redis Instance (Terraform)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* Background Job Choice (BullMQ/Redis)  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* KC-INFRA-DO-2-GCP (VPC Network), KC-INFRA-DO-13-GCP (Firewall Rules)  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Provision a managed Memorystore instance running Redis using Terraform for use as a cache and BullMQ backend, accessible via Private IP.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* Terraform code defines a \`google\_redis\_instance\` resource.  
    \* Instance is placed within the specified VPC network using Private Service Access.  
    \* Appropriate tier/size is chosen (start small, e.g., \`BASIC\` tier, \`M1\` capacity).  
    \* Firewall rules allow access only from the application's network tag/service account (KC-INFRA-DO-13-GCP).  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Use Terraform Google Provider.  
    \* Ensure necessary APIs are enabled (\`redis.googleapis.com\`, \`servicenetworking.googleapis.com\`).  
    \* Ensure Private Service Access is configured (KC-INFRA-DO-5-GCP).  
    \* Define \`google\_redis\_instance\` resource:  
        \`\`\`terraform  
        resource "google\_redis\_instance" "cache" {  
          name           \= "knowledge-card-redis-${var.environment}"  
          tier           \= "BASIC" \# Or STANDARD\_HA  
          memory\_size\_gb \= 1  
          location\_id    \= var.region \# Or specific zone if BASIC tier  
          authorized\_network \= google\_compute\_network.main.id  
          redis\_version  \= "REDIS\_7\_0" \# Choose appropriate version  
          \# transit\_encryption\_mode \= "SERVER\_AUTHENTICATION" \# Recommended if supported/needed  
        }  
        \`\`\`  
    \* Ensure application configuration includes the Redis instance host IP (\`google\_redis\_instance.cache.host\`) and port (\`google\_redis\_instance.cache.port\`) (read from env var).  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* Terraform configuration files (\`.tf\`)  
    \* \`google\_redis\_instance\`.  
\* \*\*Testing Considerations (Technical):\*\* Run \`terraform plan/apply\`. Verify instance creation in GCP console. Verify application can connect to Redis using the private IP and port. Test basic cache set/get or BullMQ connection.  
\* \*\*Dependencies (Technical):\*\* KC-INFRA-DO-2-GCP, KC-INFRA-DO-13-GCP

\---

\#\# Ticket ID: KC-INFRA-DO-7-GCP

\* \*\*Title:\*\* Setup Cloud Storage Bucket (Terraform)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* FR-STORAGE-1 (Cloud File Storage)  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* KC-INFRA-DO-1-GCP  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Provision a Cloud Storage bucket using Terraform for storing user-uploaded media files. Configure appropriate access controls and lifecycle rules.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* Terraform code defines a \`google\_storage\_bucket\` resource.  
    \* Bucket enforces uniform bucket-level access.  
    \* Bucket is private by default (no public access granted via IAM).  
    \* IAM permissions (\`roles/storage.objectCreator\`, \`roles/storage.objectViewer\`) allow the application's runtime service account to write and read objects.  
    \* CORS configuration is set up if direct browser uploads (using signed URLs) are planned.  
    \* Optional: Lifecycle rules for managing old/unused objects.  
    \* Optional: Versioning enabled.  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Use Terraform Google Provider.  
    \* Define \`google\_storage\_bucket\` resource:  
        \`\`\`terraform  
        resource "google\_storage\_bucket" "storage" {  
          name          \= "${var.project\_id}-knowledge-card-uploads-${var.environment}" \# Globally unique name  
          location      \= var.region  
          storage\_class \= "STANDARD"  
          uniform\_bucket\_level\_access \= true  
          \# versioning { enabled \= true } \# Optional  
          \# lifecycle\_rule { ... } \# Optional  
          \# cors { ... } \# Optional, for signed URL uploads  
        }  
        \`\`\`  
    \* Define \`google\_storage\_bucket\_iam\_member\` resources to grant the application's runtime service account (used by Cloud Run) necessary roles (\`roles/storage.objectCreator\`, \`roles/storage.objectViewer\`) on the bucket.  
    \* Ensure application configuration includes the bucket name (read from env var).  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* Terraform configuration files (\`.tf\`)  
    \* \`google\_storage\_bucket\`, \`google\_storage\_bucket\_iam\_member\`.  
    \* IAM Policy for Cloud Run Service Account.  
\* \*\*Testing Considerations (Technical):\*\* Run \`terraform plan/apply\`. Verify bucket creation and settings in GCP console. Test uploading/downloading files from the application running in Cloud Run (requires app changes from KC-STORAGE epic). Test signed URL generation and upload if applicable.  
\* \*\*Dependencies (Technical):\*\* KC-INFRA-DO-1-GCP

\---

\#\# Ticket ID: KC-INFRA-DO-10-GCP

\* \*\*Title:\*\* Setup Secrets Management (GCP Secret Manager, Terraform)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* NFR-SEC-1 (Implied)  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* KC-INFRA-DO-1-GCP  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Set up GCP Secret Manager using Terraform to securely store and manage sensitive information like database credentials and third-party API keys required by the application.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* Terraform code defines \`google\_secret\_manager\_secret\` resources for required secrets (e.g., DB credentials, NextAuth secret, AI service keys).  
    \* Secrets contain the necessary values (e.g., username, password, host, port, dbname for DB creds).  
    \* IAM policies (\`roles/secretmanager.secretAccessor\`) grant the application's runtime service account permission to access specific secrets.  
    \* Secrets are populated initially (manually or via Terraform \`google\_secret\_manager\_secret\_version\`).  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Use Terraform Google Provider.  
    \* Define \`google\_secret\_manager\_secret\` resource for each secret needed. Use appropriate naming convention (e.g., \`knowledge-card-db-app-password\`).  
    \* Define \`google\_secret\_manager\_secret\_version\` to initially populate the secret value. Avoid committing plaintext secrets; use variables or generate random strings (\`random\_string\` resource) where applicable.  
    \* For DB credentials, store individual components (user, password) or the full connection string.  
    \* Define \`google\_secret\_manager\_secret\_iam\_member\` resources to grant the application's runtime service account (used by Cloud Run) the \`roles/secretmanager.secretAccessor\` role for each required secret.  
    \* Application code needs to fetch secrets from Secret Manager at startup OR secrets need to be mounted as environment variables or volumes in Cloud Run. \*\*Decision:\*\* Prefer mounting as environment variables in Cloud Run for simplicity in Stage 2\.  
    \* Update Terraform configuration for Cloud SQL (KC-INFRA-DO-5-GCP) and Cloud Run (KC-INFRA-DO-8-GCP) to reference the secrets stored in Secret Manager.  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* Terraform configuration files (\`.tf\`)  
    \* \`google\_secret\_manager\_secret\`, \`google\_secret\_manager\_secret\_version\`, \`google\_secret\_manager\_secret\_iam\_member\`.  
    \* IAM Policy for Cloud Run Service Account.  
    \* Cloud Run Service definition.  
\* \*\*Testing Considerations (Technical):\*\* Run \`terraform plan/apply\`. Verify secrets are created in GCP console. Verify Cloud Run service account has permissions. Verify application running in Cloud Run can access the required configuration values (injected as env vars). Test secret rotation procedures if implemented later.  
\* \*\*Dependencies (Technical):\*\* KC-INFRA-DO-1-GCP

\---

\#\# Ticket ID: KC-INFRA-DO-8-GCP

\* \*\*Title:\*\* Setup Cloud Run Service Definition (Terraform)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* Implied by Container Deployment  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* KC-INFRA-DO-2-GCP (VPC Network), KC-INFRA-DO-4-GCP (Artifact Registry Repo), KC-INFRA-DO-13-GCP (Firewall Rules), KC-INFRA-DO-10-GCP (Secrets), KC-INFRA-DO-3-GCP (Dockerfile), KC-INFRA-DO-9-GCP (Load Balancer Backend)  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Provision a Cloud Run service using Terraform to run the containerized Next.js application in a serverless environment, connected to the VPC network.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* Terraform code defines a \`google\_cloud\_run\_v2\_service\` resource.  
    \* Service references the Artifact Registry image URI (KC-INFRA-DO-4-GCP).  
    \* Specifies CPU/Memory resources.  
    \* Configures container port (e.g., 8080, matching Dockerfile and \`PORT\` env var).  
    \* Injects environment variables (non-sensitive and sensitive sourced from Secret Manager KC-INFRA-DO-10-GCP).  
    \* Assigns a dedicated runtime Service Account with necessary permissions (access Cloud SQL, Storage, Secrets).  
    \* Configures scaling settings (min/max instances).  
    \* Configures VPC Access Connector for communication with private resources (Cloud SQL, Memorystore).  
    \* Allows ingress traffic only from the Load Balancer and internal sources.  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Use Terraform Google Provider.  
    \* Ensure necessary APIs enabled (\`run.googleapis.com\`, \`vpcaccess.googleapis.com\`).  
    \* Define a dedicated runtime IAM Service Account (\`app-runtime-sa\`) for the application. Grant it roles needed to access Cloud SQL, Storage, Secret Manager, etc. (via \`google\_project\_iam\_member\` or resource-specific IAM bindings).  
    \* Define \`google\_vpc\_access\_connector\` resource connected to the VPC network.  
    \* Define \`google\_cloud\_run\_v2\_service\` resource:  
        \`\`\`terraform  
        resource "google\_cloud\_run\_v2\_service" "app" {  
          name     \= "knowledge-card-app-${var.environment}"  
          location \= var.region  
          launch\_stage \= "GA" \# Or BETA if using beta features

          template {  
            scaling {  
              min\_instance\_count \= 1 \# Or 0 for scale-to-zero  
              max\_instance\_count \= 5 \# Adjust as needed  
            }  
            containers {  
              image \= "${var.region}-docker.pkg.dev/${var.project\_id}/${google\_artifact\_registry\_repository.app.repository\_id}/knowledge-card-app:latest" \# Tag updated by CI/CD  
              ports { container\_port \= 8080 }  
              resources {  
                limits \= {  
                  "cpu"    \= "1000m"  
                  "memory" \= "512Mi"  
                }  
                \# startup\_cpu\_boost \= true \# Optional  
              }  
              env {  
                name \= "PORT"  
                value \= "8080"  
              }  
              env {  
                name \= "NODE\_ENV"  
                value \= "production"  
              }  
              \# Add other non-sensitive ENV vars here  
              env {  
                name \= "GCP\_PROJECT\_ID"  
                value \= var.project\_id  
              }  
              \# Mount secrets as environment variables  
              env {  
                name \= "DATABASE\_URL\_SECRET\_VERSION" \# App needs to read this version name  
                value\_source {  
                  secret\_key\_ref {  
                    secret \= google\_secret\_manager\_secret.db\_connection\_string.secret\_id \# Assuming full URL stored  
                    version \= "latest" \# Or specific version  
                  }  
                }  
              }  
              \# Add other secret env vars similarly...  
            }  
            \# Assign dedicated service account  
            service\_account \= google\_service\_account.app\_runtime\_sa.email  
            \# Configure VPC Access  
            vpc\_access {  
              connector \= google\_vpc\_access\_connector.main.id  
              egress    \= "ALL\_TRAFFIC" \# Or PRIVATE\_RANGES\_ONLY  
            }  
          }  
          \# Control Ingress (Allow authenticated users, internal, and LB)  
          ingress \= "INGRESS\_TRAFFIC\_INTERNAL\_LOAD\_BALANCER"  
          \# Allow unauthenticated if LB handles auth or app is public  
          \# iam\_policy { ... allow allUsers for public ... }  
        }  
        \# Grant Cloud Run Invoker role to LB service account if needed  
        \# resource "google\_cloud\_run\_v2\_service\_iam\_member" "allow\_lb" { ... }  
        \`\`\`  
    \* Configure IAM policy for the Cloud Run service (\`google\_cloud\_run\_v2\_service\_iam\_member\`) to allow invocation from the Load Balancer (if needed, depends on LB type) and potentially \`allUsers\` if public.  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* Terraform configuration files (\`.tf\`)  
    \* \`google\_cloud\_run\_v2\_service\`, \`google\_service\_account\`, \`google\_vpc\_access\_connector\`, \`google\_project\_iam\_member\`.  
    \* Secret Manager references.  
\* \*\*Testing Considerations (Technical):\*\* Run \`terraform plan/apply\`. Verify service creation in GCP console. Check Cloud Run instances are running and healthy. Verify application is accessible via Load Balancer URL (after KC-INFRA-DO-9-GCP). Check container logs in Cloud Logging (after KC-INFRA-DO-12-GCP).  
\* \*\*Dependencies (Technical):\*\* KC-INFRA-DO-2-GCP, 3-GCP, 4-GCP, 10-GCP, 13-GCP, KC-INFRA-DO-9-GCP (LB Backend Config)

\---

\#\# Ticket ID: KC-INFRA-DO-9-GCP

\* \*\*Title:\*\* Setup Cloud Load Balancer & DNS (Terraform)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* Implied by Public Web Access  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* KC-INFRA-DO-2-GCP (VPC Network), KC-INFRA-DO-13-GCP (Firewall Rules), KC-INFRA-DO-8-GCP (Cloud Run Service)  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Provision a Global HTTP(S) Load Balancer using Terraform to distribute incoming traffic to the Cloud Run service, and configure DNS records (in Cloud DNS) to point to the Load Balancer.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* Terraform code defines necessary Load Balancing components (\`google\_compute\_global\_forwarding\_rule\`, \`google\_compute\_target\_https\_proxy\`, \`google\_compute\_url\_map\`, \`google\_compute\_backend\_service\`, \`google\_compute\_health\_check\`, \`google\_compute\_ssl\_certificate\`).  
    \* Load Balancer uses a Google-managed SSL certificate or a user-managed one via Certificate Manager.  
    \* HTTP traffic is redirected to HTTPS.  
    \* A Backend Service is configured with a Serverless NEG pointing to the Cloud Run service.  
    \* Health checks are configured for the backend service.  
    \* (Optional) Cloud Armor policy attached for security.  
    \* A Cloud DNS managed zone exists or is managed.  
    \* A Cloud DNS 'A' record points the application's domain name to the Load Balancer's static external IP address.  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Ensure necessary APIs enabled (\`compute.googleapis.com\`, \`dns.googleapis.com\`, \`certificatemanager.googleapis.com\`).  
    \* SSL Certificate: Provision a Google-managed certificate (\`google\_compute\_managed\_ssl\_certificate\`) or use Certificate Manager (\`google\_certificate\_manager\_certificate\`). Requires domain ownership validation.  
    \* Define \`google\_compute\_global\_address\` for the static external IP.  
    \* Define \`google\_compute\_health\_check\` targeting the application's health endpoint (\`/api/health\`).  
    \* Define \`google\_compute\_backend\_service\` configured for serverless NEG:  
        \`\`\`terraform  
        resource "google\_compute\_region\_network\_endpoint\_group" "serverless\_neg" {  
          name                  \= "knowledge-card-neg-${var.environment}"  
          network\_endpoint\_type \= "SERVERLESS"  
          region                \= var.region  
          cloud\_run {  
            service \= google\_cloud\_run\_v2\_service.app.name  
          }  
        }  
        resource "google\_compute\_backend\_service" "app\_backend" {  
          name                            \= "knowledge-card-backend-${var.environment}"  
          protocol                        \= "HTTP" \# Traffic to Cloud Run is HTTP  
          port\_name                       \= "http" \# Matches Cloud Run port  
          load\_balancing\_scheme           \= "EXTERNAL\_MANAGED"  
          health\_checks                   \= \[google\_compute\_health\_check.http\_health\_check.id\]  
          backend {  
            group \= google\_compute\_region\_network\_endpoint\_group.serverless\_neg.id  
          }  
          \# enable\_cdn \= true \# Optional  
          \# security\_policy \= google\_compute\_security\_policy.armor\_policy.id \# Optional  
        }  
        \`\`\`  
    \* Define \`google\_compute\_url\_map\` to route default traffic (\`/\*\`) to the backend service.  
    \* Define \`google\_compute\_target\_https\_proxy\` referencing the URL map and SSL certificate(s).  
    \* Define \`google\_compute\_global\_forwarding\_rule\` for HTTPS (port 443\) pointing to the HTTPS proxy and the static IP address.  
    \* Define another \`google\_compute\_global\_forwarding\_rule\` for HTTP (port 80\) that redirects to HTTPS (using URL map redirect or separate HTTP proxy).  
    \* DNS:  
        \* Define \`google\_dns\_managed\_zone\` if managing via Terraform.  
        \* Define \`google\_dns\_record\_set\`: \`name \= var.app\_domain\`, \`managed\_zone \= ...\`, \`type \= "A"\`, \`rrdatas \= \[google\_compute\_global\_address.static\_ip.address\]\`.  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* Terraform configuration files (\`.tf\`)  
    \* \`google\_compute\_\*\` resources for Load Balancing, \`google\_dns\_\*\` resources.  
    \* SSL Certificate resource.  
\* \*\*Testing Considerations (Technical):\*\* Run \`terraform plan/apply\`. Verify LB components creation. Check backend service health checks pass once Cloud Run service is running. Access the application via the configured domain name over HTTPS. Verify HTTP redirects to HTTPS.  
\* \*\*Dependencies (Technical):\*\* KC-INFRA-DO-2-GCP, 13-GCP, 8-GCP, SSL Certificate provisioned. Domain name registered.

\---

\#\# Ticket ID: KC-INFRA-BE-1-GCP

\* \*\*Title:\*\* Implement Health Check Endpoint  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* NFR-RELIABILITY-1 (Implied)  
\* \*\*Team:\*\* BE  
\* \*\*Dependencies (Functional):\*\* KC-SETUP-1 (Next.js app)  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Create a simple API endpoint within the Next.js application that load balancers and container orchestrators (Cloud Run probes) can use to verify the application's health status.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* A GET endpoint exists (e.g., \`/api/health\`).  
    \* The endpoint returns a success status code (200 OK) and a simple body (e.g., \`{ status: 'ok' }\`) when the application is running normally.  
    \* (Optional Stage 2+) The endpoint could perform basic checks (e.g., database connectivity) before returning success.  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Create \`src/app/api/health/route.ts\`.  
    \* Export \`async function GET(request: Request)\`:  
        \`\`\`typescript  
        import { NextResponse } from 'next/server';

        export async function GET(request: Request) {  
          // Stage 1: Basic check \- if the handler runs, the server is up.  
          // Stage 2+: Add checks like DB connection test  
          // try {  
          //   // Example: Check DB connection if prisma client is available  
          //   // await prisma.$queryRaw\`SELECT 1\`;  
          // } catch (error) {  
          //   console.error("Health check failed:", error);  
          //   return NextResponse.json({ status: 'error', error: 'Dependency check failed' }, { status: 503 });  
          // }  
          return NextResponse.json({ status: 'ok', timestamp: Date.now() });  
        }  
        \`\`\`  
    \* Ensure this endpoint does not require authentication.  
    \* Configure the Load Balancer Health Check (KC-INFRA-DO-9-GCP) and potentially Cloud Run startup/liveness probes to use this \`/api/health\` path.  
\* \*\*API Contract (if applicable):\*\*  
    \* Endpoint: \`GET /api/health\`  
    \* Response Success (200): \`{ status: 'ok', timestamp: number }\`  
    \* Response Error (503): \`{ status: 'error', error: string }\` (If deeper checks implemented and fail)  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* \`src/app/api/health/route.ts\`  
\* \*\*Testing Considerations (Technical):\*\* Test the endpoint directly using curl or browser. Verify it returns 200 OK. Verify health checks configured in Load Balancer use this endpoint and pass when the app is running.  
\* \*\*Dependencies (Technical):\*\* KC-SETUP-1

\---

\#\# Ticket ID: KC-INFRA-DO-12-GCP (Generated)

\* \*\*Title:\*\* Setup Basic Cloud Logging/Monitoring (Terraform)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* NFR-OPS-1 (Implied)  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* KC-INFRA-DO-8-GCP (Cloud Run Service), KC-INFRA-DO-9-GCP (Load Balancer)  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Configure basic logging and monitoring for the Cloud Run application using GCP Cloud Logging and Cloud Monitoring via Terraform.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* Cloud Run service logs (stdout/stderr) are automatically sent to Cloud Logging.  
    \* Log retention policy is configured (e.g., via log bucket settings or log router sink).  
    \* Basic Cloud Monitoring Alerting Policies are configured for key metrics (e.g., high request latency, high error rate (5xx) on Cloud Run/LB, high container CPU/Memory utilization, unhealthy instance count on LB backend).  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* \*\*Logging:\*\* Cloud Run automatically integrates with Cloud Logging. Logs can be viewed in the Logs Explorer, filtered by Cloud Run service. Configure log bucket retention if default is not sufficient.  
    \* \*\*Monitoring:\*\* Use Terraform Google Provider.  
    \* Define \`google\_monitoring\_alert\_policy\` resources for key metrics:  
        \* Cloud Run Request Count (filter for 5xx status): \`run.googleapis.com/request\_count\`. Threshold \> N over M minutes.  
        \* Cloud Run Request Latencies: \`run.googleapis.com/request\_latencies\`. Threshold \> X ms.  
        \* Cloud Run Container CPU Utilization: \`run.googleapis.com/container/cpu/utilization\`. Threshold \> 80%.  
        \* Cloud Run Container Memory Utilization: \`run.googleapis.com/container/memory/utilization\`. Threshold \> 80%.  
        \* LB Backend Health (Unhealthy instances): \`loadbalancing.googleapis.com/backend\_health\`. Filter for backend service, threshold \> 0\.  
        \* LB Request Count (5xx): \`loadbalancing.googleapis.com/https/request\_count\`. Filter for backend service, status code 5xx. Threshold \> N.  
    \* Define \`google\_monitoring\_notification\_channel\` (e.g., email, PagerDuty, Slack).  
    \* Link notification channels to alert policies.  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* Terraform configuration files (\`.tf\`)  
    \* \`google\_monitoring\_alert\_policy\`, \`google\_monitoring\_notification\_channel\`.  
    \* Cloud Logging configuration (retention).  
\* \*\*Testing Considerations (Technical):\*\* Run \`terraform plan/apply\`. Verify alert policies and notification channels in GCP Monitoring console. Verify logs appear in Cloud Logging. Trigger alerts (e.g., deploy code causing errors, high CPU) to test notifications.  
\* \*\*Dependencies (Technical):\*\* KC-INFRA-DO-8-GCP, KC-INFRA-DO-9-GCP

\---

\#\# Ticket ID: KC-INFRA-DO-11-GCP (Generated)

\* \*\*Title:\*\* Enhance CI/CD Pipeline for GCP Deployment (GitHub Actions)  
\* \*\*Epic:\*\* KC-INFRA  
\* \*\*PRD Requirement(s):\*\* NFR-DEPLOY-1  
\* \*\*Team:\*\* DO  
\* \*\*Dependencies (Functional):\*\* KC-TRANSITION-DO-3 (Placeholder Pipeline), KC-INFRA-DO-1-GCP (IAM Role/WIF), KC-INFRA-DO-4-GCP (Artifact Registry Repo), KC-INFRA-DO-8-GCP (Cloud Run Service)  
\* \*\*UX/UI Design Link:\*\* N/A  
\* \*\*Description (Functional):\*\* Update the CI/CD pipeline (GitHub Actions) to automatically build the Docker image, push it to Artifact Registry, and deploy updates to the Cloud Run service upon merges to the main branch.  
\* \*\*Acceptance Criteria (Functional):\*\*  
    \* GitHub Actions workflow builds the production Docker image.  
    \* Workflow authenticates to GCP using Workload Identity Federation.  
    \* Workflow authenticates to Artifact Registry.  
    \* Workflow tags the image appropriately (e.g., with Git SHA).  
    \* Workflow pushes the tagged image to the Artifact Registry repository.  
    \* Workflow deploys a new revision to the Cloud Run service using the new image URI.  
    \* Workflow runs on merge/push to the main branch.  
    \* \*\*(Missing Piece):\*\* Workflow includes a step to run database migrations (\`prisma migrate deploy\`) against the Cloud SQL database before or after deploying the new Cloud Run revision.  
\* \*\*Technical Approach / Implementation Notes:\*\*  
    \* Modify \`.github/workflows/deploy.yml\`.  
    \* \*\*GCP Authentication:\*\* Use \`google-github-actions/auth\` action with Workload Identity Federation. Provide Workload Identity Provider and Service Account email (\`cicd-pipeline-sa\`).  
    \* \*\*Artifact Registry Auth:\*\* Use \`docker login\` helper or \`gcloud auth configure-docker\` after authenticating to GCP. The \`google-github-actions/auth\` action can configure Docker automatically.  
    \* \*\*Build & Tag:\*\* Use \`docker build\` command. Generate image tag (e.g., \`IMAGE\_TAG=${{ github.sha }}\`). Artifact Registry repository URL needed (e.g., \`REGION-docker.pkg.dev/PROJECT\_ID/REPOSITORY\_ID/IMAGE\_NAME\`).  
    \* \*\*Push:\*\* Use \`docker push\` command with the tagged image name.  
    \* \*\*Deploy to Cloud Run:\*\* Use \`google-github-actions/deploy-cloudrun\` action.  
        \* Provide \`service\`: Cloud Run service name.  
        \* Provide \`image\`: Full Artifact Registry image URI with the new tag.  
        \* Provide \`region\`.  
        \* Set other flags as needed (e.g., environment variables if not managed by Terraform, \`--no-traffic\` for staged rollout).  
    \* \*\*Database Migrations (CRITICAL ADDITION):\*\*  
        \* \*\*Option A (Before Deploy):\*\* Add a step \*before\* the Cloud Run deploy step. This step needs access to the database (e.g., via Cloud SQL Proxy running in the GitHub Actions runner or direct connection if firewall allows). It would run \`npx prisma migrate deploy\`. Requires DB credentials available to the pipeline (e.g., via Secret Manager).  
        \* \*\*Option B (After Deploy \- Requires Careful Handling):\*\* Deploy the new code, then run migrations. Risky if new code depends on schema changes not yet applied.  
        \* \*\*Option C (Dedicated Migration Job/Task):\*\* Trigger a separate Cloud Run job or GKE job specifically for migrations. More complex setup.  
        \* \*\*Decision:\*\* Add step using \*\*Cloud SQL Proxy\*\* before Cloud Run deployment (Option A). Requires adding \`gcloud\` setup and proxy start/stop to the workflow, plus securely accessing DB credentials.  
    \* Structure workflow with jobs (e.g., \`build-push\`, \`migrate-db\`, \`deploy-app\`).  
    \* Use GitHub environments for secrets (GCP WIF provider, service account, project ID, region, repo ID, DB cred secret names) and environment-specific variables.  
    \* Ensure appropriate error handling.  
\* \*\*API Contract (if applicable):\*\* N/A  
\* \*\*Data Model Changes (if applicable):\*\* N/A  
\* \*\*Key Functions/Modules Involved:\*\*  
    \* \`.github/workflows/deploy.yml\`  
    \* GitHub Actions Marketplace actions (\`google-github-actions/...\`).  
    \* Docker commands (\`build\`, \`push\`).  
    \* \`gcloud\` commands (for auth, potentially proxy).  
    \* \`npx prisma migrate deploy\`.  
\* \*\*Testing Considerations (Technical):\*\* Test workflow by pushing changes to a feature branch and merging to main. Monitor workflow execution. Verify new image appears in Artifact Registry. Verify migrations run successfully. Verify Cloud Run service updates and new revision is deployed. Test rollback procedures.  
\* \*\*Dependencies (Technical):\*\* KC-TRANSITION-DO-3, KC-INFRA-DO-1-GCP, 4-GCP, 5-GCP, 8-GCP, 10-GCP. All preceding infrastructure must be deployed via Terraform first. Cloud SQL Proxy setup.  
