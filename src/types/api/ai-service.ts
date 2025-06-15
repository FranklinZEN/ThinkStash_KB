// --- Common Types ---
export interface ContentBlock {
  block_id: string;
  tmp_id?: string | null;
  user_id: string;
  document_id: string;
  type: string; // e.g., 'text', 'heading', 'list', 'image', 'code_snippet', etc.
  order_index?: number | null;
  content?: string | null; // Primary text for 'text', 'heading', 'code_snippet', 'table'
  page_number?: number | null;
  bbox?: number[] | null;
  level?: number | null; // For 'heading'
  language?: string | null; // For 'code_snippet'
  items?: (string | ContentBlock)[] | null; // For 'list' - Changed Record<string, any> to ContentBlock
  ordered?: boolean | null; // For 'list'
  list_start_number?: number | null; // For 'list'
  image_id_ref?: string | null; // For 'image'
  gcs_url?: string | null; // For 'image'
  alt_text?: string | null; // For 'image'
  caption?: string | null; // For 'image'
  llm_description?: string | null; // For 'image'
  width?: number | null; // For 'image'
  height?: number | null; // For 'image'
}

export interface DocumentMetadata {
  title?: string;
  source_url?: string;
  publication_date?: string;
  author?: string;
  // Add other relevant metadata fields
}

// --- /api/ai/reconstruct-and-analyze ---

// Request to the Python AI service's /reconstruct_and_analyze endpoint
export interface AIServiceReconstructAndAnalyzeRequest {
  // MODIFIED: Replace source_url, file_id, text_content with source_identifier
  // source_url?: string;
  // file_id?: string; // e.g., GCS file ID
  // text_content?: string; // Direct text input
  source_identifier: string; // Consolidated field
  source_type: 'url' | 'file' | 'text';
  user_id: string;
  job_id: string; // Added job_id
  // Optional: configuration for reconstruction and analysis
  config?: {
    reconstruction_mode?: 'default' | 'ocr_only' | 'layout_aware';
    analysis_level?: 'basic' | 'detailed';
    // ... other config options
  };
}

// Response from the Python AI service's /reconstruct_and_analyze endpoint
// This is what the Python service actually returns.
export interface PythonReconstructAndAnalyzeServiceResponse {
  message: string;
  document_id: string; // This is the reconstruction_id from Python service
  job_id: string;
  status_code: number;
  // ... other fields the Python service might return
  reconstructed_content?: ContentBlock[];
  analysis_output?: unknown; // Changed any to unknown
}

// Request body for THIS Next.js API route (/api/ai/reconstruct-and-analyze)
export interface ReconstructAndAnalyzeRequest {
  source_url?: string;
  file_id?: string; // e.g., GCS file ID
  text_content?: string; // Direct text input
  // source_type is inferred in the Next.js route based on provided fields
  config?: AIServiceReconstructAndAnalyzeRequest['config']; // Re-use config from AI service type
}

// Response from THIS Next.js API route (/api/ai/reconstruct-and-analyze)
// This is what our Next.js API endpoint will return to the client.
export interface NextJSReconstructAndAnalyzeResponse {
  message: string;
  reconstruction_id: string; // This will be the document_id from the Python service
  job_id: string;
}

// Placeholder for EnrichedImageMetadata from Python aiservice
export interface EnrichedImageMetadata {
  image_id: string;
  original_url?: string;
  gcs_url?: string;
  description?: string;
  width?: number;
  height?: number;
  format?: string;
  // Add other relevant fields from your Python EnrichedImageMetadata model
}

// OrchestrationOutput should accurately reflect the response from the Python aiservice's
// reconstruction pipeline (specifically, the ParallelOrchestrator's output object).
export interface OrchestrationOutput {
  document_id?: string | null; // This is the reconstruction_id (can be job_id if full doc obj not created)
  user_id?: string | null;
  // job_id: string; // job_id is available on the input and used as fallback for document_id in route.ts; Python output object itself has document_id.

  status_code: string; // From Python: "success", "failure_routing", "partial_success_..." etc.
  source_identifier: string; // From Python: OrchestrationOutput.source_identifier
  source_type: string; // From Python: OrchestrationOutput.source_type
  processing_level_used?: string; // From Python: OrchestrationOutput.processing_level_used
  extracted_title?: string | null; // From Python: OrchestrationOutput.extracted_title
  is_long_article: boolean; // From Python: OrchestrationOutput.is_long_article (even if placeholder)
  original_content_blocks: ContentBlock[]; // From Python: OrchestrationOutput.original_content_blocks
  processed_images_data?: { [key: string]: EnrichedImageMetadata }; // From Python: OrchestrationOutput.processed_images_data
  document_metadata?: DocumentMetadata | null; // From Python: OrchestrationOutput.document_metadata
  error_message?: string | null; // From Python: OrchestrationOutput.error_message
}

