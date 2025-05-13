## EPIC: KC-GCP-INFRA \- GCP Foundation & Deployment

Rationale: To establish the necessary Google Cloud Platform (GCP) infrastructure for deploying, running, and managing the (now locally enhanced and optimized) Stage 2 application, including database, storage, compute, networking, CI/CD, and monitoring.  
PRD Reference(s): PRD v3.8 \- Section 1.4 (Stage 2 Cloud Infrastructure), NFR-SCALE-1, NFR-DEPLOY-1, NFR-MAINT-5 (from nfrs\_v1\_1)  
TDD Reference(s): TDD v1.2 \- Section 2 (High-Level Architecture \- Stage 2 GCP), Section 6 (Technology Choices \- GCP), Section 9 (Deployment Strategy \- GCP)  
Environment: Google Cloud Platform (GCP)

### Ticket ID: KC-GCP-TERRAFORM-1

Title: Setup Terraform for GCP Infrastructure Provisioning  
Epic: KC-GCP-INFRA  
PRD Requirement(s): NFR-MAINT-5 (from nfrs\_v1\_1)  
TDD Reference(s): TDD v1.2, Section 2 (Infrastructure), Section 9  
Team: DevOps  
Dependencies (Functional): ADR-008 (GCP Choice Confirmed)  
Dependencies (Technical): Terraform CLI installed locally/in CI environment.  
Human/PM Action Items:

* Ensure a GCP Project is created and available for this application.  
* Ensure billing is enabled for the GCP Project.  
* Decide on a globally unique name for the Terraform state GCS bucket.  
* Ensure the person/service account running Terraform has the necessary permissions to create resources in the GCP project (e.g., Project Owner/Editor for initial setup, then more granular permissions).

Description (Functional): Initialize and configure Terraform to manage all GCP resources as Infrastructure as Code (IaC). This includes setting up the Terraform backend for state storage (e.g., a GCS bucket) and establishing the basic Terraform project structure.  
Acceptance Criteria (Functional):

