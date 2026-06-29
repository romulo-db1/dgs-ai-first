# 01 — Revisão Crítica do Claude (às cegas)

**Exercício:** 3.2 — Revisão Crítica de Código Gerado por IA
**Arquivo revisado:** `feedback-handler.ts` (gerado pelo Copilot)
**Destino correto no repositório:** `/src/functions/feedback/handler.ts` (conforme Anexo C)
**Revisor:** Claude
**Base normativa:** AGENTS.md do projeto — *"TypeScript strict mode. Zod para validação de input. pino para logging (nunca console.log). Nunca logar dados pessoais (e-mail, nome). Imports estáticos no topo (nunca require dinâmico)."*

---

## Resumo executivo

O módulo funciona no caminho feliz, mas viola **quatro regras explícitas do AGENTS.md** e contém **problemas de robustez e segurança** que o impedem de ir para produção. Foram identificados **3 achados P0** (bloqueiam o merge), **3 achados P1** (corrigir antes do go-live) e **2 achados P2** (melhoria). Cada achado abaixo traz classificação, evidência no código e correção concreta.

---

## Tabela-resumo dos achados

| # | Severidade | Categoria | Achado |
|---|------------|-----------|--------|
| A1 | **P0** | Segurança / LGPD | `attendantEmail` (dado pessoal) é logado |
| A2 | **P0** | Violação AGENTS.md | Uso de `console.log` em vez de `pino` |
| A3 | **P0** | Violação AGENTS.md + bug | Input parseado como `as any`, sem validação Zod |
| A4 | **P1** | Violação AGENTS.md | `require('@azure/cosmos')` dinâmico no meio da função |
| A5 | **P1** | Robustez | Nenhum tratamento de erro (`request.json()`, Cosmos `create`) |
| A6 | **P1** | Performance / recurso | `CosmosClient` instanciado a cada request |
| A7 | **P2** | Contrato HTTP | Resposta sem `Content-Type` e com corpo não estruturado |
| A8 | **P2** | Robustez | Sem validação de método/`Content-Type` da requisição |

---

## Achados detalhados

### A1 — `attendantEmail` é logado (P0 · Segurança / LGPD · Violação AGENTS.md)

**Evidência:**
```typescript
const feedback = {
  queryId: body.queryId,
  rating: body.rating,
  comment: body.comment,
  attendantEmail: body.attendantEmail,
  timestamp: new Date().toISOString()
};
console.log('Feedback recebido:', JSON.stringify(feedback));
```
O objeto `feedback` inclui `attendantEmail` e é serializado inteiro para o log. O AGENTS.md proíbe explicitamente logar dados pessoais (e-mail, nome). Trata-se também de exposição de dado pessoal sob a LGPD em logs potencialmente retidos/centralizados.

**Correção:** nunca incluir o e-mail no que vai ao log. Logar apenas identificadores não sensíveis e, se necessário rastrear o atendente, usar um identificador opaco (hash/ID) — nunca o e-mail em claro. O dado pode ser **persistido** no Cosmos (se o requisito de negócio exigir), mas **não logado**.
```typescript
logger.info({ queryId: feedback.queryId, rating: feedback.rating }, 'Feedback recebido');
```

---

### A2 — `console.log` em vez de `pino` (P0 · Violação AGENTS.md)

**Evidência:**
```typescript
console.log('Feedback recebido:', JSON.stringify(feedback));
```
O AGENTS.md determina `pino` como logger e proíbe `console.log`. Além da violação direta, `console.log` não produz logs estruturados, não respeita níveis de log e não passa por redatores de campo (que seriam a segunda linha de defesa contra o problema A1).

**Correção:** importar o logger compartilhado do projeto (Anexo C indica `src/shared/logger.ts`) e usar `logger.info(...)` com objeto estruturado. Idealmente configurar `redact` no pino para campos sensíveis como defesa em profundidade.

---

### A3 — Input como `as any`, sem validação Zod (P0 · Violação AGENTS.md + bug)

**Evidência:**
```typescript
const body = await request.json() as any;
const feedback = {
  queryId: body.queryId,
  rating: body.rating,
  // ...
};
```
O AGENTS.md exige Zod para validação de input. O `as any` desliga toda checagem de tipo: campos ausentes viram `undefined` e são persistidos silenciosamente; `rating` pode vir como string, fora de faixa ou ausente; payloads maliciosos passam direto. É simultaneamente violação de norma e fonte de bug real (dados malformados persistidos).

