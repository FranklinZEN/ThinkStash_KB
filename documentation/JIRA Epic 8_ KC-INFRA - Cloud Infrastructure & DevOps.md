## **JIRA Epic: KC-INFRA \- Cloud Infrastructure & DevOps (Stage 2\)**

**Rationale:** Build the scalable, secure, and maintainable cloud environment on AWS required to host the production application, database, cache, storage, and support CI/CD processes.

Ticket ID: KC-INFRA-DO-1  
Title: Setup AWS Account & Foundational IAM Roles/Users  
Epic: KC-INFRA  
PRD Requirement(s): Implied by Cloud Deployment  
Team: DO  
Dependencies (Functional): KC-TRANSITION-DO-1 (AWS Confirmed)  
UX/UI Design Link: N/A  
Description (Functional): Establish the AWS account structure and create initial IAM users/roles with appropriate permissions for infrastructure management (Terraform) and CI/CD pipelines, following security best practices.  
Acceptance Criteria (Functional):

* AWS account is accessible.  
* An IAM user or role exists with permissions to manage necessary resources via Terraform (e.g., VPC, EC2, RDS, S3, ECS, ECR, ElastiCache, IAM, Secrets Manager, CloudWatch).  
* An IAM user or role exists with permissions needed by the CI/CD pipeline (e.g., push to ECR, update ECS service, potentially manage secrets).  
* Least privilege principle is applied.  
* Root account access is secured and not used for routine operations.  
* Billing alerts are configured.  
  Technical Approach / Implementation Notes:  
* Follow AWS best practices for setting up a new account (secure root user, enable MFA).  
* Create dedicated IAM users for administrators/DevOps engineers with MFA enabled.  
* Create specific IAM roles:  
  * TerraformExecutionRole: Role assumed by users or CI/CD to apply Terraform changes. Grant necessary permissions (consider managed policies like AdministratorAccess initially for setup, then refine to least privilege).  
  * CICDPipelineRole: Role assumed by GitHub Actions (or other CI/CD tool). Grant permissions like AmazonEC2ContainerRegistryFullAccess, AmazonECS\_FullAccess (or more granular), permissions to read from Secrets Manager, etc.  
* Configure AWS credentials securely for Terraform execution (e.g., using AWS SSO, environment variables, or instance profiles if run from EC2). Configure credentials for CI/CD using OIDC connection (recommended for GitHub Actions) or dedicated IAM user keys stored as secrets.  
* Set up basic budget alerts in AWS Billing.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved: AWS Console (IAM, Billing).  
  Testing Considerations (Technical): Verify Terraform can authenticate and plan changes. Verify CI/CD role can perform necessary actions (e.g., push test image to ECR).  
  Dependencies (Technical): AWS Account access.

Ticket ID: KC-INFRA-DO-2  
Title: Define VPC & Networking Structure (Terraform)  
Epic: KC-INFRA  
PRD Requirement(s): Implied by Cloud Deployment  
Team: DO  
Dependencies (Functional): KC-INFRA-DO-1  
UX/UI Design Link: N/A  
Description (Functional): Create the foundational network infrastructure within AWS using Terraform, including a Virtual Private Cloud (VPC), subnets, route tables, internet gateway, and NAT gateway for secure and scalable resource placement.  
Acceptance Criteria (Functional):

* Terraform code defines a custom VPC.  
* Public and private subnets are created across multiple Availability Zones (AZs) for high availability.  
* Route tables correctly direct traffic (public subnets via Internet Gateway, private subnets via NAT Gateway).  
* An Internet Gateway (IGW) is attached to the VPC for public internet access.  
* A NAT Gateway (or Instance) is provisioned in a public subnet to allow outbound internet access from private subnets (e.g., for application updates, external API calls).  
* Terraform state is managed remotely (e.g., using S3 backend with DynamoDB locking).  
  Technical Approach / Implementation Notes:  
* Initialize Terraform project (terraform init). Configure remote state backend (S3 bucket, DynamoDB table \- create these manually first or via separate minimal Terraform).  
* Use Terraform AWS Provider.  
* Define VPC resource (aws\_vpc) with appropriate CIDR block.  
* Define subnets (aws\_subnet) for public and private tiers across \>=2 AZs. Tag subnets appropriately.  
* Define Internet Gateway (aws\_internet\_gateway) and attach to VPC.  
* Define NAT Gateway (aws\_nat\_gateway) with an associated Elastic IP (aws\_eip). Place NAT GW in a public subnet.  
* Define Route Tables (aws\_route\_table):  
  * Public route table associated with public subnets, default route (0.0.0.0/0) pointing to IGW.  
  * Private route table(s) associated with private subnets, default route pointing to NAT Gateway.  
* Use Terraform variables for region, AZs, CIDR blocks, environment names.  
* Structure Terraform code using modules (e.g., VPC module, subnet module) for reusability if planning multiple environments.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Terraform configuration files (.tf)  
* Terraform AWS Provider resources (aws\_vpc, aws\_subnet, aws\_route\_table, aws\_internet\_gateway, aws\_nat\_gateway, aws\_eip)  
* Terraform state backend configuration.  
  Testing Considerations (Technical): Run terraform plan and terraform apply. Verify network connectivity from resources launched in subnets (e.g., test outbound connection from private subnet via NAT). Review VPC Flow Logs if needed.  
  Dependencies (Technical): KC-INFRA-DO-1 (Permissions), Terraform installed.

