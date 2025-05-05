\# Review and AI Prompts for KC-INFRA Epic (Stage 2 \- GCP)

This document contains the technical review and AI development prompts for the KC-INFRA epic. This epic focuses on building the \*\*Google Cloud Platform (GCP)\*\* cloud infrastructure using Terraform and establishing CI/CD pipelines for the Knowledge Card application, marking the transition towards Stage 2 deployment readiness on GCP.

\---

\#\# Part 1: Tech Lead Review of KC-INFRA Epic (Stage 2 \- GCP)

This epic lays the foundation for hosting the application in GCP. It involves provisioning all necessary GCP resources using Infrastructure as Code (IaC) with Terraform and automating the build and deployment process using a CI/CD pipeline (GitHub Actions). This is a critical step towards a scalable, secure, and maintainable production environment on GCP.

\#\#\# A. Scope and Purpose:

\* \*\*Infrastructure as Code (IaC):\*\* Defines the entire cloud environment (networking, compute, database, cache, storage, load balancing, monitoring, secrets) using Terraform with the Google Provider, ensuring reproducibility and version control.  
\* \*\*Containerization & Serverless Compute:\*\* Creates an optimized production Docker image and deploys it using \*\*GCP Cloud Run\*\* for serverless container management.  
\* \*\*Managed Services:\*\* Leverages GCP managed services like \*\*Cloud SQL for PostgreSQL\*\* (with pgvector), \*\*Memorystore for Redis\*\*, \*\*Artifact Registry\*\*, \*\*Cloud Storage\*\*, \*\*Secret Manager\*\*, \*\*Cloud Load Balancing (Global HTTP/S)\*\*, and \*\*Cloud Logging/Monitoring\*\* to reduce operational overhead.  
\* \*\*CI/CD Automation:\*\* Enhances the existing placeholder pipeline to fully automate building, pushing Docker images to Artifact Registry, running database migrations, and deploying updates to Cloud Run.  
\* \*\*Security & Availability:\*\* Incorporates security best practices (GCP IAM least privilege, Firewall Rules, Secret Manager, Workload Identity Federation) and high availability patterns (Cloud SQL HA, multiple Cloud Run instances via Load Balancer).

\#\#\# B. Key Technical Points & Considerations:

