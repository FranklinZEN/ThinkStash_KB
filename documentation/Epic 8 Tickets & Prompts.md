# **Review and AI Prompts for KC-INFRA Epic (Stage 2\)**

This document contains the technical review and AI development prompts for the KC-INFRA epic. This epic focuses on building the AWS cloud infrastructure using Terraform and establishing CI/CD pipelines for the Knowledge Card application, marking the transition towards Stage 2 deployment readiness.

## **Part 1: Tech Lead Review of KC-INFRA Epic (Stage 2\)**

This epic lays the foundation for hosting the application in the cloud. It involves provisioning all necessary AWS resources using Infrastructure as Code (IaC) with Terraform and automating the build and deployment process using a CI/CD pipeline (GitHub Actions). This is a critical step towards a scalable, secure, and maintainable production environment.

**A. Scope and Purpose:**

* **Infrastructure as Code (IaC):** Defines the entire cloud environment (networking, compute, database, cache, storage, load balancing, monitoring, secrets) using Terraform, ensuring reproducibility and version control.  
* **Containerization & Orchestration:** Creates an optimized production Docker image and deploys it using AWS ECS with the Fargate launch type for serverless container management.  
* **Managed Services:** Leverages AWS managed services like RDS (PostgreSQL with pgvector), ElastiCache (Redis), ECR, S3, Secrets Manager, ALB, and CloudWatch to reduce operational overhead.  
* **CI/CD Automation:** Enhances the existing placeholder pipeline to fully automate building, testing (implicitly, though test stages could be added), pushing Docker images, and deploying updates to ECS.  
* **Security & Availability:** Incorporates security best practices (IAM least privilege, Security Groups, Secrets Manager) and high availability patterns (Multi-AZ RDS, multiple ECS tasks).

**B. Key Technical Points & Considerations:**

* **Terraform:** The core tool for infrastructure provisioning. Requires setting up remote state (S3/DynamoDB) and careful management of resources, variables, and potentially modules.  
* **AWS Services:** Involves provisioning and configuring a wide range of AWS services. Correct configuration (e.g., VPC routing, Security Group rules, IAM permissions, ECS task definitions) is crucial.  
* **Docker & ECS Fargate:** Requires a well-optimized multi-stage Dockerfile (KC-INFRA-DO-3) using the Next.js standalone output. ECS Fargate simplifies deployment by removing the need to manage underlying EC2 instances.  
* **pgvector on RDS (KC-INFRA-DO-5):** Requires ensuring the chosen PostgreSQL version supports pgvector and explicitly running CREATE EXTENSION IF NOT EXISTS vector; (likely via a Prisma migration step) after the instance is provisioned.  
* **Secrets Management (KC-INFRA-DO-10):** Uses AWS Secrets Manager. The chosen approach is to inject secrets into the ECS task definition as environment variables for simplicity, rather than having the application fetch them at runtime.  
* **CI/CD (KC-INFRA-DO-11):** Uses GitHub Actions with OIDC for secure AWS authentication (recommended over long-lived IAM user keys). Leverages helper actions (aws-actions/...) to simplify ECR login and ECS deployment steps.  
* **Networking:** Establishes a standard VPC structure with public/private subnets, NAT Gateway, and carefully configured Security Groups (KC-INFRA-DO-2, KC-INFRA-DO-13).  
* **Monitoring & Logging (KC-INFRA-DO-12):** Sets up basic observability using CloudWatch Logs (via awslogs driver) and metric alarms.

**C. Potential Gaps/Refinements:**

* **Terraform Modules:** While mentioned, the prompts don't strictly enforce using Terraform modules. For maintainability, structuring the Terraform code into modules (e.g., vpc, rds, ecs) is highly recommended (prompts updated to reflect this).  
* **CI/CD Testing Stages:** The CI/CD pipeline focuses on build and deploy. Adding automated testing stages (unit, integration, E2E) within the pipeline is essential for true continuous integration but might be considered post-Stage 2 setup.  
* **Cost Optimization:** Initial instance sizes are suggested to start small, but ongoing cost monitoring and optimization strategies (e.g., Savings Plans, instance scheduling for non-prod) are not covered here.  
* **Advanced Security:** Topics like WAF (Web Application Firewall), detailed GuardDuty setup, or more sophisticated IAM policies are outside this initial scope and deferred to a later stage.  
* **Database Migrations in CI/CD:** The pipeline deploys the application container. A strategy for running database migrations (prisma migrate deploy) as part of the deployment process needs to be considered (e.g., as a separate step in the pipeline before updating the service, or using an ECS task run). This is currently missing.