Ticket ID: KC-INFRA-DO-13 (Generated)  
Title: Configure Security Groups (Terraform)  
Epic: KC-INFRA  
PRD Requirement(s): NFR-SEC-1 (Implied)  
Team: DO  
Dependencies (Functional): KC-INFRA-DO-2 (VPC/Subnets defined)  
UX/UI Design Link: N/A  
Description (Functional): Define network security rules using AWS Security Groups via Terraform to control inbound and outbound traffic for application components (ALB, ECS tasks, Database, Cache).  
Acceptance Criteria (Functional):

* Terraform code defines necessary Security Groups (SGs).  
* ALB SG allows inbound HTTP/HTTPS traffic (ports 80/443) from the internet (0.0.0.0/0).  
* ECS Task SG allows inbound traffic from the ALB SG on the application port (e.g., 3000). Outbound access allows connections to RDS, ElastiCache, and potentially external APIs via NAT GW.  
* RDS SG allows inbound traffic from the ECS Task SG on the PostgreSQL port (5432).  
* ElastiCache SG allows inbound traffic from the ECS Task SG on the Redis port (6379).  
* SGs follow the principle of least privilege.  
  Technical Approach / Implementation Notes:  
* Define aws\_security\_group resources in Terraform.  
* Use ingress and egress blocks to define rules.  
* Reference other security groups by ID for source/destination rules (e.g., ECS task SG allows ingress from source\_security\_group\_id \= aws\_security\_group.alb.id).  
* Use variables for ports.  
* Example Rules:  
  * aws\_security\_group.alb: Ingress TCP 80/443 from 0.0.0.0/0. Egress all to 0.0.0.0/0 (or restrict if needed).  
  * aws\_security\_group.ecs\_task: Ingress TCP 3000 (app port) from aws\_security\_group.alb.id. Egress TCP 5432 to aws\_security\_group.rds.id. Egress TCP 6379 to aws\_security\_group.redis.id. Egress TCP 443 to 0.0.0.0/0 (for external APIs via NAT).  
  * aws\_security\_group.rds: Ingress TCP 5432 from aws\_security\_group.ecs\_task.id.  
  * aws\_security\_group.redis: Ingress TCP 6379 from aws\_security\_group.ecs\_task.id.  
* Associate SGs with relevant resources (ALB, ECS Service, RDS Instance, ElastiCache Cluster) in their respective Terraform configurations (KC-INFRA-DO-5, 6, 8, 9).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Terraform configuration files (.tf)  
* aws\_security\_group resources.  
  Testing Considerations (Technical): Run terraform plan/apply. Verify connectivity between resources after deployment (e.g., app connects to DB). Use AWS Network Reachability Analyzer if needed.  
  Dependencies (Technical): KC-INFRA-DO-2

Ticket ID: KC-INFRA-DO-3  
Title: Create Production Dockerfile (Multi-stage)  
Epic: KC-INFRA  
PRD Requirement(s): Implied by Container Deployment (ECS)  
Team: BE/DO  
Dependencies (Functional): KC-SETUP-1 (Next.js project)  
UX/UI Design Link: N/A  
Description (Functional): Create an optimized, multi-stage Dockerfile for building the Next.js application container image suitable for production deployment on ECS/Fargate.  
Acceptance Criteria (Functional):

* A Dockerfile exists at the project root.  
* Uses multi-stage builds to minimize final image size.  
* Installs dependencies, builds the Next.js application, and copies only necessary artifacts to the final stage.  
* Runs the application using a non-root user for security.  
* Exposes the correct application port (e.g., 3000).  
* Includes health check instruction.  
  Technical Approach / Implementation Notes:  
* Create Dockerfile.  
* **Stage 1: Dependencies**  
  * FROM node:18-alpine AS deps (Use specific Node version, alpine for smaller size)  
  * WORKDIR /app  
  * Copy package.json, package-lock.json (or yarn.lock).  
  * RUN npm ci (or yarn install \--frozen-lockfile)  
* **Stage 2: Builder**  
  * FROM node:18-alpine AS builder  
  * WORKDIR /app  
  * Copy \--from=deps /app/node\_modules ./node\_modules  
  * Copy entire project source (COPY . .)  
  * Set ENV NODE\_ENV production  
  * Run build command: RUN npm run build (Ensure next build is executed)  
* **Stage 3: Runner (Final Image)**  
  * FROM node:18-alpine AS runner  
  * WORKDIR /app  
  * ENV NODE\_ENV production  
  * Add non-root user: RUN addgroup \--system \--gid 1001 nodejs; adduser \--system \--uid 1001 nextjs  
  * Copy necessary build artifacts from builder stage:  
    * COPY \--from=builder /app/public ./public  
    * COPY \--from=builder \--chown=nextjs:nodejs /app/.next/standalone ./ (Use Next.js standalone output)  
    * COPY \--from=builder \--chown=nextjs:nodejs /app/.next/static ./.next/static  
  * USER nextjs  
  * EXPOSE 3000  
  * ENV PORT 3000  
  * CMD \["node", "server.js"\] (Command for standalone output)  
* **Health Check:** Add HEALTHCHECK instruction (e.g., check /api/health endpoint created in KC-INFRA-BE-1).  
* Add .dockerignore file to exclude node\_modules, .git, .env, etc., from being copied into the build context.  
* Ensure next.config.js has output: 'standalone' enabled.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Dockerfile  
* .dockerignore  
* next.config.js (output: 'standalone')  
  Testing Considerations (Technical): Build the Docker image locally (docker build .). Run the container locally (docker run) and verify the application starts and responds. Check image size.  
  Dependencies (Technical): KC-SETUP-1, Docker installed.

