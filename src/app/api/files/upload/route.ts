import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { NextResponse } from 'next/server';
import { Storage } from '@google-cloud/storage';
import { v4 as uuidv4 } from 'uuid';

// Initialize Google Cloud Storage
const storage = new Storage();
const bucketName = process.env.GCS_BUCKET_NAME || 'thinkstash_media_gcs_bucket';
if (!bucketName) {
    console.error("GCS_BUCKET_NAME environment variable not set.");
    // In a real app, you might want to prevent startup if config is missing.
}
const bucket = storage.bucket(bucketName);
const AI_WORKER_URL = process.env.AI_WORKER_URL || 'http://localhost:8000';

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return new NextResponse('Unauthorized', { status: 401 });
    }
    const userId = session.user.id;

    const formData = await req.formData();
    const file = formData.get('file') as File | null;

    if (!file) {
      return new NextResponse('File is required', { status: 400 });
    }

    const uniqueFileName = `${uuidv4()}-${file.name}`;
    const gcsPath = `uploads/${userId}/${uniqueFileName}`;
    const blob = bucket.file(gcsPath);

    const fileBuffer = Buffer.from(await file.arrayBuffer());
    await new Promise((resolve, reject) => {
        const stream = blob.createWriteStream({
            resumable: false,
            contentType: file.type,
        });
        stream.on('finish', resolve);
        stream.on('error', reject);
        stream.end(fileBuffer);
    });

    const fileGcsUri = `gs://${bucketName}/${gcsPath}`;

    let fileAcquisitionType = '';
    const extension = file.name.split('.').pop()?.toLowerCase();
    switch (extension) {
        case 'pdf': fileAcquisitionType = 'pdf'; break;
        case 'docx': fileAcquisitionType = 'docx'; break;
        case 'md': fileAcquisitionType = 'md'; break;
        case 'txt': fileAcquisitionType = 'txt'; break;
        default:
            return new NextResponse(`Unsupported file type: ${extension}`, { status: 400 });
    }
    
    // Dispatch task directly to Celery worker via the AI service
    const taskId = uuidv4();
    const taskPayload = {
        task_id: taskId,
        user_id: userId,
        source_identifier: fileGcsUri,
        source_type: fileAcquisitionType,
    };

    const dispatchPayload = {
        task_id: taskId,
        task_name: 'aiservice.app.tasks.process_reconstruction_task',
        payload: taskPayload,
    };

    const dispatchResponse = await fetch(`${AI_WORKER_URL}/dispatch-task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dispatchPayload),
    });

    if (!dispatchResponse.ok) {
        const errorBody = await dispatchResponse.text();
        console.error('Failed to dispatch file processing task:', dispatchResponse.status, errorBody);
        return new NextResponse(`Error from AI service: ${errorBody}`, { status: dispatchResponse.status });
    }

    const dispatchData = await dispatchResponse.json();
    return NextResponse.json({ taskId: dispatchData.task_id }, { status: 202 });

  } catch (error) {
    console.error('File upload and task dispatch failed:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
} 