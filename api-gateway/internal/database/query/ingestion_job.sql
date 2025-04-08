-- name: CreateIngestionJob :one
insert into ingestion_jobs (
    resource_id,
    op_status
) values (
    $1, $2
) returning *;

-- name: UpdateIngestionJobStatus :exec
update ingestion_jobs
set
    op_status = sqlc.arg(op_status)
where id = any(@ids::int[]);