Ticket ID: KC-INFRA-DO-4  
Title: Setup ECR Repository  
Epic: KC-INFRA  
PRD Requirement(s): Implied by Container Deployment  
Team: DO  
Dependencies (Functional): KC-INFRA-DO-1  
UX/UI Design Link: N/A  
Description (Functional): Create a private Elastic Container Registry (ECR) repository in AWS to store the production Docker images built by the CI/CD pipeline.  
Acceptance Criteria (Functional):

* An ECR repository exists in the target AWS region.  
* The repository is private.  
* Image scanning on push is enabled (recommended).  
* CI/CD pipeline has permissions (via IAM role KC-INFRA-DO-1) to push images to this repository.  
  Technical Approach / Implementation Notes:  
* **Option A (Manual Creation):** Create via AWS Console initially. Simple but not IaC.  
* **Option B (Terraform):** Define aws\_ecr\_repository resource in Terraform.  
  resource "aws\_ecr\_repository" "app" {  
    name                 \= "knowledge-card-app" \# Or use variables  
    image\_tag\_mutability \= "MUTABLE" \# Or IMMUTABLE  
    force\_delete         \= false \# Safety setting

    image\_scanning\_configuration {  
      scan\_on\_push \= true  
    }

    tags \= {  
      Environment \= "production" \# Or variable  
      Project     \= "KnowledgeCard"  
    }  
  }

* Configure repository policy if needed (e.g., restrict access), though IAM role permissions are primary.  
* Update CI/CD pipeline (KC-INFRA-DO-11) to log in to ECR, build, tag, and push the Docker image using the ECR repository URI.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* AWS Console (ECR) or Terraform (aws\_ecr\_repository).  
* CI/CD pipeline configuration.  
  Testing Considerations (Technical): Manually push a test image or verify CI/CD pipeline can push successfully. Check image scanning results in AWS console.  
  Dependencies (Technical): KC-INFRA-DO-1

Ticket ID: KC-INFRA-DO-5  
Title: Setup RDS PostgreSQL Instance (Terraform, enable pgvector)  
Epic: KC-INFRA  
PRD Requirement(s): TC-STACK-3 (PostgreSQL), Vector DB Choice (pgvector)  
Team: DO/DBA  
Dependencies (Functional): KC-INFRA-DO-2 (VPC/Subnets), KC-INFRA-DO-13 (Security Groups), KC-INFRA-DO-10 (Secrets)  
UX/UI Design Link: N/A  
Description (Functional): Provision a managed Relational Database Service (RDS) instance running PostgreSQL using Terraform, configured for high availability, backups, and with the pgvector extension enabled.  
Acceptance Criteria (Functional):

* Terraform code defines an aws\_db\_instance or aws\_rds\_cluster resource for PostgreSQL.  
* Instance is placed in private subnets across multiple AZs (Multi-AZ deployment).  
* Appropriate instance size is chosen (start small, e.g., db.t3.micro or db.t4g.micro).  
* Automated backups are enabled.  
* Database credentials (master username/password) are managed via Secrets Manager (KC-INFRA-DO-10).  
* Security Group allows access only from the application's security group (KC-INFRA-DO-13).  
* The pgvector extension is available/enabled on the database instance.  
  Technical Approach / Implementation Notes:  
* Use Terraform AWS Provider.  
* Define aws\_db\_subnet\_group using private subnets from KC-INFRA-DO-2.  
* Define aws\_db\_instance resource:  
  * engine \= "postgres"  
  * engine\_version \= "15.x" (Choose appropriate version supporting pgvector)  
  * instance\_class \= var.db\_instance\_class  
  * allocated\_storage \= 20 (Start small)  
  * db\_subnet\_group\_name \= aws\_db\_subnet\_group.main.name  
  * vpc\_security\_group\_ids \= \[aws\_security\_group.rds.id\]  
  * multi\_az \= true  
  * username \= aws\_secretsmanager\_secret\_version.db\_creds.secret\_string.username (Read from Secrets Manager \- see KC-INFRA-DO-10)  
  * password \= aws\_secretsmanager\_secret\_version.db\_creds.secret\_string.password  
  * db\_name \= "knowledge\_cards"  
  * skip\_final\_snapshot \= true (For easier destruction during dev/test, set false for prod)  
  * backup\_retention\_period \= 7 (Or desired value)  
  * parameter\_group\_name: May need a custom parameter group if specific Postgres settings are needed.  
* **Enabling pgvector:**  
  * Check AWS RDS documentation for the specific Postgres version to confirm pgvector is listed in shared\_preload\_libraries by default or if it needs adding via a custom parameter group.  
  * After the instance is running, connect using psql and run CREATE EXTENSION IF NOT EXISTS vector;. This step might need to be run manually, via user data/bootstrap script if possible with RDS, or ideally incorporated into the initial Prisma migration (migrate dev or db execute). Add a step to Prisma migration workflow to ensure extension exists.  
* Ensure the DATABASE\_URL used by the application points to the RDS instance endpoint and uses the credentials from Secrets Manager.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A (Provisions infrastructure for defined schema)  
  Key Functions/Modules Involved:  