**D. Overall:**

This is a comprehensive infrastructure epic that sets up a robust and modern cloud environment using best practices like IaC, containers, serverless compute (Fargate), and managed services. Successful implementation requires strong understanding of AWS services and Terraform. Addressing the database migration strategy within CI/CD is a key next step after this infrastructure is in place.

## **Part 2: AI Development Prompts for KC-INFRA Epic (Stage 2\)**

*(Prompts reference the full suite of project documents and incorporate review findings)*

*(Note: While these prompts cover foundational security elements like IAM roles and Security Groups, more advanced security configurations like AWS WAF, GuardDuty analysis, detailed VPC Flow Log analysis, etc., are considered out of scope for this initial Stage 2 setup and should be addressed in later stages.)*

**1\. Ticket: KC-INFRA-DO-1: Setup AWS Account & Foundational IAM Roles/Users**

* **Prompt:** Establish the AWS account structure and initial IAM configuration following best practices, as specified in **JIRA Ticket KC-INFRA-DO-1**.  
  1. Secure the root AWS account user (use strong password, enable MFA). Avoid using root for routine tasks.  
  2. Create dedicated IAM users for DevOps personnel with MFA enabled. Grant appropriate administrative permissions initially (e.g., AdministratorAccess), plan to refine later following least privilege.  
  3. Create IAM Roles:  
     * TerraformExecutionRole: For Terraform execution (by users or CI/CD). Attach necessary policies (e.g., AmazonEC2FullAccess, AmazonRDSFullAccess, AmazonS3FullAccess, AmazonECS\_FullAccess, AmazonEC2ContainerRegistryFullAccess, AmazonElastiCacheFullAccess, IAMFullAccess, AWSSecretsManagerReadWrite, AmazonCloudWatchFullAccess, etc. \- **Refine to least privilege based on actual Terraform resources used**). Configure trust policy to allow assumption by authorized IAM users/roles.  
     * CICDPipelineRole: For GitHub Actions (or other CI/CD tool). Grant permissions: AmazonEC2ContainerRegistryFullAccess, AmazonECS\_FullAccess (or granular ecs:RegisterTaskDefinition, ecs:UpdateService, ecs:DescribeServices, etc.), secretsmanager:GetSecretValue (scoped to specific secrets), iam:PassRole (for passing execution/task roles to ECS). Configure trust policy for GitHub Actions OIDC provider (sts.amazonaws.com with audience/subject filters).  
  4. Configure AWS credentials securely for local Terraform execution (e.g., AWS SSO, named profiles).  
  5. Set up basic AWS Billing alerts (e.g., estimated charges threshold).

**2\. Ticket: KC-INFRA-DO-2: Define VPC & Networking Structure (Terraform)**

* **Prompt:** Create the core AWS networking infrastructure using Terraform, as specified in **JIRA Ticket KC-INFRA-DO-2**.  
  1. Initialize Terraform project (terraform init).  
  2. Configure Terraform Remote State Backend using S3 and DynamoDB (create bucket/table first if needed).  
  3. Define aws\_vpc resource with appropriate CIDR block (e.g., 10.0.0.0/16).  
  4. Define aws\_subnet resources for public and private tiers across at least two Availability Zones. Tag subnets clearly (e.g., Tier=Public, Tier=Private).  
  5. Define aws\_internet\_gateway and attach to VPC.  
  6. Define aws\_eip and aws\_nat\_gateway. Place NAT Gateway in a public subnet.  
  7. Define aws\_route\_table resources:  
     * Public Route Table: Associate with public subnets. Add route 0.0.0.0/0 \-\> Internet Gateway.  
     * Private Route Table(s): Associate with private subnets. Add route 0.0.0.0/0 \-\> NAT Gateway.  
  8. Use variables for region, AZs, CIDRs, tags. Strongly recommend structuring this configuration using Terraform modules (e.g., modules/vpc) for maintainability and reusability.  
  9. Run terraform plan and terraform apply. Verify resources in AWS console.

**3\. Ticket: KC-INFRA-DO-13: Configure Security Groups (Terraform)**

