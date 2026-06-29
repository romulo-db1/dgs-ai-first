import { CosmosClient } from '@azure/cosmos';
import { app, HttpRequest, HttpResponseInit } from '@azure/functions';
import { z } from 'zod';

import { logger } from '../../shared/logger';

const FeedbackSchema = z
    .object({
        queryId: z.string().min(1, 'queryId is required'),
        rating: z.number().int().min(1).max(5),
        comment: z.string().max(2000).optional(),
        attendantEmail: z.string().email()
    })
    .strict();

type FeedbackInput = z.infer<typeof FeedbackSchema>;

const cosmosConnectionString = process.env.COSMOS_CONNECTION_STRING;

if (!cosmosConnectionString) {
    throw new Error('Missing required environment variable: COSMOS_CONNECTION_STRING');
}

const cosmosClient = new CosmosClient(cosmosConnectionString);
const feedbackContainer = cosmosClient
    .database('novatech')
    .container('feedbacks');

function buildJsonResponse(status: number, jsonBody: unknown): HttpResponseInit {
    return {
        status,
        headers: {
            'Content-Type': 'application/json; charset=utf-8'
        },
        jsonBody
    };
}

export async function feedbackHandler(
    request: HttpRequest
): Promise<HttpResponseInit> {
    let rawBody: unknown;

    try {
        rawBody = await request.json();
    } catch {
        logger.warn({ route: 'feedback' }, 'Invalid JSON payload');

        return buildJsonResponse(400, {
            error: {
                code: 'INVALID_JSON',
                message: 'Request body must be valid JSON.'
            }
        });
    }

    const parsedBody = FeedbackSchema.safeParse(rawBody);

    if (!parsedBody.success) {
        logger.warn(
            {
                route: 'feedback',
                validationErrors: parsedBody.error.issues.map((issue) => ({
                    path: issue.path.join('.'),
                    message: issue.message,
                    code: issue.code
                }))
            },
            'Feedback payload validation failed'
        );

        return buildJsonResponse(400, {
            error: {
                code: 'INVALID_PAYLOAD',
                message: 'Request body validation failed.',
                details: parsedBody.error.issues.map((issue) => ({
                    path: issue.path.join('.'),
                    message: issue.message,
                    code: issue.code
                }))
            }
        });
    }

    const feedbackInput: FeedbackInput = parsedBody.data;
    const feedbackToPersist = {
        queryId: feedbackInput.queryId,
        rating: feedbackInput.rating,
        comment: feedbackInput.comment,
        attendantEmail: feedbackInput.attendantEmail,
        timestamp: new Date().toISOString()
    };

    try {
        await feedbackContainer.items.create(feedbackToPersist);

        logger.info(
            {
                queryId: feedbackInput.queryId,
                rating: feedbackInput.rating
            },
            'Feedback persisted successfully'
        );

        return buildJsonResponse(201, {
            message: 'Feedback created successfully.'
        });
    } catch (error) {
        logger.error(
            {
                queryId: feedbackInput.queryId,
                rating: feedbackInput.rating,
                err: error
            },
            'Failed to persist feedback'
        );

        return buildJsonResponse(503, {
            error: {
                code: 'PERSISTENCE_UNAVAILABLE',
                message: 'Feedback service is temporarily unavailable.'
            }
        });
    }
}

app.http('feedback', {
    methods: ['POST'],
    handler: feedbackHandler
});