// --- /api/ai/rewrite-content ---
export interface RewriteContentRequest {
  // document_id: string; // Removed: Route expects content blocks directly, not a document_id to fetch them
  content_blocks_to_rewrite: ContentBlock[]; // Changed from content_blocks and name updated
  document_metadata?: DocumentMetadata; // Added: Route uses this
  rewrite_instructions?: string;
  user_id?: string; // Added: Route checks this, though prioritizes session
}

export interface RewriteContentResponse {
  rewritten_document_id?: string | null; // ID for the set of rewritten blocks
  ai_rewritten_content_blocks: ContentBlock[];
  status_code?: string; // Status from the rewrite operation
  error_message?: string | null;
  processing_time_ms?: number | null;
  // original_content_blocks could be returned by Next.js if needed by client for immediate comparison,
  // but it's not part of the Python service output for this specific call.
  // Client can manage original blocks if submitted.
}

// --- /api/ai/generate-title ---
export interface GenerateTitleRequest {
  card_id: string;
  content_blocks: ContentBlock[]; // Content to generate title from
}

export interface GenerateTitleResponse {
  suggested_title: string;
  alternatives?: string[]; // Optional: other suggestions
  error_message?: string;
}

// --- /api/ai/generate-keywords ---
export interface GenerateKeywordsRequest {
  content_blocks: ContentBlock[]; // Content to generate keywords from
  existing_keywords?: string[]; // Optional: to avoid duplicates or provide context
  max_keywords?: number; // Optional: limit number of keywords
  // user_id is typically inferred from session
}

export interface GenerateKeywordsResponse {
  suggested_keywords: string[];
  error_message?: string;
}

// --- Knowledge Card related types (if they are part of ai-service.ts, otherwise move them) ---
// These seem more general and might belong in a different types file (e.g., knowledge-card.ts)
// For now, keeping them if they were part of the original linting error context.

export interface ImageRecord {
  id: string;
  gcs_url: string;
  filename?: string;
  size?: number;
  type?: string; // MIME type
  knowledge_card_id: string;
  created_at: string;
  // Optional: if you store alt text or captions generated by AI
  alt_text?: string;
  caption?: string;
}

export interface Tag {
  id: string;
  name: string;
}

// Renamed to avoid conflict with the more detailed one below
export interface KnowledgeCardPrismaDM {
  id: string;
  userId: string;
  title: string;
  content: ContentBlock[]; // Using the common ContentBlock type
  folderId?: string | null;
  tags: Tag[];
  imageRecords: ImageRecord[]; // Using the ImageRecord type
  createdAt: string; // ISO date string
  updatedAt: string; // ISO date string
  isStarred: boolean;
}

export interface UpdateCardRequest {
  title?: string;
  content?: ContentBlock[];
  folderId?: string | null;
  tags?: string[]; // Array of tag names or IDs to associate
  isStarred?: boolean;
  // other updatable fields
}

// Added CreateCardRequest for the POST /api/cards endpoint
export interface CreateCardRequest {
  title: string;
  content: ContentBlock[];
  folderId?: string | null;
  tags?: string[];
  isStarred?: boolean;
}

// The response for Get Card / Create Card / Update Card would likely be the full KnowledgeCard object
// This type should closely mirror your Prisma 'KnowledgeCard' model,
// including relations you expect to populate.
export interface KnowledgeCardResponse {
  id: string;
  title: string;
  content: Record<string, unknown>[]; // Changed from any[] to Record<string, unknown>[]
  userId: string;
  folderId?: string | null;
  tags: { id: string; name: string }[]; // Example: populated tags
  imageRecords?: {
    // Example: populated image records
    id: string;
    appServedUrl: string;
    gcsPath: string;
    contentType: string;
    originalFilename: string;
    size: number;
  }[];
  createdAt: string; // ISO 8601 datetime string
  updatedAt: string; // ISO 8601 datetime string
  isStarred: boolean;
}

// Specific to reconstruct-and-analyze endpoint in Next.js API
export interface NextJSReconstructAndAnalyzeResponse {
  message: string;
  reconstruction_id: string; // Changed from any to string
  job_id: string;
}

// Response from the /reconstruct_and_analyze endpoint of the Python AI service
export interface ReconstructAndAnalyzeResponse {
  message: string;
  reconstruction_id: string; // Changed from any to string
  status_code: number;
  // Optional fields based on Python service response
  job_id?: string;
  document_id?: string; // Often the same as reconstruction_id from Python service
}