* Terraform configuration files (.tf)  
* aws\_db\_instance, aws\_db\_subnet\_group.  
* AWS Secrets Manager integration.  
* Prisma migration workflow (to ensure pgvector extension exists).  
  Testing Considerations (Technical): Run terraform plan/apply. Verify instance creation in AWS console. Connect to the DB using psql or DB client. Run \\dx to check for vector extension. Verify application can connect using RDS endpoint and credentials. Test backups/restore if needed.  
  Dependencies (Technical): KC-INFRA-DO-2, KC-INFRA-DO-13, KC-INFRA-DO-10

Ticket ID: KC-INFRA-DO-6  
Title: Setup ElastiCache Redis Instance (Terraform)  
Epic: KC-INFRA  
PRD Requirement(s): Background Job Choice (BullMQ/Redis)  
Team: DO  
Dependencies (Functional): KC-INFRA-DO-2 (VPC/Subnets), KC-INFRA-DO-13 (Security Groups)  
UX/UI Design Link: N/A  
Description (Functional): Provision a managed ElastiCache instance running Redis using Terraform for use as a cache and BullMQ backend.  
Acceptance Criteria (Functional):

* Terraform code defines an aws\_elasticache\_cluster or aws\_elasticache\_replication\_group resource for Redis.  
* Instance is placed in private subnets.  
* Appropriate node type is chosen (start small, e.g., cache.t3.micro).  
* Security Group allows access only from the application's security group (KC-INFRA-DO-13).  
* Cluster mode is disabled (unless required for high scale).  
  Technical Approach / Implementation Notes:  
* Use Terraform AWS Provider.  
* Define aws\_elasticache\_subnet\_group using private subnets from KC-INFRA-DO-2.  
* Define aws\_elasticache\_cluster resource (for single node) or aws\_elasticache\_replication\_group (for multi-AZ failover):  
  * engine \= "redis"  
  * engine\_version \= "7.x" (Choose appropriate version)  
  * node\_type \= var.redis\_node\_type  
  * num\_cache\_nodes \= 1 (for single cluster)  
  * subnet\_group\_name \= aws\_elasticache\_subnet\_group.main.name  
  * security\_group\_ids \= \[aws\_security\_group.redis.id\]  
  * parameter\_group\_name: Use default or create custom if needed.  
* Ensure application configuration includes the Redis primary endpoint URL (read from env var).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Terraform configuration files (.tf)  
* aws\_elasticache\_cluster, aws\_elasticache\_subnet\_group, aws\_elasticache\_replication\_group.  
  Testing Considerations (Technical): Run terraform plan/apply. Verify cluster creation in AWS console. Verify application can connect to Redis using the endpoint. Test basic cache set/get or BullMQ connection.  
  Dependencies (Technical): KC-INFRA-DO-2, KC-INFRA-DO-13

Ticket ID: KC-INFRA-DO-7  
Title: Setup S3 Bucket for Storage (Terraform)  
Epic: KC-INFRA  
PRD Requirement(s): FR-STORAGE-1 (Cloud File Storage)  
Team: DO  
Dependencies (Functional): KC-INFRA-DO-1  
UX/UI Design Link: N/A  
Description (Functional): Provision an S3 bucket using Terraform for storing user-uploaded media files (images, videos in Stage 2+). Configure appropriate access policies and lifecycle rules.  
Acceptance Criteria (Functional):

* Terraform code defines an aws\_s3\_bucket resource.  
* Bucket is private by default.  
* Bucket policy or IAM permissions allow the application (via ECS task role) to PutObject, GetObject, DeleteObject.  
* CORS configuration is set up if direct browser uploads (using pre-signed URLs) are planned.  
* Optional: Lifecycle rules for managing old/unused objects.  
* Optional: Versioning enabled.  
  Technical Approach / Implementation Notes:  
* Use Terraform AWS Provider.  
* Define aws\_s3\_bucket resource:  
  * bucket \= var.s3\_bucket\_name (Use a globally unique name)  
  * acl \= "private" (Deprecated, use bucket policy/IAM)  
* Define aws\_s3\_bucket\_policy or configure IAM role policy (on ECS task role) to grant necessary permissions (s3:PutObject, s3:GetObject, s3:DeleteObject) scoped to the bucket ARN (arn:aws:s3:::${var.s3\_bucket\_name}/\*).  
* Define aws\_s3\_bucket\_cors\_configuration if direct browser uploads using pre-signed URLs will be used (allow PUT/POST from application domain).  
* Define aws\_s3\_bucket\_lifecycle\_configuration (optional).  
* Define aws\_s3\_bucket\_versioning (optional).  
* Define aws\_s3\_bucket\_public\_access\_block to ensure bucket remains private.  
* Ensure application configuration includes the bucket name (read from env var).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Terraform configuration files (.tf)  
* aws\_s3\_bucket, aws\_s3\_bucket\_policy, aws\_s3\_bucket\_cors\_configuration, etc.  
* IAM Policy for ECS Task Role.  
  Testing Considerations (Technical): Run terraform plan/apply. Verify bucket creation and settings in AWS console. Test uploading/downloading files from the application running in ECS (requires app changes from KC-STORAGE epic). Test pre-signed URL generation and upload if applicable.  
  Dependencies (Technical): KC-INFRA-DO-1

Ticket ID: KC-INFRA-DO-10  
Title: Setup Secrets Management (AWS Secrets Manager, Terraform)  
Epic: KC-INFRA  
PRD Requirement(s): NFR-SEC-1 (Implied)  
Team: DO  
Dependencies (Functional): KC-INFRA-DO-1  
UX/UI Design Link: N/A  
Description (Functional): Set up AWS Secrets Manager using Terraform to securely store and manage sensitive information like database credentials and third-party API keys required by the application.  
Acceptance Criteria (Functional):

