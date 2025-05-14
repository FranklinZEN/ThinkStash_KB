### Best Practices for `cloudbuild.yaml`

1.  **Use Official Cloud Builders or Minimal Custom Images:**
    *   Prefer official builders from Google (`gcr.io/cloud-builders/...`) as they are maintained and optimized.
    *   If you need custom tools, build small, focused Docker images for your build steps rather than installing tools on the fly in each step. This speeds up builds and makes them more reproducible.

2.  **Minimize Build Step Duration:**
    *   Each step runs in its own container. Keep steps focused on a single task.
    *   Utilize caching mechanisms (like Docker layer caching or `gsutil` for dependencies) where appropriate to speed up subsequent builds.

3.  **Optimize Docker Builds:**
    *   Use multi-stage Dockerfiles to keep your final runtime images small and secure. The first stage can be for building/compiling, and the final stage copies only the necessary artifacts.
    *   Ensure your `.dockerignore` file is comprehensive to avoid copying unnecessary files into your Docker build context (e.g., `.git`, `node_modules` if handled in Dockerfile, local environment files).

4.  **Manage Secrets Securely:**
    *   Use Cloud Build's integration with Secret Manager to handle sensitive data (API keys, passwords) needed during the build. Don't hardcode secrets in `cloudbuild.yaml` or check them into source control.
    *   For runtime secrets, your application (e.g., running on Cloud Run) should fetch them directly from Secret Manager.

5.  **Principle of Least Privilege for Service Accounts:**
    *   The Cloud Build service account (`[PROJECT_NUMBER]@cloudbuild.gserviceaccount.com`) needs permissions to perform actions like pushing to Artifact Registry, deploying to Cloud Run, accessing secrets, etc.
    *   Grant only the necessary roles and permissions. Avoid overly broad roles like "Project Editor."
    *   If deploying services, consider having the Cloud Build service account impersonate the runtime service account of your application for deployment, ensuring the runtime SA also follows least privilege.

6.  **Use Substitutions for Configuration:**
    *   Leverage Cloud Build substitutions (`_VARIABLE_NAME` or `${_VARIABLE_NAME}`) for environment-specific configurations (e.g., project ID, region, service names, image tags like `$COMMIT_SHA` or `$TAG_NAME`). This makes your `cloudbuild.yaml` reusable across different environments or triggers.
    *   Define default values for substitutions in your trigger settings or pass them via `gcloud builds submit --substitutions=...`.

7.  **Specify Builder Versions:**
    *   Pin versions of builders (e.g., `gcr.io/cloud-builders/docker:latest` is okay for some, but specific versions like `gcr.io/cloud-builders/gsutil:4.58` can be more stable) or base images in your Dockerfiles to avoid unexpected changes breaking your build.

8.  **Parallelize Steps (When Possible):**
    *   If you have independent build steps (e.g., linting different parts of a monorepo, building independent microservices), you can define them to run in parallel by not setting `waitFor` or by using `waitFor: ['-']` for steps that can start immediately. This can significantly reduce total build time.

9.  **Clear Naming and Comments:**
    *   Use the `id` field for steps to give them meaningful names.
    *   Add comments (`#`) in your `cloudbuild.yaml` to explain complex steps or non-obvious configurations.

10. **Robust Error Handling and Logging:**
    *   Ensure your scripts and tools within build steps exit with non-zero status codes on failure so Cloud Build correctly marks the step (and build) as failed.
    *   Structure your logs (e.g., JSON for application logs if testing within a build step) for easier debugging in Cloud Logging.

11. **Control Build Concurrency:**
    *   Be aware of your project's concurrent build limits. If you have many triggers, you might need to manage concurrency or request an increase.

12. **Optimize for Cost:**
    *   Choose appropriate machine types for your builds (`options: { machineType: 'E2_HIGHCPU_8' }`). More powerful machines cost more but can reduce build time. Find a balance.
    *   Minimize unnecessary operations and data transfer.

13. **Regularly Review and Refactor:**
    *   As your project evolves, revisit your `cloudbuild.yaml` to ensure it's still optimal and secure.

