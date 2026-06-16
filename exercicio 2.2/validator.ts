import { z } from "zod";

export const querySchema = z
    .object({
        question: z
            .string()
            .trim()
            .min(1, "question must be non-empty")
            .max(2000, "question must have at most 2000 characters"),
    })
    .strict();

export type QueryInput = z.infer<typeof querySchema>;

export function parseQueryInput(
    body: unknown,
):
    | { success: true; data: QueryInput }
    | { success: false; issues: z.ZodIssue[] } {
    const result = querySchema.safeParse(body);

    if (result.success) {
        return { success: true, data: result.data };
    }

    return { success: false, issues: result.error.issues };
}
