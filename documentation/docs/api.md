# Knowledge Card System API Documentation

## Overview

This document describes the REST API endpoints for the Knowledge Card System. All endpoints require authentication unless otherwise specified.

## Authentication

### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

Response:
```json
{
  "token": "jwt-token",
  "user": {
    "id": "user-id",
    "email": "user@example.com",
    "name": "User Name"
  }
}
```

### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "name": "User Name"
}
```

## Knowledge Cards

### Create Card
```http
POST /api/cards
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Card Title",
  "content": "Card content in markdown",
  "tags": ["tag1", "tag2"],
  "folderId": "folder-id"
}
```

### Get Card
```http
GET /api/cards/:id
Authorization: Bearer <token>
```

### Update Card
```http
PUT /api/cards/:id
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Updated Title",
  "content": "Updated content",
  "tags": ["updated", "tags"]
}
```

### Delete Card
```http
DELETE /api/cards/:id
Authorization: Bearer <token>
```

### Search Cards
```http
GET /api/cards/search
Authorization: Bearer <token>
Query Parameters:
  - q: search query
  - tags: comma-separated tags
  - folderId: folder ID
  - page: page number
  - limit: items per page
```

## Folders

### Create Folder
```http
POST /api/folders
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Folder Name",
  "parentId": "parent-folder-id" // optional
}
```

### Get Folder
```http
GET /api/folders/:id
Authorization: Bearer <token>
```

### Update Folder
```http
PUT /api/folders/:id
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Updated Name",
  "parentId": "new-parent-id"
}
```

### Delete Folder
```http
DELETE /api/folders/:id
Authorization: Bearer <token>
```

## Analytics

### Get Dashboard Data
```http
GET /api/analytics/dashboard
Authorization: Bearer <token>
```

Response:
```json
{
  "totalCards": 100,
  "totalFolders": 10,
  "recentActivity": [...],
  "tagDistribution": {...}
}
```

## Error Responses

All endpoints may return the following error responses:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description",
    "details": {} // optional additional details
  }
}
```

Common error codes:
- `AUTH_REQUIRED`: Authentication required
- `INVALID_CREDENTIALS`: Invalid login credentials
- `NOT_FOUND`: Resource not found
- `VALIDATION_ERROR`: Invalid request data
- `SERVER_ERROR`: Internal server error

## Rate Limiting

API requests are limited to:
- 100 requests per minute for authenticated users
- 20 requests per minute for unauthenticated users

## Versioning

The API is versioned in the URL path:
- Current version: `/api/v1/...`
- Future versions will increment the number

## Pagination

Endpoints that return lists support pagination:
```json
{
  "data": [...],
  "pagination": {
    "total": 100,
    "page": 1,
    "limit": 10,
    "pages": 10
  }
}
```

## WebSocket Events

The system also provides real-time updates via WebSocket:

```javascript
const ws = new WebSocket('ws://api.example.com/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle real-time updates
};
```

Events include:
- `card.created`
- `card.updated`
- `card.deleted`
- `folder.created`
- `folder.updated`
- `folder.deleted` 