* Terraform code defines aws\_secretsmanager\_secret resources for required secrets (e.g., DB credentials, NextAuth secret, AI service keys).  
* Secrets contain the necessary key-value pairs (e.g., username, password, host, port, dbname for DB creds).  
* IAM policies grant the application's ECS task role permission to read specific secrets (secretsmanager:GetSecretValue).  
* Secrets are populated initially (manually or via Terraform \- handle initial password carefully).  
  Technical Approach / Implementation Notes:  
* Use Terraform AWS Provider.  
* Define aws\_secretsmanager\_secret resource for each secret needed.  
* Define aws\_secretsmanager\_secret\_version to initially populate the secret value.  
  * For DB password, consider generating a random password using random\_password Terraform resource and storing it. Avoid committing plaintext passwords.  
  * Structure DB credentials as a JSON string within the secret for easy parsing: {"username":"dbuser","password":"${random\_password.db.result}", ...}.  
* Update IAM policy for ECS Task Role (defined via Terraform aws\_iam\_role\_policy or aws\_iam\_policy\_document) to allow secretsmanager:GetSecretValue action on the specific secret ARNs.  
* Application code needs to be modified (or use agent/helper) to fetch secrets from Secrets Manager at startup instead of relying solely on environment variables for sensitive data. Alternatively, inject secrets *as* environment variables into the ECS task definition (less secure than runtime fetching). **Decision:** Prefer injecting as environment variables for simplicity in Stage 2 initial setup, fetched during deployment/task definition update.  
* Update Terraform configuration for RDS (KC-INFRA-DO-5) and potentially application environment variables in ECS Task Definition (KC-INFRA-DO-8) to reference the secrets stored in Secrets Manager.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Terraform configuration files (.tf)  
* aws\_secretsmanager\_secret, aws\_secretsmanager\_secret\_version.  
* IAM Policy for ECS Task Role.  
* ECS Task Definition configuration.  
  Testing Considerations (Technical): Run terraform plan/apply. Verify secrets are created in AWS console. Verify ECS task role has permissions. Verify application running in ECS can access the required configuration values (injected as env vars). Test secret rotation procedures if implemented later.  
  Dependencies (Technical): KC-INFRA-DO-1

Ticket ID: KC-INFRA-DO-8  
Title: Setup ECS Cluster & Fargate Service Definition (Terraform)  
Epic: KC-INFRA  
PRD Requirement(s): Implied by Container Deployment  
Team: DO  
Dependencies (Functional): KC-INFRA-DO-2 (VPC/Subnets), KC-INFRA-DO-4 (ECR Repo), KC-INFRA-DO-13 (Security Groups), KC-INFRA-DO-10 (Secrets), KC-INFRA-DO-3 (Dockerfile)  
UX/UI Design Link: N/A  
Description (Functional): Provision an Elastic Container Service (ECS) cluster and define an ECS service using the Fargate launch type via Terraform to run the containerized Next.js application.  
Acceptance Criteria (Functional):

* Terraform code defines an aws\_ecs\_cluster.  
* Terraform code defines an aws\_ecs\_task\_definition for the application container:  
  * References the ECR image URI (KC-INFRA-DO-4).  
  * Specifies CPU/Memory resources.  
  * Defines port mappings (e.g., port 3000).  
  * Includes environment variables (non-sensitive and sensitive sourced from Secrets Manager KC-INFRA-DO-10).  
  * Assigns the correct ECS Task Execution Role (for ECR pull, CloudWatch logs) and Task Role (for AWS service access like S3, Secrets Manager).  
* Terraform code defines an aws\_ecs\_service using Fargate launch type:  
  * References the task definition.  
  * Specifies desired task count (e.g., 2 for availability).  
  * Configures placement in private subnets (KC-INFRA-DO-2).  
  * Associates with the application Security Group (KC-INFRA-DO-13).  
  * Integrates with the Application Load Balancer (ALB) target group (KC-INFRA-DO-9).  
    Technical Approach / Implementation Notes:  
* Use Terraform AWS Provider.  
* Define aws\_ecs\_cluster.  
* Define IAM Roles needed by ECS:  
  * aws\_iam\_role.ecs\_task\_execution\_role: Allows ECS agent to pull images from ECR and send logs to CloudWatch. Attach managed policy AmazonECSTaskExecutionRolePolicy.  
  * aws\_iam\_role.ecs\_task\_role: Granted to the application container itself to interact with other AWS services (S3, Secrets Manager read, etc.). Attach custom policy based on application needs (S3 access from KC-INFRA-DO-7, Secrets Manager access from KC-INFRA-DO-10).  
* Define aws\_ecs\_task\_definition:  
  * family \= "knowledge-card-app"  
  * requires\_compatibilities \= \["FARGATE"\]  
  * network\_mode \= "awsvpc"  
  * cpu, memory (e.g., 512/1024)  
  * execution\_role\_arn \= aws\_iam\_role.ecs\_task\_execution\_role.arn  
  * task\_role\_arn \= aws\_iam\_role.ecs\_task\_role.arn  
  * container\_definitions: JSON string defining the container (image URI from ECR, port mappings, environment variables, secrets sourced from Secrets Manager ARN, log configuration for CloudWatch).  
