import prisma from '@/lib/prisma';
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
    throw new Error("GCS_BUCKET_NAME environment variable not set.");
}
const bucket = storage.bucket(bucketName);

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

    // Generate a unique path for the file in GCS
    const uniqueFileName = `${uuidv4()}-${file.name}`;
    const gcsPath = `uploads/${userId}/${uniqueFileName}`;
    const blob = bucket.file(gcsPath);

    // Stream the file upload to GCS
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

    // Determine the task type and content type for the worker
    let fileAcquisitionType = '';
    const extension = file.name.split('.').pop()?.toLowerCase();
    switch (extension) {
        case 'pdf':
            fileAcquisitionType = 'pdf';
            break;
        case 'docx':
            fileAcquisitionType = 'docx';
            break;
        case 'md':
            fileAcquisitionType = 'md';
            break;
        case 'txt':
            fileAcquisitionType = 'txt';
            break;
        default:
            return new NextResponse(`Unsupported file type: ${extension}`, { status: 400 });
    }

    // Create a task for the worker
    const task = await prisma.task.create({
      data: {
        userId: userId,
        type: 'RECONSTRUCT_AND_ANALYZE_FILE',
        status: 'PENDING',
        payload: { 
            gcsPath: fileGcsUri,
            originalFilename: file.name,
            contentType: file.type, // e.g. application/pdf
            fileAcquisitionType: fileAcquisitionType, // e.g. pdf, docx
        },
        progressMessage: 'File uploaded, task created'
      }
    });

    return NextResponse.json({ taskId: task.id }, { status: 202 });
  } catch (error) {
    console.error('Failed to upload file and create task:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
} 