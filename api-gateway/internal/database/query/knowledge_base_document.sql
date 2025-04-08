-- name: CreateKnowledgeBaseDocuments :one
insert into knowledge_base_documents(
    ingestion_id,
    knowledge_base_id,
    document_id
) values (
    $1, $2, $3
) returning *;