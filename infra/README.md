# Infrastructure

The selected release path does not require Docker or n8n. The API and internal outbox worker run
as ordinary Python processes, the React client is built with Vite, and PostgreSQL/Pinecone/Google
are external services configured through environment variables. This directory is reserved for
future process-supervisor, Railway, or observability manifests; secrets never belong here.