* **Prompt:** Define necessary AWS Security Groups using Terraform, as specified in **JIRA Ticket KC-INFRA-DO-13**.  
  1. Define aws\_security\_group resources within your Terraform code (e.g., sg\_alb, sg\_ecs\_task, sg\_rds, sg\_redis). Associate them with the VPC created in **KC-INFRA-DO-2**.  
  2. Configure rules using ingress and egress blocks, referencing other SGs by ID:  
     * sg\_alb: Ingress TCP 80, 443 from 0.0.0.0/0. Egress All 0.0.0.0/0.  
     * sg\_ecs\_task: Ingress TCP 3000 (app port) from source\_security\_group\_id \= aws\_security\_group.sg\_alb.id. Egress TCP 5432 to destination\_security\_group\_id \= aws\_security\_group.sg\_rds.id. Egress TCP 6379 to destination\_security\_group\_id \= aws\_security\_group.sg\_redis.id. Egress All 0.0.0.0/0 (for NAT Gateway access).  
     * sg\_rds: Ingress TCP 5432 from source\_security\_group\_id \= aws\_security\_group.sg\_ecs\_task.id.  
     * sg\_redis: Ingress TCP 6379 from source\_security\_group\_id \= aws\_security\_group.sg\_ecs\_task.id.  
  3. Use variables for ports. Apply least privilege.  
  4. Associate these SGs with the corresponding resources in later tickets (**KC-INFRA-DO-5, 6, 8, 9**).  
  5. Strongly recommend defining these Security Groups within a dedicated Terraform module (e.g., modules/security) or alongside their respective service modules (e.g., within an RDS module) for clarity.  
  6. Run terraform plan and terraform apply.

**4\. Ticket: KC-INFRA-DO-3: Create Production Dockerfile (Multi-stage)**

* **Prompt:** Create an optimized, multi-stage Dockerfile at the project root for the Next.js application, as specified in **JIRA Ticket KC-INFRA-DO-3**.  
  1. Ensure output: 'standalone' is enabled in next.config.js.  
  2. Create Dockerfile:  
     \# Stage 1: Install dependencies  
     FROM node:18-alpine AS deps  
     WORKDIR /app  
     COPY package.json yarn.lock\* package-lock.json\* ./  
     RUN yarn install \--frozen-lockfile \# Or npm ci

     \# Stage 2: Build application  
     FROM node:18-alpine AS builder  
     WORKDIR /app  
     COPY \--from=deps /app/node\_modules ./node\_modules  
     COPY . .  
     \# Set build-time env vars if needed (e.g., NEXT\_PUBLIC\_...)  
     ENV NODE\_ENV production  
     RUN yarn build \# Or npm run build

     \# Stage 3: Production image  
     FROM node:18-alpine AS runner  
     WORKDIR /app  
     ENV NODE\_ENV production  
     ENV PORT 3000  
     \# Create non-root user  
     RUN addgroup \--system \--gid 1001 nodejs  
     RUN adduser \--system \--uid 1001 nextjs  
     \# Copy necessary artifacts from builder stage (standalone output)  
     COPY \--from=builder /app/public ./public  
     COPY \--from=builder \--chown=nextjs:nodejs /app/.next/standalone ./  
     COPY \--from=builder \--chown=nextjs:nodejs /app/.next/static ./.next/static  
     USER nextjs  
     EXPOSE 3000  
     \# Healthcheck instruction (adjust path/port if needed)  
     HEALTHCHECK \--interval=30s \--timeout=5s \--start-period=15s \--retries=3 \\  
       CMD wget \--quiet \--tries=1 \--spider http://localhost:3000/api/health || exit 1  
     CMD \["node", "server.js"\]

  3. Create a .dockerignore file listing node\_modules, .git, .env, \*.log, etc.  
  4. Build locally (docker build \-t knowledge-card-app .) and test running the container (docker run \-p 3000:3000 knowledge-card-app).

**5\. Ticket: KC-INFRA-DO-4: Setup ECR Repository**

* **Prompt:** Create a private AWS ECR repository using Terraform, as specified in **JIRA Ticket KC-INFRA-DO-4**.  
  1. Add aws\_ecr\_repository resource to your Terraform code:  
     resource "aws\_ecr\_repository" "app" {  
       name                 \= "knowledge-card-app" \# Or use var.app\_name  
       image\_tag\_mutability \= "MUTABLE"            \# Change to IMMUTABLE for stricter control if desired  
       force\_delete         \= false                \# Safety setting for prod

       image\_scanning\_configuration {  
         scan\_on\_push \= true  
       }

       tags \= {  
         Environment \= var.environment \# e.g., "production"  
         Project     \= "KnowledgeCard"  
       }  
     }

  2. Run terraform plan and terraform apply.  
  3. Note the repository URI (aws\_ecr\_repository.app.repository\_url) for use in the CI/CD pipeline (**KC-INFRA-DO-11**).

