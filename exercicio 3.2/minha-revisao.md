# Revisão de Código: Azure Function `feedbackHandler`

## Violações do AGENTS.md

* **Falta de validação com Zod:** Estamos pegando os dados crus do body sem nenhuma validação. A diretriz exige o uso de Zod para garantir que a estrutura do input está correta.
* **Quebra do TypeScript Strict Mode:** O cast `await request.json() as any` anula completamente a segurança de tipos do TypeScript.
* **Uso de `console.log`:** A regra é clara: devemos usar `pino` para logging e nunca `console.log`.
* **Log de dados pessoais (PII):** O log `JSON.stringify(feedback)` está printando o objeto inteiro, o que inclui a propriedade `attendantEmail`. A diretriz proíbe expressamente logar e-mails.
* **Import dinâmico (`require`):** O módulo `@azure/cosmos` está sendo carregado via `require` dentro do handler. Precisamos usar `import` estático no topo do arquivo.

## Problemas de Segurança

* **Vazamento de PII:** Relacionado à violação acima, expor o e-mail em logs de sistema aberto (como App Insights ou Datadog) é uma falha grave de segurança/conformidade (LGPD).
* **Falta de sanitização no Input:** Como não há validação, o objeto `body` pode conter payloads enormes ou propriedades maliciosas. Estamos confiando cegamente no usuário e jogando tudo direto no banco de dados.

## Bugs Potenciais

* **Esgotamento de conexões (Connection Pool):** Instanciar o `new CosmosClient` dentro do handler significa que criamos uma nova conexão de rede e client a cada request. Isso vai causar *SNAT port exhaustion* sob carga. O client deve ser inicializado fora do escopo do handler (escopo global do módulo).
* **Ausência de tratamento de exceções (try/catch):**
    * O método `request.json()` vai lançar uma exceção não tratada e crashar a execução se o cliente enviar um body vazio ou um JSON mal formatado.
    * A operação `container.items.create(feedback)` pode falhar (ex: erro de rede, timeout, Cosmos limitando as requests). Sem um `try/catch`, devolveremos um erro não tratado para o client ao invés de um fallback seguro ou um HTTP 500 descritivo.
* **Variável de ambiente insegura:** Passar `process.env.COSMOS_CONNECTION_STRING` direto para o client sem checar se a variável realmente existe pode resultar num erro obscuro em runtime se a configuração esquecer de ser definida no portal do Azure.