\* \*\*Terraform:\*\* The core tool for infrastructure provisioning using the \`google\` provider. Requires setting up remote state (GCS) and careful management of resources, variables, and potentially modules.  
\* \*\*GCP Services:\*\* Involves provisioning and configuring a wide range of GCP services. Correct configuration (e.g., VPC routing, Firewall rules, IAM permissions, Cloud Run service definitions, Private Service Access) is crucial.  
\* \*\*Docker & Cloud Run:\*\* Requires a well-optimized multi-stage Dockerfile (\`KC-INFRA-DO-3-GCP\`) using the Next.js standalone output. Cloud Run simplifies deployment by removing the need to manage underlying infrastructure. The application must listen on the \`PORT\` environment variable (usually 8080).  
\* \*\*pgvector on Cloud SQL (\`KC-INFRA-DO-5-GCP\`):\*\* Requires ensuring the chosen PostgreSQL version supports pgvector and explicitly running \`CREATE EXTENSION IF NOT EXISTS vector;\` (likely via a Prisma migration step) after the instance is provisioned.  
\* \*\*Secrets Management (\`KC-INFRA-DO-10-GCP\`):\*\* Uses GCP Secret Manager. The chosen approach is to mount secrets into the Cloud Run service as environment variables for simplicity.  
\* \*\*CI/CD (\`KC-INFRA-DO-11-GCP\`):\*\* Uses GitHub Actions with \*\*Workload Identity Federation\*\* for secure GCP authentication (recommended over service account keys). Leverages helper actions (\`google-github-actions/...\`) to simplify Artifact Registry login and Cloud Run deployment. \*\*Crucially includes a step for database migrations (\`prisma migrate deploy\`) using Cloud SQL Proxy.\*\*  
\* \*\*Networking:\*\* Establishes a standard VPC network structure with subnets, Cloud NAT, and carefully configured Firewall Rules (\`KC-INFRA-DO-2-GCP\`, \`KC-INFRA-DO-13-GCP\`). Private Service Access is needed for Cloud SQL and Memorystore.  
\* \*\*Monitoring & Logging (\`KC-INFRA-DO-12-GCP\`):\*\* Sets up observability using Cloud Logging (automatic integration with Cloud Run) and Cloud Monitoring metric alert policies.

\#\#\# C. Potential Gaps/Refinements:

\* \*\*Terraform Modules:\*\* While mentioned, the prompts don't strictly enforce using Terraform modules. For maintainability, structuring the Terraform code into modules (e.g., \`vpc\`, \`cloud-sql\`, \`cloud-run\`) is highly recommended (prompts updated).  
\* \*\*CI/CD Testing Stages:\*\* The CI/CD pipeline focuses on build, migrate, and deploy. Adding automated testing stages (unit, integration, E2E) is essential for true CI but might be considered post-Stage 2 setup.  
\* \*\*Cost Optimization:\*\* Initial instance/machine types are suggested to start small, but ongoing cost monitoring and optimization strategies (e.g., Committed Use Discounts, Cloud Run min instances set to 0\) are not covered here.  
\* \*\*Advanced Security:\*\* Topics like Cloud Armor (WAF), detailed Security Command Center setup, or more sophisticated IAM conditions are outside this initial scope.  
\* \*\*Database Migration Robustness:\*\* The added migration step is crucial. Error handling, rollback strategies for migrations, and potential locking mechanisms during deployment need careful consideration in a production scenario.

\#\#\# D. Overall:

This is a comprehensive infrastructure epic that sets up a robust and modern GCP environment using best practices like IaC, serverless containers, and managed services. Successful implementation requires strong understanding of GCP services and Terraform. The inclusion of the database migration step in the CI/CD pipeline is a key improvement.

\---

\#\# Part 2: AI Development Prompts for KC-INFRA Epic (Stage 2 \- GCP)

\*(Prompts reference the full suite of project documents and incorporate review findings)\*  
\*(Note: While these prompts cover foundational security elements like IAM roles and Firewall Rules, more advanced security configurations like Cloud Armor, Security Command Center analysis, detailed VPC Flow Log analysis, etc., are considered out of scope for this initial Stage 2 setup.)\*

\#\#\# 1\. Ticket: KC-INFRA-DO-1-GCP: Setup GCP Project & Foundational IAM Roles/Users

\* \*\*Prompt:\*\* Establish the GCP project structure and initial IAM configuration following best practices, as specified in JIRA Ticket \`KC-INFRA-DO-1-GCP\`.  
    \* Secure user accounts (enable MFA). Assign appropriate basic roles (e.g., \`roles/viewer\`) and grant more specific roles as needed.  
    \* Create IAM Service Accounts:  
        \* \`terraform-executor-sa@PROJECT\_ID.iam.gserviceaccount.com\`: For Terraform execution. Grant necessary roles (e.g., \`roles/owner\` initially, then refine to \`roles/compute.admin\`, \`roles/cloudsql.admin\`, \`roles/storage.admin\`, \`roles/artifactregistry.admin\`, \`roles/run.admin\`, \`roles/redis.admin\`, \`roles/secretmanager.admin\`, \`roles/logging.admin\`, \`roles/monitoring.admin\`, \`roles/iam.serviceAccountUser\`, \`roles/serviceusage.serviceUsageAdmin\`). Manage credentials securely (ADC preferred).  
        \* \`cicd-pipeline-sa@PROJECT\_ID.iam.gserviceaccount.com\`: For GitHub Actions. Grant necessary roles: \`roles/artifactregistry.writer\`, \`roles/run.developer\`, \`roles/secretmanager.secretAccessor\`, \`roles/iam.serviceAccountUser\`, \`roles/cloudsql.client\` (for proxy connection).  
    \* Configure Workload Identity Federation: Create a WIF Pool and Provider linking to your GitHub repository. Allow assertions from GitHub Actions to impersonate \`cicd-pipeline-sa\`.  
    \* Configure GCP credentials securely for local Terraform execution (e.g., \`gcloud auth application-default login\`).  
    \* Set up basic GCP Billing budget alerts.

\#\#\# 2\. Ticket: KC-INFRA-DO-2-GCP: Define VPC Network & Networking Structure (Terraform)

\* \*\*Prompt:\*\* Create the core GCP networking infrastructure using Terraform, as specified in JIRA Ticket \`KC-INFRA-DO-2-GCP\`.  
    \* Initialize Terraform project (\`terraform init\`).  
    \* Configure Terraform Remote State Backend using GCS.  
    \* Define \`google\_compute\_network\` (custom mode: \`auto\_create\_subnetworks=false\`).  
    \* Define \`google\_compute\_subnetwork\` resources in target region(s) with appropriate IP CIDR ranges. Enable \`private\_ip\_google\_access\` if needed.  
    \* Define default deny ingress/egress \`google\_compute\_firewall\` rules.  
    \* Define \`google\_compute\_router\` in the target region.  
    \* Define \`google\_compute\_router\_nat\` associated with the router, configured for relevant subnets to allow egress.  
    \* Use variables for region, CIDRs, project ID, tags. \*\*Strongly recommend structuring this configuration using Terraform modules (e.g., \`modules/vpc\`).\*\*  
    \* Run \`terraform plan\` and \`terraform apply\`. Verify resources in GCP console.

\#\#\# 3\. Ticket: KC-INFRA-DO-13-GCP: Configure Firewall Rules (Terraform)

\* \*\*Prompt:\*\* Define necessary GCP Firewall Rules using Terraform, as specified in JIRA Ticket \`KC-INFRA-DO-13-GCP\`.  
    \* Define \`google\_compute\_firewall\` resources associated with the VPC network from \`KC-INFRA-DO-2-GCP\`.  
    \* Configure rules using \`allow\` blocks (protocol/ports) and appropriate \`source\_ranges\`, \`target\_tags\`, or \`target\_service\_accounts\`.  
    \* Rules needed:  
        \* Allow HTTP/HTTPS ingress (TCP 80, 443\) from \`0.0.0.0/0\` to Load Balancer target tag (\`lb-tag\`).  
        \* Allow Health Check ingress (TCP relevant port) from Google health check ranges (\`130.211.0.0/22\`, \`35.191.0.0/16\`) to application target tag (\`app-tag\`).  
        \* Allow internal traffic from \`app-tag\`/\`app-runtime-sa\` to Cloud SQL (TCP 5432\) target tag/SA (\`sql-tag\`).  
        \* Allow internal traffic from \`app-tag\`/\`app-runtime-sa\` to Memorystore (TCP 6379\) target tag/SA (\`redis-tag\`).  
    \* Apply least privilege. Assign tags/service accounts to resources in subsequent tickets.  
    \* \*\*Strongly recommend defining Firewall Rules within a dedicated Terraform module (e.g., \`modules/firewall\`) or alongside relevant service modules.\*\*  
    \* Run \`terraform plan\` and \`terraform apply\`.

\#\#\# 4\. Ticket: KC-INFRA-DO-3-GCP: Create Production Dockerfile (Multi-stage)

\* \*\*Prompt:\*\* Create an optimized, multi-stage Dockerfile at the project root for the Next.js application, suitable for Cloud Run, as specified in JIRA Ticket \`KC-INFRA-DO-3-GCP\`.  
    \* Ensure \`output: 'standalone'\` is enabled in \`next.config.js\`.  
    \* Create \`Dockerfile\` (referencing the structure in the JIRA ticket, ensuring non-root user and listening on \`PORT\` env var, likely 8080).  
    \* Create a \`.dockerignore\` file.  
    \* Build locally (\`docker build \-t knowledge-card-app .\`).  
    \* Test running locally (\`docker run \-p 8080:8080 \-e PORT=8080 knowledge-card-app\`).

\#\#\# 5\. Ticket: KC-INFRA-DO-4-GCP: Setup Artifact Registry Repository (Terraform)

\* \*\*Prompt:\*\* Create a private GCP Artifact Registry repository (Docker format) using Terraform, as specified in JIRA Ticket \`KC-INFRA-DO-4-GCP\`.  
    \* Add \`google\_artifact\_registry\_repository\` resource to Terraform code. Set \`format \= "DOCKER"\`, specify \`location\` and \`repository\_id\`. Enable scanning if desired.  
    \* Ensure the CI/CD service account (\`cicd-pipeline-sa\`) has \`roles/artifactregistry.writer\` via \`google\_artifact\_registry\_repository\_iam\_member\`.  
    \* Run \`terraform plan\` and \`terraform apply\`.  
    \* Note the repository URL (e.g., \`REGION-docker.pkg.dev/PROJECT\_ID/REPOSITORY\_ID\`) for CI/CD.

\#\#\# 6\. Ticket: KC-INFRA-DO-5-GCP: Setup Cloud SQL PostgreSQL Instance (Terraform, enable pgvector)

\* \*\*Prompt:\*\* Provision a Cloud SQL PostgreSQL instance (HA, Private IP, pgvector support) using Terraform, as specified in JIRA Ticket \`KC-INFRA-DO-5-GCP\`.  
    \* Ensure Private Service Access is configured (\`google\_compute\_global\_address\`, \`google\_service\_networking\_connection\`).  
    \* Define \`google\_sql\_database\_instance\`: Set \`database\_version\` (e.g., \`POSTGRES\_15\`), \`region\`, \`settings.tier\` (machine type), \`settings.availability\_type \= "REGIONAL"\`, \`settings.ip\_configuration.private\_network\`. Source \`root\_password\` from Secret Manager (\`KC-INFRA-DO-10-GCP\`). Enable backups. Check flags/methods for enabling \`pgvector\`.  
    \* Define \`google\_sql\_database\` for the application DB (\`knowledge\_cards\`).  
    \* Define \`google\_sql\_user\` for the application user, sourcing password from Secret Manager.  
    \* \*\*Strongly recommend defining Cloud SQL and related resources within a dedicated Terraform module (e.g., \`modules/cloud-sql\`).\*\*  
    \* Run \`terraform plan\` and \`terraform apply\`.  
    \* \*\*Post-Provisioning/Migration:\*\* Ensure \`CREATE EXTENSION IF NOT EXISTS vector;\` is run (via Prisma migration step in CI/CD pipeline \`KC-INFRA-DO-11-GCP\`).

\#\#\# 7\. Ticket: KC-INFRA-DO-6-GCP: Setup Memorystore Redis Instance (Terraform)

\* \*\*Prompt:\*\* Provision a Memorystore Redis instance using Terraform, as specified in JIRA Ticket \`KC-INFRA-DO-6-GCP\`.  
    \* Ensure Private Service Access is configured.  
    \* Define \`google\_redis\_instance\`: Set \`tier\` (e.g., \`BASIC\`), \`memory\_size\_gb\`, \`location\_id\`, \`authorized\_network\`.  
    \* \*\*Strongly recommend defining Memorystore within a dedicated Terraform module (e.g., \`modules/redis\`).\*\*  
    \* Run \`terraform plan\` and \`terraform apply\`.  
    \* Note the instance host IP and port for application configuration.

\#\#\# 8\. Ticket: KC-INFRA-DO-7-GCP: Setup Cloud Storage Bucket (Terraform)

\* \*\*Prompt:\*\* Provision a private Cloud Storage bucket using Terraform, as specified in JIRA Ticket \`KC-INFRA-DO-7-GCP\`.  
    \* Define \`google\_storage\_bucket\` with a unique name, location, and \`uniform\_bucket\_level\_access \= true\`.  
    \* Define \`google\_storage\_bucket\_iam\_member\` resources granting the application's runtime service account (\`app-runtime-sa\`) the roles \`roles/storage.objectCreator\` and \`roles/storage.objectViewer\`.  
    \* \*\*Consider defining the GCS bucket and IAM within a dedicated Terraform module (e.g., \`modules/gcs\`).\*\*  
    \* Run \`terraform plan\` and \`terraform apply\`.  
    \* Note the bucket name for application configuration.

\#\#\# 9\. Ticket: KC-INFRA-DO-10-GCP: Setup Secrets Management (GCP Secret Manager, Terraform)

\* \*\*Prompt:\*\* Set up GCP Secret Manager for sensitive data using Terraform, as specified in JIRA Ticket \`KC-INFRA-DO-10-GCP\`.  
    \* Define \`google\_secret\_manager\_secret\` resources for DB credentials (root password, app user password/connection string), NextAuth Secret, etc.  
    \* Define \`google\_secret\_manager\_secret\_version\` to populate initial values (use \`random\_string\` or variables, avoid plaintext).  
    \* Define \`google\_secret\_manager\_secret\_iam\_member\` resources granting the application's runtime service account (\`app-runtime-sa\`) the \`roles/secretmanager.secretAccessor\` role for each required secret.  
    \* \*\*Consider defining secrets within relevant Terraform modules or a dedicated secrets module.\*\*  
    \* Run \`terraform plan\` and \`terraform apply\`.  
    \* Reference these secret versions when defining environment variables in the Cloud Run service (\`KC-INFRA-DO-8-GCP\`).

\#\#\# 10\. Ticket: KC-INFRA-DO-8-GCP: Setup Cloud Run Service Definition (Terraform)

\* \*\*Prompt:\*\* Provision the Cloud Run service using Terraform, as specified in JIRA Ticket \`KC-INFRA-DO-8-GCP\`.  
    \* Define runtime IAM Service Account (\`app-runtime-sa\`) via \`google\_service\_account\`. Grant necessary roles (Cloud SQL Client, Storage Object Admin/Viewer, Secret Accessor) via IAM bindings.  
    \* Define \`google\_vpc\_access\_connector\`.  
    \* Define \`google\_cloud\_run\_v2\_service\`:  
        \* Set \`location\`, \`name\`.  
        \* \`template.containers.image\`: Use Artifact Registry image URL (tag updated by CI/CD).  
        \* \`template.containers.ports\`: Set \`container\_port \= 8080\`.  
        \* \`template.containers.resources\`: Define CPU/Memory limits.  
        \* \`template.containers.env\`: Define \`PORT=8080\`, \`NODE\_ENV=production\`, other non-sensitive vars. Mount secrets using \`value\_source.secret\_key\_ref\`.  
        \* \`template.service\_account\`: Assign the \`app-runtime-sa\`.  
        \* \`template.vpc\_access\`: Configure connector and egress.  
        \* Set \`ingress\` (e.g., \`INGRESS\_TRAFFIC\_INTERNAL\_LOAD\_BALANCER\`).  
        \* Set \`template.scaling\` (min/max instances).  
    \* \*\*Strongly recommend defining Cloud Run and related resources (SA, VPC Connector) within a dedicated Terraform module (e.g., \`modules/cloud-run\`).\*\*  
    \* Run \`terraform plan\` and \`terraform apply\`.

\#\#\# 11\. Ticket: KC-INFRA-DO-9-GCP: Setup Cloud Load Balancer & DNS (Terraform)

\* \*\*Prompt:\*\* Provision a Global HTTP(S) Load Balancer and configure Cloud DNS using Terraform, as specified in JIRA Ticket \`KC-INFRA-DO-9-GCP\`.  
    \* Ensure an SSL certificate is provisioned (Google-managed \`google\_compute\_managed\_ssl\_certificate\` or Certificate Manager) and validated.  
    \* Define \`google\_compute\_global\_address\` for static IP.  
    \* Define \`google\_compute\_health\_check\` for \`/api/health\`.  
    \* Define \`google\_compute\_region\_network\_endpoint\_group\` (Serverless NEG) pointing to the Cloud Run service (\`KC-INFRA-DO-8-GCP\`).  
    \* Define \`google\_compute\_backend\_service\` using the Serverless NEG and health check. Set \`load\_balancing\_scheme \= "EXTERNAL\_MANAGED"\`.  
    \* Define \`google\_compute\_url\_map\` routing traffic to the backend service.  
    \* Define \`google\_compute\_target\_https\_proxy\` using the URL map and SSL certificate.  
    \* Define \`google\_compute\_global\_forwarding\_rule\` for HTTPS (443) using the proxy and static IP.  
    \* Define \`google\_compute\_global\_forwarding\_rule\` for HTTP (80) to redirect to HTTPS.  
    \* Define \`google\_dns\_record\_set\` (Type A) pointing your domain to the static IP address.  
    \* \*\*Strongly recommend defining Load Balancer and DNS resources within dedicated Terraform modules (e.g., \`modules/lb\`, \`modules/dns\`).\*\*  
    \* Run \`terraform plan\` and \`terraform apply\`.

\#\#\# 12\. Ticket: KC-INFRA-BE-1-GCP: Implement Health Check Endpoint

\* \*\*Prompt:\*\* Implement a simple health check endpoint (\`/api/health\`) in the Next.js application, as specified in JIRA Ticket \`KC-INFRA-BE-1-GCP\`.  
    \* Create \`src/app/api/health/route.ts\`.  
    \* Implement the \`GET\` handler returning \`{ status: 'ok' }\` with a 200 status code.  
    \* Ensure no authentication is required. Test locally.

\#\#\# 13\. Ticket: KC-INFRA-DO-12-GCP: Setup Basic Cloud Logging/Monitoring (Terraform)

\* \*\*Prompt:\*\* Configure basic Cloud Logging and Monitoring using Terraform, as specified in JIRA Ticket \`KC-INFRA-DO-12-GCP\`.  
    \* Configure log bucket retention in Cloud Logging if needed (defaults may suffice).  
    \* Define \`google\_monitoring\_notification\_channel\` (e.g., email).  
    \* Define \`google\_monitoring\_alert\_policy\` resources for key metrics:  
        \* Cloud Run 5xx errors (\`run.googleapis.com/request\_count\` filter status 5xx).  
        \* Cloud Run latency (\`run.googleapis.com/request\_latencies\`).  
        \* Cloud Run container CPU/Memory utilization.  
        \* LB Backend health (\`loadbalancing.googleapis.com/backend\_health\`).  
        \* LB 5xx errors (\`loadbalancing.googleapis.com/https/request\_count\` filter status 5xx).  
    \* Link notification channels to alert policies.  
    \* \*\*Consider defining Monitoring resources within relevant service modules or a dedicated monitoring module.\*\*  
    \* Run \`terraform plan\` and \`terraform apply\`. Verify alerts and logs.

\#\#\# 14\. Ticket: KC-INFRA-DO-11-GCP: Enhance CI/CD Pipeline for GCP Deployment (GitHub Actions)

\* \*\*Prompt:\*\* Update the GitHub Actions workflow (\`.github/workflows/deploy.yml\`) for automated GCP deployment, including DB migrations, as specified in JIRA Ticket \`KC-INFRA-DO-11-GCP\`.  
    \* Trigger workflow on push/merge to \`main\`.  
    \* \*\*Authenticate to GCP:\*\* Use \`google-github-actions/auth\` with Workload Identity Federation (provide WIF provider, SA email \`cicd-pipeline-sa\`).  
    \* \*\*Setup gcloud:\*\* Use \`google-github-actions/setup-gcloud\`.  
    \* \*\*Configure Docker:\*\* Use \`gcloud auth configure-docker REGION-docker.pkg.dev\`.  
    \* \*\*Build, Tag, Push:\*\* Use \`docker build\`, \`docker tag\`, \`docker push\` targeting the Artifact Registry repository URL (\`REGION-docker.pkg.dev/PROJECT\_ID/REPOSITORY\_ID/IMAGE\_NAME:${{ github.sha }}\`).  
    \* \*\*Run DB Migrations (Critical Step):\*\*  
        \* Add step to download and start Cloud SQL Proxy (\`wget ...\`, \`./cloud-sql-proxy ...\`). Requires DB instance connection name.  
        \* Run migrations: \`DATABASE\_URL="postgresql://USER:PASSWORD@127.0.0.1:5432/DB\_NAME" npx prisma migrate deploy\`. Fetch \`USER\`, \`PASSWORD\`, \`DB\_NAME\` securely (e.g., from Secret Manager via \`gcloud secrets versions access latest \--secret=SECRET\_ID\`).  
        \* Stop Cloud SQL Proxy.  
    \* \*\*Deploy to Cloud Run:\*\* Use \`google-github-actions/deploy-cloudrun\`. Provide \`service\`, \`region\`, and \`image\` (using the pushed image tag).  
    \* Use GitHub secrets for sensitive values (Project ID, Region, SA email, WIF Provider, Secret IDs, etc.).  
    \* Test thoroughly by merging changes. Monitor workflow, Artifact Registry, Cloud SQL (migrations), and Cloud Run deployment status.