* Define aws\_ecs\_service:  
  * name \= "knowledge-card-service"  
  * cluster \= aws\_ecs\_cluster.main.id  
  * task\_definition \= aws\_ecs\_task\_definition.app.arn  
  * desired\_count \= 2  
  * launch\_type \= "FARGATE"  
  * network\_configuration: Specify private subnets, security group.  
  * load\_balancer: Configure target group ARN from ALB setup (KC-INFRA-DO-9).  
  * Configure deployment settings (rolling update, etc.).  
    API Contract (if applicable): N/A  
    Data Model Changes (if applicable): N/A  
    Key Functions/Modules Involved:  
* Terraform configuration files (.tf)  
* aws\_ecs\_cluster, aws\_ecs\_task\_definition, aws\_ecs\_service, aws\_iam\_role, aws\_iam\_role\_policy.  
* JSON definition for container within task definition.  
  Testing Considerations (Technical): Run terraform plan/apply. Verify cluster, task definition, service creation in AWS console. Check ECS tasks are running and healthy. Verify application is accessible via ALB DNS (after KC-INFRA-DO-9). Check container logs in CloudWatch (after KC-INFRA-DO-12).  
  Dependencies (Technical): KC-INFRA-DO-2, 3, 4, 10, 13, KC-INFRA-DO-9 (ALB Target Group)

Ticket ID: KC-INFRA-DO-9  
Title: Setup Application Load Balancer (ALB) & DNS (Terraform)  
Epic: KC-INFRA  
PRD Requirement(s): Implied by Public Web Access  
Team: DO  
Dependencies (Functional): KC-INFRA-DO-2 (VPC/Subnets), KC-INFRA-DO-13 (Security Groups), KC-INFRA-DO-8 (ECS Service)  
UX/UI Design Link: N/A  
Description (Functional): Provision an Application Load Balancer (ALB) using Terraform to distribute incoming traffic across the ECS application tasks, and configure DNS records (e.g., in Route 53\) to point to the ALB.  
Acceptance Criteria (Functional):

* Terraform code defines an aws\_lb (ALB).  
* ALB is internet-facing and placed in public subnets.  
* An aws\_lb\_listener is configured for HTTPS (port 443), using an ACM certificate. Redirects HTTP to HTTPS.  
* An aws\_lb\_target\_group is defined for the ECS service, configured with appropriate health checks.  
* The ECS service (KC-INFRA-DO-8) is registered with the target group.  
* (Optional) A Route 53 hosted zone exists or is managed.  
* A Route 53 alias record (aws\_route53\_record) points the application's domain name to the ALB DNS name.  
  Technical Approach / Implementation Notes:  
* **ACM Certificate:** Provision an SSL/TLS certificate using AWS Certificate Manager (ACM) for the application domain (requires domain ownership validation \- often done manually or via DNS validation). Use the ARN of this certificate.  
* Use Terraform AWS Provider.  
* Define aws\_lb resource:  
  * name \= "knowledge-card-alb"  
  * internal \= false  
  * load\_balancer\_type \= "application"  
  * security\_groups \= \[aws\_security\_group.alb.id\]  
  * subnets \= \[list\_of\_public\_subnet\_ids\]  
* Define aws\_lb\_target\_group:  
  * name \= "knowledge-card-tg"  
  * port \= 3000 (Application port)  
  * protocol \= "HTTP" (Traffic between ALB and tasks is usually HTTP)  
  * vpc\_id \= aws\_vpc.main.id  
  * target\_type \= "ip" (For Fargate)  
  * health\_check: Configure path (e.g., /api/health), protocol, port, thresholds.  
* Define aws\_lb\_listener for HTTPS (443):  
  * load\_balancer\_arn \= aws\_lb.main.arn  
  * port \= 443, protocol \= "HTTPS"  
  * ssl\_policy (Use recommended)  
  * certificate\_arn \= var.acm\_certificate\_arn  
  * default\_action: type \= "forward", target\_group\_arn \= aws\_lb\_target\_group.main.arn.  
* Define aws\_lb\_listener for HTTP (80):  
  * load\_balancer\_arn \= aws\_lb.main.arn  
  * port \= 80, protocol \= "HTTP"  
  * default\_action: type \= "redirect", configure redirect to HTTPS.  
* **DNS:**  
  * Define aws\_route53\_zone if managing via Terraform (or use existing).  
  * Define aws\_route53\_record: name \= var.app\_domain, zone\_id \= ..., type \= "A", alias block pointing to aws\_lb.main.zone\_id and aws\_lb.main.dns\_name.  
* Update ECS service definition (KC-INFRA-DO-8) to include the target group ARN in load\_balancer block.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Terraform configuration files (.tf)  
* aws\_lb, aws\_lb\_listener, aws\_lb\_target\_group, aws\_route53\_record.  
* ACM Certificate ARN.  
  Testing Considerations (Technical): Run terraform plan/apply. Verify ALB, listeners, target group creation. Check target group health checks pass once ECS tasks are running. Access the application via the configured domain name over HTTPS. Verify HTTP redirects to HTTPS.  
  Dependencies (Technical): KC-INFRA-DO-2, 13, 8, ACM Certificate provisioned. Domain name registered.

Ticket ID: KC-INFRA-BE-1  
Title: Implement Health Check Endpoint  
Epic: KC-INFRA  
PRD Requirement(s): NFR-RELIABILITY-1 (Implied)  
Team: BE  
Dependencies (Functional): KC-SETUP-1 (Next.js app)  
UX/UI Design Link: N/A  
Description (Functional): Create a simple API endpoint within the Next.js application that load balancers and container orchestrators can use to verify the application's health status.  
Acceptance Criteria (Functional):