**6\. Ticket: KC-INFRA-DO-5: Setup RDS PostgreSQL Instance (Terraform, enable pgvector)**

* **Prompt:** Provision a multi-AZ RDS PostgreSQL instance with pgvector support using Terraform, as specified in **JIRA Ticket KC-INFRA-DO-5**.  
  1. Define aws\_db\_subnet\_group using private subnets (**KC-INFRA-DO-2**).  
  2. Define aws\_secretsmanager\_secret and aws\_secretsmanager\_secret\_version for DB credentials (**KC-INFRA-DO-10**), potentially using random\_password.  
  3. Define aws\_db\_instance resource:  
     * engine \= "postgres", engine\_version \= "15.x" (verify pgvector support).  
     * instance\_class \= var.db\_instance\_class (e.g., "db.t4g.micro").  
     * allocated\_storage \= 20\.  
     * db\_subnet\_group\_name, vpc\_security\_group\_ids \= \[aws\_security\_group.sg\_rds.id\].  
     * multi\_az \= true.  
     * username, password sourced from Secrets Manager (**KC-INFRA-DO-10**).  
     * db\_name \= "knowledge\_cards".  
     * backup\_retention\_period \= 7\. skip\_final\_snapshot \= false for production.  
     * Check if a custom parameter\_group\_name is needed for pgvector or other settings.  
  4. Strongly recommend defining the RDS instance and its related resources (subnet group, parameter group if needed) within a dedicated Terraform module (e.g., modules/rds).  
  5. Run terraform plan and terraform apply.  
  6. **Post-Provisioning/Migration:** Ensure the command CREATE EXTENSION IF NOT EXISTS vector; is run against the provisioned database. **Recommended approach:** Add this command to a new Prisma migration file (prisma/migrations/.../migration.sql) and run prisma migrate deploy as part of your deployment process (**Missing from CI/CD ticket \- needs addressing**).

**7\. Ticket: KC-INFRA-DO-6: Setup ElastiCache Redis Instance (Terraform)**

* **Prompt:** Provision an ElastiCache Redis instance using Terraform, as specified in **JIRA Ticket KC-INFRA-DO-6**.  
  1. Define aws\_elasticache\_subnet\_group using private subnets (**KC-INFRA-DO-2**).  
  2. Define aws\_elasticache\_cluster (single node) or aws\_elasticache\_replication\_group (multi-AZ):  
     * engine \= "redis", engine\_version \= "7.x".  
     * node\_type \= var.redis\_node\_type (e.g., "cache.t3.micro").  
     * num\_cache\_nodes \= 1 (for cluster) or configure replicas for replication group.  
     * subnet\_group\_name, security\_group\_ids \= \[aws\_security\_group.sg\_redis.id\].  
  3. Strongly recommend defining the ElastiCache instance and its related resources (subnet group, parameter group if needed) within a dedicated Terraform module (e.g., modules/redis).  
  4. Run terraform plan and terraform apply.  
  5. Note the primary endpoint address for application configuration (e.g., REDIS\_URL env var).

**8\. Ticket: KC-INFRA-DO-7: Setup S3 Bucket for Storage (Terraform)**

* **Prompt:** Provision a private S3 bucket for file storage using Terraform, as specified in **JIRA Ticket KC-INFRA-DO-7**.  
  1. Define aws\_s3\_bucket resource with a unique bucket name.  
  2. Define aws\_s3\_bucket\_public\_access\_block to block all public access.  
  3. Define aws\_s3\_bucket\_versioning (optional but recommended).  
  4. Configure permissions: Modify the ECS Task Role's IAM policy (**KC-INFRA-DO-8**) to allow s3:PutObject, s3:GetObject, s3:DeleteObject actions on arn:aws:s3:::${var.s3\_bucket\_name}/\*.  
  5. Define aws\_s3\_bucket\_cors\_configuration if direct browser uploads are planned later.  
  6. Consider defining the S3 bucket and its configurations within a dedicated Terraform module (e.g., modules/s3).  
  7. Run terraform plan and terraform apply.  
  8. Note the bucket name for application configuration (e.g., S3\_BUCKET\_NAME env var).

**9\. Ticket: KC-INFRA-DO-10: Setup Secrets Management (AWS Secrets Manager, Terraform)**