---

### Next Steps for `cloudbuild.yaml` (Sequential Run):

1.  **Build Prisma Client:**
    *   **Action:** Generate the Prisma client.
    *   **Command:** `npm run prisma:generate` (assuming this script exists in `package.json` and runs `prisma generate`).
    *   **Builder:** `gcr.io/cloud-builders/npm`
    *   **Purpose:** Ensures the Prisma client is up-to-date with your schema before building the application.

2.  **Build Next.js Application:**
    *   **Action:** Compile the Next.js application for production.
    *   **Command:** `npm run build`
    *   **Builder:** `gcr.io/cloud-builders/npm`
    *   **Purpose:** Creates an optimized production build of your Next.js app.

3.  **Build Docker Image:**
    *   **Action:** Package the application into a Docker image.
    *   **Command:** `docker build -t YOUR_GCP_REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/YOUR_ARTIFACT_REGISTRY_REPO/kc-nextjs-backend:$COMMIT_SHA .`
        *   We'll need to replace the placeholders (YOUR_GCP_REGION, YOUR_GCP_PROJECT_ID, YOUR_ARTIFACT_REGISTRY_REPO) with actual values or Cloud Build substitutions. `$COMMIT_SHA` is a built-in substitution providing the commit ID.
    *   **Builder:** `gcr.io/cloud-builders/docker`
    *   **Purpose:** Creates a container image that can be deployed. This step relies on having a `Dockerfile` in your project root.

4.  **Push Docker Image to Artifact Registry:**
    *   **Action:** Upload the built Docker image to Google Artifact Registry.
    *   **Command:** `docker push YOUR_GCP_REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/YOUR_ARTIFACT_REGISTRY_REPO/kc-nextjs-backend:$COMMIT_SHA`
    *   **Builder:** `gcr.io/cloud-builders/docker`
    *   **Purpose:** Stores the image in a central, secure registry, making it available for deployment.
    *   **Permissions:** The Cloud Build service account will need the "Artifact Registry Writer" role on your Artifact Registry repository.

5.  **Apply Database Migrations (Conditional / Review Complexity):**
    *   **Action:** Run database migrations (e.g., `prisma migrate deploy`).
    *   **Command (example from doc):** Using `gcr.io/google-appengine/exec-wrapper` or `npx prisma migrate deploy`.
    *   **Builder:** This is more complex. The `exec-wrapper` is one option, or running `npx prisma ...` if the built image in a previous step (or a dedicated one) contains Node.js and Prisma CLI.
    *   **Purpose:** Ensures the database schema is compatible with the new application version before it serves traffic.
    *   **Considerations:** As noted in `KC-GCP-CICD-1`, this step can be tricky due to database connectivity from the Cloud Build environment. It requires the Cloud Build service account (or an impersonated one) to have Cloud SQL Client role and network access. We might defer implementing the fully automated version of this step if it proves too complex initially and handle it as a manual or separately scripted step.

6.  **Deploy to Cloud Run:**
    *   **Action:** Deploy the new image to your Cloud Run service.
    *   **Command:** `gcloud run deploy kc-nextjs-backend-service --image=YOUR_GCP_REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/YOUR_ARTIFACT_REGISTRY_REPO/kc-nextjs-backend:$COMMIT_SHA --region=YOUR_GCP_REGION --platform=managed --allow-unauthenticated --service-account=YOUR_BACKEND_SERVICE_ACCOUNT_EMAIL` (placeholders need to be set).
    *   **Builder:** `gcr.io/google.com/cloudsdktool/cloud-sdk`
    *   **Purpose:** Updates the Cloud Run service to use the newly pushed Docker image.
    *   **Permissions:** The Cloud Build service account needs "Cloud Run Admin" and "Service Account User" (to act as the runtime service account) roles.

### How We'll Proceed Step-by-Step:

*   For each step above, we'll add the configuration to `cloudbuild.yaml`.
*   After adding a step, you'll commit and push the changes.
*   We'll observe the Cloud Build trigger to see if the step executes successfully.
*   If there are issues, we'll troubleshoot them. 