**Correção:** definir um schema Zod e fazer `safeParse`; em falha, retornar `400` com erro estruturado e **não** persistir.
```typescript
import { z } from 'zod';

const FeedbackSchema = z.object({
  queryId: z.string().min(1),
  rating: z.number().int().min(1).max(5),
  comment: z.string().max(2000).optional(),
  attendantEmail: z.string().email()
}).strict(); // .strict() rejeita campos extras

const parsed = FeedbackSchema.safeParse(await request.json());
if (!parsed.success) {
  logger.warn({ issues: parsed.error.issues }, 'Payload de feedback inválido');
  return { status: 400, jsonBody: { error: 'INVALID_PAYLOAD' } };
}
```

---

### A4 — `require` dinâmico no meio da função (P1 · Violação AGENTS.md)

**Evidência:**
```typescript
const { CosmosClient } = require('@azure/cosmos');
```
O AGENTS.md exige imports estáticos no topo e proíbe `require` dinâmico. Em TypeScript strict isso também perde a tipagem do SDK e impede tree-shaking/análise estática.

**Correção:** mover para import estático no topo do arquivo.
```typescript
import { CosmosClient } from '@azure/cosmos';
```

---

### A5 — Ausência total de tratamento de erro (P1 · Robustez)

**Evidência:** nem `await request.json()` nem `await container.items.create(feedback)` estão protegidos. Um corpo não-JSON derruba o handler com exceção não tratada; uma falha de conexão/escrita no Cosmos idem. O cliente recebe um 500 genérico do runtime sem log controlado do motivo.

**Correção:** envolver a persistência em `try/catch`, logar o erro (sem dado sensível) e retornar status apropriado. A validação Zod (A3) já cobre o corpo malformado.
```typescript
try {
  await container.items.create(feedback);
} catch (err) {
  logger.error({ err, queryId: feedback.queryId }, 'Falha ao persistir feedback');
  return { status: 503, jsonBody: { error: 'PERSISTENCE_FAILURE' } };
}
```

---

### A6 — `CosmosClient` instanciado a cada request (P1 · Performance / recurso)

**Evidência:**
```typescript
const client = new CosmosClient(process.env.COSMOS_CONNECTION_STRING);
```
Criar o client (e suas conexões) dentro do handler, a cada invocação, é anti-padrão em Azure Functions: aumenta latência, esgota conexões e ignora o reuso de cliente entre invocações no mesmo worker. Há também ausência de verificação de que a env var existe.

**Correção:** instanciar o client uma vez no escopo do módulo (singleton por worker) e validar a variável de ambiente na inicialização.
```typescript
const connectionString = process.env.COSMOS_CONNECTION_STRING;
if (!connectionString) throw new Error('COSMOS_CONNECTION_STRING não configurada');
const cosmosClient = new CosmosClient(connectionString);
const container = cosmosClient.database('novatech').container('feedbacks');
```

---

### A7 — Resposta HTTP não estruturada (P2 · Contrato HTTP)

**Evidência:**
```typescript
return { status: 200, body: 'OK' };
```
Retorna texto plano `'OK'` sem `Content-Type`. Um endpoint de API deve responder JSON consistente para que clientes (bot/painel) tratem sucesso e erro de forma uniforme.

**Correção:** usar `jsonBody` com um corpo previsível.
```typescript
return { status: 201, jsonBody: { status: 'created', id: result.resource?.id } };
```
(`201 Created` é mais adequado que `200` para criação de recurso.)

---

### A8 — Sem validação de método/Content-Type (P2 · Robustez)

**Observação:** o `app.http` registra apenas `methods: ['POST']`, o que é correto e suficiente para o roteamento — o Azure Functions v4 já responde 404 a métodos não declarados (não 405). O ponto P2 é a ausência de verificação do `Content-Type` antes de tentar `request.json()`; combinada com A5, fica coberta, mas vale registrar explicitamente uma resposta clara para `Content-Type` não-JSON.

---

## Conclusão

Os quatro achados que o exercício exige como mínimo estão cobertos: **A3** (`as any` sem Zod), **A2** (`console.log` em vez de pino), **A4** (`require` dinâmico) e **A1** (`attendantEmail` logado). Os demais (A5–A8) elevam o módulo ao padrão de produção esperado pelo AGENTS.md e pelas convenções do Anexo C. Recomenda-se **bloquear o merge** até que ao menos os três P0 e os três P1 sejam resolvidos.