* A GET endpoint exists (e.g., /api/health).  
* The endpoint returns a success status code (e.g., 200 OK) and a simple body (e.g., { status: 'ok' }) when the application is running normally.  
* (Optional Stage 2+) The endpoint could perform basic checks (e.g., database connectivity) before returning success.  
  Technical Approach / Implementation Notes:  
* Create src/app/api/health/route.ts.  
* Export async function GET(request: Request):  
  import { NextResponse } from 'next/server';

  export async function GET(request: Request) {  
    // Stage 1: Basic check \- if the handler runs, the server is up.  
    // Stage 2+: Add checks like DB connection test  
    // try {  
    //   await prisma.$queryRaw\`SELECT 1\`; // Example DB check  
    // } catch (error) {  
    //   console.error("Health check failed:", error);  
    //   return NextResponse.json({ status: 'error', error: 'Database connection failed' }, { status: 503 });  
    // }  
    return NextResponse.json({ status: 'ok', timestamp: Date.now() });  
  }

* Ensure this endpoint does not require authentication.  
* Configure the ALB Target Group health check (KC-INFRA-DO-9) and Dockerfile HEALTHCHECK (KC-INFRA-DO-3) to use this /api/health path.  
  API Contract (if applicable):  
* **Endpoint:** GET /api/health  
* **Response Success (200):** { status: 'ok', timestamp: number }  
* Response Error (503): { status: 'error', error: string } (If deeper checks implemented and fail)  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/app/api/health/route.ts  
  Testing Considerations (Technical): Test the endpoint directly using curl or browser. Verify it returns 200 OK. Verify health checks configured in ALB and Dockerfile use this endpoint and pass when the app is running.  
  Dependencies (Technical): KC-SETUP-1

Ticket ID: KC-INFRA-DO-12 (Generated)  
Title: Setup Basic CloudWatch Logging/Monitoring (Terraform)  
Epic: KC-INFRA  
PRD Requirement(s): NFR-OPS-1 (Implied)  
Team: DO  
Dependencies (Functional): KC-INFRA-DO-8 (ECS Service)  
UX/UI Design Link: N/A  
Description (Functional): Configure basic logging and monitoring for the ECS application using AWS CloudWatch via Terraform.  
Acceptance Criteria (Functional):

* ECS task definition configures the awslogs log driver to send container standard output/error to a CloudWatch Log Group.  
* A CloudWatch Log Group is created for the application logs.  
* Basic CloudWatch Alarms are configured for key metrics (e.g., high CPU/Memory utilization on ECS service, unhealthy host count in Target Group, 5xx errors on ALB).  
* Log retention policy is set for the Log Group.  
  Technical Approach / Implementation Notes:  
* Use Terraform AWS Provider.  
* Define aws\_cloudwatch\_log\_group resource for application logs. Set retention period (retention\_in\_days).  
* Update container\_definitions in aws\_ecs\_task\_definition (KC-INFRA-DO-8) to include logConfiguration:  
  "logConfiguration": {  
    "logDriver": "awslogs",  
    "options": {  
      "awslogs-group": "${aws\_cloudwatch\_log\_group.app.name}",  
      "awslogs-region": "${var.aws\_region}",  
      "awslogs-stream-prefix": "ecs"  
    }  
  }

* Define aws\_cloudwatch\_metric\_alarm resources for key metrics:  
  * ECS Service CPUUtilization: Namespace AWS/ECS, MetricName CPUUtilization, Dimensions ClusterName, ServiceName. Threshold e.g., 80%.  
  * ECS Service MemoryUtilization: Namespace AWS/ECS, MetricName MemoryUtilization. Threshold e.g., 80%.  
  * ALB UnHealthyHostCount: Namespace AWS/ApplicationELB, MetricName UnHealthyHostCount, Dimensions LoadBalancer, TargetGroup. Threshold \> 0\.  
  * ALB HTTPCode\_Target\_5XX\_Count: Namespace AWS/ApplicationELB, MetricName HTTPCode\_Target\_5XX\_Count. Threshold \> N over M minutes.  
* Configure alarm actions (e.g., notify an SNS topic \- requires setting up aws\_sns\_topic and aws\_sns\_topic\_subscription).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Terraform configuration files (.tf)  
* aws\_cloudwatch\_log\_group, aws\_cloudwatch\_metric\_alarm.  
* ECS Task Definition (logConfiguration).  
* (Optional) aws\_sns\_topic, aws\_sns\_topic\_subscription.  
  Testing Considerations (Technical): Run terraform plan/apply. Verify log group creation and log streaming from containers in CloudWatch console. Verify alarm creation. Trigger alarms (e.g., deploy code causing high CPU, manually stop tasks) to test notifications if configured.  
  Dependencies (Technical): KC-INFRA-DO-8

Ticket ID: KC-INFRA-DO-11 (Generated)  
Title: Setup CI/CD Pipeline (GitHub Actions)  
Epic: KC-INFRA  
PRD Requirement(s): NFR-DEPLOY-1  
Team: DO  
Dependencies (Functional): KC-INFRA-DO-1 (IAM Role), KC-INFRA-DO-3 (Dockerfile), KC-INFRA-DO-4 (ECR Repo), KC-INFRA-DO-8 (ECS Cluster/Service/TaskDef), KC-INFRA-BE-1 (Health Check)  
UX/UI Design Link: N/A  
Description (Functional): Create a Continuous Integration and Continuous Deployment (CI/CD) pipeline using GitHub Actions to automate the process of building, testing (basic), pushing Docker images, and deploying the application to the AWS ECS Fargate environment.  
Acceptance Criteria (Functional):

