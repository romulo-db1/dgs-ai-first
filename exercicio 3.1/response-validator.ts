import { logger } from "../shared/logger";
import { z } from "zod";

// Keep the structured contract explicit so the validator can reject malformed
// or underspecified model output before it reaches the rest of the pipeline.
export const StructuredAnswerSchema = z
    .object({
        // Final answer shown to the support agent.
        answer: z.string().trim().min(1, "answer must be non-empty"),
        // Source document identifier used to ground the answer (e.g., POL-001).
        source_document: z
            .string()
            .trim()
            .min(1, "source_document must be non-empty"),
        // Confidence score in the inclusive range [0, 1].
        confidence_score: z
            .number()
            .min(0, "confidence_score must be >= 0")
            .max(1, "confidence_score must be <= 1"),
    })
    .strict();

export type StructuredAnswer = z.infer<typeof StructuredAnswerSchema>;

// Backward-compatible aliases for the previous naming used in the repo.
export const ragResponseSchema = StructuredAnswerSchema;
export type RagResponse = StructuredAnswer;

export type StructuredAnswerValidationRejectionReason =
    | "invalid-json"
    | "invalid-format"
    | "content-guardrail";

export type StructuredAnswerValidationResult =
    | {
        status: "approved";
        response: StructuredAnswer;
    }
    | {
        status: "rejected";
        reason: StructuredAnswerValidationRejectionReason;
        response: StructuredAnswer;
    };

export const SAFE_STRUCTURED_ANSWER: StructuredAnswer = {
    answer:
        "Não é possível confirmar a devolução pelo processo padrão para carga perigosa. Consulte a POL-001 antes de prosseguir.",
    source_document: "POL-001",
    confidence_score: 0,
};

const DANGEROUS_CARGO_PATTERN = /\b(?:carga\s+perigosa|cargas\s+perigosas|material\s+perigoso|hazardous\s+cargo|dangerous\s+cargo)\b/i;
const RETURN_PATTERN = /\b(?:devolu[cç][aã]o|devolver|devolvido|devolvida|retorno|retornar|return)\b/i;
const NEGATIVE_RETURN_PATTERN = /\b(?:não\s+(?:é\s+)?poss(?:i|í)vel|não\s+pode|não\s+deve|não\s+é\s+permitido|proibid[oa]s?|vedad[oa]s?)\b/i;
const AFFIRMATIVE_RETURN_PATTERN = /\b(?:é\s+)?poss(?:i|í)vel\b|\bpode\b|\bpermitid[oa]s?\b|\bautorizad[oa]s?\b|\baceit[oa]s?\b/i;

function parseRawModelOutput(rawOutput: unknown): unknown {
    if (typeof rawOutput !== "string") {
        return rawOutput;
    }

    try {
        return JSON.parse(rawOutput) as unknown;
    } catch {
        return undefined;
    }
}

function summarizeIssues(issues: z.ZodIssue[]): string {
    return issues
        .map((issue) => {
            const path = issue.path.length > 0 ? issue.path.join(".") : "<root>";
            return `${path}: ${issue.message}`;
        })
        .join("; ");
}

function mentionsDangerousCargoAndReturn(answer: string): boolean {
    return DANGEROUS_CARGO_PATTERN.test(answer) && RETURN_PATTERN.test(answer);
}

function containsRequiredNegative(answer: string): boolean {
    return NEGATIVE_RETURN_PATTERN.test(answer);
}

function containsPositiveReturnAssertion(answer: string): boolean {
    return AFFIRMATIVE_RETURN_PATTERN.test(answer);
}

function rejectStructuredAnswer(
    reason: StructuredAnswerValidationRejectionReason,
    logMessage: string,
    details?: Record<string, string>,
): StructuredAnswerValidationResult {
    logger.warn(details ?? {}, logMessage);
    return {
        status: "rejected",
        reason,
        response: SAFE_STRUCTURED_ANSWER,
    };
}

// Deterministic validator that complements the probabilistic prompt output.
// It never forwards an invalid response; all failures collapse to the safe
// fallback so downstream code can continue without special casing.
export function validateStructuredAnswer(
    rawOutput: unknown,
): StructuredAnswerValidationResult {
    const parsedOutput = parseRawModelOutput(rawOutput);
    if (parsedOutput === undefined) {
        return rejectStructuredAnswer(
            "invalid-json",
            "Structured answer rejected: model output is not valid JSON.",
        );
    }

    const result = StructuredAnswerSchema.safeParse(parsedOutput);
    if (!result.success) {
        return rejectStructuredAnswer(
            "invalid-format",
            "Structured answer rejected: schema validation failed.",
            { issues: summarizeIssues(result.error.issues) },
        );
    }

    const structuredAnswer = result.data;
    const answerText = structuredAnswer.answer;

    // This guardrail is intentionally separate from schema validation: a well-
    // formed answer can still violate the product policy in its prose.
    if (mentionsDangerousCargoAndReturn(answerText)) {
        if (containsRequiredNegative(answerText)) {
            return {
                status: "approved",
                response: structuredAnswer,
            };
        }

        if (containsPositiveReturnAssertion(answerText)) {
            return rejectStructuredAnswer(
                "content-guardrail",
                "Structured answer rejected: response asserts that a standard return is possible for dangerous cargo.",
                { source_document: structuredAnswer.source_document },
            );
        }

        return rejectStructuredAnswer(
            "content-guardrail",
            "Structured answer rejected: dangerous cargo and return are both mentioned, but the required negative policy statement is missing.",
            { source_document: structuredAnswer.source_document },
        );
    }

    return {
        status: "approved",
        response: structuredAnswer,
    };
}
