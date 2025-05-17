# **JIRA Epics & Tickets: Stage 2 Development Plan \- Summary**

This document provides a summarized list of Epics and their corresponding Tickets for the Knowledge Card System development.

## PHASE A: LOCAL MVP ENHANCEMENT (PRE-GCP)

## Epic 7: KC-OPTIMIZE-S1 \- Pre-Stage 2 Code & Performance Optimization
  * **Status:** COMPLETED
* **Ticket ID: KC-OPTIMIZE-BE-1** \- Profile and Optimize Slow Backend API Routes (Stage 1 Codebase)
  * **Status:** COMPLETED
* **Ticket ID: KC-OPTIMIZE-DB-1** \- Analyze and Optimize Slow Database Queries (Prisma & PostgreSQL \- Stage 1 Codebase)
  * **Status:** COMPLETED
* **Ticket ID: KC-OPTIMIZE-FE-1** \- Profile and Optimize Frontend Rendering Performance (Next.js/React \- Stage 1 Codebase)
  * **Status:** COMPLETED
* **Ticket ID: KC-OPTIMIZE-BUNDLE-1** \- Analyze and Optimize Next.js Application Bundle Size (Stage 1 Codebase)
  * **Status:** COMPLETED

## EPIC: KC-UXUI-ENHANCE-S1-LOCAL \- Comprehensive UI/UX Design (Figma) & Stage 1 Local Enhancement
  * **Status:** COMPLETED
* **Ticket ID: KC-UXUI-FIGMA-DESIGN-ALL** \- Develop Comprehensive Figma Designs for All Stage 1 Features & Prepare for Stage 2 Features
  * **Status:** COMPLETED
* **Ticket ID: KC-UXUI-S1-THEME-IMPLEMENT-1** \- Implement/Update Local Chakra UI Custom Theme based on Comprehensive Figma Design System
  * **Status:** COMPLETED
* **Ticket ID: KC-UXUI-S1-COMP-ENHANCE-1** \- Enhance Existing Stage 1 Frontend Components to Align with New Figma Designs (Local)
  * **Status:** COMPLETED

## EPIC: KC-HASHTAGS-LOCAL \- Hashtag Implementation (Locally)

* **Ticket ID: KC-HASHTAG-DM-1** \- Update Data Model (Prisma Schema) to Support Hashtags (Local DB)
  * **Status:** COMPLETED
* **Ticket ID: KC-HASHTAG-API-1** \- Implement Local Backend API Logic for Managing Hashtags on Cards
  * **Status:** COMPLETED
* **Ticket ID: KC-HASHTAG-FE-1** \- Implement Local Frontend UI for Hashtags (Input, Display, Filter \- Based on Figma Designs)
  * **Status:** PARTIALLY COMPLETED / IN PROGRESS
  * *Details: Input and Display functional. Filter functionality is pending. Figma design alignment for existing UI requires verification.*

## EPIC: KC-DB-RETHINK-S2A-LOCAL \- Database Rethink \- Phase A: Analysis & Local Schema Prep

* **Ticket ID: KC-DB-RETHINK-ANALYZE-1** \- Analyze Current DB Schema and Query Patterns for Performance (Local Focus)  
* **Ticket ID: KC-DB-RETHINK-PROPOSE-1** \- Propose and Document Schema/Index Optimizations (Informing Local & GCP)

## PHASE B: GCP MIGRATION & CORE CLOUD/AI FEATURES

## EPIC: KC-GCP-INFRA \- GCP Foundation & Deployment

* **Ticket ID: KC-GCP-TERRAFORM-1** \- Setup Terraform for GCP Infrastructure Provisioning  
* **Ticket ID: KC-GCP-DB-1** \- Provision Google Cloud SQL for PostgreSQL with pgvector (Reflecting Local Enhancements)  
* **Ticket ID: KC-GCP-STORAGE-1** \- Provision Google Cloud Storage Buckets  
* **Ticket ID: KC-GCP-REDIS-1** \- Provision Google Cloud Memorystore for Redis  
* **Ticket ID: KC-GCP-IAM-SECRETS-1** \- Configure GCP IAM Roles and Google Secret Manager  
* **Ticket ID: KC-GCP-CICD-1** \- Setup CI/CD Pipeline for GCP Deployment (Next.js Backend \- Enhanced App)  
* **Ticket ID: KC-GCP-CICD-2** \- Setup CI/CD Pipeline for GCP Deployment (CrewAI Python Services)  
* **Ticket ID: KC-GCP-MONITOR-1** \- Configure Basic Monitoring and Alerting on GCP

## EPIC: KC-AI-AGENT-S2-GCP \- AI Agent Capabilities \- Stage 2 (CrewAI on GCP)

* **Ticket ID: KC-AI-CREWAI-SETUP-1** \- Setup CrewAI Python Service Environment & Basic Structure (for GCP Deployment)  
* **Ticket ID: KC-AI-LINK-AGENT-1** \- Develop CrewAI Agents for "Create from Link" (FR-CARD-3)  
* **Ticket ID: KC-AI-LINK-API-1** \- Expose "Create from Link" CrewAI Process via API Endpoint (Python Service on GCP)  
* **Ticket ID: KC-AI-LINK-BE-INTEGRATE-1** \- Integrate Next.js Backend (on GCP) with "Create from Link" CrewAI Service (on GCP)  
* **Ticket ID: KC-AI-REGEN-TITLE-AGENT-1** \- Develop CrewAI Agents for AI Title Regeneration (FR-CARD-4)  
  * *(Further tickets for AI Regeneration of Content and Tags would follow)*

## EPIC: KC-CORE-FEAT-S2B-GCP \- Core Cloud Feature Enhancements (GCP)

* **Ticket ID: KC-CORE-SOCIAL-LOGIN-1** \- Implement Social Login (e.g., Google) using NextAuth.js on GCP  
* **Ticket ID: KC-CORE-DATA-IMPORT-1** \- Implement Manual JSON Data Import Feature on GCP

## EPIC: KC-SEMANTIC-FOUND-S2-GCP \- Semantic Search Foundation (Backend on GCP)

* **Ticket ID: KC-SEMANTIC-EMBED-SVC-1** \- Develop Vector Embedding Service for Card Content (on GCP)

*(Further Epics for Stage 2+ features like full Semantic Search UI, RAG Chat, Visualizations, Media Blocks with AI, etc., would be defined later.)*