* **Prompt:** Set up AWS Secrets Manager for sensitive data using Terraform, as specified in **JIRA Ticket KC-INFRA-DO-10**.  
  1. Define aws\_secretsmanager\_secret resources for:  
     * Database credentials (knowledge-card/db-credentials).  
     * NextAuth Secret (knowledge-card/nextauth-secret).  
     * Any other API keys/secrets.  
  2. Define aws\_secretsmanager\_secret\_version to populate initial values. Use JSON structure for DB creds: {"username":"...", "password":"...", "host":"...", "port":5432, "dbname":"..."}. Use random\_string or random\_password for generating initial secrets securely within Terraform.  
  3. Update ECS Task Role's IAM policy (**KC-INFRA-DO-8**) to allow secretsmanager:GetSecretValue on the specific ARNs of the created secrets.  
  4. Consider defining secrets within relevant Terraform modules (e.g., DB secret in RDS module) or a dedicated secrets module.  
  5. Run terraform plan and terraform apply.  
  6. Reference these secret ARNs when defining environment variables in the ECS Task Definition (**KC-INFRA-DO-8**).

**10\. Ticket: KC-INFRA-DO-8: Setup ECS Cluster & Fargate Service Definition (Terraform)**

* **Prompt:** Provision the ECS cluster, task definition, and Fargate service using Terraform, as specified in **JIRA Ticket KC-INFRA-DO-8**.  
  1. Define aws\_ecs\_cluster.  
  2. Define aws\_iam\_role.ecs\_task\_execution\_role and attach AmazonECSTaskExecutionRolePolicy.  
  3. Define aws\_iam\_role.ecs\_task\_role and attach a custom aws\_iam\_role\_policy granting necessary permissions (e.g., secretsmanager:GetSecretValue on specific secret ARNs from **KC-INFRA-DO-10**, s3:\*Object on bucket ARN from **KC-INFRA-DO-7**).  
  4. Define aws\_ecs\_task\_definition:  
     * family, requires\_compatibilities \= \["FARGATE"\], network\_mode \= "awsvpc".  
     * cpu, memory (e.g., 512, 1024).  
     * execution\_role\_arn, task\_role\_arn.  
     * container\_definitions: JSON string defining the app container:  
       * name: "knowledge-card-app"  
       * image: ${aws\_ecr\_repository.app.repository\_url}:latest (Tag will be updated by CI/CD)  
       * portMappings: \[{ "containerPort": 3000, "hostPort": 3000 }\]  
       * environment: Define non-sensitive env vars (e.g., REDIS\_URL, S3\_BUCKET\_NAME).  
       * secrets: Map sensitive env vars (e.g., DATABASE\_URL, NEXTAUTH\_SECRET) to Secrets Manager ARNs using valueFrom. Example: {"name": "DATABASE\_URL", "valueFrom": "${aws\_secretsmanager\_secret.db\_creds.arn}"} (Note: Format might need adjustment based on how DB URL is constructed from JSON secret).  
       * logConfiguration: Configure awslogs driver (**KC-INFRA-DO-12**).  
  5. Define aws\_ecs\_service:  
     * name, cluster, task\_definition (use .arn).  
     * desired\_count \= 2\. launch\_type \= "FARGATE".  
     * network\_configuration: subnets (private subnet IDs), security\_groups \= \[aws\_security\_group.sg\_ecs\_task.id\].  
     * load\_balancer: target\_group\_arn from **KC-INFRA-DO-9**.  
  6. Strongly recommend defining the ECS cluster, task definition, service, and related IAM roles within a dedicated Terraform module (e.g., modules/ecs).  
  7. Run terraform plan and terraform apply.

**11\. Ticket: KC-INFRA-DO-9: Setup Application Load Balancer (ALB) & DNS (Terraform)**

* **Prompt:** Provision an ALB and configure DNS using Terraform, as specified in **JIRA Ticket KC-INFRA-DO-9**.  
  1. Ensure an ACM certificate for your domain is provisioned and validated. Store its ARN.  
  2. Define aws\_lb (Application Load Balancer): internal \= false, place in public subnets, assign sg\_alb.  
  3. Define aws\_lb\_target\_group: port \= 3000, protocol \= "HTTP", vpc\_id, target\_type \= "ip". Configure health\_check using /api/health path (**KC-INFRA-BE-1**).  
  4. Define aws\_lb\_listener for HTTPS (443): Forward to target group, reference ACM certificate\_arn.  
  5. Define aws\_lb\_listener for HTTP (80): Redirect action to HTTPS.  
  6. Define aws\_route53\_record (Type A, Alias) pointing your application domain (var.app\_domain) to the ALB's DNS name and zone ID. (Assumes Route 53 hosted zone exists or is managed by Terraform).  
  7. Update aws\_ecs\_service (**KC-INFRA-DO-8**) load\_balancer block with the target group ARN.  
  8. Strongly recommend defining the ALB, target group, listeners, and related DNS records within a dedicated Terraform module (e.g., modules/alb).  
  9. Run terraform plan and terraform apply.

