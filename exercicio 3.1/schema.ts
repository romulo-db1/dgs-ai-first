import { z } from "zod";

export const StructuredAnswerSchema = z
    .object({
        // Resposta final exibida ao atendente.
        answer: z.string().trim().min(1, "answer must be non-empty"),
        // Identificador do documento-fonte que ancora a resposta (ex.: POL-001).
        source_document: z
            .string()
            .trim()
            .min(1, "source_document must be non-empty"),
        // Score de confiança no intervalo inclusivo [0, 1].
        confidence_score: z
            .number()
            .min(0, "confidence_score must be >= 0")
            .max(1, "confidence_score must be <= 1"),
    })
    .strict();

export type StructuredAnswer = z.infer<typeof StructuredAnswerSchema>;