* Terraform is installed and can be executed against the designated GCP project.  
* A Google Cloud Storage (GCS) bucket is created (can be manual or via initial Terraform script) and configured as the Terraform remote backend for state management.  
* Initial Terraform configuration files (main.tf, variables.tf, outputs.tf, providers.tf, backend.tf) are created in the project repository.  
* Terraform is initialized successfully (terraform init) using the GCS backend.  
* A basic terraform plan (e.g., to create a VPC network if one doesn't exist or to manage project services) executes successfully, showing the intended changes.  
  Technical Approach / Implementation Notes (for AI Vibe Coder):  
* **Prompt for AI Coder:** "Your task is to set up the initial Terraform configuration for managing GCP infrastructure.  
  1. **Create providers.tf:**  
     terraform {  
       required\_providers {  
         google \= {  
           source  \= "hashicorp/google"  
           version \= "\~\> 5.0" \# Specify a recent, stable version  
         }  
         google-beta \= {  
           source  \= "hashicorp/google-beta"  
           version \= "\~\> 5.0"  
         }  
       }  
       required\_version \= "\>= 1.0" \# Specify Terraform version  
     }

     provider "google" {  
       project \= var.gcp\_project\_id  
       region  \= var.gcp\_region  
     }

     provider "google-beta" {  
       project \= var.gcp\_project\_id  
       region  \= var.gcp\_region  
     }

  2. **Create backend.tf:** (Replace YOUR\_UNIQUE\_TERRAFORM\_STATE\_BUCKET\_NAME with the actual bucket name provided by PM/Human)  
     terraform {  
       backend "gcs" {  
         bucket  \= "YOUR\_UNIQUE\_TERRAFORM\_STATE\_BUCKET\_NAME"  
         prefix  \= "terraform/state/knowledge\_card\_system" \# Or your desired state path  
       }  
     }

     *Note: The GCS bucket for the backend must be created beforehand (can be done manually or via a separate one-time Terraform script).*  
  3. **Create variables.tf:**  
     variable "gcp\_project\_id" {  
       description \= "The GCP project ID."  
       type        \= string  
     }

     variable "gcp\_region" {  
       description \= "The GCP region for resources."  
       type        \= string  
       default     \= "us-central1" \# Or your preferred default region  
     }  
     // Add other common variables as needed

  4. **Create main.tf (Initial placeholder or basic network):**  
     // Example: Enable necessary APIs (adjust as needed)  
     resource "google\_project\_service" "project\_services" {  
       project \= var.gcp\_project\_id  
       for\_each \= toset(\[  
         "compute.googleapis.com",  
         "sqladmin.googleapis.com",  
         "storage.googleapis.com",  
         "redis.googleapis.com",  
         "iam.googleapis.com",  
         "secretmanager.googleapis.com",  
         "run.googleapis.com",          // For Cloud Run  
         "container.googleapis.com",    // For GKE (if chosen)  
         "artifactregistry.googleapis.com",  
         "cloudbuild.googleapis.com",   // If using Cloud Build  
         "logging.googleapis.com",  
         "monitoring.googleapis.com",  
         "cloudresourcemanager.googleapis.com"  
       \])  
       service                    \= each.key  
       disable\_dependent\_services \= true // Set to false if you want to auto-enable dependencies  
       disable\_on\_destroy         \= false // Set to true if you want to disable services on destroy  
     }

     // Example: Basic VPC Network (if not using default)  
     /\*  
     resource "google\_compute\_network" "main\_vpc" {  
       project                 \= var.gcp\_project\_id  
       name                    \= "kc-main-vpc"  
       auto\_create\_subnetworks \= true // Or false for custom subnets  
     }  
     \*/

  5. **Create .terraform-version file:** (Optional, but good practice)  
     1.7.4 // Specify your target Terraform version

  6. **Instructions for Human:**  
     * Create the GCS bucket for Terraform state: gsutil mb \-p YOUR\_GCP\_PROJECT\_ID \-l YOUR\_GCP\_REGION gs://YOUR\_UNIQUE\_TERRAFORM\_STATE\_BUCKET\_NAME (Enable versioning on this bucket).  
     * Initialize Terraform: terraform init.  
     * Create a terraform.tfvars file (and add to .gitignore) with gcp\_project\_id \= "your-actual-project-id".  
     * Run terraform plan and terraform apply to enable services.  
  7. **Structure:** Organize Terraform code into modules (e.g., modules/networking, modules/cloud-sql) as the configuration grows."

### Ticket ID: KC-GCP-DB-1

Title: Provision Google Cloud SQL for PostgreSQL with pgvector (Reflecting Local Enhancements)  
Epic: KC-GCP-INFRA  
PRD Requirement(s): TC-STACK-3 (from PRD v3.8)  
TDD Reference(s): TDD v1.2, Section 2, Section 3, Section 6  
Team: DevOps/BE  
Dependencies (Functional): KC-GCP-TERRAFORM-1, ADR-002 (PostgreSQL choice), ADR-003 (pgvector choice), KC-DB-RETHINK-PROPOSE-1 (for schema/index decisions from local Phase A)  
Dependencies (Technical): Terraform, GCP Cloud SQL service API enabled.  
Human/PM Action Items:

* Decide on the initial machine tier for the Cloud SQL instance (balancing cost and performance).  
* Confirm the database name, primary user name.  
* Approve the region for the Cloud SQL instance (should align with var.gcp\_region).

Description (Functional): Use Terraform to provision a Google Cloud SQL for PostgreSQL instance. Configure it with the pgvector extension enabled, appropriate machine type, storage, networking (private IP), and automated backups. The initial schema deployed will be the one resulting from local Phase A enhancements (including hashtags and any optimizations from KC-DB-RETHINK-PROPOSE-1).  
Acceptance Criteria (Functional):

* A Cloud SQL for PostgreSQL instance is provisioned via Terraform.  
* The instance is configured with a private IP address within the project's VPC (using Private Service Access).  
* The pgvector extension is enabled on the database.  
* Automated daily backups are configured with a 7-day retention policy.  
* Point-in-time recovery (PITR) is enabled.  
* Database flags for pgvector (if any specific ones are needed, e.g., shared\_preload\_libraries \= 'pg\_stat\_statements,vector') are set.  
* Connection details (instance connection name, private IP, database name, user, password stored in Google Secret Manager) are available for application use.  
  Technical Approach / Implementation Notes (for AI Vibe Coder):  
* **Prompt for AI Coder:** "Your task is to write Terraform code to provision a Google Cloud SQL for PostgreSQL instance with pgvector enabled.  
  1. **Define Resources in a new Terraform file (e.g., cloud\_sql.tf):**  
     * Use google\_sql\_database\_instance resource.  
       * Set name (e.g., kc-postgres-instance).  
       * Set database\_version to a recent PostgreSQL version (e.g., POSTGRES\_15).  
       * Set region using var.gcp\_region.  
       * Configure settings:  
         * tier: (e.g., db-f1-micro for dev, db-custom-X-YYYY for prod \- make this a variable).  
         * ip\_configuration:  
           * ipv4\_enabled \= true  
           * private\_network \= "projects/${var.gcp\_project\_id}/global/networks/YOUR\_VPC\_NAME" (Replace YOUR\_VPC\_NAME or use data source/variable. Ensure Private Service Access is configured for the VPC).  
           * require\_ssl \= true  
         * backup\_configuration: enabled \= true, point\_in\_time\_recovery\_enabled \= true, binary\_log\_enabled \= true (for PITR).  
         * database\_flags:  
           database\_flags {  
             name  \= "cloudsql.extensions"  
             value \= "pg\_stat\_statements,vector" // Ensure 'vector' is listed  
           }  
           // Add other flags as needed, e.g., for timezone  
           database\_flags {  
             name \= "log\_min\_duration\_statement"  
             value \= "250" // Log queries slower than 250ms  
           }

     * Use google\_sql\_database resource to create the main application database (e.g., knowledge\_cards\_db).  
     * Use google\_sql\_user resource to create the application user.  
       * The password for this user **must be generated and stored in Google Secret Manager** (see KC-GCP-IAM-SECRETS-1). This Terraform resource should reference the secret.  
  2. **Enabling pgvector Extension:** While listing 'vector' in cloudsql.extensions flag requests it, the extension often needs to be explicitly created within the database. This might require a provisioner or a manual step after instance creation:  
     * **Option (Manual/Post-Terraform):** Connect to the database and run CREATE EXTENSION IF NOT EXISTS vector;.  
     * **Option (Terraform null\_resource \- more complex):** Use a null\_resource with a local-exec provisioner that uses gcloud sql connect and psql to run the command. This is more advanced and can be brittle. Often, a simple manual step or a DB migration tool handling this is easier. For now, document the manual step.  
  3. **Variables:** Use variables for instance name, tier, DB name, user name to make it configurable.  
  4. **Private Service Access:** Ensure Private Service Access is configured between your VPC and Google services. This might be a separate Terraform resource (google\_compute\_global\_address and google\_service\_networking\_connection) if not already set up at the VPC level.  
     // Example for Private Service Access (ensure this is configured once per VPC)  
     resource "google\_compute\_global\_address" "private\_ip\_address" {  
       project       \= var.gcp\_project\_id  
       name          \= "private-ip-for-google-services"  
       purpose       \= "VPC\_PEERING"  
       address\_type  \= "INTERNAL"  
       ip\_version    \= "IPV4"  
       network       \= "projects/${var.gcp\_project\_id}/global/networks/YOUR\_VPC\_NAME" // Your VPC  
       address       \= "10.100.0.0" // Example private range, pick an unused one  
       prefix\_length \= 16  
     }

     resource "google\_service\_networking\_connection" "private\_vpc\_connection" {  
       project                 \= var.gcp\_project\_id  
       network                 \= "projects/${var.gcp\_project\_id}/global/networks/YOUR\_VPC\_NAME" // Your VPC  
       service                 \= "servicenetworking.googleapis.com"  
       reserved\_peering\_ranges \= \[google\_compute\_global\_address.private\_ip\_address.name\]  
     }  
     // Cloud SQL instance should depend on google\_service\_networking\_connection.private\_vpc\_connection

  5. **Output:** Output the instance connection name and private IP address.  
     output "db\_instance\_connection\_name" {  
       value \= google\_sql\_database\_instance.default.connection\_name  
     }  
     output "db\_instance\_private\_ip" {  
       value \= google\_sql\_database\_instance.default.private\_ip\_address  
     }

  6. **Documentation:** Add a note that after the instance is up, the CREATE EXTENSION IF NOT EXISTS vector; command needs to be run on the application database by connecting as a superuser or the admin user."

### Ticket ID: KC-GCP-STORAGE-1

Title: Provision Google Cloud Storage Buckets  
Epic: KC-GCP-INFRA  
PRD Requirement(s): TC-STACK-5 (from PRD v3.8)  
TDD Reference(s): TDD v1.2, Section 2, Section 6  
Team: DevOps  
Dependencies (Functional): KC-GCP-TERRAFORM-1  
Dependencies (Technical): Terraform, GCP Cloud Storage service API enabled.  
Human/PM Action Items:

* Decide on globally unique names for GCS buckets (e.g., one for media, one for backups if not using Cloud SQL's native backups exclusively).  
* Confirm storage class (e.g., Standard for frequently accessed media).

Description (Functional): Use Terraform to provision Google Cloud Storage (GCS) buckets required for the application, including a bucket for media file uploads (Stage 2 Media Blocks). Configure appropriate permissions (Uniform Bucket-Level Access) and consider lifecycle policies.  
Acceptance Criteria (Functional):

* A GCS bucket for media files (e.g., kc-media-uploads-prod) is provisioned via Terraform.  
* The bucket is configured with Uniform Bucket-Level Access enabled.  
* Appropriate IAM permissions are set for application services (e.g., backend service account) to read/write objects to the media bucket.  
* Public access to the media bucket is blocked.  
* (Optional) Basic lifecycle rules are considered (e.g., for deleting incomplete multipart uploads).  
  Technical Approach / Implementation Notes (for AI Vibe Coder):  
* **Prompt for AI Coder:** "Write Terraform code (e.g., in gcs.tf) to provision a Google Cloud Storage bucket for media uploads.  
  1. **Define google\_storage\_bucket Resource:**  
     variable "media\_bucket\_name" {  
       description \= "Name for the GCS bucket for media uploads."  
       type        \= string  
     }

     resource "google\_storage\_bucket" "media\_uploads" {  
       project                     \= var.gcp\_project\_id  
       name                        \= var.media\_bucket\_name  
       location                    \= var.gcp\_region // Or a multi-region if appropriate  
       storage\_class               \= "STANDARD"  
       uniform\_bucket\_level\_access \= true  
       force\_destroy               \= false // Set to true for non-prod if you want to easily delete non-empty buckets

       versioning {  
         enabled \= true // Good practice for media files  
       }

       // Example lifecycle rule: delete incomplete multipart uploads after 7 days  
       lifecycle\_rule {  
         action {  
           type \= "AbortIncompleteMultipartUpload"  
         }  
         condition {  
           days\_since\_initiation \= 7  
         }  
       }  
     }

  2. **Define IAM Permissions:** Grant the application's backend service account (created in KC-GCP-IAM-SECRETS-1) permissions to write and read objects in this bucket.  
     data "google\_iam\_policy" "media\_bucket\_admin" {  
       binding {  
         role \= "roles/storage.objectAdmin"  
         members \= \[  
           "serviceAccount:YOUR\_BACKEND\_SERVICE\_ACCOUNT\_EMAIL", // Replace with actual SA email  
         \]  
       }  
       binding {  
         role \= "roles/storage.objectViewer" // If separate read access needed by other services/users  
         members \= \[  
           // "serviceAccount:YOUR\_READONLY\_SERVICE\_ACCOUNT\_EMAIL",  
         \]  
       }  
     }

     resource "google\_storage\_bucket\_iam\_policy" "media\_uploads\_policy" {  
       bucket      \= google\_storage\_bucket.media\_uploads.name  
       policy\_data \= data.google\_iam\_policy.media\_bucket\_admin.policy\_data  
     }

     *Alternatively, use google\_storage\_bucket\_iam\_member for individual role bindings.*  
  3. **Variables:** Add media\_bucket\_name to variables.tf and provide a value in terraform.tfvars.  
  4. **Output:** Output the bucket name.  
     output "media\_bucket\_url" {  
       value \= google\_storage\_bucket.media\_uploads.url  
     }  
     \`\`\`"

### Ticket ID: KC-GCP-REDIS-1

Title: Provision Google Cloud Memorystore for Redis  
Epic: KC-GCP-INFRA  
PRD Requirement(s): TC-STACK-3 (from PRD v3.8)  
TDD Reference(s): TDD v1.2, Section 2, Section 6  
Team: DevOps  
Dependencies (Functional): KC-GCP-TERRAFORM-1, VPC network with Private Service Access configured.  
Dependencies (Technical): Terraform, GCP Memorystore (Redis) API enabled.  
Human/PM Action Items:

* Decide on the initial tier (Basic or Standard HA) and capacity (GB) for the Redis instance.  
* Confirm the region for the Redis instance.

Description (Functional): Use Terraform to provision a Google Cloud Memorystore for Redis instance. This will be used for caching and as the backend for the BullMQ job queue system. Configure appropriate tier, capacity, and networking (private IP).  
Acceptance Criteria (Functional):

* A Memorystore for Redis instance is provisioned via Terraform.  
* The instance is configured with a private IP address within the project's VPC using Private Service Access.  
* The tier (e.g., BASIC for dev, STANDARD\_HA for prod) and capacity are suitable for initial Stage 2 needs.  
* Connection details (host IP, port) are available for application use (ideally stored or discoverable).  
  Technical Approach / Implementation Notes (for AI Vibe Coder):  
* **Prompt for AI Coder:** "Write Terraform code (e.g., in redis.tf) to provision a Google Cloud Memorystore for Redis instance.  
  1. **Define google\_redis\_instance Resource:**  
     variable "redis\_instance\_name" {  
       description \= "Name for the Memorystore Redis instance."  
       type        \= string  
       default     \= "kc-redis-main"  
     }

     variable "redis\_tier" {  
       description \= "Tier for Redis (BASIC or STANDARD\_HA)."  
       type        \= string  
       default     \= "BASIC"  
     }

     variable "redis\_memory\_size\_gb" {  
       description \= "Memory size in GB for Redis."  
       type        \= number  
       default     \= 1  
     }

     resource "google\_redis\_instance" "main\_cache" {  
       project          \= var.gcp\_project\_id  
       name             \= var.redis\_instance\_name  
       tier             \= var.redis\_tier  
       memory\_size\_gb   \= var.redis\_memory\_size\_gb  
       location\_id      \= var.gcp\_region // Or a specific zone if tier is BASIC  
       region           \= var.gcp\_region // Required field  
       connect\_mode     \= "PRIVATE\_SERVICE\_ACCESS"  
       authorized\_network \= "projects/${var.gcp\_project\_id}/global/networks/YOUR\_VPC\_NAME" // Your VPC name

       // transit\_encryption\_mode \= "SERVER\_AUTHENTICATION" // Recommended for prod  
       // maintenance\_policy { ... } // Optional  
     }

     *Ensure YOUR\_VPC\_NAME is correctly specified. The VPC must have Private Service Access configured (see KC-GCP-DB-1 notes).*  
  2. **Variables:** Add redis\_instance\_name, redis\_tier, redis\_memory\_size\_gb to variables.tf and provide values in terraform.tfvars.  
  3. **Output:** Output the Redis host IP and port.  
     output "redis\_host" {  
       value \= google\_redis\_instance.main\_cache.host  
     }  
     output "redis\_port" {  
       value \= google\_redis\_instance.main\_cache.port  
     }  
     \`\`\`"

### Ticket ID: KC-GCP-IAM-SECRETS-1

Title: Configure GCP IAM Roles and Google Secret Manager  
Epic: KC-GCP-INFRA  
PRD Requirement(s): NFR-SEC-1, NFR-SEC-4 (from nfrs\_v1\_1), TC-STACK-8 (from PRD v3.8)  
TDD Reference(s): TDD v1.2, Section 2, Section 8  
Team: DevOps  
Dependencies (Functional): KC-GCP-TERRAFORM-1  
Dependencies (Technical): Terraform, GCP IAM API, GCP Secret Manager API enabled.  
Human/PM Action Items:

* List all external services requiring API keys (e.g., LLM provider from ADR-010).  
* Confirm names for service accounts (e.g., sa-kc-backend, sa-kc-crewai, sa-kc-cicd).

Description (Functional): Use Terraform to define necessary IAM roles and service accounts for application components (Next.js backend, CrewAI services, CI/CD pipeline) following the principle of least privilege. Provision Google Secret Manager to store sensitive information like API keys and database credentials.  
Acceptance Criteria (Functional):

* Dedicated GCP service accounts are created via Terraform for the Next.js backend, CrewAI services, and the CI/CD pipeline.  
* These service accounts are granted only the necessary IAM permissions (e.g., access to Cloud SQL, GCS, Memorystore, Secret Manager, Cloud Run/GKE invoker/developer).  
* Secrets (e.g., database password from KC-GCP-DB-1, LLM API keys, NextAuth secret) are created as secrets in Google Secret Manager, provisioned via Terraform.  
* Application services' IAM configurations allow them to retrieve their respective secrets from Secret Manager at runtime.  
  Technical Approach / Implementation Notes (for AI Vibe Coder):  
* **Prompt for AI Coder:** "Write Terraform code (e.g., in iam\_secrets.tf) to manage IAM and Secrets.  
  1. **Create Service Accounts:**  
     resource "google\_service\_account" "backend\_sa" {  
       project      \= var.gcp\_project\_id  
       account\_id   \= "kc-backend-sa"  
       display\_name \= "Knowledge Card Backend Service Account"  
     }  
     // Create similar SAs for CrewAI services and CI/CD pipeline  
     resource "google\_service\_account" "crewai\_sa" { /\* ... \*/ }  
     resource "google\_service\_account" "cicd\_sa" { /\* ... \*/ }

  2. **Grant IAM Permissions to Service Accounts:**  
     * Example: Backend SA needs to access Cloud SQL, GCS, Memorystore, Secret Manager.  
       // Backend SA permissions  
       resource "google\_project\_iam\_member" "backend\_sa\_sql\_client" {  
         project \= var.gcp\_project\_id  
         role    \= "roles/cloudsql.client"  
         member  \= "serviceAccount:${google\_service\_account.backend\_sa.email}"  
       }  
       resource "google\_project\_iam\_member" "backend\_sa\_storage\_object\_admin" {  
         project \= var.gcp\_project\_id  
         role    \= "roles/storage.objectAdmin" // Or more granular on specific buckets  
         member  \= "serviceAccount:${google\_service\_account.backend\_sa.email}"  
       }  
       resource "google\_project\_iam\_member" "backend\_sa\_redis\_editor" {  
         project \= var.gcp\_project\_id  
         role    \= "roles/redis.editor"  
         member  \= "serviceAccount:${google\_service\_account.backend\_sa.email}"  
       }  
       resource "google\_project\_iam\_member" "backend\_sa\_secret\_accessor" {  
         project \= var.gcp\_project\_id  
         role    \= "roles/secretmanager.secretAccessor"  
         member  \= "serviceAccount:${google\_service\_account.backend\_sa.email}"  
       }  
       // Add permissions for Cloud Run Invoker if backend calls CrewAI services, etc.  
       // Assign similar granular permissions for crewai\_sa and cicd\_sa

  3. **Create Secrets in Secret Manager:**  
     * Example for Database Password (assuming password is not set directly in google\_sql\_user but generated externally or by a previous step and needs to be stored).  
       resource "google\_secret\_manager\_secret" "db\_password\_secret" {  
         project   \= var.gcp\_project\_id  
         secret\_id \= "kc-db-password"  
         replication {  
           automatic \= true  
         }  
       }

       resource "google\_secret\_manager\_secret\_version" "db\_password\_version" {  
         secret      \= google\_secret\_manager\_secret.db\_password\_secret.id  
         secret\_data \= "YOUR\_SECURELY\_GENERATED\_DB\_PASSWORD" // IMPORTANT: Use a variable or random provider  
       }

       // Example for LLM API Key  
       resource "google\_secret\_manager\_secret" "llm\_api\_key\_secret" {  
         project   \= var.gcp\_project\_id  
         secret\_id \= "kc-llm-api-key"  
         // ... replication  
       }  
       resource "google\_secret\_manager\_secret\_version" "llm\_api\_key\_version" {  
         secret      \= google\_secret\_manager\_secret.llm\_api\_key\_secret.id  
         secret\_data \= var.llm\_api\_key // Get from a secure tfvars file  
       }

     * **IMPORTANT:** For secret\_data, never hardcode sensitive values directly. Use input variables (marked sensitive, from a .tfvars file not committed to Git) or a random\_password resource for generated passwords.  
  4. **Grant Service Accounts Access to Specific Secrets:**  
     resource "google\_secret\_manager\_secret\_iam\_member" "backend\_sa\_access\_db\_password" {  
       project   \= var.gcp\_project\_id  
       secret\_id \= google\_secret\_manager\_secret.db\_password\_secret.secret\_id  
       role      \= "roles/secretmanager.secretAccessor"  
       member    \= "serviceAccount:${google\_service\_account.backend\_sa.email}"  
     }  
     // Grant crewai\_sa access to llm\_api\_key\_secret, etc.

  5. **Variables:** Add llm\_api\_key as a sensitive variable in variables.tf and provide its value in a secure terraform.tfvars file (added to .gitignore)."

### Ticket ID: KC-GCP-CICD-1

Title: Setup CI/CD Pipeline for GCP Deployment (Next.js Backend \- Enhanced App)  
Epic: KC-GCP-INFRA  
PRD Requirement(s): NFR-DEPLOY-1 (from nfrs\_v1\_1), TC-STACK-8 (from PRD v3.8)  
TDD Reference(s): TDD v1.2, Section 2, Section 9  
Team: DevOps  
Dependencies (Functional): KC-GCP-TERRAFORM-1, KC-GCP-IAM-SECRETS-1 (for CI/CD service account), Completion of Phase A local enhancements (KC-OPTIMIZE-S1, KC-HASHTAGS-LOCAL, KC-UXUI-ENHANCE-S1-LOCAL). GCP Artifact Registry created (can be part of this ticket or separate Terraform). Target GCP Compute service (e.g., Cloud Run service definition) provisioned via Terraform.  
Dependencies (Technical): CI/CD tool (Google Cloud Build or GitHub Actions), Docker, GCP Artifact Registry, GCP Compute (Cloud Run/GKE).  
Human/PM Action Items:

* Decide on the CI/CD tool (Google Cloud Build or GitHub Actions).  
* Define branching strategy that triggers deployments (e.g., merge to main deploys to prod, merge to develop deploys to staging).  
* Ensure repository is connected to the chosen CI/CD tool.

Description (Functional): Configure a CI/CD pipeline to automate the build, testing (unit/integration), and deployment of the Next.js backend application (which has undergone Phase A enhancements) to the chosen GCP compute service (e.g., Cloud Run).  
Status Update (YYYY-MM-DD): The Google Cloud Build trigger associated with `ThinkStash_KB_Fresh_Filter/cloudbuild.yaml` is successfully firing on code pushes. The current `cloudbuild.yaml` correctly sets up Node.js (via nvm) and installs npm dependencies. This achieves the initial part of triggering the pipeline.
Acceptance Criteria (Functional):

* A CI/CD pipeline is triggered on code pushes/merges to specified branches. (*Partially DONE: Basic trigger and Node.js/npm install build confirmed working.*)
* The pipeline builds the Next.js application Docker image.
* Automated tests (unit, integration \- as per NFR-MAINT-3 from nfrs\_v1\_1) are executed within the pipeline.
* On successful tests, the Docker image is tagged and pushed to Google Artifact Registry.
* The new image is deployed to the target GCP compute service (e.g., new revision on Cloud Run) using a safe deployment strategy (e.g., rolling update, canary if configured).
* Database migrations (prisma migrate deploy) are applied as a step in the deployment process before the new application version serves traffic.
* Pipeline provides clear success/failure notifications.
  Technical Approach / Implementation Notes (for AI Vibe Coder):  
* **Prompt for AI Coder (Example for Google Cloud Build):** "Your task is to create a cloudbuild.yaml file for the Next.js backend application to deploy to Google Cloud Run.  
  1. **Define cloudbuild.yaml:**  
     steps:  
     \# Install dependencies  
     \- name: 'gcr.io/cloud-builders/npm'  
       args: \['install'\]

     \# Run linters (example)  
     \- name: 'gcr.io/cloud-builders/npm'  
       args: \['run', 'lint'\]

     \# Run tests (example)  
     \- name: 'gcr.io/cloud-builders/npm'  
       args: \['run', 'test'\] \# Ensure your test script is configured in package.json

     \# Build Prisma Client  
     \- name: 'gcr.io/cloud-builders/npm'  
       args: \['run', 'prisma:generate'\] \# Assuming 'prisma:generate': 'prisma generate' in package.json

     \# Build Next.js app  
     \- name: 'gcr.io/cloud-builders/npm'  
       args: \['run', 'build'\]

     \# Build Docker image  
     \- name: 'gcr.io/cloud-builders/docker'  
       args: \['build', '-t', 'YOUR\_GCP\_REGION-docker.pkg.dev/YOUR\_GCP\_PROJECT\_ID/YOUR\_ARTIFACT\_REGISTRY\_REPO/kc-nextjs-backend:$COMMIT\_SHA', '.'\]

     \# Push Docker image to Artifact Registry  
     \- name: 'gcr.io/cloud-builders/docker'  
       args: \['push', 'YOUR\_GCP\_REGION-docker.pkg.dev/YOUR\_GCP\_PROJECT\_ID/YOUR\_ARTIFACT\_REGISTRY\_REPO/kc-nextjs-backend:$COMMIT\_SHA'\]

     \# Apply Database Migrations (ensure Cloud Build SA has DB access or use a secure proxy/impersonation)  
     \- name: 'gcr.io/google-appengine/exec-wrapper' \# For running commands needing DB connection  
       args:  
       \- '-i'  
       \- 'YOUR\_GCP\_REGION-docker.pkg.dev/YOUR\_GCP\_PROJECT\_ID/YOUR\_ARTIFACT\_REGISTRY\_REPO/kc-nextjs-backend:$COMMIT\_SHA' \# Use the built image if it has prisma CLI  
       \- '-s'  
       \- 'YOUR\_DB\_INSTANCE\_CONNECTION\_NAME' \# e.g., your-project:your-region:your-instance  
       \# \- '-e' \# Pass environment variables if needed for DB connection  
       \# \- '--'  
       \- 'npx'  
       \- 'prisma'  
       \- 'migrate'  
       \- 'deploy'  
       \# This step is complex due to DB connectivity from Cloud Build.  
       \# Alternative: Run migrations from a GKE job or a Cloud Run job triggered after image push.

     \# Deploy to Cloud Run  
     \- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'  
       entrypoint: gcloud  
       args:  
         \- 'run'  
         \- 'deploy'  
         \- 'kc-nextjs-backend-service' \# Your Cloud Run service name  
         \- '--image=YOUR\_GCP\_REGION-docker.pkg.dev/YOUR\_GCP\_PROJECT\_ID/YOUR\_ARTIFACT\_REGISTRY\_REPO/kc-nextjs-backend:$COMMIT\_SHA'  
         \- '--region=YOUR\_GCP\_REGION'  
         \- '--platform=managed'  
         \- '--allow-unauthenticated' \# Or configure IAM for authenticated access  
         \- '--service-account=YOUR\_BACKEND\_SERVICE\_ACCOUNT\_EMAIL' \# SA for the Cloud Run service  
         \# Add other flags for env vars, secrets, VPC connector, etc.  
     images:  
     \- 'YOUR\_GCP\_REGION-docker.pkg.dev/YOUR\_GCP\_PROJECT\_ID/YOUR\_ARTIFACT\_REGISTRY\_REPO/kc-nextjs-backend:$COMMIT\_SHA'  
     \# Add substitutions for region, project ID, repo name, service name, etc.  
     \# options:  
     \#   machineType: 'E2\_HIGHCPU\_8' \# If build needs more resources

  2. **Create Dockerfile for Next.js:** Ensure it's a multi-stage build optimized for production (copy only necessary files, use non-root user).  
     \# Dockerfile for Next.js application  
     \# Stage 1: Build  
     FROM node:18-alpine AS builder  
     WORKDIR /app  
     COPY package\*.json ./  
     RUN npm install  
     COPY . .  
     RUN npm run prisma:generate  
     RUN npm run build

     \# Stage 2: Production  
     FROM node:18-alpine  
     WORKDIR /app  
     ENV NODE\_ENV production  
     \# If you have a standalone output, copy that. Otherwise, copy necessary files.  
     COPY \--from=builder /app/.next ./.next  
     COPY \--from=builder /app/public ./public  
     COPY \--from=builder /app/package.json ./package.json  
     \# For standalone output, you might only need .next/standalone and public, static  
     \# CMD \["node", ".next/server.js"\] // For default Next.js server  
     \# If using standalone output:  
     \# EXPOSE 3000  
     \# CMD \["node", "server.js"\] // Check path for standalone server.js  
     \# Ensure you copy the node\_modules or relevant parts if not using standalone fully.  
     \# A common pattern for smaller images is to copy only the standalone output.  
     \# RUN npm install \--production (if not using standalone output and copying package.json)  
     \# USER node \# Run as non-root user

     \# Example for standalone output (recommended for smaller images)  
     \# FROM node:18-alpine AS deps  
     \# WORKDIR /app  
     \# COPY package.json package-lock.json ./  
     \# RUN npm install \--production

     \# FROM node:18-alpine AS builder  
     \# WORKDIR /app  
     \# COPY \--from=deps /app/node\_modules ./node\_modules  
     \# COPY . .  
     \# ENV NEXT\_TELEMETRY\_DISABLED 1  
     \# RUN npm run prisma:generate \# Ensure Prisma client is generated  
     \# RUN npm run build \# Ensure outputStandalone is true in next.config.js

     \# FROM node:18-alpine AS runner  
     \# WORKDIR /app  
     \# ENV NODE\_ENV production  
     \# ENV NEXT\_TELEMETRY\_DISABLED 1  
     \# COPY \--from=builder /app/public ./public  
     \# COPY \--from=builder \--chown=nextjs:nodejs /app/.next/standalone ./  
     \# COPY \--from=builder \--chown=nextjs:nodejs /app/.next/static ./.next/static  
     \# USER nextjs \# Assumes nextjs user is created or use an existing non-root user  
     \# EXPOSE 3000  
     \# ENV PORT 3000  
     \# CMD \["node", "server.js"\]

     *(Adjust Dockerfile based on whether you use Next.js standalone output mode for smaller images).*  
  3. **Setup Cloud Build Trigger:** In GCP Console, create a Cloud Build trigger connected to your Git repository and branch.  
  4. **Artifact Registry:** Create a Docker repository in GCP Artifact Registry (e.g., YOUR\_ARTIFACT\_REGISTRY\_REPO) via Terraform or manually.  
  5. **Permissions:** Ensure the Cloud Build service account (PROJECT\_NUMBER@cloudbuild.gserviceaccount.com) has roles like "Artifact Registry Writer," "Cloud Run Admin," "Service Account User" (to impersonate the Cloud Run service SA if needed for deployment), and permissions to access secrets for build-time variables if any. Also, permissions to run prisma migrate deploy (Cloud SQL Client). This is complex and critical.  
  6. **Secrets in Cloud Build:** For build-time secrets (if any, not runtime secrets which Cloud Run handles), use Cloud Build's support for Secret Manager.  
  7. **Database Migrations:** The step for database migrations is tricky from Cloud Build due to network access. Alternatives:  
     * Run migrations from a GKE Job.  
     * Have the application instance run migrations on startup (can be risky for multiple instances).  
     * Use a Cloud Run Job (new feature) specifically for migrations.  
     * The gcloud appengine exec-wrapper is one way but requires the image to have the necessary tools and auth.  
     * **Simplest for now might be to document it as a manual step post-deployment or a separate scripted step until a robust automated solution is built.** For AI coder, focus on build and deploy first, noting migration as a separate concern if the exec-wrapper is too complex to automate initially."

### Ticket ID: KC-GCP-CICD-2

Title: Setup CI/CD Pipeline for GCP Deployment (CrewAI Python Services)  
Epic: KC-GCP-INFRA  
PRD Requirement(s): NFR-DEPLOY-1 (from nfrs\_v1\_1), TC-STACK-8 (from PRD v3.8)  
TDD Reference(s): TDD v1.2, Section 2, Section 9  
Team: DevOps  
Dependencies (Functional): KC-GCP-TERRAFORM-1, KC-GCP-IAM-SECRETS-1 (for CI/CD SA), KC-AI-CREWAI-SETUP-1 (Python service structure and Dockerfile ready). Target GCP Compute service for CrewAI (e.g., Cloud Run service definition) provisioned.  
Dependencies (Technical): CI/CD tool, Docker, GCP Artifact Registry, GCP Compute.  
Human/PM Action Items:

* Confirm if CrewAI services will be in the same mono-repo or separate repositories. This affects trigger configuration.

Description (Functional): Configure a separate CI/CD pipeline (or a distinct part of a mono-repo pipeline) for each CrewAI Python microservice to automate its build, testing, and deployment to GCP compute (e.g., Cloud Run).  
Acceptance Criteria (Functional):

* A CI/CD pipeline is triggered for each CrewAI service on code changes to its specific path/repository.  
* The pipeline builds the Python service Docker image.  
* Automated tests (e.g., pytest) for the Python service are executed.  
* On success, the Docker image is tagged and pushed to Google Artifact Registry.  
* The new image is deployed to its target GCP compute service (e.g., Cloud Run).  
  Technical Approach / Implementation Notes (for AI Vibe Coder):  
* **Prompt for AI Coder (Example for Google Cloud Build, assuming Python service in services/crewai\_service/):** "Create a cloudbuild.yaml file (e.g., services/crewai\_service/cloudbuild.yaml) for the CrewAI Python service.  
  1. **Define cloudbuild.yaml:**  
     steps:  
     \# Install dependencies (using requirements.txt or poetry/pipenv)  
     \- name: 'python:3.10-slim' \# Or your chosen Python version  
       entrypoint: 'pip'  
       args: \['install', '-r', 'services/crewai\_service/requirements.txt', '--user'\] \# Adjust path

     \# Run tests (example using pytest)  
     \- name: 'python:3.10-slim'  
       entrypoint: 'python'  
       args: \['-m', 'pytest', 'services/crewai\_service/tests'\] \# Adjust path

     \# Build Docker image  
     \- name: 'gcr.io/cloud-builders/docker'  
       args: \['build', '-t', 'YOUR\_GCP\_REGION-docker.pkg.dev/YOUR\_GCP\_PROJECT\_ID/YOUR\_ARTIFACT\_REGISTRY\_REPO/kc-crewai-service:$COMMIT\_SHA', '-f', 'services/crewai\_service/Dockerfile', '.'\] \# Ensure Dockerfile path is correct

     \# Push Docker image  
     \- name: 'gcr.io/cloud-builders/docker'  
       args: \['push', 'YOUR\_GCP\_REGION-docker.pkg.dev/YOUR\_GCP\_PROJECT\_ID/YOUR\_ARTIFACT\_REGISTRY\_REPO/kc-crewai-service:$COMMIT\_SHA'\]

     \# Deploy to Cloud Run  
     \- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'  
       entrypoint: gcloud  
       args:  
         \- 'run'  
         \- 'deploy'  
         \- 'kc-crewai-service' \# Your Cloud Run service name for this AI agent  
         \- '--image=YOUR\_GCP\_REGION-docker.pkg.dev/YOUR\_GCP\_PROJECT\_ID/YOUR\_ARTIFACT\_REGISTRY\_REPO/kc-crewai-service:$COMMIT\_SHA'  
         \- '--region=YOUR\_GCP\_REGION'  
         \- '--platform=managed'  
         \# \- '--allow-unauthenticated' \# Or configure IAM, typically these are internal services  
         \- '--service-account=YOUR\_CREWAI\_SERVICE\_ACCOUNT\_EMAIL' \# SA for this Cloud Run service  
         \# Add other flags for env vars (e.g., LLM API key from Secret Manager), secrets, VPC connector  
     images:  
     \- 'YOUR\_GCP\_REGION-docker.pkg.dev/YOUR\_GCP\_PROJECT\_ID/YOUR\_ARTIFACT\_REGISTRY\_REPO/kc-crewai-service:$COMMIT\_SHA'

  2. **Ensure Dockerfile exists for the Python service** (created in KC-AI-CREWAI-SETUP-1).  
  3. **Setup Cloud Build Trigger:** Configure trigger for the specific path of this service if in a mono-repo, or for its dedicated repository.  
  4. **Permissions:** Ensure Cloud Build SA has necessary permissions similar to KC-GCP-CICD-1 but for deploying this service."

### Ticket ID: KC-GCP-MONITOR-1

Title: Configure Basic Monitoring and Alerting on GCP  
Epic: KC-GCP-INFRA  
PRD Requirement(s): NFR-REL-6 (from nfrs\_v1\_1), TC-STACK-8 (from PRD v3.8)  
TDD Reference(s): TDD v1.2, Section 2  
Team: DevOps  
Dependencies (Functional): KC-GCP-CICD-1, KC-GCP-CICD-2 (Application services deployed to GCP and generating logs/metrics).  
Dependencies (Technical): Google Cloud Monitoring, Google Cloud Logging APIs enabled.  
Human/PM Action Items:

* Define critical alert thresholds and notification channels (e.g., email, PagerDuty).

Description (Functional): Setup basic monitoring dashboards and alerts in Google Cloud's operations suite (Cloud Monitoring, Cloud Logging) for key metrics of the deployed application services (Next.js backend, CrewAI services) and infrastructure (Cloud SQL, Memorystore, Cloud Run/GKE).  
Acceptance Criteria (Functional):

* Custom dashboards are created in Cloud Monitoring to visualize key metrics:  
  * For Cloud Run/GKE services: CPU utilization, memory utilization, request count, latency, error rates (5xx).  
  * For Cloud SQL: CPU utilization, memory utilization, disk I/O, disk space, number of connections, query latency (if available).  
  * For Memorystore for Redis: CPU utilization, memory utilization, cache hit rate.  
  * For BullMQ (if metrics exposed): Queue lengths, job failure rates.  
* Alerts are configured in Cloud Monitoring for critical thresholds (e.g., sustained high CPU \>80%, high 5xx error rate \>1% for 5 mins, low disk space on DB \<10%, Redis memory usage \>80%, critical health check failures).  
* Application logs from Next.js backend and CrewAI services are consistently collected and searchable in Google Cloud Logging.  
* Error reporting (e.g., Google Cloud Error Reporting or Sentry, if integrated) is configured and capturing backend exceptions.  
  Technical Approach / Implementation Notes (for AI Vibe Coder):  
* **Prompt for AI Coder:** "Your task is to set up monitoring and alerting for the application on GCP.  
  1. **Create Custom Dashboards in Cloud Monitoring:**  
     * Go to the GCP Console \-\> Monitoring \-\> Dashboards.  
     * Create a new dashboard (e.g., "Knowledge Card App Overview").  
     * Add widgets for key metrics from Cloud Run (for Next.js and CrewAI services), Cloud SQL, and Memorystore. Examples:  
       * Cloud Run: Request Count, Request Latency (p50, p95), Container CPU, Container Memory. Filter by service name.  
       * Cloud SQL: CPU Utilization, Memory Utilization, Disk Space Used, Active Connections.  
       * Memorystore: CPU Utilization, Memory Usage Ratio, Cache Hit Ratio.  
  2. **Configure Alerting Policies in Cloud Monitoring:**  
     * Go to Monitoring \-\> Alerting \-\> Create Policy.  
     * For each critical metric, define a condition (e.g., Cloud Run Service \- Request Count \- 5xx errors \> X for Y minutes).  
     * Configure notification channels (e.g., Email, PagerDuty \- requires setup).  
     * Example alerts:  
       * High 5xx error rate on Cloud Run services.  
       * High CPU/Memory on Cloud Run services.  
       * High CPU/Memory/Disk on Cloud SQL.  
       * Low available disk space on Cloud SQL.  
       * High memory usage on Memorystore.  
  3. **Verify Log Collection in Cloud Logging:**  
     * Ensure your Next.js and Python applications are writing logs to stdout/stderr. These are automatically collected by Cloud Logging when running on Cloud Run/GKE.  
     * Ensure logs are structured (e.g., JSON format) if possible, for easier querying and analysis in Cloud Logging. Libraries like pino for Node.js or Python's standard logging with a JSON formatter can be used.  
  4. **Setup Error Reporting:**  
     * If using Google Cloud Error Reporting, ensure your application runtimes are configured to send exceptions (often automatic for some languages/frameworks on GCP, or via client libraries).  
     * If using Sentry, ensure the Sentry DSN is configured in your application services (via Secret Manager).  
  5. **Document:** Briefly document the created dashboards and key alerts."