**12\. Ticket: KC-INFRA-BE-1: Implement Health Check Endpoint**

* **Prompt:** Implement a simple health check endpoint in the Next.js application, as specified in **JIRA Ticket KC-INFRA-BE-1**.  
  1. Create src/app/api/health/route.ts.  
  2. Implement the GET handler:  
     import { NextResponse } from 'next/server';

     export async function GET(request: Request) {  
       // Add DB check or other checks later if needed  
       // For now, just return OK if the server is running  
       return NextResponse.json({ status: 'ok', timestamp: Date.now() });  
     }

  3. Ensure no authentication is required for this route.  
  4. Test locally: curl http://localhost:3000/api/health.

**13\. Ticket: KC-INFRA-DO-12: Setup Basic CloudWatch Logging/Monitoring (Terraform)**

* **Prompt:** Configure basic CloudWatch logging and monitoring using Terraform, as specified in **JIRA Ticket KC-INFRA-DO-12**.  
  1. Define aws\_cloudwatch\_log\_group for the application (e.g., /ecs/knowledge-card-app). Set retention\_in\_days.  
  2. Update container\_definitions in aws\_ecs\_task\_definition (**KC-INFRA-DO-8**) to include logConfiguration using awslogs driver, referencing the created log group name.  
  3. Define aws\_cloudwatch\_metric\_alarm resources for:  
     * ECS Service CPU Utilization (\> 80%).  
     * ECS Service Memory Utilization (\> 80%).  
     * ALB Target Group UnHealthyHostCount (\> 0).  
     * ALB 5xx Errors (HTTPCode\_Target\_5XX\_Count \> threshold).  
  4. Configure alarm actions (e.g., notify an SNS topic \- requires aws\_sns\_topic setup).  
  5. Consider defining CloudWatch resources within relevant service modules or a dedicated monitoring module.  
  6. Run terraform plan and terraform apply. Verify logs appear in CloudWatch and alarms are created.

**14\. Ticket: KC-INFRA-DO-11: Enhance CI/CD Pipeline for AWS Deployment (GitHub Actions)**

* **Prompt:** Update the GitHub Actions workflow (.github/workflows/deploy.yml) for automated AWS deployment, as specified in **JIRA Ticket KC-INFRA-DO-11**.  
  1. Trigger workflow on push/merge to main branch.  
  2. **Configure AWS Credentials:** Use aws-actions/configure-aws-credentials@v4 action with OIDC. Configure role-to-assume (arn:aws:iam::ACCOUNT\_ID:role/CICDPipelineRole from **KC-INFRA-DO-1**) and aws-region.  
  3. **Login to ECR:** Use aws-actions/amazon-ecr-login@v2.  
  4. **Build, Tag, Push Docker Image:**  
     * Get ECR repository URI (aws ecr describe-repositories... or store as variable/secret).  
     * Generate image tag (e.g., IMAGE\_TAG=${{ github.sha }}).  
     * Run docker build \-t $ECR\_REGISTRY/$ECR\_REPOSITORY:$IMAGE\_TAG ..  
     * Run docker push $ECR\_REGISTRY/$ECR\_REPOSITORY:$IMAGE\_TAG.  
  5. **Deploy to ECS (Recommended: Helper Action):**  
     * Use aws-actions/amazon-ecs-deploy-task-definition@v1.  
     * Provide path to a task definition JSON file (task-definition.json). This file should be similar to the container\_definitions part of the Terraform resource but parameterized for the image URI.  
     * The action registers a new task definition revision with the pushed image URI.  
     * Specify the ECS service name and cluster name.  
     * The action updates the ECS service to use the new task definition revision, triggering a deployment.  
  6. **(Alternative: AWS CLI)** Script steps using aws ecs describe-task-definition, update JSON, aws ecs register-task-definition, aws ecs update-service. More complex.  
  7. Ensure workflow has necessary environment variables/secrets (AWS region, ECR repo name, ECS cluster/service name, task definition file path).  
  8. Test by merging changes to main. Monitor workflow run, ECR, and ECS service deployment status. **Remember to address database migrations separately.**