* A GitHub Actions workflow file exists (e.g., `.github/workflows/deploy.yml`).
* The pipeline is triggered on pushes/merges to the main branch (or develop/staging branches).
* The pipeline successfully authenticates to AWS using OIDC (via CICDPipelineRole).
* The pipeline builds the production Docker image (using Dockerfile from KC-INFRA-DO-3).
* (Future enhancement) The pipeline runs automated checks (linting, unit/integration tests).
* The pipeline tags and pushes the Docker image to the ECR repository (KC-INFRA-DO-4).
* The pipeline runs database migrations (`npx prisma migrate deploy`) against the target database before deploying the new application version.
* The pipeline updates the ECS service (KC-INFRA-DO-8) to deploy the new Docker image tag, triggering a rolling deployment.
* The pipeline handles failures gracefully and provides informative logs.
Technical Approach / Implementation Notes:
* Create `.github/workflows/deploy.yml`.
* Define trigger (e.g., `on: push: branches: [ main ]`).
* **AWS Authentication:** Use `aws-actions/configure-aws-credentials` action with OIDC role (`CICDPipelineRole` ARN from KC-INFRA-DO-1) and specified region.
* **Checkout Code:** Use `actions/checkout`.
* **Install Node/Deps:** Use `actions/setup-node`.
* **(Placeholder) Run Checks:** Add steps for `npm run lint`, `npm run test:fe`, `npm run test:be` (ensure test DB setup if needed in CI environment).
* **Login to ECR:** Use `aws-actions/amazon-ecr-login`.
* **Build & Push Image:** Use `docker/build-push-action` to build the Dockerfile, tag with Git SHA or timestamp, and push to ECR repository URL (from KC-INFRA-DO-4).
* **Database Migrations:** Add a step to execute `npx prisma migrate deploy`. This requires the pipeline environment to have database access (correct network config/security groups if run from CI runner, or run as a separate ECS task) and the `DATABASE_URL` environment variable set (potentially fetched from Secrets Manager).
* **Deploy to ECS:** Use `aws-actions/amazon-ecs-deploy-task-definition` to:
  * Download existing task definition.
  * Update image field with the newly pushed ECR image URI.
  * Register the new task definition revision.
  * Update the ECS service to use the new task definition revision, triggering deployment.
* Use GitHub secrets for any necessary configuration values not suitable for the repository.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved:
* `.github/workflows/deploy.yml`
* GitHub Actions runner environment.
* AWS services (ECR, ECS, IAM, Secrets Manager).
* Docker, Node.js, npm/yarn, Prisma CLI.
Testing Considerations (Technical): Test pipeline execution on pushes/PRs. Verify successful image builds and pushes to ECR. Verify successful deployment to ECS staging environment. Monitor ECS service events during deployment. **Crucially, test the database migration step ensures schema changes are applied before the new code depending on them is deployed.** Verify rollbacks occur correctly if deployment fails health checks.
Dependencies (Technical): KC-INFRA-DO-1, KC-INFRA-DO-3, KC-INFRA-DO-4, KC-INFRA-DO-8, KC-INFRA-BE-1, Prisma CLI configured for migrations.

Ticket ID: KC-INFRA-TEST-DO-1
Title: Test Terraform Infrastructure Code
Epic: KC-INFRA
PRD Requirement(s): NFR-MAINT-1
Team: DO
Dependencies (Functional): All Terraform tickets (KC-INFRA-DO-2, 4, 5, 6, 7, 8, 9, 10, 12, 13)
UX/UI Design Link: N/A
Description (Functional): Implement automated checks and potentially integration tests for the Terraform Infrastructure as Code (IaC) to ensure its correctness, adherence to standards, and prevent regressions.
Acceptance Criteria (Functional):
* Terraform code is automatically formatted and validated in the CI pipeline.
* Basic static analysis checks (e.g., using `tflint`) are performed in CI.
* (Optional) Integration tests are implemented for critical modules (e.g., VPC, ECS setup) using tools like Terratest.
Technical Approach / Implementation Notes:
* **CI Pipeline Integration:** Add steps to the GitHub Actions workflow (KC-INFRA-DO-11):
  * Run `terraform fmt --check`.
  * Run `terraform validate`.
  * (Optional) Install and run `tflint` for static analysis checks against best practices.
* **(Optional) Integration Testing with Terratest:**
  * Set up Go environment for writing Terratest tests.
  * Write tests for key Terraform modules (e.g., VPC, ECS):
    * Run `terraform init` and `terraform apply` within the test.
    * Use AWS SDK (Go) to verify created resources have expected configurations (e.g., check subnet tags, security group rules, ECS service desired count).
    * Run `terraform destroy` at the end of the test.
  * Requires AWS credentials configured in the testing environment.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: Terraform CLI, GitHub Actions workflow, `tflint` (optional), Go/Terratest (optional), AWS SDK (Go, optional).
Testing Considerations (Technical): Terratest runs real infrastructure, incurring AWS costs and taking time. Focus integration tests on critical, stable modules. Static checks (fmt, validate, tflint) provide faster feedback.
Dependencies (Technical): All Terraform tickets, Terraform CLI, CI Environment (GitHub Actions).